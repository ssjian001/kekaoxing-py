"""设备 Repository。"""

from __future__ import annotations

import apsw

from src.models.common import Equipment
from src.db.repositories.base import BaseRepository


class EquipmentRepository(BaseRepository):
    """设备数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "equipment", Equipment)

    def get_available(self) -> list[Equipment]:
        """获取所有可用设备。"""
        return self.list_all(status="available")

    def get_by_type(self, type: str) -> list[Equipment]:
        """按类型筛选设备。"""
        return self.list_all(type=type)
