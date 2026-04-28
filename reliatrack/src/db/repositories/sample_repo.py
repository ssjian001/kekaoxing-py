"""样品 Repository。"""

from __future__ import annotations

from typing import Optional

import apsw

from src.models.sample import Sample, SampleTransaction
from src.db.repositories.base import BaseRepository


class SampleRepository(BaseRepository):
    """样品数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "samples", Sample)

    def get_by_project(self, project_id: int) -> list[Sample]:
        return self.list_all(project_id=project_id)

    def get_by_sn(self, sn: str) -> Optional[Sample]:
        rows = self._conn.execute(
            "SELECT * FROM [samples] WHERE sn = ?", (sn,)
        ).fetchall()
        return self._rows_to_models(rows)[0] if rows else None

    def get_by_status(self, status: str) -> list[Sample]:
        return self.list_all(status=status)

    def get_transactions(self, sample_id: int) -> list[SampleTransaction]:
        """获取样品的出入库记录。"""
        cols = self._conn.execute(
            "PRAGMA table_info([sample_transactions])"
        ).fetchall()
        col_names = [c[1] for c in cols]
        rows = self._conn.execute(
            "SELECT * FROM [sample_transactions] WHERE sample_id = ? ORDER BY created_at DESC",
            (sample_id,),
        ).fetchall()
        return [SampleTransaction(**dict(zip(col_names, r))) for r in rows]

    def update_status(self, id: int, status: str) -> None:
        """更新样品状态。"""
        self.update(id, status=status)

    def add_transaction(self, sample_id: int, txn_type: str, **kwargs: object) -> int:
        """添加出入库记录到 sample_transactions 表。"""
        data = {"sample_id": sample_id, "type": txn_type, **kwargs}
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [sample_transactions] ({col_str}) VALUES ({placeholders})"
        self._conn.execute(sql, vals)
        row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row else 0

    def list_transactions(
        self, filter_sn: str = "", filter_type: str = ""
    ) -> list[dict]:
        """查询所有出入库记录，JOIN 样品和操作人信息。

        Args:
            filter_sn: 可选 SN 模糊搜索。
            filter_type: 可选操作类型精确过滤 (check_out/check_in/return/transfer)。

        Returns:
            包含完整关联信息的字典列表。
        """
        sql = """
            SELECT st.*, s.sn as sample_sn, s.batch_no,
                   t.name as operator_name
            FROM sample_transactions st
            LEFT JOIN samples s ON st.sample_id = s.id
            LEFT JOIN technicians t ON st.operator_id = t.id
        """
        params: list[object] = []
        conditions: list[str] = []

        if filter_sn.strip():
            conditions.append("s.sn LIKE ?")
            params.append(f"%{filter_sn.strip()}%")
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
            "related_task_id", "expected_return", "created_at",
            "sample_sn", "batch_no", "operator_name",
        ]
        return [dict(zip(cols, row)) for row in rows]

    def delete_transactions(self, sample_id: int) -> None:
        """删除样品的所有出入库记录（级联删除子表）。"""
        self._conn.execute(
            "DELETE FROM [sample_transactions] WHERE sample_id = ?", (sample_id,)
        )
