"""系统设置 Repository。"""

from __future__ import annotations

from typing import Optional

import apsw

from src.models.common import Settings
from src.db.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    """系统设置数据访问（键值对）。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "settings", Settings)

    def get(self, key: str) -> Optional[str]:
        """获取设置值。"""
        row = self._conn.execute(
            "SELECT value FROM [settings] WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        """设置值（UPSERT）。"""
        self._conn.execute(
            """INSERT INTO [settings] (key, value, updated_at)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
               updated_at = excluded.updated_at""",
            (key, value),
        )
