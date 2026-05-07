"""Issue / FA Repository。"""

from __future__ import annotations

import logging
import os

import apsw

from typing import Any, cast
from pathlib import Path

from src.models.issue import Issue, FARecord, IssueAttachment, CAPARecord
from src.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


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

    _FA_COLS = "id, issue_id, step_no, step_title, description, method, findings, possible_cause, cause_category, failure_mechanism, confirmed, analyst_id, attachments, created_at"

    def get_fa_records(self, issue_id: int) -> list[FARecord]:
        """获取 Issue 的 FA 分析记录。"""
        rows = self._conn.execute(
            f"SELECT {self._FA_COLS} FROM [fa_records] WHERE issue_id = ? ORDER BY step_no",
            (issue_id,),
        ).fetchall()
        return [FARecord(**cast(dict[str, Any], dict(
            zip(("id", "issue_id", "step_no", "step_title", "description", "method",
                 "findings", "possible_cause", "cause_category", "failure_mechanism",
                 "confirmed", "analyst_id", "attachments", "created_at"), r)
        ))) for r in rows]

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

    _ATTACH_COLS = "id, issue_id, file_path, file_type, description, created_at"

    def get_attachments(self, issue_id: int) -> list[IssueAttachment]:
        """获取 Issue 附件。"""
        rows = self._conn.execute(
            f"SELECT {self._ATTACH_COLS} FROM [issue_attachments] WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [IssueAttachment(**cast(dict[str, Any], dict(
            zip(("id", "issue_id", "file_path", "file_type", "description", "created_at"), r)
        ))) for r in rows]

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

    @staticmethod
    def _remove_disk_file(file_path: str) -> None:
        """安全删除附件磁盘文件，忽略不存在或无权限的文件。"""
        try:
            p = Path(file_path)
            if p.exists():
                p.unlink()
        except OSError:
            logger.warning("附件磁盘文件删除失败: %s", file_path)

    def delete_attachments(self, issue_id: int) -> None:
        """删除 Issue 的所有附件（DB 记录 + 磁盘文件）。"""
        rows = self._conn.execute(
            "SELECT file_path FROM [issue_attachments] WHERE issue_id = ?",
            (issue_id,),
        ).fetchall()
        for (fp,) in rows:
            self._remove_disk_file(fp)
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE issue_id = ?", (issue_id,)
        )

    def delete_attachment(self, attachment_id: int) -> None:
        """删除单条附件（DB 记录 + 磁盘文件）。"""
        row = self._conn.execute(
            "SELECT file_path FROM [issue_attachments] WHERE id = ?",
            (attachment_id,),
        ).fetchone()
        if row:
            self._remove_disk_file(row[0])
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE id = ?", (attachment_id,)
        )

    # ── CAPA 记录 ──

    _CAPA_SELECT_COLS = "id, issue_id, action, assignee_id, assignee_name, due_date, status, verification_result, verified_by, created_at, updated_at"
    _CAPA_SAFE_COLS = frozenset({
        "issue_id", "action", "assignee_id", "assignee_name", "due_date",
        "status", "verification_result", "verified_by",
    })

    def get_capa_records(self, issue_id: int) -> list[CAPARecord]:
        """获取 Issue 的 CAPA 记录。"""
        rows = self._conn.execute(
            f"SELECT {self._CAPA_SELECT_COLS} FROM [capa_records] WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [CAPARecord(**cast(dict[str, Any], dict(
            zip(("id", "issue_id", "action", "assignee_id", "assignee_name", "due_date", "status",
                 "verification_result", "verified_by", "created_at", "updated_at"), r)
        ))) for r in rows]

    def add_capa_record(self, issue_id: int, **kwargs: object) -> int:
        """添加 CAPA 记录。"""
        kwargs["issue_id"] = issue_id
        # 白名单过滤，防止任意列名注入
        safe = {k: v for k, v in kwargs.items() if k in self._CAPA_SAFE_COLS}
        cols = list(safe.keys())
        vals = list(safe.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join(f"[{c}]" for c in cols)
        sql = f"INSERT INTO [capa_records] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def update_capa_record(self, capa_id: int, **kwargs: object) -> None:
        """更新 CAPA 记录。"""
        safe = {k: v for k, v in kwargs.items() if k in self._CAPA_SAFE_COLS}
        sets = ", ".join(f"[{k}] = ?" for k in safe)
        vals = list(safe.values()) + [capa_id]
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

    def count_capa_all(self, project_id: int | None = None) -> int:
        """统计 CAPA 记录总数（可按项目筛选）。"""
        if project_id is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] cr "
                "JOIN [issues] i ON cr.issue_id = i.id "
                "WHERE i.project_id = ?",
                (project_id,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM [capa_records]").fetchone()
        return row[0] if row else 0

    def count_capa_done(self, project_id: int | None = None) -> int:
        """统计已完成/已验证的 CAPA 记录数。"""
        if project_id is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] cr "
                "JOIN [issues] i ON cr.issue_id = i.id "
                "WHERE i.project_id = ? AND cr.status IN ('done', 'verified')",
                (project_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] WHERE status IN ('done', 'verified')"
            ).fetchone()
        return row[0] if row else 0

    def delete_by_project(self, project_id: int) -> int:
        """删除项目关联的所有 issue（含附件磁盘清理），返回删除行数。

        子表（fa_records / issue_attachments / capa_records）依赖 FK CASCADE。
        附件磁盘文件需手动清理。不删除 projects 本身——由 ProjectService 负责。
        """
        # 收集附件文件路径（磁盘清理，CASCADE 不处理文件系统）
        attachment_paths = self._conn.execute(
            "SELECT file_path FROM [issue_attachments] ia "
            "JOIN [issues] i ON ia.issue_id = i.id "
            "WHERE i.project_id = ?",
            (project_id,),
        ).fetchall()
        for (fp,) in attachment_paths:
            self._remove_disk_file(fp)
        # FK CASCADE 自动清理 fa_records / issue_attachments / capa_records
        cursor = self._conn.execute(
            "DELETE FROM [issues] WHERE project_id = ?", (project_id,),
        )
        return cursor.getrowcount() if hasattr(cursor, "getrowcount") else 0
