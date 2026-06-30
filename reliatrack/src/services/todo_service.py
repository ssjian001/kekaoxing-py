"""待办事项 Service — 待办 CRUD。"""

from __future__ import annotations

import logging

from src.db.repositories.todo_repo import TodoRepository
from src.models.todo import TodoItem

logger = logging.getLogger(__name__)


class TodoService:
    """待办事项业务逻辑。"""

    def __init__(self, repo: TodoRepository) -> None:
        self._repo = repo

    def create(self, **kwargs: object) -> int:
        """创建待办事项。"""
        return self._repo.create(dict(kwargs))

    def get(self, todo_id: int) -> TodoItem | None:
        """按 ID 查询。"""
        return self._repo.get(todo_id)

    def update(self, todo_id: int, **kwargs: object) -> None:
        """按 ID 更新。"""
        self._repo.update(todo_id, **kwargs)

    def delete(self, todo_id: int) -> None:
        """按 ID 删除。"""
        self._repo.delete(todo_id)

    def list_all(self) -> list[TodoItem]:
        """查询所有待办。"""
        return self._repo.list_all()

    def list_by_project(self, project_id: int) -> list[TodoItem]:
        """按项目查询待办。"""
        return self._repo.list_by_project(project_id)

    def toggle_status(self, todo_id: int) -> str | None:
        """切换状态：pending→in_progress→done→pending。返回新状态，失败返回 None。"""
        item = self._repo.get(todo_id)
        if item is None:
            return None
        status_cycle = {"pending": "in_progress", "in_progress": "done", "done": "pending"}
        new_status = status_cycle.get(item.status, "pending")
        self._repo.update(todo_id, status=new_status)
        return new_status

    def create_delete_command(self, todo_id: int):
        """创建删除命令。"""
        from src.services.undo_manager import DeleteEntityCommand
        return DeleteEntityCommand(self._repo, todo_id, "待办事项")
