"""CAPA PDCA 扩展 + Schema v15 迁移 + count bug 修复测试。

覆盖项：
- Schema v15 迁移：capa_records 新增 root_cause/effectiveness/follow_up 列
- CAPA PDCA 字段 CRUD（增/查/改/删）
- count_capa_done SQL 修复（'done'→'completed'）
"""

from __future__ import annotations

import apsw
import pytest

from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def db_conn() -> apsw.Connection:
    """内存数据库，走完整 init_schema 迁移链。"""
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def issue_repo(db_conn: apsw.Connection) -> IssueRepository:
    return IssueRepository(db_conn)


def _insert_project(db_conn: apsw.Connection) -> int:
    db_conn.execute(
        "INSERT INTO projects (name, product, customer, description, status) "
        "VALUES (?, ?, ?, ?, ?)",
        ("测试项目", "产品A", "客户X", "描述", "active"),
    )
    return db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_issue(db_conn: apsw.Connection, project_id: int) -> int:
    db_conn.execute(
        "INSERT INTO issues (project_id, title, severity, status) VALUES (?, ?, ?, ?)",
        (project_id, "测试Issue", "major", "open"),
    )
    return db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_technician(db_conn: apsw.Connection) -> int:
    db_conn.execute(
        "INSERT INTO technicians (name, role, department) VALUES (?, ?, ?)",
        ("张工", "DQE", "质量部"),
    )
    return db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ═══════════════════════════════════════════════════════════════════
#  Schema v15 迁移测试
# ═══════════════════════════════════════════════════════════════════

class TestSchemaV15Migration:
    """验证 v15 迁移正确添加 PDCA 字段且旧数据不受影响。"""

    def test_schema_v15_migration(self, db_conn: apsw.Connection) -> None:
        """v15 迁移后 capa_records 有 root_cause/effectiveness/follow_up 列。"""
        cols = {r[1] for r in db_conn.execute("PRAGMA table_info(capa_records)").fetchall()}
        assert "root_cause" in cols, "capa_records 缺少 root_cause 列"
        assert "effectiveness" in cols, "capa_records 缺少 effectiveness 列"
        assert "follow_up" in cols, "capa_records 缺少 follow_up 列"

    def test_v14_data_survives_migration(self, db_conn: apsw.Connection) -> None:
        """插入一条 v14 格式的 CAPA（不含 PDCA 字段），检查新列默认值为空。"""
        pid = _insert_project(db_conn)
        iid = _insert_issue(db_conn, pid)
        tid = _insert_technician(db_conn)

        # 模拟 v14 格式：不传 PDCA 字段
        repo = IssueRepository(db_conn)
        capa_id = repo.add_capa_record(
            issue_id=iid,
            action="纠正措施",
            assignee_id=tid,
            assignee_name="张工",
            due_date="2026-06-01",
        )
        assert capa_id > 0

        records = repo.get_capa_records(iid)
        assert len(records) == 1
        # PDCA 字段应为空字符串默认值
        assert records[0].root_cause == ""
        assert records[0].effectiveness == ""
        assert records[0].follow_up == ""

    def test_schema_version_is_latest(self, db_conn: apsw.Connection) -> None:
        """init_schema 后版本应为最新。"""
        from src.db.schema import SCHEMA_VERSION
        row = db_conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row[0] == SCHEMA_VERSION


# ═══════════════════════════════════════════════════════════════════
#  CAPA PDCA 字段 CRUD
# ═══════════════════════════════════════════════════════════════════

