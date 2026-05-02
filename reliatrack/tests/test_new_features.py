"""新增功能测试 — 覆盖 P1-6 要求的所有新功能点。

使用真实内存 SQLite 数据库，不 mock。
"""

from __future__ import annotations

import pytest

from src.db.repositories import (
    TechnicianRepository,
    SampleRepository,
    EquipmentRepository,
    IssueRepository,
    TestPlanRepository,
    TestTaskRepository,
    TestResultRepository,
)
from src.services.technician_service import TechnicianService
from src.services.sample_service import SampleService
from src.services.test_plan_service import TestPlanService
from src.models.test_plan import TestTask
from src.models.sample import Sample
from src.models.issue import Issue
from src.models.common import Equipment


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def tech_svc(db_conn):
    """创建 TechnicianService（带 test_task_repo 和 issue_repo 用于引用检查）。"""
    return TechnicianService(
        TechnicianRepository(db_conn),
        TestTaskRepository(db_conn),
        IssueRepository(db_conn),
    )


@pytest.fixture()
def sample_svc(db_conn):
    """创建 SampleService（带 test_result_repo 和 issue_repo 用于引用检查）。"""
    return SampleService(
        SampleRepository(db_conn),
        TestResultRepository(db_conn),
        IssueRepository(db_conn),
    )


@pytest.fixture()
def plan_svc(db_conn):
    return TestPlanService(
        TestPlanRepository(db_conn), TestTaskRepository(db_conn),
        TestResultRepository(db_conn),
    )


@pytest.fixture()
def task_repo(db_conn):
    return TestTaskRepository(db_conn)


@pytest.fixture()
def equip_repo(db_conn):
    return EquipmentRepository(db_conn)


@pytest.fixture()
def issue_repo(db_conn):
    return IssueRepository(db_conn)


@pytest.fixture()
def sample_repo(db_conn):
    return SampleRepository(db_conn)


@pytest.fixture()
def plan_repo(db_conn):
    return TestPlanRepository(db_conn)


# ═══════════════════════════════════════════════════════════════════
#  1. BaseRepository.invalidate_columns_cache()
# ═══════════════════════════════════════════════════════════════════

class TestInvalidateColumnsCache:
    def test_cache_cleared_and_requeried(self, db_conn):
        """验证 invalidate_columns_cache() 后 _columns() 重新查询数据库。"""
        repo = SampleRepository(db_conn)

        # 首次调用缓存列名
        cols1 = repo._columns()
        assert len(cols1) > 0
        assert repo._columns_cache is not None

        # 清除缓存
        repo.invalidate_columns_cache()
        assert repo._columns_cache is None

        # 再次调用应重新查询并缓存
        cols2 = repo._columns()
        assert cols2 == cols1
        assert repo._columns_cache is not None


# ═══════════════════════════════════════════════════════════════════
#  2. TechnicianService.delete() — 引用检查
# ═══════════════════════════════════════════════════════════════════

class TestTechnicianServiceDelete:
    def test_delete_no_references(self, tech_svc, db_conn):
        """无引用时正常删除。"""
        tid = tech_svc.create("无引用技术员", role="测试员")
        tech_svc.delete(tid)
        assert tech_svc.get(tid) is None

    def test_delete_referenced_by_task(self, tech_svc, plan_svc, sample_project, db_conn):
        """被测试任务引用时拒绝删除。"""
        tid = tech_svc.create("任务引用技术员", role="测试员")
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        plan_svc.create_task(plid, "任务1", duration=5, technician_id=tid)

        with pytest.raises(ValueError, match="引用"):
            tech_svc.delete(tid)

    def test_delete_referenced_by_issue(self, tech_svc, sample_project, db_conn):
        """被 Issue（指派人）引用时拒绝删除。"""
        tid = tech_svc.create("Issue引用技术员", role="测试员")
        issue_repo = IssueRepository(db_conn)
        issue_repo.insert(
            title="关联Issue",
            project_id=sample_project["id"],
            assignee_id=tid,
        )

        with pytest.raises(ValueError, match="引用"):
            tech_svc.delete(tid)


# ═══════════════════════════════════════════════════════════════════
#  3. SampleService.delete() — 引用检查
# ═══════════════════════════════════════════════════════════════════

