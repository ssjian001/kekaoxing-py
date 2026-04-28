"""知识库 Repository。"""

from __future__ import annotations

import apsw

from src.models.knowledge import KnowledgeEntry
from src.db.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository):
    """知识库数据访问。"""

    def __init__(self, conn: apsw.Connection) -> None:
        super().__init__(conn, "knowledge_entries", KnowledgeEntry)

    def create(self, data: dict) -> int:
        """创建知识库条目，返回 lastrowid。"""
        return self.insert(**data)

    def get(self, entry_id: int) -> KnowledgeEntry | None:
        """按 ID 查询单条。"""
        return self.get_by_id(entry_id)

    def update(self, entry_id: int, data: dict) -> None:
        """按 ID 更新指定字段。"""
        if data:
            self._repo_update(entry_id, **data)

    def delete(self, entry_id: int) -> None:
        """按 ID 删除。"""
        self._repo_delete(entry_id)

    def list_all(self) -> list[KnowledgeEntry]:
        """查询所有条目。"""
        return self._list()

    def search(self, keyword: str) -> list[KnowledgeEntry]:
        """按关键词在 category、failure_mode、cause_analysis、improvement 字段上模糊搜索。"""
        cols = self._columns()
        search_columns = [c for c in ("category", "failure_mode", "cause_analysis", "improvement") if c in cols]
        if not search_columns:
            search_columns = cols
        return super().search(keyword, columns=search_columns)

    # ── 内部别名（避免与基类方法名冲突）──

    def _repo_update(self, entry_id: int, **kwargs: object) -> None:
        """更新条目。"""
        set_clause = ", ".join([f"[{k}] = ?" for k in kwargs])
        vals = list(kwargs.values()) + [entry_id]
        sql = f"UPDATE [{self._table}] SET {set_clause} WHERE id = ?"
        self._conn.execute(sql, vals)

    def _repo_delete(self, entry_id: int) -> None:
        """删除条目。"""
        self._conn.execute(f"DELETE FROM [{self._table}] WHERE id = ?", (entry_id,))

    def _list(self) -> list[KnowledgeEntry]:
        """查询所有条目，按 id DESC 排序。"""
        rows = self._conn.execute(
            f"SELECT * FROM [{self._table}] ORDER BY id DESC"
        ).fetchall()
        return self._rows_to_models(rows)
