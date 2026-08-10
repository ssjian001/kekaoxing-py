"""系统设置 Service。"""

from __future__ import annotations

import logging

from src.db.repositories import SettingsRepository

logger = logging.getLogger(__name__)


class SettingsService:
    """系统设置业务逻辑（键值对）。"""

    def __init__(self, repo: SettingsRepository) -> None:
        self._repo = repo

    def get(self, key: str) -> str | None:
        return self._repo.get(key)

    def set(self, key: str, value: str) -> None:
        self._repo.set(key, value)
