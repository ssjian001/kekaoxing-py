"""测试任务 Repository。"""

from __future__ import annotations

import json
import logging

import apsw

from src.models.test_plan import TestTask
from src.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


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
        """删除关联到任务的 Issue。

        schema 中 fa_records / issue_attachments 的外键已添加
        ON DELETE CASCADE，删除 issues 后子表自动级联。
        """
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

    def count_by_status(self, **filters) -> dict[str, int]:
        """按状态分组计数。"""
        where = ""
        params: list = []
        if filters.get('project_id'):
            plan_ids = [r[0] for r in self._conn.execute(
                "SELECT id FROM test_plans WHERE project_id = ?", (filters['project_id'],)
            ).fetchall()]
            if plan_ids:
                placeholders = ','.join(['?'] * len(plan_ids))
                where = f"WHERE plan_id IN ({placeholders})"
                params = plan_ids
        sql = f"SELECT status, COUNT(*) FROM [test_tasks] {where} GROUP BY status"
        return dict(self._conn.execute(sql, params).fetchall())

    def count_by_technician(self, technician_id: int) -> int:
        """统计指定技术员的任务数量。"""
        return self.count(technician_id=technician_id)

    def update_progress(self, id: int, progress: float) -> None:
        """更新任务进度。"""
        self.update(id, progress=progress)

    def bulk_update_start_day(self, updates: list[tuple[int, int]]) -> None:
        """批量更新任务开始天数 [(task_id, start_day), ...]。"""
        self.begin_transaction()
        try:
            for task_id, start_day in updates:
                self._conn.execute(
                    "UPDATE [test_tasks] SET start_day = ? WHERE id = ?",
                    (start_day, task_id),
                )
            self.commit()
        except Exception:
            self.rollback()
            logger.exception("bulk_update_start_day failed for %d tasks", len(updates))
            raise

    def delete_by_plan(self, plan_id: int) -> int:
        """删除计划关联的所有测试任务（含 test_results / issues 子表），返回删除行数。"""
        # 先删 test_results
        self._conn.execute(
            "DELETE FROM [test_results] WHERE task_id IN "
            "(SELECT id FROM [test_tasks] WHERE plan_id = ?)", (plan_id,)
        )
        # 删 issues 子表 (fa_records / issue_attachments / capa_records)
        self._conn.execute(
            "DELETE FROM [fa_records] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE task_id IN "
            "(SELECT id FROM [test_tasks] WHERE plan_id = ?))", (plan_id,)
        )
        # 先收集附件文件路径，再删 DB 记录
        attachment_paths = self._conn.execute(
            "SELECT file_path FROM [issue_attachments] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE task_id IN "
            "(SELECT id FROM [test_tasks] WHERE plan_id = ?))", (plan_id,)
        ).fetchall()
        from pathlib import Path
        for (fp,) in attachment_paths:
            try:
                p = Path(fp)
                if p.exists():
                    p.unlink()
            except OSError:
                logger.warning("批量删除附件文件失败: %s", fp)
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE task_id IN "
            "(SELECT id FROM [test_tasks] WHERE plan_id = ?))", (plan_id,)
        )
        self._conn.execute(
            "DELETE FROM [capa_records] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE task_id IN "
            "(SELECT id FROM [test_tasks] WHERE plan_id = ?))", (plan_id,)
        )
        # 删 issues
        self._conn.execute(
            "DELETE FROM [issues] WHERE task_id IN "
            "(SELECT id FROM [test_tasks] WHERE plan_id = ?)", (plan_id,)
        )
        # 删 tasks
        cursor = self._conn.execute(
            "DELETE FROM [test_tasks] WHERE plan_id = ?", (plan_id,)
        )
        return cursor.getrowcount() if hasattr(cursor, "getrowcount") else 0
