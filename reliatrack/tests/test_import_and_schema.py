"""本会话新增功能测试 — 覆盖以下特性：

1. import_tasks_from_plan() — 从其他计划复制任务
2. table_exists() — BaseRepository 表存在检查
3. _validate_schema_integrity() — schema 完整性验证与自动重建
"""

from __future__ import annotations

import pytest
import apsw

from src.db.repositories import (
    TestPlanRepository,
    TestTaskRepository,
    TestResultRepository,
    ProjectRepository,
)
from src.services.test_plan_service import TestPlanService
from src.db.schema import init_schema


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def plan_svc(db_conn):
    return TestPlanService(
        TestPlanRepository(db_conn), TestTaskRepository(db_conn),
        TestResultRepository(db_conn),
    )


@pytest.fixture()
def plan_repo(db_conn):
    return TestPlanRepository(db_conn)


@pytest.fixture()
def task_repo(db_conn):
    return TestTaskRepository(db_conn)


# ═══════════════════════════════════════════════════════════════════
#  1. import_tasks_from_plan()
# ═══════════════════════════════════════════════════════════════════

class TestImportTasksFromPlan:
    """测试从其他计划导入任务功能。"""

    def test_import_copies_task_template_fields(self, plan_svc, sample_project):
        """导入时只复制模板字段，不复制运行时数据。"""
        pid = sample_project["id"]
        # 创建来源计划和任务
        src_plan = plan_svc.create_plan(pid, "来源计划")
        plan_svc.create_task(
            src_plan, "高温老化", category="环境试验",
            test_standard="MIL-STD-810H", duration=10,
            priority=2, temperature="85°C", humidity="85%RH",
            accept_criteria="外观无变化", notes="参考标准第5章",
        )

        # 创建目标计划
        dst_plan = plan_svc.create_plan(pid, "目标计划")

        # 获取来源任务并导入
        src_tasks = plan_svc.get_tasks(src_plan)
        assert len(src_tasks) == 1

        count = plan_svc.import_tasks_from_plan(dst_plan, src_tasks)
        assert count == 1

        # 验证目标计划有任务
        dst_tasks = plan_svc.get_tasks(dst_plan)
        assert len(dst_tasks) == 1

        t = dst_tasks[0]
        assert t.name == "高温老化"
        assert t.category == "环境试验"
        assert t.test_standard == "MIL-STD-810H"
        assert t.duration == 10
        assert t.priority == 2
        assert t.temperature == "85°C"
        assert t.humidity == "85%RH"
        assert t.accept_criteria == "外观无变化"
        assert t.notes == "参考标准第5章"
        # plan_id 指向目标
        assert t.plan_id == dst_plan
        # 运行时字段重置
        assert t.progress == 0.0
        assert t.status == "pending"
        assert t.actual_start_date == ""
        assert t.actual_end_date == ""

    def test_import_multiple_tasks(self, plan_svc, sample_project):
        """导入多个任务。"""
        pid = sample_project["id"]
        src_plan = plan_svc.create_plan(pid, "来源")
        plan_svc.create_task(src_plan, "任务A", duration=5)
        plan_svc.create_task(src_plan, "任务B", duration=3)
        plan_svc.create_task(src_plan, "任务C", duration=7)

        dst_plan = plan_svc.create_plan(pid, "目标")

        src_tasks = plan_svc.get_tasks(src_plan)
        count = plan_svc.import_tasks_from_plan(dst_plan, src_tasks)
        assert count == 3
        assert len(plan_svc.get_tasks(dst_plan)) == 3

    def test_import_empty_list_returns_zero(self, plan_svc, sample_project):
        """空任务列表返回 0。"""
        pid = sample_project["id"]
        dst_plan = plan_svc.create_plan(pid, "目标")
        count = plan_svc.import_tasks_from_plan(dst_plan, [])
        assert count == 0

    def test_import_preserves_sort_order(self, plan_svc, sample_project):
        """导入任务的 sort_order 接续已有任务。"""
        pid = sample_project["id"]
        dst_plan = plan_svc.create_plan(pid, "目标")
        # 先创建一个已有任务，sort_order=0（默认）
        plan_svc.create_task(dst_plan, "已有任务", duration=1, sort_order=10)

        src_plan = plan_svc.create_plan(pid, "来源")
        plan_svc.create_task(src_plan, "新任务A", duration=2)
        plan_svc.create_task(src_plan, "新任务B", duration=3)

        src_tasks = plan_svc.get_tasks(src_plan)
        plan_svc.import_tasks_from_plan(dst_plan, src_tasks)

        dst_tasks = plan_svc.get_tasks(dst_plan)
        # 已有任务 sort_order=10，新任务从 11 开始
        new_tasks = [t for t in dst_tasks if t.name.startswith("新任务")]
        assert len(new_tasks) == 2
        assert new_tasks[0].sort_order == 11
        assert new_tasks[1].sort_order == 12

    def test_import_does_not_affect_source(self, plan_svc, sample_project):
        """导入不影响来源计划的任务。"""
        pid = sample_project["id"]
        src_plan = plan_svc.create_plan(pid, "来源")
        plan_svc.create_task(src_plan, "任务X", duration=5)

        dst_plan = plan_svc.create_plan(pid, "目标")
        src_tasks = plan_svc.get_tasks(src_plan)
        plan_svc.import_tasks_from_plan(dst_plan, src_tasks)

        # 来源计划仍只有 1 个任务
        assert len(plan_svc.get_tasks(src_plan)) == 1

    def test_import_across_plans_in_same_project(self, plan_svc, sample_project):
        """同项目下两个计划之间导入。"""
        pid = sample_project["id"]
        plan_a = plan_svc.create_plan(pid, "计划A")
        plan_b = plan_svc.create_plan(pid, "计划B")

        plan_svc.create_task(plan_a, "高温", category="环境", duration=5)
        plan_svc.create_task(plan_a, "振动", category="机械", duration=3)

        # 从 A 导入到 B
        tasks_a = plan_svc.get_tasks(plan_a)
        count = plan_svc.import_tasks_from_plan(plan_b, tasks_a)
        assert count == 2

        tasks_b = plan_svc.get_tasks(plan_b)
        assert len(tasks_b) == 2
        names = {t.name for t in tasks_b}
        assert names == {"高温", "振动"}

        # A 不受影响
        assert len(plan_svc.get_tasks(plan_a)) == 2


