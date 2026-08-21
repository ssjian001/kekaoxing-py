"""样品 Repository。"""

from __future__ import annotations

from typing import Any, Optional, cast

import apsw

from src.models.sample import Sample, SampleTransaction
from src.db.repositories.base import BaseRepository


class SampleRepository(BaseRepository):
    """样品数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "samples", Sample)

    def get_by_project(self, project_id: int) -> list[Sample]:
        return self.list_all(project_id=project_id)

    def count_by_status(self, project_id: int | None = None) -> dict[str, int]:
        """按状态分组计数，可选按 project_id 过滤。"""
        if project_id:
            sql = "SELECT status, COUNT(*) FROM [samples] WHERE project_id = ? GROUP BY status"
            return dict(self._conn.execute(sql, (project_id,)).fetchall())
        return dict(
            self._conn.execute(
                "SELECT status, COUNT(*) FROM [samples] GROUP BY status"
            ).fetchall()
        )

    def get_by_sn(self, sn: str) -> Optional[Sample]:
        _COLS = ["id", "sn", "batch_no", "spec", "project_id", "status", "location",
                "test_hours", "qr_code", "notes", "supplier", "scrapped_reason",
                "created_at", "updated_at"]
        rows = self._conn.execute(
            f"SELECT {', '.join(_COLS)} FROM [samples] WHERE sn = ?", (sn,)
        ).fetchall()
        return self._rows_to_models(rows, cols=_COLS)[0] if rows else None

    def get_by_status(self, status: str) -> list[Sample]:
        return self.list_all(status=status)

    _TXN_COLS = ("id", "sample_id", "type", "operator_id", "purpose",
                 "related_task_id", "expected_return", "actual_return", "notes", "created_at")
    def update_status(self, id: int, status: str) -> None:
        """更新样品状态。"""
        self.update(id, status=status)

    _TXN_SAFE_COLS = frozenset({
        "sample_id", "type", "operator_id", "purpose",
        "related_task_id", "expected_return", "actual_return", "notes",
    })

    def add_transaction(self, sample_id: int, txn_type: str, **kwargs: object) -> int:
        """添加出入库记录到 sample_transactions 表。"""
        merged = {"sample_id": sample_id, "type": txn_type, **kwargs}
        safe = {k: v for k, v in merged.items() if k in self._TXN_SAFE_COLS}
        cols = list(safe.keys())
        vals = list(safe.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [sample_transactions] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def list_transactions(
        self, filter_sn: str = "", filter_type: str = ""
    ) -> list[dict]:
        """查询所有出入库记录，JOIN 样品、操作人和测试任务信息。

        Args:
            filter_sn: 可选 SN 模糊搜索。
            filter_type: 可选操作类型精确过滤 (check_out/check_in/return/transfer)。

        Returns:
            包含完整关联信息的字典列表。
        """
        st_cols = "st.id, st.sample_id, st.type, st.operator_id, st.purpose, st.related_task_id, st.expected_return, st.actual_return, st.notes, st.created_at"
        sql = f"""
            SELECT {st_cols}, s.sn as sample_sn, s.batch_no,
                   t.name as operator_name,
                   tk.name as task_name
            FROM sample_transactions st
            LEFT JOIN samples s ON st.sample_id = s.id
            LEFT JOIN technicians t ON st.operator_id = t.id
            LEFT JOIN test_tasks tk ON st.related_task_id = tk.id
        """
        params: list[object] = []
        conditions: list[str] = []

        if filter_sn.strip():
            # SQLite ESCAPE 子句要求单字符；此处传反斜杠（SQL 字面量 '\'）
            conditions.append("s.sn LIKE ? ESCAPE '\\'")
            sn_escaped = filter_sn.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{sn_escaped}%")
        if filter_type.strip():
            conditions.append("st.type = ?")
            params.append(filter_type.strip())

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY st.created_at DESC"

        rows = self._conn.execute(sql, params).fetchall()
        # apsw: empty result sets auto-complete, getdescription fails; hardcode cols
        cols = [
            "id", "sample_id", "type", "operator_id", "purpose",
            "related_task_id", "expected_return", "actual_return", "notes", "created_at",
            "sample_sn", "batch_no", "operator_name", "task_name",
        ]
        return [dict(zip(cols, row)) for row in rows]

    def delete_transactions(self, sample_id: int) -> None:
        """删除样品的所有出入库记录（级联删除子表）。"""
        self._conn.execute(
            "DELETE FROM [sample_transactions] WHERE sample_id = ?", (sample_id,)
        )

    def remove_from_task_sample_ids(self, sample_id: int) -> int:
        """从所有 test_tasks.sample_ids JSON 数组中移除指定样品 ID。

        Returns:
            更新的行数。
        """
        import json
        rows = self._conn.execute(
            "SELECT id, sample_ids FROM [test_tasks] WHERE sample_ids != '[]'"
        ).fetchall()
        updated = 0
        for row_id, raw in rows:
            try:
                ids = json.loads(str(raw)) if raw else []
            except (json.JSONDecodeError, TypeError):
                continue
            if sample_id not in ids:
                continue
            ids = [i for i in ids if i != sample_id]
            self._conn.execute(
                "UPDATE [test_tasks] SET sample_ids = ? WHERE id = ?",
                (json.dumps(ids, ensure_ascii=False), row_id),
            )
            updated += 1
        return updated

    def delete_by_project(self, project_id: int) -> int:
        """删除项目关联的所有样品，返回删除行数。

        sample_transactions 依赖 FK CASCADE（sample_transactions.sample_id → samples(id) ON DELETE CASCADE）。
        """
        cursor = self._conn.execute(
            "DELETE FROM [samples] WHERE project_id = ?", (project_id,)
        )
        row = self._conn.execute("SELECT changes()").fetchone()
        return row[0] if row else 0

    def bulk_update_field(self, sample_ids: list[int], **fields: Any) -> None:
        """批量更新多个样品的指定字段。

        用一条 SQL 一次性更新所有匹配 ID 的记录。
        """
        if not sample_ids or not fields:
            return
        safe = self._safe_kwargs(fields)
        if not safe:
            return
        set_clause = ", ".join([f"[{k}] = ?" for k in safe])
        set_clause += ", [updated_at] = datetime('now','localtime')"
        vals = list(safe.values())
        placeholders = ", ".join(["?"] * len(sample_ids))
        sql = f"UPDATE [samples] SET {set_clause} WHERE id IN ({placeholders})"
        self._conn.execute(sql, vals + list(sample_ids))
