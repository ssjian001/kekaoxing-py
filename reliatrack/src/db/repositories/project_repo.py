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
