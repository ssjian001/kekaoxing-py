"""测试计划 Repository。"""

from __future__ import annotations

import apsw

from typing import Any, cast

from src.models.test_plan import TestPlan, TestTask
from src.db.schema import TASK_COLUMNS
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

    def get_archived_by_project(self, project_id: int) -> list[TestPlan]:
        """获取项目下已归档的计划（SQL 层过滤）。"""
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        rows = self._conn.execute(
            f"SELECT {cols_sql} FROM [test_plans] "
            f"WHERE project_id = ? AND status = ? ORDER BY id",
            (project_id, "archived"),
        ).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def get_tasks(self, plan_id: int) -> list[TestTask]:
        """获取计划下所有测试任务。"""
        # 审计 2026-10-25：列清单收编为 schema.TASK_COLUMNS 单一来源
        col_names = TASK_COLUMNS
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

    def delete_by_project(self, project_id: int) -> int:
        """删除项目关联的所有测试计划，CASCADE 自动清理下游数据。

        自动级联清理（PRAGMA foreign_keys=ON 时）：
          - test_plans → test_tasks → test_results
          - issues → fa_records / issue_attachments / capa_records
          - 直接引用 plan_id 但无 task_id 的孤立 issues

        审计 2026-10-25：级联删除的 issue_attachments 磁盘文件原先无人
        收集（对照 delete_by_plan 有 JOIN 收集 + 延后清理），孤儿附件会
        永久残留。现删除前先收集，事务成功后统一清理。

        返回删除的测试计划数量。
        """
        # 收集范围：挂在该项目 plans 上（经 tasks 或直接 plan_id）的
        # 全部 Issue 附件，含 CASCADE 即将删掉的孤立 Issue
        attachment_paths = self._conn.execute(
            "SELECT DISTINCT ia.file_path FROM [issue_attachments] ia "
            "JOIN [issues] i ON ia.issue_id = i.id "
            "LEFT JOIN [test_tasks] tt ON i.task_id = tt.id "
            "LEFT JOIN [test_plans] tp ON i.plan_id = tp.id "
            "WHERE tp.project_id = ? OR tt.plan_id IN "
            "  (SELECT id FROM [test_plans] WHERE project_id = ?)",
            (project_id, project_id),
        ).fetchall()
        from src.db.repositories.issue_repo import defer_disk_deletions
        # 先执行 DB 删除（事务内），成功后再清理磁盘文件
        with self.transaction():
            cursor = self._conn.execute(
                "DELETE FROM [test_plans] WHERE project_id = ?", (project_id,)
            )
            row = self._conn.execute("SELECT changes()").fetchone()
        defer_disk_deletions(
            self._conn, [fp for (fp,) in attachment_paths]
        )
        return row[0] if row else 0
