"""架构优化新增方法测试 — 覆盖 5 个 service 工厂方法 + exec_crud undo_command 路径。

使用 :memory: SQLite + mock MainWindow，全部 headless 运行。
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.db.repositories.equipment_repo import EquipmentRepository
from src.db.repositories.technician_repo import TechnicianRepository
from src.db.repositories.knowledge_repo import KnowledgeRepository
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.test_task_repo import TestTaskRepository
from src.db.repositories.test_plan_repo import TestPlanRepository
from src.db.repositories.test_result_repo import TestResultRepository
from src.services.equipment_service import EquipmentService
from src.services.technician_service import TechnicianService
from src.services.knowledge_service import KnowledgeService
from src.services.issue_service import IssueService
from src.services.test_plan_service import TestPlanService
from src.services.undo_manager import UndoManager, DeleteEntityCommand, SoftDeleteCommand
from src.handlers.crud_helpers import exec_crud


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture()
def equip_svc(db_conn):
    return EquipmentService(EquipmentRepository(db_conn))


@pytest.fixture()
def tech_svc(db_conn):
    return TechnicianService(
        TechnicianRepository(db_conn),
        TestTaskRepository(db_conn),
        IssueRepository(db_conn),
    )


@pytest.fixture()
def knowledge_svc(db_conn):
    return KnowledgeService(KnowledgeRepository(db_conn))


@pytest.fixture()
def issue_svc(db_conn):
    return IssueService(IssueRepository(db_conn), db_conn)


@pytest.fixture()
def plan_svc(db_conn):
    return TestPlanService(
        TestPlanRepository(db_conn),
        TestTaskRepository(db_conn),
        TestResultRepository(db_conn),
    )


@pytest.fixture()
def undo_mgr():
    return UndoManager()


# ═══════════════════════════════════════════════════════════════════
#  1. EquipmentService.create_delete_command
# ═══════════════════════════════════════════════════════════════════


class TestEquipmentCreateDeleteCommand:
    def test_creates_command_when_no_references(self, equip_svc, db_conn):
        """无引用时正常创建 DeleteEntityCommand。"""
        eid = equip_svc.create("设备-A", type="温箱")
        cmd = equip_svc.create_delete_command(eid)
        assert isinstance(cmd, DeleteEntityCommand)
        assert cmd.description == "删除设备"

    def test_rejects_when_referenced_by_task(self, equip_svc, plan_svc, sample_project):
        """被任务引用时 raise ValueError。"""
        eid = equip_svc.create("被引用设备")
        plid = plan_svc.create_plan(sample_project["id"], "计划", start_date="2026-01-01")
        plan_svc.create_task(plid, "任务1", duration=5, equipment_id=eid)

        with pytest.raises(ValueError, match="引用"):
            equip_svc.create_delete_command(eid)

    def test_execute_command_deletes_equipment(self, equip_svc, undo_mgr):
        """command 通过 UndoManager 执行后设备被删除。"""
        eid = equip_svc.create("待删除设备")
        cmd = equip_svc.create_delete_command(eid)
        undo_mgr.execute(cmd)

        assert equip_svc.get(eid) is None

    def test_undo_restores_equipment(self, equip_svc, undo_mgr):
        """undo 后设备恢复（原始 ID 保持）。"""
        eid = equip_svc.create("恢复设备")
        cmd = equip_svc.create_delete_command(eid)
        undo_mgr.execute(cmd)
        assert equip_svc.get(eid) is None

        undo_mgr.undo()
        restored = equip_svc.get(eid)
        assert restored is not None
        assert restored.name == "恢复设备"


# ═══════════════════════════════════════════════════════════════════
#  2. TechnicianService.create_delete_command
# ═══════════════════════════════════════════════════════════════════


class TestTechnicianCreateDeleteCommand:
    def test_creates_command_when_no_references(self, tech_svc):
        """无引用时正常创建 DeleteEntityCommand。"""
        tid = tech_svc.create("张工", role="DQE", department="质量部")
        cmd = tech_svc.create_delete_command(tid)
        assert isinstance(cmd, DeleteEntityCommand)
        assert cmd.description == "删除技术员"

    def test_rejects_when_referenced_by_task(
        self, tech_svc, plan_svc, sample_project, db_conn,
    ):
        """被任务引用时拒绝删除。"""
        tid = tech_svc.create("任务引用技术员")
        plid = plan_svc.create_plan(sample_project["id"], "计划", start_date="2026-01-01")
        plan_svc.create_task(plid, "任务1", duration=5, technician_id=tid)

        with pytest.raises(ValueError, match="测试任务"):
            tech_svc.create_delete_command(tid)

    def test_rejects_when_referenced_by_issue_assignee(self, tech_svc, issue_svc, sample_project):
        """被 Issue 指派时拒绝删除。"""
        tid = tech_svc.create("Issue指派技术员")
        issue_svc.create("Issue-1", project_id=sample_project["id"], assignee_id=tid)

        with pytest.raises(ValueError, match="Issue"):
            tech_svc.create_delete_command(tid)

    def test_rejects_when_referenced_by_fa_analyst(self, tech_svc, issue_svc, sample_project, db_conn):
        """被 FA 分析记录引用时拒绝删除。"""
        tid = tech_svc.create("FA分析技术员")
        iid = issue_svc.create("FA-Issue", project_id=sample_project["id"])
        issue_svc.add_fa_record(iid, step_no=1, step_title="步骤1", analyst_id=tid)

        with pytest.raises(ValueError, match="FA"):
            tech_svc.create_delete_command(tid)


# ═══════════════════════════════════════════════════════════════════
#  3. KnowledgeService.create_delete_command
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeCreateDeleteCommand:
    def test_creates_command(self, knowledge_svc):
        """无校验，直接创建 DeleteEntityCommand。"""
        kid = knowledge_svc.create(category="环境", failure_mode="腐蚀")
        cmd = knowledge_svc.create_delete_command(kid)
        assert isinstance(cmd, DeleteEntityCommand)
        assert cmd.description == "删除知识条目"

    def test_execute_deletes_entry(self, knowledge_svc, undo_mgr):
        """command 执行后知识条目被删除。"""
        kid = knowledge_svc.create(category="环境", failure_mode="腐蚀")
        cmd = knowledge_svc.create_delete_command(kid)
        undo_mgr.execute(cmd)

        assert knowledge_svc.get(kid) is None

    def test_undo_restores_entry(self, knowledge_svc, undo_mgr):
        """undo 后知识条目恢复。"""
        kid = knowledge_svc.create(category="环境", failure_mode="腐蚀")
        cmd = knowledge_svc.create_delete_command(kid)
        undo_mgr.execute(cmd)
        assert knowledge_svc.get(kid) is None

        undo_mgr.undo()
        restored = knowledge_svc.get(kid)
        assert restored is not None
        assert restored.failure_mode == "腐蚀"


# ═══════════════════════════════════════════════════════════════════
#  4. IssueService.create_delete_command (SoftDeleteCommand)
# ═══════════════════════════════════════════════════════════════════


class TestIssueCreateDeleteCommand:
    def test_returns_soft_delete_command(self, issue_svc, sample_project):
        """返回 SoftDeleteCommand 类型。"""
        iid = issue_svc.create("软删除Issue", project_id=sample_project["id"])
        cmd = issue_svc.create_delete_command(iid)
        assert isinstance(cmd, SoftDeleteCommand)
        assert cmd.description == "删除Issue"

    def test_execute_sets_is_deleted(self, issue_svc, undo_mgr, sample_project):
        """执行后 is_deleted=1。"""
        iid = issue_svc.create("待软删", project_id=sample_project["id"])
        cmd = issue_svc.create_delete_command(iid)
        undo_mgr.execute(cmd)

        issue = issue_svc.get(iid)
        assert issue is not None
        assert issue.is_deleted == 1

    def test_undo_restores_is_deleted(self, issue_svc, undo_mgr, sample_project):
        """undo 后 is_deleted=0。"""
        iid = issue_svc.create("待恢复", project_id=sample_project["id"])
        cmd = issue_svc.create_delete_command(iid)
        undo_mgr.execute(cmd)
        assert issue_svc.get(iid).is_deleted == 1

        undo_mgr.undo()
        issue = issue_svc.get(iid)
        assert issue is not None
        assert issue.is_deleted == 0


# ═══════════════════════════════════════════════════════════════════
#  5. TestPlanService.create_task_delete_command
# ═══════════════════════════════════════════════════════════════════


class TestPlanCreateTaskDeleteCommand:
    def test_creates_command(self, plan_svc, sample_project):
        """无校验，正常创建 DeleteEntityCommand。"""
        plid = plan_svc.create_plan(sample_project["id"], "计划", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "待删任务", duration=5)
        cmd = plan_svc.create_task_delete_command(tid)
        assert isinstance(cmd, DeleteEntityCommand)
        assert cmd.description == "删除任务"

    def test_execute_deletes_task(self, plan_svc, undo_mgr, sample_project):
        """执行后任务被删除。"""
        plid = plan_svc.create_plan(sample_project["id"], "计划", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "待删任务", duration=5)
        cmd = plan_svc.create_task_delete_command(tid)
        undo_mgr.execute(cmd)

        assert plan_svc.get_task(tid) is None


# ═══════════════════════════════════════════════════════════════════
#  6. exec_crud undo_command 路径
# ═══════════════════════════════════════════════════════════════════


def _make_mock_win(undo_manager):
    """构造 mock MainWindow，含 _ctrl 和 undo_manager。"""
    win = MagicMock()
    ctrl = MagicMock()
    ctrl.undo_manager = undo_manager
    ctrl.notify_data_changed = MagicMock()
    win.ctrl = ctrl
    return win


class TestExecCrudUndoCommand:
    def test_undo_manager_execute_called(self, undo_mgr):
        """提供 undo_command 时，undo_manager.execute 被调用。"""
        cmd = MagicMock(spec=DeleteEntityCommand)
        win = _make_mock_win(undo_mgr)

        # 用真实 UndoManager 来确认 execute 被调用了
        # 改为直接 mock undo_mgr 的 execute 以验证调用
        undo_mgr_execute = undo_mgr.execute

        with patch.object(undo_mgr, "execute", wraps=undo_mgr_execute) as spy:
            exec_crud(
                win=win,
                action=lambda: None,
                toast_msg="已删除",
                entity="equipment",
                undo_command=cmd,
            )
            spy.assert_called_once_with(cmd)

    def test_action_not_called_when_undo_command_provided(self, undo_mgr):
        """提供 undo_command 时，action 不被调用。"""
        cmd = MagicMock(spec=DeleteEntityCommand)
        win = _make_mock_win(undo_mgr)
        action = MagicMock()

        exec_crud(
            win=win,
            action=action,
            toast_msg="已删除",
            entity="equipment",
            undo_command=cmd,
        )
        action.assert_not_called()

    def test_win_toast_called_on_success(self, undo_mgr):
        """undo_command 执行成功后 win.toast 被调用。"""
        cmd = MagicMock(spec=DeleteEntityCommand)
        win = _make_mock_win(undo_mgr)

        result = exec_crud(
            win=win,
            action=lambda: None,
            toast_msg="删除成功",
            entity="equipment",
            undo_command=cmd,
        )
        assert result is True
        win.toast.assert_called_once_with("删除成功", "success")

    def test_returns_false_on_exception(self, undo_mgr):
        """undo_command 执行异常时返回 False。"""
        cmd = MagicMock(spec=DeleteEntityCommand)
        cmd.do.side_effect = RuntimeError("boom")
        win = _make_mock_win(undo_mgr)

        # exec_crud 会弹 QMessageBox.critical，需要 patch 掉以避免 Qt 依赖
        with patch("src.handlers.crud_helpers.QMessageBox") as mock_qmb:
            result = exec_crud(
                win=win,
                action=lambda: None,
                toast_msg="删除失败",
                entity="equipment",
                undo_command=cmd,
            )
        assert result is False
        mock_qmb.critical.assert_called_once()
        win.toast.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
#  7. Service.transaction() 上下文管理器
# ═══════════════════════════════════════════════════════════════════


class TestServiceTransaction:
    def test_equipment_service_transaction_is_context_manager(self, equip_svc, db_conn):
        """EquipmentService.transaction() 返回可用的上下文管理器。"""
        with equip_svc.transaction():
            eid = equip_svc.create("事务设备")
        assert equip_svc.get(eid) is not None

    def test_equipment_service_transaction_rollback_on_error(self, equip_svc):
        """事务中抛异常时回滚。"""
        try:
            with equip_svc.transaction():
                eid = equip_svc.create("回滚设备")
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        assert equip_svc.get(eid) is None

    def test_technician_service_transaction_is_context_manager(self, tech_svc):
        """TechnicianService.transaction() 返回可用的上下文管理器。"""
        with tech_svc.transaction():
            tid = tech_svc.create("事务技术员")
        assert tech_svc.get(tid) is not None

    def test_technician_service_transaction_rollback_on_error(self, tech_svc):
        """事务中抛异常时回滚。"""
        try:
            with tech_svc.transaction():
                tid = tech_svc.create("回滚技术员")
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        assert tech_svc.get(tid) is None
