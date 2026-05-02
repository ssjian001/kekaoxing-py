"""测试计划 Repository。"""

from __future__ import annotations

import apsw

from typing import Any, cast

from src.models.test_plan import TestPlan, TestTask
from src.db.repositories.base import BaseRepository


class TestPlanRepository(BaseRepository):
    """测试计划数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "test_plans", TestPlan)

    def get_by_project(self, project_id: int) -> list[TestPlan]:
        return self.list_all(project_id=project_id)

    def get_tasks(self, plan_id: int) -> list[TestTask]:
        """获取计划下所有测试任务。"""
        cols = self._conn.execute(
            "PRAGMA table_info([test_tasks])"
        ).fetchall()
        col_names = [c[1] for c in cols]
        rows = self._conn.execute(
            "SELECT * FROM [test_tasks] WHERE plan_id = ? ORDER BY sort_order, id",
            (plan_id,),
        ).fetchall()
        return [TestTask(**cast(dict[str, Any], dict(zip(col_names, r)))) for r in rows]

    def get_task_count(self, plan_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [test_tasks] WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        return row[0] if row else 0

    def delete_orphan_issues_by_plan(self, plan_id: int) -> None:
        """删除直接引用 plan_id 但无 task_id 的孤立 issue。

        ON DELETE CASCADE 会自动清理 fa_records 和 issue_attachments。
        """
        self._conn.execute(
            "DELETE FROM [issues] WHERE plan_id = ? AND task_id IS NULL",
            (plan_id,),
        )

    def delete_by_project(self, project_id: int) -> int:
        """删除项目关联的所有测试计划（含孤立 issues），返回删除行数。"""
        # 删除直接关联 plan_id 但无 task_id 的孤立 issue 子表
        self._conn.execute(
            "DELETE FROM [fa_records] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE plan_id IN "
            "(SELECT id FROM [test_plans] WHERE project_id = ?) AND task_id IS NULL)",
            (project_id,)
        )
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE plan_id IN "
            "(SELECT id FROM [test_plans] WHERE project_id = ?) AND task_id IS NULL)",
            (project_id,)
        )
        self._conn.execute(
            "DELETE FROM [capa_records] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE plan_id IN "
            "(SELECT id FROM [test_plans] WHERE project_id = ?) AND task_id IS NULL)",
            (project_id,)
        )
        # 删孤立 issues
        self._conn.execute(
            "DELETE FROM [issues] WHERE plan_id IN "
            "(SELECT id FROM [test_plans] WHERE project_id = ?) AND task_id IS NULL",
            (project_id,)
        )
        # 删 plans
        cursor = self._conn.execute(
            "DELETE FROM [test_plans] WHERE project_id = ?", (project_id,)
        )
        return cursor.getrowcount() if hasattr(cursor, "getrowcount") else 0
