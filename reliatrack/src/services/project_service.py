"""项目 Service — 项目 CRUD + 统计。"""

from __future__ import annotations

import logging

from src.db.repositories import (
    ProjectRepository, TestPlanRepository, SampleRepository,
    IssueRepository, TestTaskRepository,
)
from src.models.project import Project

logger = logging.getLogger(__name__)


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
        """按 ID 查询。"""
        return self._repo.get_by_id(project_id)

    def update(self, project_id: int, **kwargs: object) -> None:
        self._repo.update(project_id, **kwargs)

    def delete(self, project_id: int) -> None:
        """删除项目及所有关联数据（批量 SQL，无 N+1）。"""
        with self._repo.transaction():
            # 0. 解关联跨项目引用（审计 #7）：其他项目的 Issue 若引用本项目
            #    样品/任务，直接删样品会经 FK CASCADE 物理清除它们（绕过软删
            #    保护）。先置 NULL 保留这些 Issue 本体。
            self._issue_repo.detach_references_of_project(project_id)
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

    def cascade_stats(self, project_id: int) -> dict[str, int]:
        """返回项目级联删除影响的关联记录数。"""
        conn = self._repo.conn
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM test_plans WHERE project_id = ?", (project_id,)
        )
        plans = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM test_tasks WHERE plan_id IN "
            "(SELECT id FROM test_plans WHERE project_id = ?)",
            (project_id,),
        )
        tasks = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM samples WHERE project_id = ?", (project_id,)
        )
        samples = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM issues WHERE project_id = ?", (project_id,)
        )
        issues = cur.fetchone()[0]
        return {"plans": plans, "tasks": tasks, "samples": samples, "issues": issues}

    def list_all(self) -> list[Project]:
        return self._repo.list_all()
