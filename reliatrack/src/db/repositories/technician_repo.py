"""技术员 Repository。"""

from __future__ import annotations

import apsw

from src.models.common import Technician
from src.db.repositories.base import BaseRepository


class TechnicianRepository(BaseRepository):
    """技术员数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "technicians", Technician)

    def get_by_role(self, role: str) -> list[Technician]:
        """按角色筛选技术员。"""
        return self.list_all(role=role)
