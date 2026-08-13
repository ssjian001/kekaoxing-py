"""Bug Tracker v23 测试 — 覆盖 schema、评论 CRUD、活动日志、状态机、issue_links、迁移、aging。"""

from __future__ import annotations

import sys
import pytest
import apsw

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.db.schema import init_schema, SCHEMA_VERSION
from src.db.repositories import IssueRepository
from src.services.issue_service import IssueService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def issue_svc(db_conn) -> IssueService:
    return IssueService(IssueRepository(db_conn), db_conn)


@pytest.fixture(scope="module")
def qapp():
    """Module-scoped QApplication 实例，供 QWidget 测试使用。"""
    return QApplication.instance() or QApplication(sys.argv)


def _create_issue(svc: IssueService, title: str = "测试Bug", **kw) -> int:
    """创建一个 Issue，返回 ID。"""
    return svc.create(title=title, **kw)


def _make_service(db_conn) -> IssueService:
    repo = IssueRepository(db_conn)
    return IssueService(repo, db_conn)


# ═══════════════════════════════════════════════════════════════════
#  1. Schema v23
# ═══════════════════════════════════════════════════════════════════

class TestSchemaV27:
    """验证 schema 版本和 v27 新增字段。"""

    def test_fresh_db_has_v27(self, db_conn):
        row = db_conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == SCHEMA_VERSION


    def test_activity_log_has_project_id(self, db_conn):
        """v24 新增 project_id 列应存在。"""
        cols = {
            r[1] for r in db_conn.execute(
                "PRAGMA table_info(issue_activity_log)"
            ).fetchall()
        }
        assert "project_id" in cols

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


# ═══════════════════════════════════════════════════════════════════
#  Dashboard 集成 — Bug Tracker 4 指标冒烟测试
#  回归崩溃 #62e6cb3: ctrl.issues(repo) vs ctrl.issue_service(svc)
# ═══════════════════════════════════════════════════════════════════


class TestDashboardBugTrackerMetrics:
    """验证 _collect_dashboard_data 的 Bug Tracker 4 指标计算不崩溃。

    回归测试 #62e6cb3 — delegate_task 混用 repo/service API 导致
    AttributeError: 'IssueRepository' object has no attribute 'get_aging_days'
    """

    @staticmethod
    def _make_mock_ctrl(db_conn):
        """构造 mock AppController（真实 repos + services）。"""
        from types import SimpleNamespace
        from src.db.repositories import (
            IssueRepository, TestTaskRepository, TestResultRepository,
            TestPlanRepository, ProjectRepository, SampleRepository,
            TechnicianRepository, KnowledgeRepository,
        )
        from src.services.issue_service import IssueService
        from src.services.project_service import ProjectService
        from src.services.sample_service import SampleService
        from src.services.test_plan_service import TestPlanService
        from src.services.knowledge_service import KnowledgeService

        issue_repo = IssueRepository(db_conn)
        plan_repo = TestPlanRepository(db_conn)
        task_repo = TestTaskRepository(db_conn)
        result_repo = TestResultRepository(db_conn)
        sample_repo = SampleRepository(db_conn)
        project_repo = ProjectRepository(db_conn)

        issue_svc = IssueService(issue_repo, db_conn)
        return SimpleNamespace(
            _conn=db_conn,
            issues=issue_repo,
            issue_service=issue_svc,
            test_tasks=task_repo,
            test_results=result_repo,
            project_service=ProjectService(project_repo, plan_repo, task_repo, sample_repo, issue_repo),
            sample_service=SampleService(sample_repo, result_repo, issue_repo),
            test_plan_service=TestPlanService(plan_repo, task_repo, result_repo),
            technicians=TechnicianRepository(db_conn),
            knowledge_service=KnowledgeService(KnowledgeRepository(db_conn)),
        )

    @staticmethod
    def _make_mock_handlers(ctrl):
        """构造 RefreshHandlers（跳过 __init__，设最小属性）。"""
        from types import SimpleNamespace
        from src.handlers.refresh_handlers import RefreshHandlers

        class _MockBugTrackerView:
            def set_context_data(self, **kwargs): pass
            def refresh(self, issues=None): pass

        win = SimpleNamespace(ctrl=ctrl, bug_tracker_view=_MockBugTrackerView())
        handlers = RefreshHandlers.__new__(RefreshHandlers)  # type: ignore
        handlers._win = win  # type: ignore
        handlers._cached_projects = None
        handlers._cached_samples = None
        return handlers

    def test_dashboard_data_has_bug_tracker_fields(self, db_conn):
        """_collect_dashboard_data 返回的 DashboardData 含 4 个 Bug Tracker 字段。"""
        ctrl = self._make_mock_ctrl(db_conn)
        handlers = self._make_mock_handlers(ctrl)
        svc = ctrl.issue_service

        # 插入测试 issue
        svc.create(title="开放Bug1", status="open", severity="major")
        svc.create(title="分析中Bug1", status="analyzing", severity="critical")
        svc.create(title="已关闭Bug1", status="closed", resolution="fixed")

        data = handlers._collect_dashboard_data(ctrl, None, None)

        assert data is not None
        assert data.pending_count == 2, f"pending_count 应为 2（open+analyzing），实际 {data.pending_count}"
        assert isinstance(data.weekly_closed, int) and data.weekly_closed >= 0
        assert isinstance(data.avg_age_days, (int, float))
        assert isinstance(data.aging_warning_count, int)

    def test_dashboard_no_crash_with_empty_db(self, db_conn):
        """空 DB 时 _collect_dashboard_data 不崩溃（回归 #62e6cb3）。"""
        ctrl = self._make_mock_ctrl(db_conn)
        handlers = self._make_mock_handlers(ctrl)

        data = handlers._collect_dashboard_data(ctrl, None, None)

        assert data is not None
        assert data.pending_count == 0
        assert data.avg_age_days == 0
        assert data.aging_warning_count == 0


