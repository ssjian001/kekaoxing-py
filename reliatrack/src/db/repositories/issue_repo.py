"""Issue / FA Repository。"""

from __future__ import annotations

import logging
import os

import apsw

from typing import Any, cast
from pathlib import Path

from src.models.issue import Issue, FARecord, IssueAttachment, CAPARecord
from src.db.connection import DEFAULT_ATTACHMENTS_DIR
from src.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class IssueRepository(BaseRepository):
    """Issue 数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "issues", Issue)

    def list_all(self, **filters: Any) -> list[Issue]:
        """查询所有未删除的 Issue，支持可选过滤条件。

        软删除的记录 (is_deleted=1) 会被自动过滤。

        Raises:
            Exception: 数据库操作失败时向上传播。
        """
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        sql = f"SELECT {cols_sql} FROM [issues]"
        params: list[Any] = []
        # 始终过滤已软删除的记录
        clauses = ["[is_deleted] = 0"]
        for k, v in filters.items():
            clauses.append(f"[{k}] = ?")
            params.append(v)
        sql += " WHERE " + " AND ".join(clauses)
        rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def count(self, **kwargs) -> int:
        """计数 — 始终过滤 is_deleted=0。

        Raises:
            Exception: 数据库操作失败时向上传播（替代静默返回 0）。
        """
        kwargs["is_deleted"] = 0
        return super().count(**kwargs)

    # ── 软删除方法 ──

    def soft_delete(self, issue_id: int) -> None:
        """软删除 Issue：标记 is_deleted=1 并记录 deleted_at。"""
        self._conn.execute(
            "UPDATE [issues] SET is_deleted = 1, "
            "deleted_at = datetime('now','localtime'), "
            "updated_at = datetime('now','localtime') "
            "WHERE id = ?",
            (issue_id,),
        )

    def list_deleted(self) -> list[Issue]:
        """查询所有已软删除的 Issue。"""
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        rows = self._conn.execute(
            f"SELECT {cols_sql} FROM [issues] WHERE is_deleted = 1 ORDER BY id"
        ).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def restore(self, issue_id: int) -> None:
        """恢复已软删除的 Issue。"""
        self._conn.execute(
            "UPDATE [issues] SET is_deleted = 0, deleted_at = '', "
            "updated_at = datetime('now','localtime') "
            "WHERE id = ?",
            (issue_id,),
        )

    def purge_old(self, days: int = 30) -> int:
        """彻底删除已软删除超过 N 天的 Issue，返回删除行数。"""
        self._conn.execute(
            "DELETE FROM [issues] WHERE is_deleted = 1 "
            "AND deleted_at < datetime('now','localtime', ?)",
            (f"-{days} days",),
        )
        row = self._conn.execute("SELECT changes()").fetchone()
        return row[0] if row else 0

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
        """按严重度分组计数，可选按 project_id 过滤。始终排除已软删除。"""
        if project_id:
            sql = (
                "SELECT severity, COUNT(*) FROM [issues] "
                "WHERE is_deleted = 0 AND "
                "(project_id = ? OR task_id IN (SELECT id FROM [test_tasks] "
                "WHERE plan_id IN (SELECT id FROM [test_plans] WHERE project_id = ?))) "
                "GROUP BY severity"
            )
            return dict(self._conn.execute(sql, (project_id, project_id)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT severity, COUNT(*) FROM [issues] WHERE is_deleted = 0 GROUP BY severity"
            ).fetchall()
        )

    def count_by_status(self, project_id: int | None = None) -> dict[str, int]:
        """按状态分组计数，可选按 project_id 过滤。始终排除已软删除。"""
        if project_id:
            sql = (
                "SELECT status, COUNT(*) FROM [issues] "
                "WHERE is_deleted = 0 AND "
                "(project_id = ? OR task_id IN (SELECT id FROM [test_tasks] "
                "WHERE plan_id IN (SELECT id FROM [test_plans] WHERE project_id = ?))) "
                "GROUP BY status"
            )
            return dict(self._conn.execute(sql, (project_id, project_id)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT status, COUNT(*) FROM [issues] WHERE is_deleted = 0 GROUP BY status"
            ).fetchall()
        )

    def get_by_project(self, project_id: int) -> list[Issue]:
        return self.list_all(project_id=project_id)

    def get_unassigned(self) -> list[Issue]:
        """返回未关联项目 (project_id IS NULL) 且未软删除的 Issue。

        Raises:
            Exception: 数据库操作失败时向上传播。
        """
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        sql = f"SELECT {cols_sql} FROM [issues] WHERE [project_id] IS NULL AND [is_deleted] = 0 ORDER BY id"
        rows = self._conn.execute(sql).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

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

    _FA_COLS = ("id", "issue_id", "step_no", "step_title", "description", "method",
                "findings", "possible_cause", "cause_category", "failure_mechanism",
                "confirmed", "analyst_id", "attachments", "created_at")
    _FA_SAFE_COLS = frozenset({
        "issue_id", "step_no", "step_title", "description", "method",
        "findings", "possible_cause", "cause_category", "failure_mechanism",
        "confirmed", "analyst_id", "attachments",
    })

    def get_fa_records(self, issue_id: int) -> list[FARecord]:
        """获取 Issue 的 FA 分析记录。"""
        col_str = ", ".join(self._FA_COLS)
        rows = self._conn.execute(
            f"SELECT {col_str} FROM [fa_records] WHERE issue_id = ? ORDER BY step_no",
            (issue_id,),
        ).fetchall()
        return [FARecord(**cast(dict[str, Any], dict(
            zip(self._FA_COLS, r)
        ))) for r in rows]

    def add_fa_record(self, issue_id: int, **kwargs: object) -> int:
        """添加 FA 分析步骤。"""
        kwargs["issue_id"] = issue_id
        safe = {k: v for k, v in kwargs.items() if k in self._FA_SAFE_COLS}
        cols = list(safe.keys())
        vals = list(safe.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [fa_records] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def update_fa_record(self, fa_id: int, **kwargs: object) -> None:
        """更新单条 FA 记录。"""
        safe = {k: v for k, v in kwargs.items() if k in self._FA_SAFE_COLS}
        if not safe:
            return
        sets = ", ".join(f"[{k}] = ?" for k in safe)
        vals = list(safe.values()) + [fa_id]
        self._conn.execute(f"UPDATE [fa_records] SET {sets} WHERE id = ?", vals)

    def delete_fa_record(self, fa_id: int) -> None:
        """删除单条 FA 记录。"""
        self._conn.execute("DELETE FROM [fa_records] WHERE id = ?", (fa_id,))

    # ── 附件 ──

    _ATTACH_COLS = ("id", "issue_id", "file_path", "file_type", "description", "created_at")
    _ATTACH_SAFE_COLS = frozenset({
        "issue_id", "file_path", "file_type", "description",
    })

    def get_attachments(self, issue_id: int) -> list[IssueAttachment]:
        """获取 Issue 附件。"""
        col_str = ", ".join(self._ATTACH_COLS)
        rows = self._conn.execute(
            f"SELECT {col_str} FROM [issue_attachments] WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [IssueAttachment(**cast(dict[str, Any], dict(
            zip(self._ATTACH_COLS, r)
        ))) for r in rows]

    def get_all_attachments(self) -> list[IssueAttachment]:
        """获取所有附件（一次性查询，用于完整性扫描）。"""
        col_str = ", ".join(self._ATTACH_COLS)
        rows = self._conn.execute(
            f"SELECT {col_str} FROM [issue_attachments] ORDER BY issue_id, created_at"
        ).fetchall()
        return [IssueAttachment(**cast(dict[str, Any], dict(
            zip(self._ATTACH_COLS, r)
        ))) for r in rows]

    def add_attachment(self, issue_id: int, **kwargs: object) -> int:
        """添加 Issue 附件。"""
        kwargs["issue_id"] = issue_id
        safe = {k: v for k, v in kwargs.items() if k in self._ATTACH_SAFE_COLS}
        cols = list(safe.keys())
        vals = list(safe.values())
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

    # 附件磁盘存储允许的基础目录（resolve 后的真实路径）
    _ALLOWED_ATTACH_DIRS: tuple[str, ...] = (
        str(Path(DEFAULT_ATTACHMENTS_DIR.parent).resolve()),
    )

    @staticmethod
    def _remove_disk_file(file_path: str) -> None:
        """安全删除附件磁盘文件，忽略不存在或无权限的文件。

        安全策略：
        1. 拒绝符号链接（防止 symlink 指向外部文件被删除）
        2. resolve() 后校验是否在允许目录内
        3. 静默忽略不存在的文件和有权限错误的文件
        """
        try:
            raw = Path(file_path)
            # 拒绝符号链接
            if raw.is_symlink():
                logger.warning("附件路径是符号链接，拒绝删除: %s -> %s", raw, raw.resolve())
                return
            p = raw.resolve()
            # 路径前缀校验：只删除允许目录下的文件
            allowed = IssueRepository._ALLOWED_ATTACH_DIRS
            if not any(str(p).startswith(d) for d in allowed):
                logger.warning("附件路径超出允许范围，跳过删除: %s", p)
                return
            if p.exists():
                p.unlink()
        except OSError:
            logger.warning("附件磁盘文件删除失败: %s", file_path)

    def delete_attachments(self, issue_id: int) -> None:
        """删除 Issue 的所有附件（DB 记录 + 磁盘文件）。

        先删磁盘文件再删 DB 记录：与 delete_attachment 顺序一致。
        磁盘删除失败时保留 DB 记录，用户可重试；
        避免 DB 记录丢失后文件变为孤儿。
        """
        rows = self._conn.execute(
            "SELECT id, file_path FROM [issue_attachments] WHERE issue_id = ?",
            (issue_id,),
        ).fetchall()
        for (aid, fp) in rows:
            if fp:
                p = Path(fp).resolve()
                allowed = IssueRepository._ALLOWED_ATTACH_DIRS
                if any(str(p).startswith(d) for d in allowed) and p.exists():
                    try:
                        p.unlink()
                    except OSError as exc:
                        raise RuntimeError(f"磁盘文件删除失败: {fp}") from exc
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE issue_id = ?", (issue_id,)
        )

    def delete_attachment(self, attachment_id: int) -> None:
        """删除单条附件（磁盘文件 + DB 记录）。

        先删磁盘文件再删 DB 记录：磁盘删除失败时保留 DB 记录，
        用户可重试；避免 DB 记录丢失后文件变为孤儿。
        """
        row = self._conn.execute(
            "SELECT file_path FROM [issue_attachments] WHERE id = ?",
            (attachment_id,),
        ).fetchone()
        if not row:
            return
        file_path = row[0]
        # 先尝试删除磁盘文件
        if file_path:
            p = Path(file_path).resolve()
            allowed = IssueRepository._ALLOWED_ATTACH_DIRS
            if any(str(p).startswith(d) for d in allowed) and p.exists():
                try:
                    p.unlink()
                except OSError as exc:
                    raise RuntimeError(
                        f"磁盘文件删除失败: {file_path}"
                    ) from exc
        # 磁盘文件已删除（或不存在 / 不在允许目录），安全删除 DB 记录
        self._conn.execute(
            "DELETE FROM [issue_attachments] WHERE id = ?", (attachment_id,)
        )

    # ── CAPA 记录 ──

    _CAPA_SELECT_COLS = ("id", "issue_id", "action", "assignee_id", "assignee_name",
                         "due_date", "status", "verification_result", "verified_by",
                         "verifier_name",
                         "root_cause", "effectiveness", "follow_up",
                         "created_at", "updated_at")
    _CAPA_SAFE_COLS = frozenset({
        "issue_id", "action", "assignee_id", "assignee_name", "due_date",
        "status", "verification_result", "verified_by",
        "verifier_name",
        "root_cause", "effectiveness", "follow_up",
    })

    def get_capa_records(self, issue_id: int) -> list[CAPARecord]:
        """获取 Issue 的 CAPA 记录。"""
        col_str = ", ".join(self._CAPA_SELECT_COLS)
        rows = self._conn.execute(
            f"SELECT {col_str} FROM [capa_records] WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [CAPARecord(**cast(dict[str, Any], dict(
            zip(self._CAPA_SELECT_COLS, r)
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
        if not safe:
            return
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
                "WHERE i.project_id = ? AND cr.status IN ('completed', 'verified')",
                (project_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] WHERE status IN ('completed', 'verified')"
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


class FARecordRepository(BaseRepository):
    """FA 分析记录数据访问（用于 DeleteEntityCommand 撤销）。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "fa_records", FARecord)


class CAPARecordRepository(BaseRepository):
    """CAPA 记录数据访问（用于 DeleteEntityCommand 撤销）。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "capa_records", CAPARecord)
