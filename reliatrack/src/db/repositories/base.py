"""Repository 基类 — 通用 CRUD 操作。

所有 Repository 继承此基类，只需实现 row_to_model() 方法。
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Type, TypeVar

import apsw

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository:
    """数据访问基类，提供通用 CRUD。

    Args:
        conn: apsw 数据库连接
        table: 表名
        model_class: 对应的 dataclass 类
    """

    def __init__(self, conn: apsw.Connection, table: str, model_class: Type[T]) -> None:
        self._conn = conn
        self._table = table
        self._model_class = model_class
        self._columns_cache: list[str] | None = None

    # ── 事务支持 ──

    def begin_transaction(self) -> None:
        self._conn.execute("BEGIN")

    def commit(self) -> None:
        self._conn.execute("COMMIT")

    def rollback(self) -> None:
        self._conn.execute("ROLLBACK")

    def transaction(self):
        """事务上下文管理器 — 自动 commit/rollback。

        用法::

            with repo.transaction():
                repo.insert(...)
                repo.update(...)
        """
        return _Transaction(self)

    # ── 列名查询（避免位置索引）──

    def _columns(self) -> list[str]:
        """获取表的所有列名（带缓存）。"""
        if self._columns_cache is not None:
            return self._columns_cache
        rows = self._conn.execute(f"PRAGMA table_info([{self._table}])").fetchall()
        self._columns_cache = [str(r[1]) for r in rows]
        return self._columns_cache

    def invalidate_columns_cache(self) -> None:
        """清除列名缓存（Schema 迁移后调用）。"""
        self._columns_cache = None

    def _rows_to_models(self, rows: list[tuple]) -> list[Any]:
        """将查询结果转为 dataclass 列表。"""
        cols = self._columns()
        return [self._model_class(**dict(zip(cols, row))) for row in rows]

    def _row_to_model(self, row: tuple) -> Any:
        """将单条查询结果转为 dataclass。"""
        cols = self._columns()
        return self._model_class(**dict(zip(cols, row)))

    # ── 通用 CRUD ──

    def insert(self, **kwargs: Any) -> int:
        """插入一行，返回 lastrowid。"""
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [{self._table}] ({col_str}) VALUES ({placeholders})"
        try:
            self._conn.execute(sql, vals)
            row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
            return row[0] if row else 0
        except Exception:
            logger.exception("Insert failed: table=%s, data=%s", self._table, kwargs)
            raise

    def update(self, id: int, **kwargs: Any) -> None:
        """按 ID 更新指定字段。自动刷新 updated_at。"""
        if not kwargs:
            return
        # 自动维护 updated_at（如果表有此列且调用方未显式传入）
        auto_ts = (
            "updated_at" not in kwargs
            and "updated_at" in self._columns()
        )
        if auto_ts:
            set_clause = ", ".join([f"[{k}] = ?" for k in kwargs])
            set_clause += ", [updated_at] = datetime('now','localtime')"
        else:
            set_clause = ", ".join([f"[{k}] = ?" for k in kwargs])
        vals = list(kwargs.values()) + [id]
        sql = f"UPDATE [{self._table}] SET {set_clause} WHERE id = ?"
        try:
            self._conn.execute(sql, vals)
        except Exception:
            logger.exception("Update failed: table=%s, id=%d", self._table, id)
            raise

    def delete(self, id: int) -> None:
        """按 ID 删除。"""
        self._conn.execute(f"DELETE FROM [{self._table}] WHERE id = ?", (id,))

    def get_by_id(self, id: int) -> Optional[Any]:
        """按 ID 查询单条。"""
        row = self._conn.execute(
            f"SELECT * FROM [{self._table}] WHERE id = ?", (id,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list_all(self, **filters: Any) -> list[Any]:
        """查询所有，支持可选过滤条件。"""
        sql = f"SELECT * FROM [{self._table}]"
        params: list[Any] = []
        if filters:
            clauses = []
            for k, v in filters.items():
                clauses.append(f"[{k}] = ?")
                params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._conn.execute(sql, params).fetchall()
        return self._rows_to_models(rows)

    def search(self, keyword: str, columns: list[str] | None = None) -> list[Any]:
        """按关键词模糊搜索。"""
        if columns is None:
            columns = self._columns()
        clauses = [f"CAST([{c}] AS TEXT) LIKE ?" for c in columns]
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        params = [pattern] * len(clauses)
        sql = f"SELECT * FROM [{self._table}] WHERE {' OR '.join(clauses)} ESCAPE '\\'"
        rows = self._conn.execute(sql, params).fetchall()
        return self._rows_to_models(rows)

    def count(self, **filters: Any) -> int:
        """计数，支持可选过滤。"""
        sql = f"SELECT COUNT(*) FROM [{self._table}]"
        params: list[Any] = []
        if filters:
            clauses = []
            for k, v in filters.items():
                clauses.append(f"[{k}] = ?")
                params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        row = self._conn.execute(sql, params).fetchone()
        return row[0] if row else 0


class _Transaction:
    """事务上下文管理器。"""

    def __init__(self, repo: BaseRepository) -> None:
        self._repo = repo

    def __enter__(self) -> _Transaction:
        self._repo.begin_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._repo.rollback()
        else:
            self._repo.commit()