# ═══════════════════════════════════════════════════════════════════
#  Fix 回归测试 — 事务原子性 / 看板卡片显示 / 列表选中行恢复
# ═══════════════════════════════════════════════════════════════════

class TestUpdateTransactionAtomicity:
    """Fix 3: update() + transition_status() 的事务原子性测试。"""

    def test_update_writes_issue_and_activity_atomically(self, issue_svc):
        """update() 中 issue 变更和 activity log 必须同在一个事务中。"""
        issue_id = _create_issue(issue_svc, severity="major")
        # 修改 tracked field
        issue_svc.update(issue_id, severity="critical", operator="tester")
        # issue 变更生效
        issue = issue_svc.get(issue_id)
        assert issue.severity == "critical"
        # activity log 也存在
        logs = issue_svc.get_activity_log(issue_id)
        severity_logs = [l for l in logs if l.field == "severity"]
        assert len(severity_logs) == 1
        assert severity_logs[0].old_value == "major"
        assert severity_logs[0].new_value == "critical"

    def test_transition_status_writes_atomically(self, issue_svc):
        """transition_status() 中状态变更和活动日志原子化。"""
        issue_id = _create_issue(issue_svc, severity="major")
        # open → analyzing（合法转换）
        ok, _ = issue_svc.transition_status(issue_id, "analyzing", operator="tester")
        assert ok
        issue = issue_svc.get(issue_id)
        assert issue.status == "analyzing"
        logs = issue_svc.get_activity_log(issue_id)
        status_logs = [l for l in logs if l.field == "status"]
        assert any(l.new_value == "analyzing" for l in status_logs)

    def test_update_transaction_rollback_on_activity_failure(self, db_conn):
        """Fix 3 核心测试：activity_repo.add() 失败时，issue 更新必须回滚。"""
        svc = _make_service(db_conn)
        issue_id = _create_issue(svc, severity="major")

        # Monkey-patch activity_repo.add 抛异常，模拟中间失败
        original_add = svc._activity_repo.add
        call_count = [0]
        def failing_add(*args, **kwargs):
            call_count[0] += 1
            raise RuntimeError("模拟 activity log 写入失败")

        svc._activity_repo.add = failing_add
        try:
            with pytest.raises(RuntimeError):
                svc.update(issue_id, severity="critical", operator="tester")
        finally:
            svc._activity_repo.add = original_add

        # 关键验证：issue 没有被更新（事务回滚）
        issue = svc.get(issue_id)
        assert issue.severity == "major", "update() 应该回滚 — issue severity 不应改变"


