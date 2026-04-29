"""测试结果 Repository — CRUD 操作。"""

from __future__ import annotations

from typing import Optional

import apsw

from src.models.test_plan import TestResult
from src.db.repositories.base import BaseRepository


class TestResultRepository(BaseRepository):
    """测试结果数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "test_results", TestResult)

    def get_by_task(self, task_id: int) -> list[TestResult]:
        """获取任务的所有测试结果。"""
        rows = self._conn.execute(
            "SELECT * FROM [test_results] WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
        return self._rows_to_models(rows)

    def get_by_sample(self, sample_id: int) -> list[TestResult]:
        """获取样品的所有测试结果。"""
        rows = self._conn.execute(
            "SELECT * FROM [test_results] WHERE sample_id = ? ORDER BY test_date DESC",
            (sample_id,),
        ).fetchall()
        return self._rows_to_models(rows)

    def get_task_result_for_sample(self, task_id: int, sample_id: int) -> Optional[TestResult]:
        """获取某任务+样品的测试结果（一对一）。"""
        row = self._conn.execute(
            "SELECT * FROM [test_results] WHERE task_id = ? AND sample_id = ?",
            (task_id, sample_id),
        ).fetchone()
        return self._row_to_model(row) if row else None

    def upsert(self, task_id: int, sample_id: int, **kwargs: object) -> int:
        """插入或更新某任务+样品的测试结果，返回 id。"""
        existing = self.get_task_result_for_sample(task_id, sample_id)
        if existing and existing.id is not None:
            self.update(existing.id, **kwargs)
            return existing.id
        return self.insert(task_id=task_id, sample_id=sample_id, **kwargs)

    def delete_by_task(self, task_id: int) -> int:
        """删除任务的所有测试结果，返回删除行数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [test_results] WHERE task_id = ?", (task_id,)
        ).fetchone()
        count = row[0] if row else 0
        self._conn.execute("DELETE FROM [test_results] WHERE task_id = ?", (task_id,))
        return count

    def count_by_task(self, task_id: int) -> int:
        """统计任务的测试结果数量。"""
        return self.count(task_id=task_id)
