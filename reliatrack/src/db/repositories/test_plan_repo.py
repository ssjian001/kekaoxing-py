"""测试计划 Repository。"""

from __future__ import annotations

import apsw

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
        return [TestTask(**dict(zip(col_names, r))) for r in rows]

    def get_task_count(self, plan_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [test_tasks] WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        return row[0] if row else 0