class TestCapaPDCAFields:
    """验证 CAPA 记录的 PDCA 字段增/查/改/删。"""

    def test_capa_add_with_pdca_fields(self, issue_repo: IssueRepository, db_conn: apsw.Connection) -> None:
        """新增 CAPA 时可以填写 PDCA 字段。"""
        pid = _insert_project(db_conn)
        iid = _insert_issue(db_conn, pid)
        tid = _insert_technician(db_conn)

        capa_id = issue_repo.add_capa_record(
            issue_id=iid,
            action="更换材料供应商",
            assignee_id=tid,
            assignee_name="张工",
            due_date="2026-07-01",
            root_cause="焊锡材料纯度不足",
            effectiveness="良率从 92% 提升至 98%",
            follow_up="建立来料检验 SOP",
        )
        assert capa_id > 0

        records = issue_repo.get_capa_records(iid)
        assert len(records) == 1
        r = records[0]
        assert r.action == "更换材料供应商"
        assert r.root_cause == "焊锡材料纯度不足"
        assert r.effectiveness == "良率从 92% 提升至 98%"
        assert r.follow_up == "建立来料检验 SOP"
        assert r.assignee_name == "张工"

    def test_capa_update_pdca_fields(self, issue_repo: IssueRepository, db_conn: apsw.Connection) -> None:
        """更新 CAPA 的 PDCA 字段。"""
        pid = _insert_project(db_conn)
        iid = _insert_issue(db_conn, pid)
        tid = _insert_technician(db_conn)

        capa_id = issue_repo.add_capa_record(
            issue_id=iid,
            action="改进工艺参数",
            assignee_id=tid,
            assignee_name="张工",
        )

        # 更新 PDCA 字段
        issue_repo.update_capa_record(
            capa_id,
            root_cause="温度曲线偏移",
            effectiveness="CPK 达标",
            follow_up="每月审核温控记录",
            status="completed",
        )

        records = issue_repo.get_capa_records(iid)
        assert len(records) == 1
        r = records[0]
        assert r.root_cause == "温度曲线偏移"
        assert r.effectiveness == "CPK 达标"
        assert r.follow_up == "每月审核温控记录"
        assert r.status == "completed"

    def test_capa_delete(self, issue_repo: IssueRepository, db_conn: apsw.Connection) -> None:
        """删除单条 CAPA。"""
        pid = _insert_project(db_conn)
        iid = _insert_issue(db_conn, pid)

        capa_id1 = issue_repo.add_capa_record(
            issue_id=iid, action="纠正措施A",
        )
        capa_id2 = issue_repo.add_capa_record(
            issue_id=iid, action="纠正措施B",
        )
        assert capa_id1 > 0
        assert capa_id2 > 0

        records = issue_repo.get_capa_records(iid)
        assert len(records) == 2

        # 删除第一条
        issue_repo.delete_capa_record(capa_id1)

        records = issue_repo.get_capa_records(iid)
        assert len(records) == 1
        assert records[0].action == "纠正措施B"


# ═══════════════════════════════════════════════════════════════════
#  count_capa_done SQL 修复验证
# ═══════════════════════════════════════════════════════════════════

class TestCountCapaDoneFix:
    """验证 count_capa_done 修复：status='completed' 被正确计数。"""

    def test_count_capa_done_fixed(self, issue_repo: IssueRepository, db_conn: apsw.Connection) -> None:
        """count_capa_done 应返回 completed + verified 的数量。"""
        pid = _insert_project(db_conn)
        iid = _insert_issue(db_conn, pid)

        # 3 条 CAPA：pending / completed / verified
        issue_repo.add_capa_record(issue_id=iid, action="CAPA-待处理", status="pending")
        issue_repo.add_capa_record(issue_id=iid, action="CAPA-已完成", status="completed")
        issue_repo.add_capa_record(issue_id=iid, action="CAPA-已验证", status="verified")

        # count_capa_done 应返回 2（completed + verified）
        count = issue_repo.count_capa_done()
        assert count == 2, f"期望 count_capa_done() == 2（completed + verified），实际 {count}"

    def test_count_capa_done_by_project(self, issue_repo: IssueRepository, db_conn: apsw.Connection) -> None:
        """count_capa_done 按 project_id 筛选也应正确计数。"""
        pid1 = _insert_project(db_conn)
        pid2 = _insert_project(db_conn)
        iid1 = _insert_issue(db_conn, pid1)
        iid2 = _insert_issue(db_conn, pid2)

        # 项目1：1 completed + 1 pending
        issue_repo.add_capa_record(issue_id=iid1, action="P1-完成", status="completed")
        issue_repo.add_capa_record(issue_id=iid1, action="P1-待处理", status="pending")

        # 项目2：1 verified
        issue_repo.add_capa_record(issue_id=iid2, action="P2-验证", status="verified")

        assert issue_repo.count_capa_done(project_id=pid1) == 1
        assert issue_repo.count_capa_done(project_id=pid2) == 1
        assert issue_repo.count_capa_done() == 2  # 全局

    def test_count_capa_all_vs_done(self, issue_repo: IssueRepository, db_conn: apsw.Connection) -> None:
        """count_capa_all 和 count_capa_done 的区分。"""
        pid = _insert_project(db_conn)
        iid = _insert_issue(db_conn, pid)

        issue_repo.add_capa_record(issue_id=iid, action="待处理", status="pending")
        issue_repo.add_capa_record(issue_id=iid, action="已完成", status="completed")
        issue_repo.add_capa_record(issue_id=iid, action="已验证", status="verified")
        issue_repo.add_capa_record(issue_id=iid, action="进行中", status="in_progress")

        assert issue_repo.count_capa_all() == 4
        assert issue_repo.count_capa_done() == 2  # only completed + verified
