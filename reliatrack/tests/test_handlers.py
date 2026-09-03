"""Handler 联动测试 — FA/CAPA ↔ Issue sync 逻辑验证。

直接测试 IssueHandlers._sync_issue_from_fa / _sync_issue_from_capa 的联动规则，
使用真实 :memory: DB + IssueService，Mock MainWindow 避免 Qt 依赖。
"""

from __future__ import annotations

import pytest
import apsw
from unittest.mock import MagicMock

from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository
from src.services.issue_service import IssueService
from src.handlers.issue_handlers import IssueHandlers


# ══════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture()
def db_conn() -> apsw.Connection:
    """内存数据库，关闭 FK 以避免测试数据依赖。"""
    conn = apsw.Connection(":memory:")
    init_schema(conn)
    # init_schema 可能在迁移流程中把 FK 重新打开，确保测试环境关闭
    conn.execute("PRAGMA foreign_keys=OFF")
    yield conn
    conn.close()


@pytest.fixture()
def issue_service(db_conn: apsw.Connection) -> IssueService:
    """真实 IssueService，底层使用 :memory: DB。"""
    repo = IssueRepository(db_conn)
    return IssueService(repo)


@pytest.fixture()
def mock_win(issue_service: IssueService) -> MagicMock:
    """Mock MainWindow —— ctrl.issue_service 使用真实 IssueService。"""
    win = MagicMock()
    ctrl = MagicMock()
    ctrl.issue_service = issue_service
    win.ctrl = ctrl
    win.bug_tracker_view = MagicMock()
    win.bug_tracker_view.get_selected_issue_id.return_value = None
    return win


@pytest.fixture()
def handlers(mock_win: MagicMock) -> IssueHandlers:
    """IssueHandlers 实例。"""
    return IssueHandlers(mock_win)


@pytest.fixture()
def sample_issue(issue_service: IssueService) -> int:
    """创建一个测试 Issue 并返回其 ID。"""
    return issue_service.create(
        title="测试Issue",
        project_id=1,  # FK 关闭，不校验
        severity="major",
        status="open",
    )


# ══════════════════════════════════════════════════════════════
#  _sync_issue_from_fa 联动测试 (7 cases)
# ══════════════════════════════════════════════════════════════