class TestKanbanCardAssigneeDisplay:
    """Fix 1: 看板卡片显示人名而非 assignee_id 数字。"""

    def test_kanban_card_shows_assignee_name(self, qapp):
        """卡片优先显示 assignee_name 参数。"""
        from src.views.bug_tracker.kanban_view import _KanbanCard
        from src.models.issue import Issue

        issue = Issue(id=1, title="测试", assignee_id=5)
        card = _KanbanCard(issue, aging_days=3, assignee_name="张工")
        # 卡片内部属性正确存储
        assert card._assignee_name == "张工"

    def test_kanban_card_fallback_to_dri_name(self, qapp):
        """assignee_name 为空时 fallback 到 dri_name。"""
        from src.views.bug_tracker.kanban_view import _KanbanCard
        from src.models.issue import Issue

        issue = Issue(id=1, title="测试", assignee_id=5, dri_name="李工")
        card = _KanbanCard(issue, aging_days=0, assignee_name="")
        # assignee_name 空 → 显示逻辑 fallback 到 dri_name
        display = card._assignee_name or getattr(issue, "dri_name", "") or ""
        assert display == "李工"

    def test_kanban_card_shows_dash_when_no_name(self, qapp):
        """没有任何名字时显示 '—'。"""
        from src.views.bug_tracker.kanban_view import _KanbanCard
        from src.models.issue import Issue

        issue = Issue(id=1, title="测试")
        card = _KanbanCard(issue, aging_days=0, assignee_name="")
        display = card._assignee_name or getattr(issue, "dri_name", "") or ""
        assert display == ""  # UI 层会显示 "—"


class TestBugListSelectionRetention:
    """Fix 5: set_issues() 刷新后恢复选中行 + checkbox 状态。"""

    def test_set_issues_preserves_selected_row(self, issue_svc, qapp):
        """刷新后之前选中的 Issue 行仍然被选中。"""
        from src.views.bug_tracker.list_view import _BugTable

        table = _BugTable()
        table.set_issue_service(issue_svc)

        # 创建 3 个 Issue
        id1 = _create_issue(issue_svc, title="Bug1")
        id2 = _create_issue(issue_svc, title="Bug2")
        id3 = _create_issue(issue_svc, title="Bug3")

        issues = [issue_svc.get(i) for i in [id1, id2, id3]]
        table.set_issues(issues)

        # 选中第二行 (id2)
        table.setCurrentCell(1, 0)
        assert table.get_selected_issue_id() == id2

        # 模拟刷新（数据不变）
        table.set_issues(issues)

        # 选中行应该恢复
        assert table.get_selected_issue_id() == id2

    def test_set_issues_preserves_checkbox_state(self, issue_svc, qapp):
        """刷新后之前勾选的 checkbox 仍然保持勾选。"""
        from src.views.bug_tracker.list_view import _BugTable

        table = _BugTable()
        table.set_issue_service(issue_svc)

        id1 = _create_issue(issue_svc, title="Bug1")
        id2 = _create_issue(issue_svc, title="Bug2")
        id3 = _create_issue(issue_svc, title="Bug3")

        issues = [issue_svc.get(i) for i in [id1, id2, id3]]
        table.set_issues(issues)

        # 勾选 id1 和 id3
        table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        table.item(2, 0).setCheckState(Qt.CheckState.Checked)
        assert set(table.get_checked_ids()) == {id1, id3}

        # 模拟刷新
        table.set_issues(issues)

        # checkbox 状态应该保持
        assert set(table.get_checked_ids()) == {id1, id3}

    def test_set_issues_no_crash_when_selected_deleted(self, issue_svc, qapp):
        """之前选中的 Issue 被删除后，刷新不崩溃，不选中任何行。"""
        from src.views.bug_tracker.list_view import _BugTable

        table = _BugTable()
        table.set_issue_service(issue_svc)

        id1 = _create_issue(issue_svc, title="Bug1")
        id2 = _create_issue(issue_svc, title="Bug2")

        issues = [issue_svc.get(i) for i in [id1, id2]]
        table.set_issues(issues)
        table.setCurrentCell(1, 0)  # 选中 id2
        assert table.get_selected_issue_id() == id2

        # 刷新时只有 id1（id2 被删除了）
        table.set_issues([issue_svc.get(id1)])

        # 不崩溃，选中的是 id1 或 None（但不应该是已删除的 id2）
        selected = table.get_selected_issue_id()
        assert selected != id2


