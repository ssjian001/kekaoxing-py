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

    def delete_transactions(self, sample_id: int) -> None:
        """删除样品的所有出入库记录（级联删除子表）。"""
        self._conn.execute(
            "DELETE FROM [sample_transactions] WHERE sample_id = ?", (sample_id,)
        )
