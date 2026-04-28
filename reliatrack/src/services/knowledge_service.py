"""知识库 Service — 知识库 CRUD。"""

from __future__ import annotations

from src.db.repositories.knowledge_repo import KnowledgeRepository
from src.models.knowledge import KnowledgeEntry


class KnowledgeService:
    """知识库业务逻辑。"""

    def __init__(self, repo: KnowledgeRepository) -> None:
        self._repo = repo

    def create(self, **kwargs: object) -> int:
        """创建知识库条目。"""
        return self._repo.create(dict(kwargs))

    def get(self, entry_id: int) -> KnowledgeEntry | None:
        """按 ID 查询。"""
        return self._repo.get(entry_id)

    def update(self, entry_id: int, **kwargs: object) -> None:
        """按 ID 更新。"""
        self._repo.update(entry_id, **kwargs)

    def delete(self, entry_id: int) -> None:
        """按 ID 删除。"""
        self._repo.delete(entry_id)

    def list_all(self) -> list[KnowledgeEntry]:
        """查询所有条目。"""
        return self._repo.list_all()

    def search(self, keyword: str) -> list[KnowledgeEntry]:
        """按关键词搜索。"""
        return self._repo.search(keyword)
