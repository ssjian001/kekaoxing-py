"""测试计划 Service — 计划/任务 CRUD + 排程。"""

from __future__ import annotations

import logging

from src.db.repositories import TestPlanRepository, TestTaskRepository, TestResultRepository
from src.models.test_plan import TestPlan, TestTask, TestResult

logger = logging.getLogger(__name__)


class TestPlanService:
    """测试计划业务逻辑。"""

    __test__ = False

    def __init__(
        self,
        plan_repo: TestPlanRepository,
        task_repo: TestTaskRepository,
        result_repo: TestResultRepository,
    ) -> None:
        self._plan_repo = plan_repo
        self._task_repo = task_repo
        self._result_repo = result_repo

    # ── 计划 ──

    def create_plan(self, project_id: int, name: str, **kwargs: object) -> int:
        return self._plan_repo.insert(project_id=project_id, name=name, **kwargs)

    def get_plan(self, plan_id: int) -> TestPlan | None:
        return self._plan_repo.get_by_id(plan_id)

    def get_plans_by_project(self, project_id: int) -> list[TestPlan]:
        return self._plan_repo.get_by_project(project_id)

    def get_active_plans_by_project(self, project_id: int) -> list[TestPlan]:
        """获取项目下非归档的计划（SQL 层过滤，不含 archived）。"""
        return self._plan_repo.get_active_by_project(project_id)

    def get_archived_plans_by_project(self, project_id: int) -> list[TestPlan]:
        """获取项目下已归档的计划（SQL 层过滤，仅 archived）。"""
        return self._plan_repo.get_archived_by_project(project_id)

    def update_plan(self, plan_id: int, **kwargs: object) -> None:
        self._plan_repo.update(plan_id, **kwargs)
    def list_all_plans(self) -> list[TestPlan]:
        return self._plan_repo.list_all()

    def list_all_active_plans(self) -> list[TestPlan]:
        """获取所有非归档的计划。"""
        return [p for p in self._plan_repo.list_all()
                if p.status != "archived"]

    # ── 任务 ──

    def create_task(self, plan_id: int, name: str, **kwargs: object) -> int:
        return self._task_repo.insert(plan_id=plan_id, name=name, **kwargs)

    def get_task(self, task_id: int) -> TestTask | None:
        return self._task_repo.get_by_id(task_id)

    def get_tasks(self, plan_id: int) -> list[TestTask]:
        return self._plan_repo.get_tasks(plan_id)

    def get_tasks_by_project(self, project_id: int, *,
                             exclude_archived: bool = False) -> list[TestTask]:
        """按项目获取任务（SQL 过滤，非全表加载）。

        Args:
            exclude_archived: 为 True 时排除已归档计划的任务。
        """
        tasks = self._task_repo.get_by_project(project_id)
        if exclude_archived:
            archived_plan_ids: set[int] = set()
            for p in self._plan_repo.get_by_project(project_id):
                if p.status == "archived" and p.id is not None:
                    archived_plan_ids.add(p.id)
            if archived_plan_ids:
                tasks = [t for t in tasks if t.plan_id not in archived_plan_ids]
        return tasks
    def update_task(self, task_id: int, **kwargs: object) -> None:
        self._task_repo.update(task_id, **kwargs)
    def delete_task(self, task_id: int) -> None:
        with self._task_repo.transaction():
            # 先删子表: test_results
            self._task_repo.delete_test_results(task_id)
            # Issue 解除关联而非删除（保护已验证/关闭的 Issue 历史记录）
            self._task_repo.detach_issues_by_task(task_id)
            self._task_repo.delete(task_id)

    def bulk_update_start_day(self, updates: list[tuple[int, int]]) -> None:
        self._task_repo.bulk_update_start_day(updates)

    def transaction(self):
        """公共事务上下文（供 handler 使用，替代越层访问 _result_repo.transaction）。"""
        return self._result_repo.transaction()

    def task_repo(self):
        """任务 repo 访问器（undo Command 需要，审计 B4 收编避免越层私有访问）。"""
        return self._task_repo

    def task_count(self, plan_id: int) -> int:
        return self._plan_repo.get_task_count(plan_id)

    # ── 测试结果 ──

    def get_task_results(self, task_id: int) -> list[TestResult]:
        """获取任务的所有测试结果。"""
        return self._result_repo.get_by_task(task_id)

    def get_pass_counts_by_tasks(self, task_ids: list[int]) -> dict[int, tuple[int, int]]:
        """批量获取多个任务的通过率 {task_id: (pass_count, total)}。"""
        return self._result_repo.get_pass_counts_by_tasks(task_ids)

    def get_all_results_by_tasks(self, task_ids: list[int]) -> list[TestResult]:
        """批量获取多个任务的全部测试结果（含 sample_id）。"""
        return self._result_repo.get_all_by_tasks(task_ids)

    def save_result(
        self,
        task_id: int,
        sample_id: int | None,
        result: str,
        test_date: str = "",
        measured_value: str = "",
        notes: str = "",
        tester_id: int | None = None,
        environment: str = "{}",
    ) -> int:
        """保存/更新测试结果，返回 id。"""
        return self._result_repo.upsert(
            task_id=task_id,
            sample_id=sample_id,
            result=result,
            test_date=test_date,
            measured_value=measured_value,
            notes=notes,
            tester_id=tester_id,
            environment=environment,
        )

    def delete_result(self, result_id: int) -> None:
        """删除测试结果。"""
        self._result_repo.delete(result_id)
    def import_tasks_from_plan(self, target_plan_id: int, source_tasks: list[TestTask]) -> int:
        """从其他计划复制任务到目标计划。只复制任务模板字段，不复制运行时数据。

        Returns:
            导入的任务数。
        """
        if not source_tasks:
            return 0
        existing = self.get_tasks(target_plan_id)
        max_sort = max((t.sort_order for t in existing), default=0)

        with self._task_repo.transaction():
            for i, t in enumerate(source_tasks, 1):
                self._task_repo.insert(
                    plan_id=target_plan_id,
                    name=t.name,
                    category=t.category,
                    test_standard=t.test_standard,
                    duration=t.duration,
                    priority=t.priority,
                    temperature=t.temperature,
                    humidity=t.humidity,
                    accept_criteria=t.accept_criteria,
                    notes=t.notes,
                    environment=t.environment,
                    sort_order=max_sort + i,
                )
        return len(source_tasks)
