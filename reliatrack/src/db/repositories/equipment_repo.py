"""设备 Repository。"""

from __future__ import annotations

import apsw

from src.models.common import Equipment
from src.db.repositories.base import BaseRepository


class EquipmentRepository(BaseRepository):
    """设备数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "equipment", Equipment)

    def count_task_references(self, equipment_id: int) -> int:
        """统计设备被测试任务引用的次数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [test_tasks] WHERE equipment_id = ?",
            (equipment_id,),
        ).fetchone()
        return row[0] if row else 0