class TestSampleServiceDelete:
    def test_delete_referenced_by_test_result(self, sample_svc, plan_svc, sample_project, db_conn):
        """被 test_results 引用时拒绝删除。"""
        sid = sample_svc.create("SN-REF-001", project_id=sample_project["id"])
        plid = plan_svc.create_plan(sample_project["id"], "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "任务1", duration=5)

        # 插入一条 test_result 引用该样品
        result_repo = TestResultRepository(db_conn)
        result_repo.insert(task_id=tid, sample_id=sid, result="pass")

        with pytest.raises(ValueError, match="引用"):
            sample_svc.delete(sid)


# ═══════════════════════════════════════════════════════════════════
#  4. Model __post_init__ 校验
# ═══════════════════════════════════════════════════════════════════

class TestModelPostInitValidation:
    def test_task_negative_duration(self):
        with pytest.raises(ValueError, match="工期不能为负数"):
            TestTask(duration=-1)

    def test_task_progress_out_of_range(self):
        with pytest.raises(ValueError, match="进度必须在 0-100 之间"):
            TestTask(progress=150)

    def test_task_priority_out_of_range(self):
        with pytest.raises(ValueError, match="优先级必须在 1-5 之间"):
            TestTask(priority=0)

    def test_sample_negative_test_hours(self):
        with pytest.raises(ValueError, match="测试小时数不能为负数"):
            Sample(test_hours=-1)

    def test_issue_occurrence_count_zero(self):
        with pytest.raises(ValueError, match="发生次数必须≥1"):
            Issue(occurrence_count=0)

    def test_issue_priority_out_of_range(self):
        with pytest.raises(ValueError, match="优先级必须在 1-5 之间"):
            Issue(priority=6)

    def test_equipment_calibration_interval_zero(self):
        with pytest.raises(ValueError, match="校准间隔必须≥1个月"):
            Equipment(calibration_interval_months=0)


# ═══════════════════════════════════════════════════════════════════
#  5. TestTaskRepo.count_by_status()
# ═══════════════════════════════════════════════════════════════════

class TestCountByStatus:
    def test_count_by_status_with_project_filter(self, task_repo, plan_svc, sample_project, db_conn):
        """验证按项目筛选 + 状态分组计数。"""
        pid = sample_project["id"]
        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")

        # 创建 3 个不同状态的任务（通过直接 SQL 绕过 status 自动设置逻辑）
        db_conn.execute(
            "INSERT INTO test_tasks (plan_id, name, duration, status) VALUES (?, ?, 5, 'pending')",
            (plid, "T1"),
        )
        db_conn.execute(
            "INSERT INTO test_tasks (plan_id, name, duration, status) VALUES (?, ?, 3, 'pending')",
            (plid, "T2"),
        )
        db_conn.execute(
            "INSERT INTO test_tasks (plan_id, name, duration, status) VALUES (?, ?, 2, 'in_progress')",
            (plid, "T3"),
        )

        result = task_repo.count_by_status(project_id=pid)
        assert result.get("pending") == 2
        assert result.get("in_progress") == 1
        assert "completed" not in result

    def test_count_by_status_no_filter(self, task_repo, plan_svc, sample_project, db_conn):
        """不传 project_id 时统计全表。"""
        pid = sample_project["id"]
        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")
        db_conn.execute(
            "INSERT INTO test_tasks (plan_id, name, duration, status) VALUES (?, ?, 5, 'pending')",
            (plid, "T1"),
        )

        result = task_repo.count_by_status()
        assert result.get("pending", 0) >= 1


# ═══════════════════════════════════════════════════════════════════
#  6. EquipmentRepo.count_calibration_due()
# ═══════════════════════════════════════════════════════════════════

class TestCountCalibrationDue:
    def test_count_due_with_threshold(self, equip_repo, db_conn):
        """验证阈值日期筛选。"""
        # 插入设备：next_calibration_date 在阈值之前 → 应计数
        db_conn.execute(
            "INSERT INTO equipment (name, next_calibration_date) VALUES (?, ?)",
            ("设备-到期", "2026-05-01"),
        )
        # 插入设备：next_calibration_date 在阈值之后 → 不计数
        db_conn.execute(
            "INSERT INTO equipment (name, next_calibration_date) VALUES (?, ?)",
            ("设备-未到期", "2026-12-31"),
        )
        # 插入设备：next_calibration_date 为空 → 不计数
        db_conn.execute(
            "INSERT INTO equipment (name, next_calibration_date) VALUES (?, ?)",
            ("设备-无日期", ""),
        )

        # 阈值日期为 2026-06-01
        count = equip_repo.count_calibration_due("2026-06-01")
        assert count == 1

    def test_count_due_none_match(self, equip_repo, db_conn):
        """所有设备都未到期时返回 0。"""
        db_conn.execute(
            "INSERT INTO equipment (name, next_calibration_date) VALUES (?, ?)",
            ("设备-Future", "2027-01-01"),
        )
        count = equip_repo.count_calibration_due("2026-06-01")
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
#  7. IssueRepo / SampleRepo / TestPlanRepo.delete_by_project()
# ═══════════════════════════════════════════════════════════════════

class TestDeleteByProject:
    def test_issue_delete_by_project(self, issue_repo, sample_project, db_conn):
        """验证 IssueRepo.delete_by_project 批量删除。"""
        pid = sample_project["id"]
        # 插入多条 issue
        iid1 = issue_repo.insert(title="Issue1", project_id=pid)
        iid2 = issue_repo.insert(title="Issue2", project_id=pid)

        # 为 iid1 添加 FA 记录
        issue_repo.add_fa_record(iid1, step_no=1, method="X光", step_title="步骤1")

        issue_repo.delete_by_project(pid)
        # 验证数据已被删除（apsw cursor 无 getrowcount，返回值可能为 0）
        assert issue_repo.get_by_id(iid1) is None
        assert issue_repo.get_by_id(iid2) is None
        # 验证 FA 记录也已级联删除
        assert len(issue_repo.get_fa_records(iid1)) == 0

    def test_sample_delete_by_project(self, sample_repo, sample_project, db_conn):
        """验证 SampleRepo.delete_by_project 批量删除。"""
        pid = sample_project["id"]
        sid1 = sample_repo.insert(sn="SN-BATCH-001", project_id=pid)
        sid2 = sample_repo.insert(sn="SN-BATCH-002", project_id=pid)

        # 添加出入库记录
        sample_repo.add_transaction(sid1, "check_out")

        sample_repo.delete_by_project(pid)
        # 验证数据已被删除（apsw cursor 无 getrowcount，返回值可能为 0）
        assert sample_repo.get_by_id(sid1) is None
        assert sample_repo.get_by_id(sid2) is None

    def test_plan_delete_by_project(self, plan_repo, sample_project, db_conn):
        """验证 TestPlanRepo.delete_by_project 批量删除。"""
        pid = sample_project["id"]
        plid1 = plan_repo.insert(name="计划A", project_id=pid, start_date="2026-01-01")
        plid2 = plan_repo.insert(name="计划B", project_id=pid, start_date="2026-02-01")

        plan_repo.delete_by_project(pid)
        # 验证数据已被删除（apsw cursor 无 getrowcount，返回值可能为 0）
        assert plan_repo.get_by_id(plid1) is None
        assert plan_repo.get_by_id(plid2) is None

    def test_delete_by_project_does_not_affect_other_projects(
        self, issue_repo, sample_repo, plan_repo, db_conn
    ):
        """删除项目A的数据不影响项目B。"""
        # 创建两个项目
        db_conn.execute(
            "INSERT INTO projects (name) VALUES ('项目A')"
        )
        db_conn.execute(
            "INSERT INTO projects (name) VALUES ('项目B')"
        )
        pid_a = db_conn.execute("SELECT id FROM projects WHERE name = '项目A'").fetchone()[0]
        pid_b = db_conn.execute("SELECT id FROM projects WHERE name = '项目B'").fetchone()[0]

        # 各插入一条 issue
        iid_a = issue_repo.insert(title="A-Issue", project_id=pid_a)
        iid_b = issue_repo.insert(title="B-Issue", project_id=pid_b)

        # 删除项目A的 issues
        issue_repo.delete_by_project(pid_a)
        assert issue_repo.get_by_id(iid_a) is None
        assert issue_repo.get_by_id(iid_b) is not None
