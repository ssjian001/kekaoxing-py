"""项目 Service — 项目 CRUD + 统计。"""

from __future__ import annotations

from src.db.repositories import (
    ProjectRepository, TestPlanRepository, SampleRepository,
    IssueRepository, TestTaskRepository,
)
from src.models.project import Project


class ProjectService:
    """项目业务逻辑。"""

    def __init__(
        self,
        repo: ProjectRepository,
        plan_repo: TestPlanRepository,
        task_repo: TestTaskRepository,
        sample_repo: SampleRepository,
        issue_repo: IssueRepository,
    ) -> None:
        self._repo = repo
        self._plan_repo = plan_repo
        self._task_repo = task_repo
        self._sample_repo = sample_repo
        self._issue_repo = issue_repo

    def create(self, name: str, **kwargs: object) -> int:
        return self._repo.insert(name=name, **kwargs)

    def get(self, project_id: int) -> Project | None:
        return self._repo.get_by_id(project_id)

    def get_active(self) -> list[Project]:
        return self._repo.get_active()

    def get_by_name(self, name: str) -> Project | None:
        return self._repo.get_by_name(name)

    def update(self, project_id: int, **kwargs: object) -> None:
        self._repo.update(project_id, **kwargs)

    def delete(self, project_id: int) -> None:
        """删除项目及所有关联数据（批量 SQL，无 N+1）。"""
        with self._repo.transaction():
            # 1. 批量删除 issues（含 fa_records / attachments / capa_records）
            self._issue_repo.delete_by_project(project_id)
            # 2. 批量删除 samples（含 transactions）
            self._sample_repo.delete_by_project(project_id)
            # 3. 批量删除 plans 下的 tasks（含 test_results / issues 子表）
            for plan in self._plan_repo.get_by_project(project_id):
                if plan.id is not None:
                    self._task_repo.delete_by_plan(plan.id)
            # 4. 批量删除 plans（含孤立 issues 及其子表）
            self._plan_repo.delete_by_project(project_id)
            # 5. 删除项目本身
            self._repo.delete(project_id)

    def list_all(self) -> list[Project]:
        return self._repo.list_all()
