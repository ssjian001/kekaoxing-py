"""Service 层单元测试 — 覆盖核心 CRUD + 边界条件。

使用真实内存 SQLite 数据库，不 mock。
"""

from __future__ import annotations

import pytest

from src.db.repositories import (
    ProjectRepository,
    SampleRepository,
    EquipmentRepository,
    IssueRepository,
    TestPlanRepository,
    TestTaskRepository,
    TestResultRepository,
)
from src.services.project_service import ProjectService
from src.services.sample_service import SampleService
from src.services.equipment_service import EquipmentService
from src.services.issue_service import IssueService
from src.services.test_plan_service import TestPlanService
from src.services.undo_manager import (
    UndoManager,
    UpdateFieldCommand,
    MoveTaskCommand,
    AddEntityCommand,
    DeleteEntityCommand,
    BatchScheduleCommand,
)


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def proj_svc(db_conn):
    """创建 ProjectService（依赖 5 个 repo）。"""
    plan_repo = TestPlanRepository(db_conn)
    task_repo = TestTaskRepository(db_conn)
    sample_repo = SampleRepository(db_conn)
    issue_repo = IssueRepository(db_conn)
    return ProjectService(
        ProjectRepository(db_conn), plan_repo, task_repo, sample_repo, issue_repo,
    )


@pytest.fixture()
def sample_svc(db_conn):
    return SampleService(SampleRepository(db_conn))


@pytest.fixture()
def equip_svc(db_conn):
    return EquipmentService(EquipmentRepository(db_conn))


@pytest.fixture()
def issue_svc(db_conn):
    return IssueService(IssueRepository(db_conn))


@pytest.fixture()
def plan_svc(db_conn):
    return TestPlanService(
        TestPlanRepository(db_conn), TestTaskRepository(db_conn),
        TestResultRepository(db_conn),
    )


# ═══════════════════════════════════════════════════════════════════
#  ProjectService
# ═══════════════════════════════════════════════════════════════════

class TestProjectService:
    def test_create_and_get(self, proj_svc):
        pid = proj_svc.create("项目A", product="P1")
        p = proj_svc.get(pid)
        assert p is not None
        assert p.name == "项目A"

    def test_list_all(self, proj_svc):
        proj_svc.create("项目A")
        proj_svc.create("项目B")
        assert len(proj_svc.list_all()) == 2
    def test_get_nonexistent(self, proj_svc):
        assert proj_svc.get(9999) is None

    def test_update(self, proj_svc):
        pid = proj_svc.create("项目A")
        proj_svc.update(pid, name="项目B")
        assert proj_svc.get(pid).name == "项目B"

    def test_delete(self, proj_svc):
        pid = proj_svc.create("待删除")
        proj_svc.delete(pid)
        assert proj_svc.get(pid) is None
        assert len(proj_svc.list_all()) == 0

    def test_delete_cascade_removes_associated(self, proj_svc, sample_svc, issue_svc, plan_svc):
        """删除项目应级联删除关联的样品、Issue、计划+任务。"""
        pid = proj_svc.create("级联测试")
        sid = sample_svc.create("SN-001", project_id=pid, status="in_stock")
        iid = issue_svc.create("Bug", project_id=pid, status="open")
        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "任务1", duration=5)

        proj_svc.delete(pid)

        assert sample_svc.get(sid) is None
        assert issue_svc.get(iid) is None
        assert plan_svc.get_task(tid) is None
        assert plan_svc.get_plan(plid) is None


# ═══════════════════════════════════════════════════════════════════
#  SampleService
# ═══════════════════════════════════════════════════════════════════

class TestSampleService:
    def test_create_and_get(self, sample_svc, sample_project):
        sid = sample_svc.create("SN-001", project_id=sample_project["id"], status="in_stock")
        s = sample_svc.get(sid)
        assert s is not None
        assert s.sn == "SN-001"

    def test_list_all(self, sample_svc, sample_project):
        sample_svc.create("SN-001", project_id=sample_project["id"])
        sample_svc.create("SN-002", project_id=sample_project["id"])
        assert len(sample_svc.list_all()) == 2

    def test_get_by_sn(self, sample_svc, sample_project):
        sample_svc.create("UNIQUE-SN", project_id=sample_project["id"])
        s = sample_svc.get_by_sn("UNIQUE-SN")
        assert s is not None

    def test_update_status(self, sample_svc, sample_project):
        sid = sample_svc.create("SN-001", project_id=sample_project["id"], status="in_stock")
        sample_svc.update_status(sid, "in_use")
        assert sample_svc.get(sid).status == "in_use"

    def test_delete_with_transactions(self, sample_svc, sample_project, sample_technician):
        sid = sample_svc.create("SN-001", project_id=sample_project["id"])
        sample_svc.add_transaction(sid, "checkout", operator_id=sample_technician["id"])
        sample_svc.delete(sid)
        assert sample_svc.get(sid) is None
# ═══════════════════════════════════════════════════════════════════
#  EquipmentService
# ═══════════════════════════════════════════════════════════════════

