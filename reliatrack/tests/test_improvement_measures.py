"""improvement_measures 字段测试 — CRUD、CAPA 联动、旧数据迁移。"""

from __future__ import annotations

import apsw
import pytest

from src.models.issue import Issue
from src.db.schema import init_schema, _migrate_v19
from src.db.repositories.issue_repo import IssueRepository
from src.services.issue_service import IssueService


# ── helper ──────────────────────────────────────────────────────────

def _make_service(db_conn):
    """构造 IssueService(IssueRepository(db_conn))。"""
    return IssueService(IssueRepository(db_conn))


def _create_issue(service: IssueService, **overrides) -> int:
    """创建一条 Issue 并返回 id。"""
    defaults = dict(title="测试问题")
    defaults.update(overrides)
    return service.create(**defaults)


# ═══════════════════════════════════════════════════════════════════
#  1. improvement_measures CRUD
# ═══════════════════════════════════════════════════════════════════

class TestImprovementMeasuresCRUD:
    """improvement_measures 字段的创建、更新、读取。"""

    def test_create_with_improvement_measures(self, db_conn):
        """创建 Issue 时可以指定 improvement_measures。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, improvement_measures="更换供应商; 加强来料检验")
        assert svc.get(iid).improvement_measures == "更换供应商; 加强来料检验"

    def test_update_improvement_measures(self, db_conn):
        """更新 Issue 的 improvement_measures。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc)
        assert svc.get(iid).improvement_measures == ""

        svc.update(iid, improvement_measures="修订 PCB 焊盘设计规范")
        assert svc.get(iid).improvement_measures == "修订 PCB 焊盘设计规范"

    def test_improvement_measures_independent_of_resolution(self, db_conn):
        """improvement_measures 和 resolution 互不影响。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, resolution="fixed", improvement_measures="更换电容供应商")

        issue = svc.get(iid)
        assert issue.resolution == "fixed"
        assert issue.improvement_measures == "更换电容供应商"

        # 更新 resolution 不影响 improvement_measures
        svc.update(iid, resolution="wont_fix")
        issue = svc.get(iid)
        assert issue.resolution == "wont_fix"
        assert issue.improvement_measures == "更换电容供应商"


# ═══════════════════════════════════════════════════════════════════
#  2. CAPA 联动 → improvement_measures（而非 resolution）
# ═══════════════════════════════════════════════════════════════════

class TestCAPASyncToImprovementMeasures:
    """CAPA action 汇总写入 improvement_measures 而非 resolution。"""

    def test_capa_action_not_overwrite_resolution(self, db_conn):
        """添加 CAPA 后 resolution（枚举值）不被覆盖。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, resolution="fixed")

        # 模拟 handler 行为：直接通过 service 更新
        svc.add_capa_record(iid, action="更换供应商", status="pending")

        # resolution 仍然是枚举值（handler 会通过 _sync 写 improvement_measures）
        assert svc.get(iid).resolution == "fixed"

    def test_model_has_improvement_measures_field(self):
        """Issue model 有 improvement_measures 字段。"""
        fields = {f.name for f in Issue.__dataclass_fields__.values()}
        assert "improvement_measures" in fields


# ═══════════════════════════════════════════════════════════════════
#  3. Schema v19 迁移
# ═══════════════════════════════════════════════════════════════════

class TestSchemaV19Migration:
    """v19 迁移：improvement_measures 列 + 旧 resolution 文本迁移。"""

    def test_issues_table_has_improvement_measures(self, db_conn):
        """issues 表有 improvement_measures 列。"""
        rows = db_conn.execute("PRAGMA table_info(issues)").fetchall()
        col_names = {row[1] for row in rows}
        assert "improvement_measures" in col_names

    def test_v19_migrates_non_enum_resolution_to_improvement(self):
        """v19 迁移把 resolution 中的非枚举文本搬到 improvement_measures。"""
        conn = apsw.Connection(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        init_schema(conn)

        # 插入一条 resolution 为自由文本的 Issue（模拟旧数据）
        conn.execute(
            "INSERT INTO issues (title, resolution) VALUES (?, ?)",
            ("旧Issue", "这是旧的改善对策文本"),
        )
        # 插入一条 resolution 为枚举值的 Issue
        conn.execute(
            "INSERT INTO issues (title, resolution) VALUES (?, ?)",
            ("新Issue", "fixed"),
        )

        # 模拟从 v18 → v19 迁移
        conn.execute("DELETE FROM schema_version WHERE version >= 19")
        conn.execute("BEGIN")
        _migrate_v19(conn)
        conn.execute("COMMIT")

        # 旧文本已迁移到 improvement_measures
        old_issue = conn.execute(
            "SELECT resolution, improvement_measures FROM issues WHERE title='旧Issue'"
        ).fetchone()
        assert old_issue[0] == ""  # resolution 已清空
        assert old_issue[1] == "这是旧的改善对策文本"  # 搬到 improvement_measures

        # 枚举值不受影响
        new_issue = conn.execute(
            "SELECT resolution, improvement_measures FROM issues WHERE title='新Issue'"
        ).fetchone()
        assert new_issue[0] == "fixed"  # resolution 保持不变
        assert new_issue[1] == ""  # improvement_measures 为空

        conn.close()

    def test_v19_idempotent(self):
        """v19 迁移幂等：重复执行不出错。"""
        conn = apsw.Connection(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        init_schema(conn)

        conn.execute("DELETE FROM schema_version WHERE version >= 19")
        conn.execute("BEGIN")
        _migrate_v19(conn)
        conn.execute("COMMIT")

        # 再次执行不应报错
        conn.execute("DELETE FROM schema_version WHERE version >= 19")
        conn.execute("BEGIN")
        _migrate_v19(conn)
        conn.execute("COMMIT")

        conn.close()
