"""Issue / FA Repository。"""

from __future__ import annotations

import apsw

from typing import Any, cast

from src.models.issue import Issue, FARecord, IssueAttachment, CAPARecord
from src.db.repositories.base import BaseRepository


class IssueRepository(BaseRepository):
    """Issue 数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "issues", Issue)

    def count_by_assignee(self, assignee_id: int) -> int:
        """统计指定指派人（技术员）的 Issue 数量。"""
        return self.count(assignee_id=assignee_id)

    def count_by_sample(self, sample_id: int) -> int:
        """统计指定样品的 Issue 数量。"""
        return self.count(sample_id=sample_id)

    def count_by_analyst(self, analyst_id: int) -> int:
        """统计 fa_records 中指定分析人的记录数量。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [fa_records] WHERE analyst_id = ?",
            (analyst_id,),
        ).fetchone()
        return row[0] if row else 0

    def count_by_severity(self, project_id: int | None = None) -> dict[str, int]:
        """按严重度分组计数，可选按 project_id 过滤。"""
        if project_id:
            sql = (
                "SELECT severity, COUNT(*) FROM [issues] "
                "WHERE task_id IN (SELECT id FROM [test_tasks] "
                "WHERE plan_id IN (SELECT id FROM [test_plans] WHERE project_id = ?)) "
                "GROUP BY severity"
            )
            return dict(self._conn.execute(sql, (project_id,)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT severity, COUNT(*) FROM [issues] GROUP BY severity"
            ).fetchall()
        )

    def count_by_status(self, project_id: int | None = None) -> dict[str, int]:
        """按状态分组计数，可选按 project_id 过滤。"""
        if project_id:
            sql = (
                "SELECT status, COUNT(*) FROM [issues] "
                "WHERE task_id IN (SELECT id FROM [test_tasks] "
                "WHERE plan_id IN (SELECT id FROM [test_plans] WHERE project_id = ?)) "
                "GROUP BY status"
            )
            return dict(self._conn.execute(sql, (project_id,)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT status, COUNT(*) FROM [issues] GROUP BY status"
            ).fetchall()
        )

    def get_by_project(self, project_id: int) -> list[Issue]:
        return self.list_all(project_id=project_id)

    def get_by_status(self, status: str) -> list[Issue]:
        return self.list_all(status=status)

    def get_by_task(self, task_id: int) -> list[Issue]:
        return self.list_all(task_id=task_id)

    def get_by_sample(self, sample_id: int) -> list[Issue]:
        return self.list_all(sample_id=sample_id)

    def update_status(self, id: int, status: str) -> None:
        """更新 Issue 状态。"""
        self.update(id, status=status)

    # ── FA 记录 ──

    def get_fa_records(self, issue_id: int) -> list[FARecord]:
        """获取 Issue 的 FA 分析记录。"""
        cols = self._conn.execute(
            "PRAGMA table_info([fa_records])"
        ).fetchall()
        col_names = [c[1] for c in cols]
        rows = self._conn.execute(
            "SELECT * FROM [fa_records] WHERE issue_id = ? ORDER BY step_no",
            (issue_id,),
        ).fetchall()
        return [FARecord(**cast(dict[str, Any], dict(zip(col_names, r)))) for r in rows]

    def add_fa_record(self, issue_id: int, **kwargs: object) -> int:
        """添加 FA 分析步骤。"""
        kwargs["issue_id"] = issue_id
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [fa_records] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    # ── 附件 ──

    def get_attachments(self, issue_id: int) -> list[IssueAttachment]:
        """获取 Issue 附件。"""
        cols = self._conn.execute(
            "PRAGMA table_info([issue_attachments])"
        ).fetchall()
        col_names = [c[1] for c in cols]
        rows = self._conn.execute(
            "SELECT * FROM [issue_attachments] WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [IssueAttachment(**cast(dict[str, Any], dict(zip(col_names, r)))) for r in rows]

    def add_attachment(self, issue_id: int, **kwargs: object) -> int:
        """添加 Issue 附件。"""
        kwargs["issue_id"] = issue_id
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [issue_attachments] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def delete_fa_records(self, issue_id: int) -> None:
        """删除 Issue 的所有 FA 分析记录（级联删除子表）。"""
        self._conn.execute(
            "DELETE FROM [fa_records] WHERE issue_id = ?", (issue_id,)
        )

    def delete_attachments(self, issue_id: int) -> None:
        """删除 Issue 的所有附件（级联删除子表）。"""
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE issue_id = ?", (issue_id,)
        )

    def delete_attachment(self, attachment_id: int) -> None:  # attachment management
        """删除单条附件。"""
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE id = ?", (attachment_id,)
        )

    # ── CAPA 记录 ──

    def get_capa_records(self, issue_id: int) -> list[CAPARecord]:
        """获取 Issue 的 CAPA 记录。"""
        cols = self._conn.execute(
            "PRAGMA table_info([capa_records])"
        ).fetchall()
        col_names = [c[1] for c in cols]
        rows = self._conn.execute(
            "SELECT * FROM [capa_records] WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [CAPARecord(**cast(dict[str, Any], dict(zip(col_names, r)))) for r in rows]

    def add_capa_record(self, issue_id: int, **kwargs: object) -> int:
        """添加 CAPA 记录。"""
        kwargs["issue_id"] = issue_id
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [capa_records] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def update_capa_record(self, capa_id: int, **kwargs: object) -> None:
        """更新 CAPA 记录。"""
        sets = ", ".join(f"[{k}] = ?" for k in kwargs)
        vals = list(kwargs.values()) + [capa_id]
        self._conn.execute(
            f"UPDATE [capa_records] SET {sets} WHERE id = ?", vals
        )

    def delete_capa_record(self, capa_id: int) -> None:
        """删除单条 CAPA 记录。"""
        self._conn.execute(
            "DELETE FROM [capa_records] WHERE id = ?", (capa_id,)
        )

    def delete_capa_records(self, issue_id: int) -> None:
        """删除 Issue 的所有 CAPA 记录。"""
        self._conn.execute(
            "DELETE FROM [capa_records] WHERE issue_id = ?", (issue_id,)
        )

    def delete_by_project(self, project_id: int) -> int:
        """删除项目关联的所有 issue（含 FA/CAPA/附件），返回删除行数。"""
        # 先删子表
        self._conn.execute(
            "DELETE FROM [fa_records] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE project_id = ?)", (project_id,)
        )
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE project_id = ?)", (project_id,)
        )
        self._conn.execute(
            "DELETE FROM [capa_records] WHERE issue_id IN "
            "(SELECT id FROM [issues] WHERE project_id = ?)", (project_id,)
        )
        cursor = self._conn.execute(
            "DELETE FROM [issues] WHERE project_id = ?", (project_id,)
        )
        return cursor.getrowcount() if hasattr(cursor, "getrowcount") else 0
