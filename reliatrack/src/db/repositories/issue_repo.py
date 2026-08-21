"""Issue / FA Repository。"""

from __future__ import annotations

import logging

import apsw

from typing import Any, cast
from pathlib import Path

from src.models.issue import (
    Issue, FARecord, IssueAttachment, CAPARecord,
    IssueComment, IssueActivityLog, IssueLink,
)
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
        safe = self._safe_kwargs(filters)
        for k, v in safe.items():
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

    def get_by_ids(self, issue_ids: list[int]) -> list[Issue]:
        """批量获取多个 Issue（含软删，与 get_by_id 语义一致）。

        一次 IN 查询替代 N 次 get_by_id（get_aging_days_map 批量回退路径）。
        """
        if not issue_ids:
            return []
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        placeholders = ",".join("?" * len(issue_ids))
        rows = self._conn.execute(
            f"SELECT {cols_sql} FROM [issues] WHERE id IN ({placeholders})",
            issue_ids,
        ).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

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
        """彻底删除已软删除超过 N 天的 Issue，返回删除行数。

        审计修复：删除前先清理附件磁盘文件（与 delete() 一致），
        否则 DB 行级联删除后附件变孤儿文件。
        """
        attachment_paths = self._conn.execute(
            "SELECT ia.file_path FROM [issue_attachments] ia "
            "JOIN [issues] i ON ia.issue_id = i.id "
            "WHERE i.is_deleted = 1 "
            "AND i.deleted_at < datetime('now','localtime', ?)",
            (f"-{days} days",),
        ).fetchall()
        for (fp,) in attachment_paths:
            self._remove_disk_file(fp)
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

    def count_by_sample_all(self, sample_id: int) -> int:
        """统计指定样品的 Issue 数量（含已软删除）。

        用于删除前的引用保护：软删 Issue 仍持有 sample_id 外键，
        若只按 is_deleted=0 计数，删除样品会触发 FK ON DELETE CASCADE
        物理清除软删 Issue 及其 FA/CAPA/评论（绕过硬删除保底）。
        """
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [issues] WHERE sample_id = ?",
            (sample_id,),
        ).fetchone()
        return row[0] if row else 0

    def count_by_analyst(self, analyst_id: int) -> int:
        """统计 fa_records 中指定分析人的记录数量。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [fa_records] WHERE analyst_id = ?",
            (analyst_id,),
        ).fetchone()
        return row[0] if row else 0

    def count_by_severity(self, project_id: int | None = None) -> dict[str, int]:
        """按严重度分组计数，可选按 project_id 过滤。始终排除已软删除和已归档计划的 Issue。"""
        if project_id:
            sql = (
                "SELECT i.severity, COUNT(*) FROM [issues] i "
                "LEFT JOIN [test_tasks] tt ON i.task_id = tt.id "
                "LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id) "
                "WHERE i.is_deleted = 0 AND i.project_id = ? "
                "AND (tp.status IS NULL OR tp.status != 'archived') "
                "GROUP BY i.severity"
            )
            return dict(self._conn.execute(sql, (project_id,)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT severity, COUNT(*) FROM [issues] WHERE is_deleted = 0 GROUP BY severity"
            ).fetchall()
        )

    def count_by_status(self, project_id: int | None = None) -> dict[str, int]:
        """按状态分组计数，可选按 project_id 过滤。始终排除已软删除和已归档计划的 Issue。"""
        if project_id:
            sql = (
                "SELECT i.status, COUNT(*) FROM [issues] i "
                "LEFT JOIN [test_tasks] tt ON i.task_id = tt.id "
                "LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id) "
                "WHERE i.is_deleted = 0 AND i.project_id = ? "
                "AND (tp.status IS NULL OR tp.status != 'archived') "
                "GROUP BY i.status"
            )
            return dict(self._conn.execute(sql, (project_id,)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT status, COUNT(*) FROM [issues] WHERE is_deleted = 0 GROUP BY status"
            ).fetchall()
        )

    def get_by_project(self, project_id: int) -> list[Issue]:
        """获取项目下未删除且未关联已归档计划的 Issue。"""
        cols_list = self._columns()
        cols_sql = ", ".join(f"i.[{c}]" for c in cols_list)
        rows = self._conn.execute(f"""
            SELECT {cols_sql} FROM [issues] i
            LEFT JOIN [test_tasks] tt ON i.task_id = tt.id
            LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id)
            WHERE i.project_id = ? AND i.is_deleted = 0
              AND (tp.status IS NULL OR tp.status != 'archived')
            ORDER BY i.id
        """, (project_id,)).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

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
        """获取任务下未删除且未关联已归档计划的 Issue。"""
        cols_list = self._columns()
        cols_sql = ", ".join(f"i.[{c}]" for c in cols_list)
        rows = self._conn.execute(f"""
            SELECT {cols_sql} FROM [issues] i
            LEFT JOIN [test_tasks] tt ON i.task_id = tt.id
            LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id)
            WHERE i.task_id = ? AND i.is_deleted = 0
              AND (tp.status IS NULL OR tp.status != 'archived')
            ORDER BY i.id
        """, (task_id,)).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def get_by_sample(self, sample_id: int) -> list[Issue]:
        """获取样品下未删除且未关联已归档计划的 Issue。"""
        cols_list = self._columns()
        cols_sql = ", ".join(f"i.[{c}]" for c in cols_list)
        rows = self._conn.execute(f"""
            SELECT {cols_sql} FROM [issues] i
            LEFT JOIN [test_tasks] tt ON i.task_id = tt.id
            LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id)
            WHERE i.sample_id = ? AND i.is_deleted = 0
              AND (tp.status IS NULL OR tp.status != 'archived')
            ORDER BY i.id
        """, (sample_id,)).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

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

    def get_fa_records_by_issue_ids(self, issue_ids: list[int]) -> dict[int, list[FARecord]]:
        """批量获取多个 Issue 的 FA 记录。返回 {issue_id: [records]}。"""
        if not issue_ids:
            return {}
        placeholders = ", ".join("?" * len(issue_ids))
        col_str = ", ".join(self._FA_COLS)
        rows = self._conn.execute(
            f"SELECT {col_str} FROM [fa_records] WHERE issue_id IN ({placeholders}) ORDER BY step_no",
            issue_ids,
        ).fetchall()
        result: dict[int, list[FARecord]] = {}
        for r in rows:
            record = FARecord(**cast(dict[str, Any], dict(zip(self._FA_COLS, r))))
            # r[1] = issue_id (FA_COLS: id=0, issue_id=1, ...)
            issue_key = int(r[1]) if r[1] is not None else 0
            result.setdefault(issue_key, []).append(record)
        return result

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
        str(DEFAULT_ATTACHMENTS_DIR.resolve()),
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
                self._remove_disk_file(fp)
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
            self._remove_disk_file(str(file_path))
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

    def get_capa_records_by_issue_ids(self, issue_ids: list[int]) -> dict[int, list[CAPARecord]]:
        """批量获取多个 Issue 的 CAPA 记录。返回 {issue_id: [records]}。"""
        if not issue_ids:
            return {}
        placeholders = ", ".join("?" * len(issue_ids))
        col_str = ", ".join(self._CAPA_SELECT_COLS)
        rows = self._conn.execute(
            f"SELECT {col_str} FROM [capa_records] WHERE issue_id IN ({placeholders}) ORDER BY created_at",
            issue_ids,
        ).fetchall()
        result: dict[int, list[CAPARecord]] = {}
        for r in rows:
            record = CAPARecord(**cast(dict[str, Any], dict(zip(self._CAPA_SELECT_COLS, r))))
            issue_key = int(r[1]) if r[1] is not None else 0
            result.setdefault(issue_key, []).append(record)
        return result

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
        """统计 CAPA 记录总数（可按项目筛选，排除已归档计划的 CAPA）。"""
        if project_id is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] cr "
                "JOIN [issues] i ON cr.issue_id = i.id "
                "LEFT JOIN [test_tasks] tt ON i.task_id = tt.id "
                "LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id) "
                "WHERE i.project_id = ? AND i.is_deleted = 0 "
                "AND (tp.status IS NULL OR tp.status != 'archived')",
                (project_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] cr "
                "JOIN [issues] i ON cr.issue_id = i.id "
                "WHERE i.is_deleted = 0"
            ).fetchone()
        return row[0] if row else 0

    def count_capa_done(self, project_id: int | None = None) -> int:
        """统计已完成/已验证的 CAPA 记录数（排除已归档计划的 CAPA）。"""
        if project_id is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] cr "
                "JOIN [issues] i ON cr.issue_id = i.id "
                "LEFT JOIN [test_tasks] tt ON i.task_id = tt.id "
                "LEFT JOIN [test_plans] tp ON tp.id = COALESCE(i.plan_id, tt.plan_id) "
                "WHERE i.project_id = ? AND cr.status IN ('completed', 'verified') AND i.is_deleted = 0 "
                "AND (tp.status IS NULL OR tp.status != 'archived')",
                (project_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM [capa_records] cr "
                "JOIN [issues] i ON cr.issue_id = i.id "
                "WHERE cr.status IN ('completed', 'verified') AND i.is_deleted = 0"
            ).fetchone()
        return row[0] if row else 0

    def detach_references_of_project(self, project_id: int) -> int:
        """解关联"外项目 Issue 对本项目样品/任务"的引用（置 NULL），返回行数。

        项目级联删除前调用：这些 Issue 本体属于其他项目（或无项目），
        若不解关联，删除本项目样品/任务时 FK ON DELETE CASCADE 会物理
        清除它们——包括已软删的，绕过软删保护（2026-08-21 审计 #7）。
        """
        cursor = self._conn.execute(
            "UPDATE [issues] SET sample_id = NULL "
            "WHERE sample_id IN (SELECT id FROM [samples] WHERE project_id = ?) "
            "AND (project_id IS NULL OR project_id != ?)",
            (project_id, project_id),
        )
        cursor2 = self._conn.execute(
            "UPDATE [issues] SET task_id = NULL "
            "WHERE task_id IN (SELECT t.id FROM [test_tasks] t "
            "JOIN [test_plans] p ON t.plan_id = p.id WHERE p.project_id = ?) "
            "AND (project_id IS NULL OR project_id != ?)",
            (project_id, project_id),
        )
        return 0

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
        row = self._conn.execute("SELECT changes()").fetchone()
        return row[0] if row else 0


class FARecordRepository(BaseRepository):
    """FA 分析记录数据访问（用于 DeleteEntityCommand 撤销）。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "fa_records", FARecord)


