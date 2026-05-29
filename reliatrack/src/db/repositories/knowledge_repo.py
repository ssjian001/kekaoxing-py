"""知识库 Repository。"""

from __future__ import annotations

import apsw

from typing import Any

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

    def list_all(self, **filters: Any) -> list[KnowledgeEntry]:
        """查询所有条目，按 id DESC 排序，支持可选过滤条件。"""
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        sql = f"SELECT {cols_sql} FROM [{self._table}]"
        params: list[Any] = []
        if filters:
            clauses = []
            for k, v in filters.items():
                clauses.append(f"[{k}] = ?")
                params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._conn.execute(sql + " ORDER BY id DESC", params).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def search(self, keyword: str, columns: list[str] | None = None) -> list[KnowledgeEntry]:
        """按关键词在 category、failure_mode、cause_analysis、improvement 字段上模糊搜索。"""
        if columns is None:
            cols = self._columns()
        else:
            cols = columns
        search_columns = [c for c in ("category", "failure_mode", "cause_analysis", "improvement") if c in cols]
        if not search_columns:
            search_columns = cols
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        return super().search(keyword, columns=search_columns)  # type: ignore[return-value]
