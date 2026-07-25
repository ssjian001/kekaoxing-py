"""测试计划 Repository。"""

from __future__ import annotations

import apsw

from typing import Any, cast

from src.models.test_plan import TestPlan, TestTask
from src.db.repositories.base import BaseRepository


class TestPlanRepository(BaseRepository):
    """测试计划数据访问。"""

    __test__ = False

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "test_plans", TestPlan)

    def get_by_project(self, project_id: int) -> list[TestPlan]:
        return self.list_all(project_id=project_id)

    def get_active_by_project(self, project_id: int) -> list[TestPlan]:
        """获取项目下非归档的计划（SQL 层过滤）。"""
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        rows = self._conn.execute(
            f"SELECT {cols_sql} FROM [test_plans] "
            f"WHERE project_id = ? AND status != ? ORDER BY id",
            (project_id, "archived"),
        ).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def get_tasks(self, plan_id: int) -> list[TestTask]:
        """获取计划下所有测试任务。"""
        col_names = (
            "id", "plan_id", "name", "category", "test_standard", "technician_id",
            "equipment_id", "sample_ids", "duration", "start_day", "progress",
            "status", "priority", "environment", "log_file", "dependencies",
            "notes", "temperature", "humidity", "accept_criteria",
            "actual_start_date", "actual_end_date", "sort_order",
            "manual_scheduled",
            "created_at", "updated_at",
        )
        cols_sql = ", ".join(col_names)
        rows = self._conn.execute(
            f"SELECT {cols_sql} FROM [test_tasks] WHERE plan_id = ? ORDER BY sort_order, id",
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
        """删除项目关联的所有测试计划，CASCADE 自动清理下游数据。

        自动级联清理（PRAGMA foreign_keys=ON 时）：
          - test_plans → test_tasks → test_results
          - issues → fa_records / issue_attachments / capa_records
          - 直接引用 plan_id 但无 task_id 的孤立 issues

        返回删除的测试计划数量。
        """
        cursor = self._conn.execute(
            "DELETE FROM [test_plans] WHERE project_id = ?", (project_id,)
        )
        return cursor.getrowcount() if hasattr(cursor, "getrowcount") else 0