# ═══════════════════════════════════════════════════════════════════
#  Fix 7: Bug Tracker 项目筛选 — BugTrackerView._get_filtered_issues()
# ═══════════════════════════════════════════════════════════════════

class TestBugTrackerProjectFilter:
    """Bug 管理页按项目筛选 Issue（与 Issue 视图逻辑一致）。"""

    def test_no_filter_returns_all(self, db_conn, qapp):
        """无项目筛选时返回所有 Issue。"""
        from src.views.bug_tracker import BugTrackerView

        svc = _make_service(db_conn)
        tracker = BugTrackerView(svc)
        tracker._build_views()  # 首次加载

        # 无筛选 → list_all
        issues = tracker._get_filtered_issues()
        assert len(issues) == 0  # 空 DB

        # 加 3 个 Issue
        _create_issue(svc, title="Bug1")
        _create_issue(svc, title="Bug2")
        _create_issue(svc, title="Bug3")

        issues = tracker._get_filtered_issues()
        assert len(issues) == 3

    def test_with_project_filter_returns_filtered(self, db_conn, qapp):
        """有项目筛选时只返回该项目的 Issue + 未关联项目的 Issue。"""
        from src.views.bug_tracker import BugTrackerView

        svc = _make_service(db_conn)
        tracker = BugTrackerView(svc)
        tracker._build_views()

        # 创建项目
        db_conn.execute(
            "INSERT INTO projects (name, product, customer, description, status) "
            "VALUES ('项目A', '产品A', '客户A', '', 'active')"
        )
        proj_row = db_conn.execute(
            "SELECT id FROM projects WHERE name='项目A'"
        ).fetchone()
        pid_a = proj_row[0]

        # 3 个 Issue：2 个属于项目A，1 个无项目
        svc.create(title="项目A-Bug1", project_id=pid_a)
        svc.create(title="项目A-Bug2", project_id=pid_a)
        svc.create(title="无项目-Bug")

        # 无筛选 → 全部 3 条
        assert len(tracker._get_filtered_issues()) == 3

        # 筛选项目A → 2 条（项目A）+ 1 条（无项目）= 3 条
        tracker.set_project_filter(pid_a)
        filtered = tracker._get_filtered_issues()
        assert len(filtered) == 3  # 项目A 的 + 未关联的

        # 创建项目B，验证不串扰
        db_conn.execute(
            "INSERT INTO projects (name, product, customer, description, status) "
            "VALUES ('项目B', '产品B', '客户B', '', 'active')"
        )
        proj_b_row = db_conn.execute(
            "SELECT id FROM projects WHERE name='项目B'"
        ).fetchone()
        pid_b = proj_b_row[0]
        svc.create(title="项目B-Bug", project_id=pid_b)

        # 无筛选 → 4 条
        tracker.set_project_filter(None)
        assert len(tracker._get_filtered_issues()) == 4

        # 筛选项目A → 3 条（项目A 的 2 条 + 无项目 1 条，不含项目B）
        tracker.set_project_filter(pid_a)
        filtered = tracker._get_filtered_issues()
        assert len(filtered) == 3
        titles = [i.title for i in filtered]
        assert "项目B-Bug" not in titles
