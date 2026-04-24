"""测试任务 Repository。"""

from __future__ import annotations

import json

import apsw

from src.models.test_plan import TestTask
from src.db.repositories.base import BaseRepository


class TestTaskRepository(BaseRepository):
    """测试任务数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "test_tasks", TestTask)

    def delete_test_results(self, task_id: int) -> None:
        """删除任务的所有测试结果（级联删除子表）。"""
        self._conn.execute(
            "DELETE FROM [test_results] WHERE task_id = ?", (task_id,)
        )

    def delete_issues_by_task(self, task_id: int) -> None:
        """删除关联到任务的 Issue 及其子表（fa_records, issue_attachments）。

        注意：schema 中 fa_records / issue_attachments 的外键没有
        ON DELETE CASCADE，必须手动级联删除子表，否则在
        PRAGMA foreign_keys=ON 下会触发 ConstraintError。
        """
        # 先查出关联的 issue id，逐个级联删除子表
        rows = self._conn.execute(
            "SELECT id FROM [issues] WHERE task_id = ?", (task_id,)
        ).fetchall()
        for (issue_id,) in rows:
            self._conn.execute(
                "DELETE FROM [fa_records] WHERE issue_id = ?", (issue_id,)
            )
            self._conn.execute(
                "DELETE FROM [issue_attachments] WHERE issue_id = ?", (issue_id,)
            )
        self._conn.execute(
            "DELETE FROM [issues] WHERE task_id = ?", (task_id,)
        )

    def get_by_plan(self, plan_id: int) -> list[TestTask]:
        return self.list_all(plan_id=plan_id)

    def get_by_status(self, status: str) -> list[TestTask]:
        return self.list_all(status=status)

    def get_by_technician(self, technician_id: int) -> list[TestTask]:
        return self.list_all(technician_id=technician_id)

    def get_dependencies(self, task_id: int) -> list[TestTask]:
        """获取任务的所有依赖任务。"""
        row = self._conn.execute(
            "SELECT dependencies FROM [test_tasks] WHERE id = ?", (task_id,)
        ).fetchone()
        if not row or not row[0]:
            return []
        try:
            dep_ids = json.loads(row[0])
            if not dep_ids:
                return []
        except (json.JSONDecodeError, TypeError):
            return []
        placeholders = ", ".join(["?"] * len(dep_ids))
        rows = self._conn.execute(
            f"SELECT * FROM [test_tasks] WHERE id IN ({placeholders})", dep_ids
        ).fetchall()
        return self._rows_to_models(rows)

    def update_progress(self, id: int, progress: float) -> None:
        """更新任务进度。"""
        self.update(id, progress=progress)

    def bulk_update_start_day(self, updates: list[tuple[int, int]]) -> None:
        """批量更新任务开始天数 [(task_id, start_day), ...]。"""
        for task_id, start_day in updates:
            self._conn.execute(
                "UPDATE [test_tasks] SET start_day = ? WHERE id = ?",
                (start_day, task_id),
            )
