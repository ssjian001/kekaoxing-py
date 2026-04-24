"""项目 Repository。"""

from __future__ import annotations

from typing import Optional

import apsw

from src.models.project import Project
from src.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    """项目数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "projects", Project)

    def get_active(self) -> list[Project]:
        """获取所有活跃项目。"""
        return self.list_all(status="active")

    def get_by_name(self, name: str) -> Optional[Project]:
        """按名称查找项目。"""
        rows = self._conn.execute(
            "SELECT * FROM [projects] WHERE name = ?", (name,)
        ).fetchall()
        return self._rows_to_models(rows)[0] if rows else None
