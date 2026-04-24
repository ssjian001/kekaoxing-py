"""系统设置 Service。"""

from __future__ import annotations

from typing import Optional

from src.db.repositories import SettingsRepository


class SettingsService:
    """系统设置业务逻辑（键值对）。"""

    def __init__(self, repo: SettingsRepository) -> None:
        self._repo = repo

    def get(self, key: str) -> Optional[str]:
        return self._repo.get(key)

    def set(self, key: str, value: str) -> None:
        self._repo.set(key, value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self._repo.get(key)
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes")

    def get_int(self, key: str, default: int = 0) -> int:
        val = self._repo.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default