class TestSyncIssueFromFA:
    """FA 记录变更 → Issue 联动规则。"""

    def test_fa_added_open_to_analyzing(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA1: open 状态 + 添加 FA 记录 → 状态变为 analyzing。"""
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "open"

        issue_service.add_fa_record(sample_issue, step_no=1, step_title="外观检查")
        handlers._sync_issue_from_fa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "analyzing"

    def test_fa_confirmed_cause_updates_root_cause(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA2: confirmed=1 且 possible_cause 非空 → root_cause 被更新。"""
        issue_service.add_fa_record(
            sample_issue,
            step_no=1,
            step_title="切片分析",
            possible_cause="焊料虚焊",
            confirmed=1,
        )
        handlers._sync_issue_from_fa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert "焊料虚焊" in issue.root_cause

    def test_multiple_confirmed_causes_joined(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA3: 多条 confirmed=1 的 possible_cause 用 '; ' 拼接。"""
        issue_service.add_fa_record(
            sample_issue,
            step_no=1,
            step_title="步骤1",
            possible_cause="原因A",
            confirmed=1,
        )
        issue_service.add_fa_record(
            sample_issue,
            step_no=2,
            step_title="步骤2",
            possible_cause="原因B",
            confirmed=1,
        )
        handlers._sync_issue_from_fa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.root_cause == "原因A; 原因B"

    def test_unconfirmed_cause_not_updated(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA4: confirmed=0 或 2 的 possible_cause → root_cause 不更新。"""
        issue_service.add_fa_record(
            sample_issue,
            step_no=1,
            step_title="步骤1",
            possible_cause="待定原因",
            confirmed=0,
        )
        issue_service.add_fa_record(
            sample_issue,
            step_no=2,
            step_title="步骤2",
            possible_cause="排除原因",
            confirmed=2,
        )
        handlers._sync_issue_from_fa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        # 状态会变 analyzing（有 FA 记录），但 root_cause 保持空
        assert issue.root_cause == ""

    def test_already_analyzing_status_unchanged(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA5: Issue 已经是 analyzing → 状态不变。"""
        issue_service.update(sample_issue, status="analyzing")
        issue_service.add_fa_record(
            sample_issue,
            step_no=1,
            step_title="步骤1",
            possible_cause="新原因",
            confirmed=1,
        )
        handlers._sync_issue_from_fa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "analyzing"
        assert "新原因" in issue.root_cause

    def test_no_fa_records_no_updates(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA6: 无 FA 记录 → Issue 不做任何更新。"""
        original = issue_service.get(sample_issue)
        assert original is not None

        handlers._sync_issue_from_fa(sample_issue)

        after = issue_service.get(sample_issue)
        assert after is not None
        assert after.status == original.status
        assert after.root_cause == original.root_cause

    def test_fa_no_confirmed_causes_root_cause_stays_empty(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA7: 有 FA 记录但无 confirmed 原因 → root_cause 保持空。"""
        issue_service.add_fa_record(
            sample_issue,
            step_no=1,
            step_title="外观检查",
            possible_cause="可能原因",
            confirmed=0,
        )
        handlers._sync_issue_from_fa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "analyzing"
        assert issue.root_cause == ""


# ══════════════════════════════════════════════════════════════
#  _sync_issue_from_capa 联动测试 (7 cases)
# ══════════════════════════════════════════════════════════════


class TestSyncIssueFromCAPA:
    """CAPA 记录变更 → Issue 联动规则。"""

    def test_capa_action_updates_improvement_measures(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA1: CAPA action → Issue.improvement_measures 被更新。"""
        issue_service.add_capa_record(
            sample_issue,
            action="更换供应商",
            status="pending",
        )
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.improvement_measures == "更换供应商"

    def test_multiple_capas_actions_joined(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA2: 多条 CAPA action 用 '; ' 拼接。"""
        issue_service.add_capa_record(
            sample_issue,
            action="更换供应商",
            status="pending",
        )
        issue_service.add_capa_record(
            sample_issue,
            action="加强来料检验",
            status="pending",
        )
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.improvement_measures == "更换供应商; 加强来料检验"

    def test_all_capas_completed_verifies_status(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA3: 所有 CAPA 状态为 completed/verified → analyzing→verified。"""
        issue_service.update(sample_issue, status="analyzing")
        issue_service.add_capa_record(
            sample_issue,
            action="措施A",
            status="completed",
        )
        issue_service.add_capa_record(
            sample_issue,
            action="措施B",
            status="verified",
        )
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "verified"

    def test_all_capas_deleted_clears_improvement_measures(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA4: 所有 CAPA 被删空 → improvement_measures 被清空。"""
        capa_id = issue_service.add_capa_record(
            sample_issue,
            action="临时措施",
            status="pending",
        )
        # 先同步一次，让 improvement_measures 有值
        handlers._sync_issue_from_capa(sample_issue)
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.improvement_measures != ""

        # 删除所有 CAPA
        issue_service.delete_capa_record(capa_id)
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.improvement_measures == ""

    def test_capas_exist_actions_all_empty_clears_improvement_measures(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA5: CAPA 存在但 action 全为空 → improvement_measures 被清空。

        注：action 列为 NOT NULL，所以空字符串代表空 action。
        通过直接插入空 action 来测试此场景。
        """
        # 先设置 improvement_measures 有值
        issue_service.update(sample_issue, improvement_measures="旧解决方案")
        # 添加一条 action 为空的 CAPA
        issue_service.add_capa_record(
            sample_issue,
            action="",
            status="pending",
        )
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.improvement_measures == ""

    def test_not_analyzing_status_unchanged_even_if_all_capas_done(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA6: Issue 非 analyzing 状态 → 即使所有 CAPA 完成，状态不变。"""
        # sample_issue 默认 status=open
        issue_service.add_capa_record(
            sample_issue,
            action="措施A",
            status="completed",
        )
        issue_service.add_capa_record(
            sample_issue,
            action="措施B",
            status="verified",
        )
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "open"  # 不变

    def test_partial_capas_done_no_status_change(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA7: 部分 CAPA 完成 → analyzing 状态不变。"""
        issue_service.update(sample_issue, status="analyzing")
        issue_service.add_capa_record(
            sample_issue,
            action="措施A",
            status="completed",
        )
        issue_service.add_capa_record(
            sample_issue,
            action="措施B",
            status="in_progress",
        )
        handlers._sync_issue_from_capa(sample_issue)

        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "analyzing"  # 不变，因为有未完成的


# ══════════════════════════════════════════════════════════════
#  _handle_fa_record_added 联动测试 (2 cases)
# ══════════════════════════════════════════════════════════════


class TestHandleFARecordAdded:
    """FA 记录添加 handler 集成测试。"""

    def test_fa_record_added_refreshes_panel_and_syncs(
        self,
        handlers: IssueHandlers,
        mock_win: MagicMock,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """FA-Handler1: FA 记录添加 → FA 面板刷新 + sync 联动触发。"""
        mock_win.bug_tracker_view.get_selected_issue_id.return_value = sample_issue

        data = {
            "issue_id": sample_issue,
            "step_no": 1,
            "step_title": "外观检查",
            "possible_cause": "虚焊",
            "confirmed": 1,
        }
        handlers._handle_fa_record_added(data)

        # 验证 FA 面板被刷新
        mock_win.bug_tracker_view.refresh_fa.assert_called_once()
        fa_records = mock_win.bug_tracker_view.refresh_fa.call_args[0][0]
        assert len(fa_records) == 1
        assert fa_records[0].possible_cause == "虚焊"

        # 验证联动：状态应变为 analyzing
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "analyzing"
        assert issue.root_cause == "虚焊"

        # 验证 toast 被调用
        mock_win.toast.assert_called_once_with("FA 步骤已添加", "success")

    def test_fa_record_added_invalid_issue_id_no_crash(
        self,
        handlers: IssueHandlers,
        mock_win: MagicMock,
    ) -> None:
        """FA-Handler2: issue_id 为 None → 不崩溃。"""
        data = {"step_no": 1, "step_title": "测试"}
        # issue_id 为 None → handler 应直接 return
        handlers._handle_fa_record_added(data)
        # 不应调用 refresh_fa
        mock_win.bug_tracker_view.refresh_fa.assert_not_called()

    def test_fa_record_added_missing_issue_id_key(
        self,
        handlers: IssueHandlers,
        mock_win: MagicMock,
    ) -> None:
        """FA-Handler3: data 中无 issue_id 键 → 不崩溃。"""
        data = {"step_no": 1, "step_title": "测试"}
        handlers._handle_fa_record_added(data)
        mock_win.bug_tracker_view.refresh_fa.assert_not_called()


# ══════════════════════════════════════════════════════════════
#  _handle_capa_record_added 联动测试 (2 cases)
# ══════════════════════════════════════════════════════════════


class TestHandleCAPARecordAdded:
    """CAPA 记录添加 handler 集成测试。"""

    def test_capa_record_added_refreshes_panel_and_syncs(
        self,
        handlers: IssueHandlers,
        mock_win: MagicMock,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """CAPA-Handler1: CAPA 记录添加 → CAPA 面板刷新 + sync 联动触发。"""
        mock_win.bug_tracker_view.get_selected_issue_id.return_value = sample_issue

        data = {
            "issue_id": sample_issue,
            "action": "更换供应商",
            "status": "pending",
        }
        handlers._handle_capa_record_added(data)

        # 验证 CAPA 面板被刷新
        mock_win.bug_tracker_view.refresh_capa.assert_called_once()
        capa_records = mock_win.bug_tracker_view.refresh_capa.call_args[0][0]
        assert len(capa_records) == 1
        assert capa_records[0].action == "更换供应商"

        # 验证联动：improvement_measures 应被更新
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.improvement_measures == "更换供应商"

        # 验证 toast 被调用
        mock_win.toast.assert_called_once_with("CAPA 措施已添加", "success")

    def test_capa_record_added_invalid_issue_id_no_crash(
        self,
        handlers: IssueHandlers,
        mock_win: MagicMock,
    ) -> None:
        """CAPA-Handler2: issue_id 为 None → 不崩溃。"""
        data = {"action": "测试措施"}
        handlers._handle_capa_record_added(data)
        mock_win.bug_tracker_view.refresh_capa.assert_not_called()


# ══════════════════════════════════════════════════════════════
#  边界条件 / 集成场景
# ══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件和异常场景。"""

    def test_sync_fa_nonexistent_issue(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
    ) -> None:
        """联动不存在的 Issue ID → 不崩溃。"""
        handlers._sync_issue_from_fa(99999)
        # 无异常即可

    def test_sync_capa_nonexistent_issue(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
    ) -> None:
        """联动不存在的 Issue ID → 不崩溃。"""
        handlers._sync_issue_from_capa(99999)
        # 无异常即可

    def test_full_workflow_fa_then_capa(
        self,
        handlers: IssueHandlers,
        issue_service: IssueService,
        sample_issue: int,
    ) -> None:
        """完整工作流: open → (FA) → analyzing → (CAPA completed) → verified。"""
        # 1. 初始状态
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "open"

        # 2. 添加 FA 记录 → analyzing
        issue_service.add_fa_record(
            sample_issue,
            step_no=1,
            step_title="根因分析",
            possible_cause="PCB 焊盘设计缺陷",
            confirmed=1,
        )
        handlers._sync_issue_from_fa(sample_issue)
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "analyzing"
        assert issue.root_cause == "PCB 焊盘设计缺陷"

        # 3. 添加 CAPA → improvement_measures 更新
        issue_service.add_capa_record(
            sample_issue,
            action="修订 PCB 焊盘设计规范",
            status="completed",
        )
        handlers._sync_issue_from_capa(sample_issue)
        issue = issue_service.get(sample_issue)
        assert issue is not None
        assert issue.status == "verified"
        assert issue.improvement_measures == "修订 PCB 焊盘设计规范"

    def test_handler_ctrl_none_graceful(
        self,
        mock_win: MagicMock,
    ) -> None:
        """ctrl 为 None → handler 方法不崩溃。"""
        mock_win.ctrl = None
        handlers = IssueHandlers(mock_win)

        # 应静默返回
        handlers._sync_issue_from_fa(1)
        handlers._sync_issue_from_capa(1)
        handlers._handle_fa_record_added({"issue_id": 1})
        handlers._handle_capa_record_added({"issue_id": 1})

    def test_handler_issue_service_none_graceful(
        self,
        mock_win: MagicMock,
    ) -> None:
        """ctrl.issue_service 为 None → handler 方法不崩溃。"""
        mock_win.ctrl.issue_service = None
        handlers = IssueHandlers(mock_win)

        handlers._sync_issue_from_fa(1)
        handlers._sync_issue_from_capa(1)
        handlers._handle_fa_record_added({"issue_id": 1})
        handlers._handle_capa_record_added({"issue_id": 1})


# ══════════════════════════════════════════════════════════════
#  PlanHandlers — 实际日期快捷编辑测试
# ══════════════════════════════════════════════════════════════


class TestActualDateEdit:
    """_on_actual_date_edit 直接调用不崩溃，正确委托到 update_task。"""

    @pytest.fixture()
    def mock_plan_win(self, db_conn: apsw.Connection) -> MagicMock:
        """Mock MainWindow，使 PlanHandlers 可构造 + 调用 _on_actual_date_edit。"""
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.db.repositories.test_result_repo import TestResultRepository
        from src.services.test_plan_service import TestPlanService
        plan_repo = TestPlanRepository(db_conn)
        task_repo = TestTaskRepository(db_conn)
        result_repo = TestResultRepository(db_conn)
        svc = TestPlanService(plan_repo, task_repo, result_repo)

        db_conn.execute(
            "INSERT INTO test_plans (id, project_id, name, status) VALUES (1, 1, 'P', 'active')"
        )
        db_conn.execute(
            "INSERT INTO test_tasks (id, plan_id, name, duration) VALUES (1, 1, 'T1', 5)"
        )

        win = MagicMock()
        win.ctrl.test_plan_service = svc
        win.ctrl.test_tasks = task_repo
        win.toast = MagicMock()
        return win

    def test_update_actual_start_date(
        self, mock_plan_win: MagicMock
    ) -> None:
        """设置 actual_start_date → DB 写入正确 + toast 触发。"""
        from src.handlers.plan_handlers import PlanHandlers
        handlers = PlanHandlers(mock_plan_win)

        handlers._on_actual_date_edit(1, "actual_start_date", "2026-03-15")

        task = mock_plan_win.ctrl.test_plan_service.get_task(1)
        assert task is not None
        assert task.actual_start_date == "2026-03-15"
        mock_plan_win.toast.assert_called_once()

    def test_update_actual_end_date(
        self, mock_plan_win: MagicMock
    ) -> None:
        """设置 actual_end_date → DB 写入正确。"""
        from src.handlers.plan_handlers import PlanHandlers
        handlers = PlanHandlers(mock_plan_win)

        handlers._on_actual_date_edit(1, "actual_end_date", "2026-03-20")

        task = mock_plan_win.ctrl.test_plan_service.get_task(1)
        assert task is not None
        assert task.actual_end_date == "2026-03-20"

    def test_clear_actual_date(
        self, mock_plan_win: MagicMock
    ) -> None:
        """清空实际日期（空字符串）不崩溃，DB 正确置空。"""
        from src.handlers.plan_handlers import PlanHandlers
        mock_plan_win.ctrl.test_plan_service.update_task(1, actual_start_date="2026-03-15")

        handlers = PlanHandlers(mock_plan_win)
        handlers._on_actual_date_edit(1, "actual_start_date", "")

        task = mock_plan_win.ctrl.test_plan_service.get_task(1)
        assert task is not None
        assert task.actual_start_date == ""

    def test_service_none_no_crash(
        self, mock_plan_win: MagicMock
    ) -> None:
        """ctrl.test_plan_service 为 None → 不崩溃。"""
        mock_plan_win.ctrl.test_plan_service = None
        from src.handlers.plan_handlers import PlanHandlers
        handlers = PlanHandlers(mock_plan_win)

        handlers._on_actual_date_edit(1, "actual_start_date", "2026-03-15")

# ══════════════════════════════════════════════════════════════
#  PlanHandlers — 浮动批量操作栏信号（BatchActionBar 接线）
# ══════════════════════════════════════════════════════════════


class TestBatchActionBarWiring:
    """批量操作栏 3 个核心信号必须连接（2026-08-09 修复：原为死信号）。"""

    @pytest.fixture()
    def batch_win(self, db_conn: apsw.Connection) -> MagicMock:
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.db.repositories.test_result_repo import TestResultRepository
        from src.services.test_plan_service import TestPlanService
        plan_repo = TestPlanRepository(db_conn)
        task_repo = TestTaskRepository(db_conn)
        result_repo = TestResultRepository(db_conn)
        svc = TestPlanService(plan_repo, task_repo, result_repo)

        db_conn.execute(
            "INSERT INTO test_plans (id, project_id, name, status) VALUES (1, 1, 'P', 'active')"
        )
        db_conn.execute(
            "INSERT INTO test_tasks (id, plan_id, name, duration, status) VALUES (1, 1, 'T1', 5, 'pending')"
        )
        db_conn.execute(
            "INSERT INTO test_tasks (id, plan_id, name, duration, status) VALUES (2, 1, 'T2', 3, 'pending')"
        )

        win = MagicMock()
        win.ctrl.test_plan_service = svc
        win.ctrl.test_tasks = task_repo
        win.toast = MagicMock()
        # 模拟 task_table.get_selected_task_ids
        task_table = MagicMock()
        task_table.get_selected_task_ids.return_value = [1, 2]
        win.test_plan_view._task_table = task_table
        win.test_plan_view.get_selected_plan_id.return_value = 1
        return win

    def test_connect_signals_wires_batch_bar(self, batch_win: MagicMock) -> None:
        """connect_signals 必须连接 status_selected / tech_selected / export_clicked。"""
        import inspect
        from src.handlers import plan_handlers
        src = inspect.getsource(plan_handlers.PlanHandlers.connect_signals)
        assert "_batch_bar.status_selected.connect" in src
        assert "_batch_bar.tech_selected.connect" in src
        assert "_batch_bar.export_clicked.connect" in src

    def test_batch_status_updates_tasks(self, batch_win: MagicMock) -> None:
        """批量改状态：_on_batch_status('completed') → 状态+联动字段全更新（B5）。"""
        from src.handlers.plan_handlers import PlanHandlers
        handlers = PlanHandlers(batch_win)
        handlers._on_batch_status("completed")

        t1 = batch_win.ctrl.test_plan_service.get_task(1)
        t2 = batch_win.ctrl.test_plan_service.get_task(2)
        assert t1 is not None and t1.status == "completed"
        assert t2 is not None and t2.status == "completed"
        # B5 联动: completed 必须补实际完成日期与进度
        assert t1.progress == 100.0 and t2.progress == 100.0
        assert t1.actual_end_date and t2.actual_end_date

    def test_batch_status_no_selection_toast(self, batch_win: MagicMock) -> None:
        """未选任务 → toast 提示且不崩溃。"""
        batch_win.test_plan_view._task_table.get_selected_task_ids.return_value = []
        from src.handlers.plan_handlers import PlanHandlers
        handlers = PlanHandlers(batch_win)
        handlers._on_batch_status("completed")
        batch_win.toast.assert_called_once()

    def test_batch_assign_technician(self, batch_win: MagicMock) -> None:
        """批量指派技术员：tech_id → 名称 → 任务 technician_id 更新。"""
        batch_win.ctrl.technicians = MagicMock()
        batch_win.ctrl.technicians.list_all.return_value = [
            type("Tech", (), {"id": 7, "name": "张三"})(),
        ]
        from src.handlers.plan_handlers import PlanHandlers
        handlers = PlanHandlers(batch_win)
        handlers._on_batch_assign_technician(7)

        t1 = batch_win.ctrl.test_plan_service.get_task(1)
        assert t1 is not None and t1.technician_id == 7


class TestArchivedPlansByProject:
    """get_archived_plans_by_project 回归测试（2026-09-03 修复：main.py:832 AttributeError）。"""

    @pytest.fixture()
    def plan_svc_arch(self, db_conn: apsw.Connection):
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.db.repositories.test_result_repo import TestResultRepository
        from src.services.test_plan_service import TestPlanService
        return TestPlanService(
            TestPlanRepository(db_conn),
            TestTaskRepository(db_conn),
            TestResultRepository(db_conn),
        )

    @pytest.fixture()
    def arch_project(self, db_conn: apsw.Connection) -> int:
        db_conn.execute(
            "INSERT INTO projects (id, name, product, customer, description, status)"
            " VALUES (1, '归档测试项目', 'X', 'Y', '', 'active')"
        )
        return 1

    def test_archived_plans_returns_only_archived(
        self, plan_svc_arch, arch_project: int
    ) -> None:
        """归档视图：只返回 status='archived' 的计划，active 计划排除。"""
        pid = arch_project
        p1 = plan_svc_arch.create_plan(pid, "活跃计划")
        p2 = plan_svc_arch.create_plan(pid, "已归档计划")
        plan_svc_arch.update_plan(p2, status="archived")

        active = plan_svc_arch.get_active_plans_by_project(pid)
        archived = plan_svc_arch.get_archived_plans_by_project(pid)

        assert [p.name for p in active] == ["活跃计划"]
        assert [p.name for p in archived] == ["已归档计划"]

    def test_archived_plans_empty_when_none(self, plan_svc_arch, arch_project: int) -> None:
        """无归档计划时返回空列表（不崩溃）。"""
        plan_svc_arch.create_plan(arch_project, "只有活跃")
        assert plan_svc_arch.get_archived_plans_by_project(arch_project) == []
