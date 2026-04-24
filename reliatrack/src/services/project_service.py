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
        # 先删最深层子表，逐级向上
        # 1. 删除关联 issue 的 fa_records + attachments + issues
        for issue in self._issue_repo.get_by_project(project_id):
            self._issue_repo.delete_fa_records(issue.id)
            self._issue_repo.delete_attachments(issue.id)
            self._issue_repo.delete(issue.id)
        # 2. 删除关联 sample 的 transactions + samples
        for sample in self._sample_repo.get_by_project(project_id):
            self._sample_repo.delete_transactions(sample.id)
            self._sample_repo.delete(sample.id)
        # 3. 删除关联 plan 的 tasks(test_results/issues) + plans
        for plan in self._plan_repo.get_by_project(project_id):
            for task in self._task_repo.get_by_plan(plan.id):
                self._task_repo.delete_test_results(task.id)
                self._task_repo.delete_issues_by_task(task.id)
                self._task_repo.delete(task.id)
            self._plan_repo.delete(plan.id)
        self._repo.delete(project_id)

    def list_all(self) -> list[Project]:
        return self._repo.list_all()
