"""Issue / FA Repository。"""

from __future__ import annotations

import apsw

from src.models.issue import Issue, FARecord, IssueAttachment
from src.db.repositories.base import BaseRepository


class IssueRepository(BaseRepository):
    """Issue 数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "issues", Issue)

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
        return [FARecord(**dict(zip(col_names, r))) for r in rows]

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
        return [IssueAttachment(**dict(zip(col_names, r))) for r in rows]

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
