"""Bug Tracker v23 测试 — 覆盖 schema、评论 CRUD、活动日志、状态机、issue_links、迁移、aging。"""

from __future__ import annotations

import pytest
import apsw

from src.db.schema import init_schema, SCHEMA_VERSION
from src.db.repositories import IssueRepository
from src.services.issue_service import IssueService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def issue_svc(db_conn) -> IssueService:
    return IssueService(IssueRepository(db_conn), db_conn)


def _create_issue(svc: IssueService, title: str = "测试Bug", **kw) -> int:
    """创建一个 Issue，返回 ID。"""
    return svc.create(title=title, **kw)


def _make_service(db_conn) -> IssueService:
    repo = IssueRepository(db_conn)
    return IssueService(repo, db_conn)


# ═══════════════════════════════════════════════════════════════════
#  1. Schema v23
# ═══════════════════════════════════════════════════════════════════

class TestSchemaV23:
    """验证 schema 版本和 v23 新增表结构。"""

    def test_schema_version_is_23(self):
        assert SCHEMA_VERSION == 23

    def test_fresh_db_has_v23(self, db_conn):
        row = db_conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 23

    def test_new_tables_exist(self, db_conn):
        """v23 新增的三张表应全部存在。"""
        tables = {
            r[0] for r in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "issue_comments" in tables
        assert "issue_activity_log" in tables
        assert "issue_links" in tables

    def test_indexes_exist(self, db_conn):
        """v23 新增的索引应全部存在。"""
        indexes = {
            r[0] for r in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        for idx in (
            "idx_comments_issue", "idx_comments_created",
            "idx_activity_issue", "idx_activity_created",
            "idx_links_source", "idx_links_target",
        ):
            assert idx in indexes, f"索引 {idx} 缺失"


# ═══════════════════════════════════════════════════════════════════
#  2. 评论 CRUD
# ═══════════════════════════════════════════════════════════════════

class TestCommentsCRUD:
    """覆盖 add_comment / get_comments / delete_comment（软删除）。"""

    def test_add_and_get_comment(self, issue_svc):
        iid = _create_issue(issue_svc, "评论测试")
        cid = issue_svc.add_comment(iid, "这是一条评论", author_name="测试员")
        assert isinstance(cid, int) and cid > 0

        comments = issue_svc.get_comments(iid)
        assert len(comments) == 1
        assert comments[0].content == "这是一条评论"
        assert comments[0].author_name == "测试员"

    def test_delete_comment_soft(self, issue_svc):
        iid = _create_issue(issue_svc, "软删除测试")
        cid = issue_svc.add_comment(iid, "将被删除")
        assert len(issue_svc.get_comments(iid)) == 1

        issue_svc.delete_comment(cid)
        comments = issue_svc.get_comments(iid)
        assert len(comments) == 0

        # 验证 DB 中还保留（软删除标记）
        row = issue_svc._comment_repo._conn.execute(
            "SELECT is_deleted FROM issue_comments WHERE id = ?", (cid,)
        ).fetchone()
        assert row is not None
        assert row[0] == 1

    def test_comments_ordered_by_time(self, issue_svc):
        iid = _create_issue(issue_svc, "排序测试")
        # 插入两条评论，中间留一点时间差
        cid1 = issue_svc.add_comment(iid, "第一条")
        cid2 = issue_svc.add_comment(iid, "第二条")
        comments = issue_svc.get_comments(iid)
        assert len(comments) == 2
        assert comments[0].created_at <= comments[1].created_at
        # 验证 ID 顺序也一致
        assert comments[0].id <= comments[1].id


# ═══════════════════════════════════════════════════════════════════
#  3. 活动日志
# ═══════════════════════════════════════════════════════════════════

class TestActivityLog:
    """覆盖 transition_status / update 的活动日志记录。"""

    def test_status_change_logs_activity(self, issue_svc):
        iid = _create_issue(issue_svc, "状态日志测试")
        ok, reason = issue_svc.transition_status(iid, "analyzing", operator="张三")
        assert ok, reason

        logs = issue_svc.get_activity_log(iid)
        status_logs = [l for l in logs if l.field == "status"]
        assert len(status_logs) == 1
        assert status_logs[0].old_value == "open"
        assert status_logs[0].new_value == "analyzing"
        assert status_logs[0].operator == "张三"

    def test_update_logs_tracked_fields(self, issue_svc):
        """update 应记录 severity / priority 等追踪字段变更。"""
        iid = _create_issue(issue_svc, "更新日志测试", severity="major")
        issue_svc.update(iid, severity="critical", operator="李四")

        logs = issue_svc.get_activity_log(iid)
        sev_logs = [l for l in logs if l.field == "severity"]
        assert len(sev_logs) == 1
        assert sev_logs[0].old_value == "major"
        assert sev_logs[0].new_value == "critical"
        assert sev_logs[0].operator == "李四"

    def test_update_ignores_untracked_fields(self, issue_svc):
        """update title 不应产生活动日志。"""
        iid = _create_issue(issue_svc, "原始标题")
        issue_svc.update(iid, title="新标题")

        logs = issue_svc.get_activity_log(iid)
        assert len(logs) == 0

    def test_activity_with_duration(self, issue_svc):
        """get_activity_with_duration 返回包含停留时长的结果。"""
        iid = _create_issue(issue_svc, "停留时长测试")
        issue_svc.transition_status(iid, "analyzing")
        result = issue_svc.get_activity_with_duration(iid)
        assert len(result) >= 1
        for entry in result:
            assert "field" in entry
            assert "stay_duration" in entry
            # duration 应为非空字符串或至少是有效格式
            assert isinstance(entry["stay_duration"], str)


# ═══════════════════════════════════════════════════════════════════
#  4. 状态机
# ═══════════════════════════════════════════════════════════════════

class TestStateMachine:
    """覆盖状态转换规则（含 FA 前置 / resolution 前置 / reopen）。"""

    def test_legal_transition_open_to_analyzing(self, issue_svc):
        iid = _create_issue(issue_svc, "状态机-合法")
        ok, reason = issue_svc.transition_status(iid, "analyzing")
        assert ok, reason
        issue = issue_svc.get(iid)
        assert issue.status == "analyzing"

    def test_illegal_transition_open_to_verified_blocked(self, issue_svc):
        """open→verified 不在转换规则中，应被拒绝。"""
        iid = _create_issue(issue_svc, "状态机-非法")
        ok, reason = issue_svc.transition_status(iid, "verified")
        assert not ok
        assert "不允许" in reason
        assert "open" in reason and "verified" in reason
        issue = issue_svc.get(iid)
        assert issue.status == "open"

    def test_verified_requires_fa(self, issue_svc):
        """添加 FA 记录后 open→analyzing→verified 应成功。"""
        iid = _create_issue(issue_svc, "FA前置通过")
        # 先转为 analyzing
        ok, reason = issue_svc.transition_status(iid, "analyzing")
        assert ok, reason
        # 添加 FA 记录
        issue_svc.add_fa_record(iid, step_title="根因分析", description="分析...")
        # 再转 verified
        ok, reason = issue_svc.transition_status(iid, "verified")
        assert ok, reason
        issue = issue_svc.get(iid)
        assert issue.status == "verified"

    def test_closed_requires_resolution(self, issue_svc):
        """closed 无 resolution 应被拒绝。"""
        iid = _create_issue(issue_svc, "关闭需resolution", resolution="")
        ok, reason = issue_svc.transition_status(iid, "closed")
        assert not ok
        assert "resolution" in reason or "处理结果" in reason or "关闭" in reason

    def test_closed_with_resolution(self, issue_svc):
        """有 resolution 后 closed 应成功。"""
        iid = _create_issue(issue_svc, "带resolution关闭", resolution="fixed")
        ok, reason = issue_svc.transition_status(iid, "closed")
        assert ok, reason
        issue = issue_svc.get(iid)
        assert issue.status == "closed"

    def test_reopen_clears_resolution(self, issue_svc):
        """closed→open reopen 后 resolution 应被清空。"""
        iid = _create_issue(issue_svc, "Reopen清空resolution", resolution="fixed")
        issue_svc.transition_status(iid, "closed")
        # reopen
        ok, reason = issue_svc.transition_status(iid, "open")
        assert ok, reason
        issue = issue_svc.get(iid)
        assert issue.status == "open"
        assert issue.resolution == "", f"reopen 后 resolution 应为空，实际为 {issue.resolution!r}"

    def test_reopen_allowed(self, issue_svc):
        """closed→open 应被允许。"""
        iid = _create_issue(issue_svc, "Reopen测试", resolution="fixed")
        ok, reason = issue_svc.transition_status(iid, "closed")
        assert ok, reason
        ok, reason = issue_svc.transition_status(iid, "open")
        assert ok, reason
        assert issue_svc.get(iid).status == "open"


# ═══════════════════════════════════════════════════════════════════
#  5. Issue 关联
# ═══════════════════════════════════════════════════════════════════

class TestIssueLinks:
    """覆盖 add_link / get_links（双向）/ delete_link + 约束。"""

    def test_add_and_get_link(self, issue_svc):
        id_a = _create_issue(issue_svc, "Link A")
        id_b = _create_issue(issue_svc, "Link B")
        link_id = issue_svc.add_link(id_a, id_b, "blocks")
        assert isinstance(link_id, int) and link_id > 0

        links = issue_svc.get_links(id_a)
        assert len(links) == 1
        assert links[0].source_id == id_a
        assert links[0].target_id == id_b
        assert links[0].link_type == "blocks"

    def test_self_reference_blocked(self, issue_svc):
        """source=target 应抛 ConstraintError。"""
        iid = _create_issue(issue_svc, "自引用")
        with pytest.raises(apsw.ConstraintError):
            issue_svc.add_link(iid, iid, "relates_to")

    def test_duplicate_link_blocked(self, issue_svc):
        """重复的 source+target+type 应抛 ConstraintError。"""
        id_a = _create_issue(issue_svc, "重复 A")
        id_b = _create_issue(issue_svc, "重复 B")
        issue_svc.add_link(id_a, id_b, "relates_to")
        with pytest.raises(apsw.ConstraintError):
            issue_svc.add_link(id_a, id_b, "relates_to")

    def test_cascade_delete(self, issue_svc, db_conn):
        """删除 issue 后关联应通过 CASCADE 自动删除。"""
        id_a = _create_issue(issue_svc, "Cascade A")
        id_b = _create_issue(issue_svc, "Cascade B")
        link_id = issue_svc.add_link(id_a, id_b, "relates_to")
        # 删除 issue A
        db_conn.execute("DELETE FROM issues WHERE id = ?", (id_a,))
        # link 应被级联删除
        remaining = db_conn.execute(
            "SELECT COUNT(*) FROM issue_links WHERE id = ?", (link_id,)
        ).fetchone()[0]
        assert remaining == 0

    def test_bidirectional_query(self, issue_svc):
        """A→B link，查询 B 也应返回该 link。"""
        id_a = _create_issue(issue_svc, "双向 A")
        id_b = _create_issue(issue_svc, "双向 B")
        issue_svc.add_link(id_a, id_b, "relates_to")

        links_from_b = issue_svc.get_links(id_b)
        assert len(links_from_b) == 1
        link = links_from_b[0]
        assert link.source_id == id_a
        assert link.target_id == id_b


# ═══════════════════════════════════════════════════════════════════
#  6. v22 → v23 迁移
# ═══════════════════════════════════════════════════════════════════

class TestMigrationFromV22:
    """手动构建 v22 DB → 跑迁移 → 验证 v23 新表存在 + 旧数据完整。"""

    def _build_v22_db(self) -> apsw.Connection:
        """构建一个 schema version 22 的内存数据库。"""
        conn = apsw.Connection(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        # 用 init_schema 创建完整 schema，然后回退版本号到 22
        init_schema(conn)
        # 删除 v23 及以上的版本记录
        conn.execute("DELETE FROM schema_version WHERE version >= 23")
        # 删除 v23 新增的表（以模拟 v22 状态）
        conn.execute("DROP TABLE IF EXISTS issue_comments")
        conn.execute("DROP TABLE IF EXISTS issue_activity_log")
        conn.execute("DROP TABLE IF EXISTS issue_links")
        # 现在数据库在 v22
        return conn

    def test_migrate_v22_to_v23(self):
        """从 v22 迁移到 v23，新表存在且旧数据完整。"""
        conn = self._build_v22_db()

        # 验证当前在 v22
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 22, f"预期 v22，实际 v{row[0]}"

        # 插入一些旧数据验证迁移后数据完整性
        conn.execute(
            "INSERT INTO projects (name) VALUES ('迁移测试项目')"
        )
        conn.execute(
            "INSERT INTO issues (title, status) VALUES ('迁移前 Issue', 'open')"
        )
        issue_id = conn.execute(
            "SELECT id FROM issues WHERE title = '迁移前 Issue'"
        ).fetchone()[0]

        # 执行 v23 迁移
        from src.db.schema import _migrate_v23
        conn.execute("BEGIN")
        _migrate_v23(conn)
        conn.execute("COMMIT")

        # 验证版本更新
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 23

        # 验证新表存在
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "issue_comments" in tables
        assert "issue_activity_log" in tables
        assert "issue_links" in tables

        # 验证旧数据完整
        issue = conn.execute(
            "SELECT title, status FROM issues WHERE id = ?", (issue_id,)
        ).fetchone()
        assert issue is not None
        assert issue[0] == "迁移前 Issue"
        assert issue[1] == "open"

        # 验证新表结构正确
        for tbl, expected_cols in [
            ("issue_comments", {"id", "issue_id", "author_name", "content", "is_deleted", "created_at"}),
            ("issue_activity_log", {"id", "issue_id", "field", "old_value", "new_value", "operator", "created_at"}),
            ("issue_links", {"id", "source_id", "target_id", "link_type", "created_at"}),
        ]:
            cols = {
                r[1] for r in conn.execute(f"PRAGMA table_info([{tbl}])").fetchall()
            }
            assert cols == expected_cols, f"表 {tbl} 列不匹配: {cols} vs {expected_cols}"

        # 验证新表可以正常写入
        conn.execute(
            "INSERT INTO issue_comments (issue_id, content) VALUES (?, ?)",
            (issue_id, "迁移后评论"),
        )
        row = conn.execute(
            "SELECT COUNT(*) FROM issue_comments WHERE issue_id = ?", (issue_id,)
        ).fetchone()
        assert row[0] == 1  # 插入成功

        conn.close()


# ═══════════════════════════════════════════════════════════════════
#  7. Aging 计算
# ═══════════════════════════════════════════════════════════════════

class TestAgingCalculation:
    """覆盖 get_aging_days 的基本行为。"""

    def test_aging_days_returns_int(self, issue_svc):
        iid = _create_issue(issue_svc, "Aging测试")
        days = issue_svc.get_aging_days(iid)
        assert isinstance(days, int)
        assert days >= 0

    def test_aging_fallback_no_activity(self, issue_svc):
        """无活动日志时 aging 应来自 created_at，不报错。"""
        iid = _create_issue(issue_svc, "无活动日志Aging")
        days = issue_svc.get_aging_days(iid)
        # 刚创建的 issue，aging 应为 0
        assert isinstance(days, int)
        assert days == 0, f"刚创建的 issue aging 应为 0，实际为 {days}"