class TestEquipmentService:
    def test_create_and_get(self, equip_svc):
        eid = equip_svc.create("温箱-01", type="高低温箱")
        e = equip_svc.get(eid)
        assert e is not None
        assert e.name == "温箱-01"

    def test_list_all(self, equip_svc):
        equip_svc.create("设备A")
        equip_svc.create("设备B")
        assert len(equip_svc.list_all()) == 2

    def test_update(self, equip_svc):
        eid = equip_svc.create("旧名称")
        equip_svc.update(eid, name="新名称")
        assert equip_svc.get(eid).name == "新名称"

    def test_delete(self, equip_svc):
        eid = equip_svc.create("可删除")
        equip_svc.delete(eid)
        assert equip_svc.get(eid) is None

    def test_delete_referenced_raises(self, equip_svc, plan_svc, sample_project):
        """被任务引用的设备不能删除。"""
        eid = equip_svc.create("被引用设备")
        plid = plan_svc.create_plan(sample_project["id"], "计划", start_date="2026-01-01")
        plan_svc.create_task(plid, "任务1", duration=5, equipment_id=eid)

        with pytest.raises(ValueError, match="引用"):
            equip_svc.delete(eid)


# ═══════════════════════════════════════════════════════════════════
#  IssueService
# ═══════════════════════════════════════════════════════════════════

class TestIssueService:
    def test_create_and_get(self, issue_svc, sample_project):
        iid = issue_svc.create("Bug标题", project_id=sample_project["id"], severity="major")
        issue = issue_svc.get(iid)
        assert issue is not None
        assert issue.title == "Bug标题"

    def test_list_all(self, issue_svc, sample_project):
        issue_svc.create("Issue1", project_id=sample_project["id"])
        issue_svc.create("Issue2", project_id=sample_project["id"])
        assert len(issue_svc.list_all()) == 2

    def test_update(self, issue_svc, sample_project):
        iid = issue_svc.create("旧标题", project_id=sample_project["id"])
        issue_svc.update(iid, title="新标题")
        assert issue_svc.get(iid).title == "新标题"

    def test_update_status(self, issue_svc, sample_project):
        """状态变更走 transition_status（带校验+活动日志）——原 update_status
        死方法绕过状态机已删除（2026-08-21 审计）。closed 需 resolution。"""
        iid = issue_svc.create("待关闭", project_id=sample_project["id"], status="open")
        # 无 resolution 时状态机正确拒绝（这正是被删死方法绕过的校验）
        ok, reason = issue_svc.transition_status(iid, "closed")
        assert not ok and "resolution" in reason.lower() or "处理结果" in reason
        issue_svc.update(iid, resolution="已修复并验证")
        ok, _ = issue_svc.transition_status(iid, "closed")
        assert ok
        assert issue_svc.get(iid).status == "closed"

    def test_fa_records(self, issue_svc, sample_project):
        iid = issue_svc.create("需要FA", project_id=sample_project["id"])
        issue_svc.add_fa_record(iid, step_no=1, method="X光", step_title="步骤1")
        issue_svc.add_fa_record(iid, step_no=2, method="切片", step_title="步骤2")
        fa = issue_svc.get_fa_records(iid)
        assert len(fa) == 2
        assert fa[0].step_no == 1

    def test_delete_cascade_fa(self, issue_svc, sample_project):
        iid = issue_svc.create("级联删除", project_id=sample_project["id"])
        issue_svc.add_fa_record(iid, step_no=1, method="X光", step_title="步骤1")
        issue_svc.delete(iid)
        assert issue_svc.get(iid) is None

    def test_get_by_project(self, issue_svc, sample_project):
        issue_svc.create("P1-Issue", project_id=sample_project["id"])
        pid2 = 9999  # 不存在的项目
        assert len(issue_svc.get_by_project(sample_project["id"])) == 1
        assert len(issue_svc.get_by_project(pid2)) == 0


# ═══════════════════════════════════════════════════════════════════
#  TestPlanService
# ═══════════════════════════════════════════════════════════════════

