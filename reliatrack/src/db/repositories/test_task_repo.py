"""测试任务 Repository。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import apsw

from src.models.test_plan import TestTask
from src.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class TestTaskRepository(BaseRepository):
    """测试任务数据访问。"""

    # 显式列名列表（与 schema 顺序一致，用于 SELECT 和映射）。
    # 始终传入 _rows_to_models(rows, cols=_TASK_COLS) 以保证列序一致；
    # 不能依赖 PRAGMA table_info 序——ALTER TABLE ADD COLUMN 会将新列加到物理末尾。
    _TASK_COLS = [
        "id", "plan_id", "name", "category", "test_standard", "technician_id",
        "equipment_id", "sample_ids", "duration", "start_day", "progress", "status",
        "priority", "environment", "log_file", "dependencies", "notes", "temperature",
        "humidity", "accept_criteria", "actual_start_date", "actual_end_date",
        "sort_order", "created_at", "updated_at",
    ]

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

    def get_by_project(self, project_id: int) -> list[TestTask]:
        """按项目 ID 获取任务（通过 plan_id JOIN）。"""
        plan_ids = [r[0] for r in self._conn.execute(
            "SELECT id FROM test_plans WHERE project_id = ?", (project_id,)
        ).fetchall()]
        if not plan_ids:
            return []
        placeholders = ','.join(['?'] * len(plan_ids))
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        rows = self._conn.execute(
            f"SELECT {cols_sql} FROM [{self._table}] WHERE plan_id IN ({placeholders}) ORDER BY id",
            plan_ids,
        ).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

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
            f"SELECT {', '.join(self._TASK_COLS)} FROM [test_tasks] WHERE id IN ({placeholders})", dep_ids
        ).fetchall()
        return self._rows_to_models(rows, cols=self._TASK_COLS)

    def count_by_status(self, **filters) -> dict[str, int]:
        """按状态分组计数。支持 project_id 和 plan_id 筛选。"""
        where = ""
        params: list = []
        # plan_id 直接过滤（优先级高于 project_id）
        if filters.get('plan_id'):
            where = "WHERE plan_id = ?"
            params = [filters['plan_id']]
        elif filters.get('project_id'):
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
        with self.transaction():
            for task_id, start_day in updates:
                self._conn.execute(
                    "UPDATE [test_tasks] SET start_day = ? WHERE id = ?",
                    (start_day, task_id),
                )

    def delete_by_plan(self, plan_id: int) -> int:
        """删除计划关联的所有测试任务，返回删除行数。

        附件文件清理（磁盘 .unlink）需手动执行，其余子表依赖 FK CASCADE。
        issues 及其子表（fa_records, capa_records, issue_attachments）由
        FK ON DELETE CASCADE 自动级联清理。
        """
        # 收集附件文件路径（磁盘清理，CASCADE 不处理文件系统）
        attachment_paths = self._conn.execute(
            "SELECT file_path FROM [issue_attachments] ia "
            "JOIN [issues] i ON ia.issue_id = i.id "
            "JOIN [test_tasks] tt ON i.task_id = tt.id "
            "WHERE tt.plan_id = ?",
            (plan_id,),
        ).fetchall()
        from src.db.repositories.issue_repo import IssueRepository
        for (fp,) in attachment_paths:
            IssueRepository._remove_disk_file(fp)
        # FK CASCADE: test_tasks → issues → fa_records/capa_records/issue_attachments
        cursor = self._conn.execute(
            "DELETE FROM [test_tasks] WHERE plan_id = ?", (plan_id,),
        )
        return cursor.getrowcount() if hasattr(cursor, "getrowcount") else 0
