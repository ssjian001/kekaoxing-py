"""测试计划 Service — 计划/任务 CRUD + 排程。"""

from __future__ import annotations

from src.db.repositories import TestPlanRepository, TestTaskRepository
from src.models.test_plan import TestPlan, TestTask


class TestPlanService:
    """测试计划业务逻辑。"""

    def __init__(
        self,
        plan_repo: TestPlanRepository,
        task_repo: TestTaskRepository,
    ) -> None:
        self._plan_repo = plan_repo
        self._task_repo = task_repo

    # ── 计划 ──

    def create_plan(self, project_id: int, name: str, **kwargs: object) -> int:
        return self._plan_repo.insert(project_id=project_id, name=name, **kwargs)

    def get_plan(self, plan_id: int) -> TestPlan | None:
        return self._plan_repo.get_by_id(plan_id)

    def get_plans_by_project(self, project_id: int) -> list[TestPlan]:
        return self._plan_repo.get_by_project(project_id)

    def update_plan(self, plan_id: int, **kwargs: object) -> None:
        self._plan_repo.update(plan_id, **kwargs)

    def delete_plan(self, plan_id: int) -> None:
        # 先删任务及其子表（test_results/issues），再删计划
        for task in self._task_repo.get_by_plan(plan_id):
            self.delete_task(task.id)
        self._plan_repo.delete(plan_id)

    def list_all_plans(self) -> list[TestPlan]:
        return self._plan_repo.list_all()

    # ── 任务 ──

    def create_task(self, plan_id: int, name: str, **kwargs: object) -> int:
        return self._task_repo.insert(plan_id=plan_id, name=name, **kwargs)

    def get_task(self, task_id: int) -> TestTask | None:
        return self._task_repo.get_by_id(task_id)

    def get_tasks(self, plan_id: int) -> list[TestTask]:
        return self._plan_repo.get_tasks(plan_id)

    def get_task_dependencies(self, task_id: int) -> list[TestTask]:
        return self._task_repo.get_dependencies(task_id)

    def update_task(self, task_id: int, **kwargs: object) -> None:
        self._task_repo.update(task_id, **kwargs)

    def update_task_progress(self, task_id: int, progress: float) -> None:
        status = "completed" if progress >= 100.0 else ("in_progress" if progress > 0 else "pending")
        self._task_repo.update(task_id, progress=progress, status=status)

    def delete_task(self, task_id: int) -> None:
        # 先删子表: test_results → issues(含 fa_records/attachments) → task
        self._task_repo.delete_test_results(task_id)
        self._task_repo.delete_issues_by_task(task_id)
        self._task_repo.delete(task_id)

    def bulk_update_start_day(self, updates: list[tuple[int, int]]) -> None:
        self._task_repo.bulk_update_start_day(updates)

    def task_count(self, plan_id: int) -> int:
        return self._plan_repo.get_task_count(plan_id)
