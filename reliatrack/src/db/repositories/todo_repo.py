"""待办事项 Repository。"""

from __future__ import annotations

from typing import Any

from src.models.todo import TodoItem
from src.db.repositories.base import BaseRepository


class TodoRepository(BaseRepository):
    """待办事项数据访问。"""

    def __init__(self, conn) -> None:
        super().__init__(conn, "todos", TodoItem)

    def create(self, data: dict) -> int:
        """创建待办事项，返回 lastrowid。"""
        return self.insert(**data)

    def get(self, id: int) -> TodoItem | None:
        """按 ID 查询。"""
        return self.get_by_id(id)

    def update(self, id: int, **kwargs: Any) -> None:
        """按 ID 更新。"""
        super().update(id, **kwargs)

    def delete(self, id: int) -> None:
        """按 ID 删除。"""
        super().delete(id)

    def list_all(self, **filters: Any) -> list[TodoItem]:
        """查询所有待办，按 created_at DESC 排序，支持可选过滤条件。"""
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
        rows = self._conn.execute(sql + " ORDER BY id DESC", params).fetchall()
        return self._rows_to_models(rows, cols=cols_list)

    def list_due_reminders(self, now: str) -> list[TodoItem]:
        """查询 remind_at <= now AND reminded=0 AND archived=0 的待办。"""
        cols_sql = self._columns_sql()
        sql = f"SELECT {cols_sql} FROM [todos] WHERE [remind_at] != '' AND [remind_at] <= ? AND [reminded] = 0 AND [archived] = 0"
        rows = self._conn.execute(sql, (now,)).fetchall()
        return self._rows_to_models(rows, cols=self._columns())

    def mark_reminded(self, todo_id: int) -> None:
        """标记提醒已触发。"""
        self._conn.execute("UPDATE [todos] SET reminded = 1 WHERE id = ?", (todo_id,))

    def archive(self, todo_id: int) -> None:
        """归档指定待办。"""
        self._conn.execute("UPDATE [todos] SET archived = 1 WHERE id = ?", (todo_id,))

    def unarchive(self, todo_id: int) -> None:
        """取消归档。"""
        self._conn.execute("UPDATE [todos] SET archived = 0 WHERE id = ?", (todo_id,))