# ═══════════════════════════════════════════════════════════════════
#  2. table_exists()
# ═══════════════════════════════════════════════════════════════════

class TestTableExists:
    """测试 BaseRepository.table_exists() 方法。"""

    def test_existing_table(self, db_conn):
        """已初始化的表返回 True。"""
        repo = ProjectRepository(db_conn)
        assert repo.table_exists() is True

    def test_nonexistent_table(self, db_conn):
        """不存在的表返回 False。"""
        # 直接创建一个指向不存在表的 repo
        from src.db.repositories.base import BaseRepository
        from src.models.project import Project
        repo = BaseRepository(db_conn, "nonexistent_table_xyz", Project)
        assert repo.table_exists() is False

    def test_after_drop(self, db_conn):
        """删除表后返回 False。"""
        repo = ProjectRepository(db_conn)
        assert repo.table_exists() is True
        db_conn.execute("DROP TABLE projects")
        repo.invalidate_columns_cache()
        assert repo.table_exists() is False


# ═══════════════════════════════════════════════════════════════════
#  3. _validate_schema_integrity()
# ═══════════════════════════════════════════════════════════════════

class TestSchemaIntegrityValidation:
    """测试 schema 完整性自动验证与重建。"""

    def test_init_schema_creates_all_tables(self, db_conn):
        """init_schema 后所有核心表存在。"""
        from src.db.schema import _validate_schema_integrity
        # 正常初始化后不应抛异常
        _validate_schema_integrity(db_conn)

    def test_rebuild_on_missing_knowledge_table(self, db_conn):
        """非 FK 依赖的核心表缺失时自动重建。"""
        from src.db.schema import _validate_schema_integrity

        # knowledge_entries 无外键依赖，可安全删除
        db_conn.execute("DROP TABLE knowledge_entries")

        # 重建应成功
        _validate_schema_integrity(db_conn)

        # 验证表已恢复
        cols = db_conn.execute("PRAGMA table_info(knowledge_entries)").fetchall()
        assert len(cols) > 0

    def test_no_rebuild_when_all_tables_exist(self, db_conn):
        """表完整时不做多余操作（幂等性）。"""
        from src.db.schema import _validate_schema_integrity

        # 插入数据验证不会被清除
        db_conn.execute("INSERT INTO projects (name) VALUES ('测试项目')")

        _validate_schema_integrity(db_conn)

        # 数据仍在
        row = db_conn.execute(
            "SELECT name FROM projects WHERE name = '测试项目'"
        ).fetchone()
        assert row is not None
        assert row[0] == "测试项目"