class CAPARecordRepository(BaseRepository):
    """CAPA 记录数据访问（用于 DeleteEntityCommand 撤销）。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "capa_records", CAPARecord)


# ═══════════════════════════════════════════════════════════════════
#  Bug Tracker — v23 新增：评论 / 活动日志 / 关联
# ═══════════════════════════════════════════════════════════════════


class IssueCommentRepository(BaseRepository):
    """Issue 评论数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "issue_comments", IssueComment)

    def get_by_issue(self, issue_id: int) -> list[IssueComment]:
        """获取某 Issue 的所有未删除评论（按时间升序）。"""
        rows = self._conn.execute(
            "SELECT * FROM [issue_comments] WHERE issue_id = ? AND is_deleted = 0 ORDER BY created_at ASC",
            (issue_id,),
        ).fetchall()
        cols = [d[1] for d in self._conn.execute("PRAGMA table_info([issue_comments])").fetchall()]
        return [IssueComment(**dict(zip(cols, row))) for row in rows]

    def soft_delete(self, comment_id: int) -> None:
        """软删除评论。"""
        self._conn.execute(
            "UPDATE [issue_comments] SET is_deleted = 1 WHERE id = ?",
            (comment_id,),
        )


class IssueActivityLogRepository(BaseRepository):
    """Issue 活动日志数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "issue_activity_log", IssueActivityLog)

    def add(self, issue_id: int, field: str, old_value: str, new_value: str, operator: str = "") -> int:
        """写入一条活动日志（含 project_id 冗余存储用于按项目筛选）。"""
        # 查 issue 的 project_id（冗余写入避免后续 JOIN 开销）
        row = self._conn.execute(
            "SELECT project_id FROM [issues] WHERE id = ?", (issue_id,)
        ).fetchone()
        project_id = row[0] if row else None
        self._conn.execute(
            "INSERT INTO [issue_activity_log] (issue_id, project_id, field, old_value, new_value, operator)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (issue_id, project_id, field, str(old_value), str(new_value), operator),
        )
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def get_by_issue(self, issue_id: int) -> list[IssueActivityLog]:
        """获取某 Issue 的活动日志（按时间升序）。"""
        rows = self._conn.execute(
            "SELECT * FROM [issue_activity_log] WHERE issue_id = ? ORDER BY created_at ASC",
            (issue_id,),
        ).fetchall()
        cols = [d[1] for d in self._conn.execute("PRAGMA table_info([issue_activity_log])").fetchall()]
        return [IssueActivityLog(**dict(zip(cols, row))) for row in rows]

    def get_by_issues(self, issue_ids: list[int]) -> list[IssueActivityLog]:
        """批量获取多个 Issue 的活动日志（按 issue_id, created_at 升序）。

        一次 IN 查询替代 N 次单行查询（列表渲染 aging 列时避免逐行 DB 访问）。
        """
        if not issue_ids:
            return []
        placeholders = ",".join("?" * len(issue_ids))
        rows = self._conn.execute(
            f"SELECT * FROM [issue_activity_log] WHERE issue_id IN ({placeholders}) "
            "ORDER BY issue_id ASC, created_at ASC",
            issue_ids,
        ).fetchall()
        cols = [d[1] for d in self._conn.execute("PRAGMA table_info([issue_activity_log])").fetchall()]
        return [IssueActivityLog(**dict(zip(cols, row))) for row in rows]


class IssueLinkRepository(BaseRepository):
    """Issue 关联数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "issue_links", IssueLink)

    def add(self, source_id: int, target_id: int, link_type: str = "relates_to") -> int:
        """创建关联。source/target 相同或重复关联会抛 ConstraintError。"""
        self._conn.execute(
            "INSERT INTO [issue_links] (source_id, target_id, link_type) VALUES (?, ?, ?)",
            (source_id, target_id, link_type),
        )
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def get_for_issue(self, issue_id: int) -> list[IssueLink]:
        """获取某 Issue 的所有关联（双向 — source 和 target 都查）。"""
        rows = self._conn.execute(
            "SELECT * FROM [issue_links] WHERE source_id = ? OR target_id = ? ORDER BY created_at DESC",
            (issue_id, issue_id),
        ).fetchall()
        cols = [d[1] for d in self._conn.execute("PRAGMA table_info([issue_links])").fetchall()]
        return [IssueLink(**dict(zip(cols, row))) for row in rows]

    def delete(self, id: int) -> None:
        """删除关联。"""
        self._conn.execute("DELETE FROM [issue_links] WHERE id = ?", (id,))
