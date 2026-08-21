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
        self._columns_set: set[str] | None = None

    @property
    def conn(self) -> apsw.Connection:
        """数据库连接（只读）。"""
        return self._conn

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
        if not rows:
            logger.warning("PRAGMA table_info(%s) returned empty — table may not exist", self._table)
        self._columns_cache = [str(r[1]) for r in rows]
        return self._columns_cache

    def table_exists(self) -> bool:
        """检查表是否实际存在（至少有一列）。"""
        return bool(self._columns())

    def _columns_sql(self) -> str:
        """返回显式列名列表字符串，如 '[id], [name], [status]'。

        当 PRAGMA 返回空（表不存在）时回退到 '*'，避免生成无效 SQL。
        """
        cols = self._columns()
        if not cols:
            return "*"
        return ", ".join(f"[{c}]" for c in cols)

    def invalidate_columns_cache(self) -> None:
        """清除列名缓存（Schema 迁移后调用）。"""
        self._columns_cache = None
        self._columns_set = None

    def _rows_to_models(
        self, rows: list[tuple], cols: list[str] | None = None,
        strict: bool = False,
    ) -> list[Any]:
        """将查询结果转为 dataclass 列表。

        防御性实现：列数与行值数不一致时截断到较短者，避免字段串位。
        优先使用调用方传入的显式列名列表（与 SELECT 顺序一致），
        而非 PRAGMA 序（可能与物理表列序不一致）。

        Args:
            strict: 为 True 时 int 字段遇到非数字 str 时抛 ValueError，
                    而非静默保持原值。默认 False 兼容旧数据。
        """
        if cols is None:
            cols = self._columns()
        result = []
        for row in rows:
            # 截断到较短者，防止列数与行值数不一致（如 SELECT * 与 PRAGMA 顺序差异）
            data = dict(zip(cols, row))
            # 验证非 None 数值字段类型
            for col, val in data.items():
                if val is not None:
                    model_fields = getattr(self._model_class, "__annotations__", {})
                    expected = model_fields.get(col)
                    if expected in (int, "int", "Integer") and isinstance(val, str):
                        if val == "":
                            data[col] = 0
                        elif val.lstrip("-").isdigit():
                            data[col] = int(val)
                        elif strict:
                            raise ValueError(
                                f"Type mismatch: {self._table}.{col} "
                                f"expected int, got {val!r}"
                            )
                        else:
                            logger.warning(
                                "Type mismatch: %s.%s expected int, got %r; keeping as-is",
                                self._table, col, val,
                            )
            result.append(self._model_class(**data))
        return result

    def _row_to_model(
        self, row: tuple, cols: list[str] | None = None
    ) -> Any:
        """将单条查询结果转为 dataclass。"""
        return self._rows_to_models([row], cols=cols)[0]

    # ── 通用 CRUD ──

    def _safe_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """过滤 kwargs，只保留表中实际存在的列名（防 SQL 列名注入）。

        列名集合缓存于 _columns_set，invalidate_columns_cache 时同步失效。
        """
        if not hasattr(self, '_columns_set') or self._columns_set is None:
            self._columns_set = set(self._columns())
        return {k: v for k, v in kwargs.items() if k in self._columns_set}

    def insert(self, **kwargs: Any) -> int:
        """插入一行，返回 lastrowid。"""
        safe = self._safe_kwargs(kwargs)
        if not safe:
            raise ValueError(f"insert(): no valid columns for {self._table}")
        cols = list(safe.keys())
        vals = list(safe.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join([f"[{c}]" for c in cols])
        sql = f"INSERT INTO [{self._table}] ({col_str}) VALUES ({placeholders})"
        try:
            self._conn.execute(sql, vals)
            row = self._conn.execute("SELECT last_insert_rowid()").fetchone()
            return row[0] if row else 0
        except Exception:
            logger.exception("Insert failed: table=%s, data=%s", self._table, safe)
            raise

    def update(self, id: int, **kwargs: Any) -> None:
        """按 ID 更新指定字段。自动刷新 updated_at。"""
        if not kwargs:
            return
        safe = self._safe_kwargs(kwargs)
        if not safe:
            return
        # 自动维护 updated_at（如果表有此列且调用方未显式传入）
        auto_ts = (
            "updated_at" not in safe
            and "updated_at" in self._columns()
        )
        if auto_ts:
            set_clause = ", ".join([f"[{k}] = ?" for k in safe])
            set_clause += ", [updated_at] = datetime('now','localtime')"
        else:
            set_clause = ", ".join([f"[{k}] = ?" for k in safe])
        vals = list(safe.values()) + [id]
        sql = f"UPDATE [{self._table}] SET {set_clause} WHERE id = ?"
        try:
            self._conn.execute(sql, vals)
        except Exception:
            logger.exception("Update failed: table=%s, id=%d", self._table, id)
            raise

    def delete(self, id: int) -> None:
        """按 ID 删除。"""
        try:
            self._conn.execute(f"DELETE FROM [{self._table}] WHERE id = ?", (id,))
        except Exception:
            logger.exception("Delete failed: table=%s, id=%d", self._table, id)
            raise

    def get_by_id(self, id: int) -> Optional[Any]:
        """按 ID 查询单条。"""
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        row = self._conn.execute(
            f"SELECT {cols_sql} FROM [{self._table}] WHERE id = ?", (id,)
        ).fetchone()
        return self._row_to_model(row, cols=cols_list) if row else None

    def list_all(self, **filters: Any) -> list[Any]:
        """查询所有，支持可选过滤条件。"""
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        sql = f"SELECT {cols_sql} FROM [{self._table}]"
        params: list[Any] = []
        if filters:
            clauses = []
            safe = self._safe_kwargs(filters)
            for k, v in safe.items():
                clauses.append(f"[{k}] = ?")
                params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        try:
            rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
            return self._rows_to_models(rows, cols=cols_list)
        except Exception:
            logger.exception("list_all failed: table=%s, filters=%s", self._table, filters)
            raise

    def search(self, keyword: str, columns: list[str] | None = None) -> list[Any]:
        """按关键词模糊搜索。"""
        if columns is None:
            columns = self._columns()
        # 审计 #10：ESCAPE 子句只绑定紧邻的 LIKE 表达式。原实现把 ESCAPE
        # 拼在 OR 链尾部，仅最后一个子句生效——含 %/_ 关键词时其余列
        # 漏匹配/误匹配。改为每个 LIKE 子句独立携带 ESCAPE。
        clauses = [f"CAST([{c}] AS TEXT) LIKE ? ESCAPE '\\'" for c in columns]
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        params = [pattern] * len(clauses)
        cols_sql = self._columns_sql()
        cols_list = self._columns()
        sql = f"SELECT {cols_sql} FROM [{self._table}] WHERE {' OR '.join(clauses)}"
        rows = self._conn.execute(sql, params).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def count(self, **filters: Any) -> int:
        """计数，支持可选过滤。

        Raises:
            Exception: 数据库操作失败时向上传播。
        """
        sql = f"SELECT COUNT(*) FROM [{self._table}]"
        params: list[Any] = []
        if filters:
            clauses = []
            safe = self._safe_kwargs(filters)
            for k, v in safe.items():
                clauses.append(f"[{k}] = ?")
                params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        row = self._conn.execute(sql, params).fetchone()
        return row[0] if row else 0


class _Transaction:
    """事务上下文管理器（支持嵌套 — 外层已有事务时跳过 BEGIN/COMMIT）。"""

    def __init__(self, repo: BaseRepository) -> None:
        self._repo = repo
        self._owns_transaction = False

    def __enter__(self) -> _Transaction:
        # 如果已在事务中，不重复 BEGIN（SQLite 不支持嵌套事务）
        if not self._repo.conn.in_transaction:
            self._repo.begin_transaction()
            self._owns_transaction = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._owns_transaction:
            return
        if exc_type is not None:
            self._repo.rollback()
        else:
            self._repo.commit()