class TestPlanSvc:
    def test_create_plan_and_task(self, plan_svc, sample_project):
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        plan = plan_svc.get_plan(plid)
        assert plan is not None
        assert plan.name == "计划1"

        tid = plan_svc.create_task(plid, "任务A", duration=10, category="环境试验")
        task = plan_svc.get_task(tid)
        assert task is not None
        assert task.duration == 10

    def test_get_tasks_by_plan(self, plan_svc, sample_project):
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        plan_svc.create_task(plid, "任务1", duration=5)
        plan_svc.create_task(plid, "任务2", duration=3)
        tasks = plan_svc.get_tasks(plid)
        assert len(tasks) == 2
    def test_delete_task(self, plan_svc, sample_project):
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "任务1", duration=5)
        plan_svc.delete_task(tid)
        assert plan_svc.get_task(tid) is None
        assert len(plan_svc.get_tasks(plid)) == 0
    def test_task_count(self, plan_svc, sample_project):
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        plan_svc.create_task(plid, "T1", duration=5)
        plan_svc.create_task(plid, "T2", duration=3)
        assert plan_svc.task_count(plid) == 2

    def test_bulk_update_start_day(self, plan_svc, sample_project):
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        t1 = plan_svc.create_task(plid, "T1", duration=5)
        t2 = plan_svc.create_task(plid, "T2", duration=3)

        plan_svc.bulk_update_start_day([(t1, 10), (t2, 15)])
        assert plan_svc.get_task(t1).start_day == 10
        assert plan_svc.get_task(t2).start_day == 15

    def test_update_task_actual_dates(self, plan_svc, sample_project):
        """设置实际开始/完成日期后能正确读回。"""
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "任务1", duration=5)

        plan_svc.update_task(tid, actual_start_date="2026-01-05", actual_end_date="2026-01-10")
        task = plan_svc.get_task(tid)
        assert task is not None
        assert task.actual_start_date == "2026-01-05"
        assert task.actual_end_date == "2026-01-10"

    def test_update_task_clear_actual_date(self, plan_svc, sample_project):
        """清空实际日期（设为空字符串）后正确读回。"""
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "任务1", duration=5,
                                   actual_start_date="2026-01-05")

        plan_svc.update_task(tid, actual_start_date="")
        task = plan_svc.get_task(tid)
        assert task is not None
        assert task.actual_start_date == ""


# ═══════════════════════════════════════════════════════════════════
#  UndoManager
# ═══════════════════════════════════════════════════════════════════

class TestUndoManager:
    def test_update_field_undo_redo(self, sample_svc, sample_project):
        """UpdateFieldCommand 的 do/undo/redo 循环。"""
        sid = sample_svc.create("SN-001", project_id=sample_project["id"], status="in_stock")
        repo = sample_svc._repo
        mgr = UndoManager()

        mgr.execute(UpdateFieldCommand(repo, sid, "status", "in_stock", "in_use"))
        assert sample_svc.get(sid).status == "in_use"

        mgr.undo()
        assert sample_svc.get(sid).status == "in_stock"

        mgr.redo()
        assert sample_svc.get(sid).status == "in_use"

    def test_add_entity_undo(self, sample_svc, sample_project):
        """AddEntityCommand 撤销应删除实体。"""
        repo = sample_svc._repo
        mgr = UndoManager()

        mgr.execute(AddEntityCommand(repo, {"sn": "UNDO-SN", "project_id": sample_project["id"]}, "样品"))
        all_samples = sample_svc.list_all()
        assert any(s.sn == "UNDO-SN" for s in all_samples)

        mgr.undo()
        all_samples = sample_svc.list_all()
        assert not any(s.sn == "UNDO-SN" for s in all_samples)

    def test_delete_entity_undo(self, sample_svc, sample_project):
        """DeleteEntityCommand 撤销应恢复实体（新 ID）。"""
        sid = sample_svc.create("RESTORE-SN", project_id=sample_project["id"])
        repo = sample_svc._repo
        mgr = UndoManager()

        mgr.execute(DeleteEntityCommand(repo, sid, "样品"))
        assert sample_svc.get(sid) is None
        assert sample_svc.get_by_sn("RESTORE-SN") is None

        mgr.undo()
        # 注意: 恢复后 ID 不同，用 SN 查询
        restored = sample_svc.get_by_sn("RESTORE-SN")
        assert restored is not None

    def test_max_history(self, sample_svc, sample_project):
        """超过 max_history 后最早的命令被丢弃。"""
        repo = sample_svc._repo
        mgr = UndoManager(max_history=3)

        sids = []
        for i in range(5):
            sids.append(sample_svc.create(f"SN-{i}", project_id=sample_project["id"], status="in_stock"))

        for i, sid in enumerate(sids):
            mgr.execute(UpdateFieldCommand(repo, sid, "status", "in_stock", f"stage_{i}"))

        # 只有最近 3 次可以撤销
        assert mgr.undo_count == 3
        assert mgr.redo_count == 0

    def test_clear(self, sample_svc, sample_project):
        mgr = UndoManager()
        sid = sample_svc.create("SN", project_id=sample_project["id"])
        repo = sample_svc._repo
        mgr.execute(UpdateFieldCommand(repo, sid, "status", "in_stock", "in_use"))
        mgr.clear()
        assert not mgr.can_undo()
        assert not mgr.can_redo()

    def test_batch_schedule_command(self, plan_svc, sample_project):
        """BatchScheduleCommand: 批量移动后撤销恢复。"""
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        t1 = plan_svc.create_task(plid, "T1", duration=5)
        t2 = plan_svc.create_task(plid, "T2", duration=3)

        task_repo = plan_svc._task_repo
        mgr = UndoManager()

        changes = [(t1, 0, 10), (t2, 0, 15)]
        mgr.execute(BatchScheduleCommand(task_repo, changes))

        assert plan_svc.get_task(t1).start_day == 10
        assert plan_svc.get_task(t2).start_day == 15

        mgr.undo()
        assert plan_svc.get_task(t1).start_day == 0
        assert plan_svc.get_task(t2).start_day == 0

        mgr.redo()
        assert plan_svc.get_task(t1).start_day == 10
        assert plan_svc.get_task(t2).start_day == 15
