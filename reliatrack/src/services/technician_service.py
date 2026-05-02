"""技术员 Service — 技术员 CRUD。"""

from __future__ import annotations

from src.db.repositories import TechnicianRepository
from src.db.repositories.test_task_repo import TestTaskRepository
from src.db.repositories.issue_repo import IssueRepository
from src.models.common import Technician


class TechnicianService:
    """技术员业务逻辑。"""

    def __init__(
        self,
        repo: TechnicianRepository,
        test_task_repo: TestTaskRepository | None = None,
        issue_repo: IssueRepository | None = None,
    ) -> None:
        self._repo = repo
        self._test_task_repo = test_task_repo
        self._issue_repo = issue_repo

    def create(self, name: str, **kwargs: object) -> int:
        return self._repo.insert(name=name, **kwargs)

    def get(self, technician_id: int) -> Technician | None:
        return self._repo.get_by_id(technician_id)

    def update(self, technician_id: int, **kwargs: object) -> None:
        self._repo.update(technician_id, **kwargs)

    def delete(self, technician_id: int) -> None:
        """删除技术员，有引用时拒绝删除。"""
        reasons: list[str] = []

        if self._test_task_repo is not None:
            task_count = self._test_task_repo.count_by_technician(technician_id)
            if task_count > 0:
                reasons.append(f"{task_count} 个测试任务")

        if self._issue_repo is not None:
            assignee_count = self._issue_repo.count_by_assignee(technician_id)
            if assignee_count > 0:
                reasons.append(f"{assignee_count} 个 Issue（指派人）")

            analyst_count = self._issue_repo.count_by_analyst(technician_id)
            if analyst_count > 0:
                reasons.append(f"{analyst_count} 条 FA 分析记录")

        if reasons:
            detail = "、".join(reasons)
            raise ValueError(
                f"技术员 #{technician_id} 仍被 {detail} 引用，请先解除分配"
            )

        self._repo.delete(technician_id)

    def list_all(self) -> list[Technician]:
        return self._repo.list_all()
