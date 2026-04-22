"""撤销/重做框架 — 基于命令模式 (Command Pattern)

用法:
    undo_mgr = UndoManager()
    undo_mgr.execute(MoveTaskCommand(db, task_id, old_day, new_day))
    undo_mgr.undo()
    undo_mgr.redo()
"""

from __future__ import annotations

from abc import ABC, abstractmethod


# ═══════════════════════════════════════════════════════
#  Command 基类
# ═══════════════════════════════════════════════════════

class Command(ABC):
    """可撤销操作的抽象基类。"""

    description: str  # 人类可读描述，如 "移动任务到第5天"

    @abstractmethod
    def do(self) -> None:
        """执行操作。"""
        ...

    @abstractmethod
    def undo(self) -> None:
        """撤销操作。"""
        ...

    def redo(self) -> None:
        """重做操作（默认行为等同于 do）。"""
        self.do()


# ═══════════════════════════════════════════════════════
#  具体命令
# ═══════════════════════════════════════════════════════

class MoveTaskCommand(Command):
    """移动任务到新的开始天。"""

    def __init__(self, db, task_id: int, old_day: int, new_day: int):
        self.db = db
        self.task_id = task_id
        self.old_day = old_day
        self.new_day = new_day
        self.description = f"移动任务到第{new_day}天"

    def do(self) -> None:
        self.db.update_task_fields(self.task_id, {"start_day": self.new_day})

    def undo(self) -> None:
        self.db.update_task_fields(self.task_id, {"start_day": self.old_day})


class UpdateTaskCommand(Command):
    """更新任务的任意单个字段。"""

    def __init__(self, db, task_id: int, field: str, old_value, new_value):
        self.db = db
        self.task_id = task_id
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.description = f"更新任务 {field}"

    def do(self) -> None:
        self.db.update_task_fields(self.task_id, {self.field: self.new_value})

    def undo(self) -> None:
        self.db.update_task_fields(self.task_id, {self.field: self.old_value})


class DeleteTasksCommand(Command):
    """批量删除任务（保存完整数据以便恢复）。"""

    def __init__(self, db, tasks_data: list[dict]):
        """
        Args:
            db: 数据库实例
            tasks_data: 待删除任务的完整数据列表，每项需包含足够信息
                        以便 insert_task_from_dict 重新插入。
        """
        self.db = db
        self.tasks_data = tasks_data
        self.description = f"删除 {len(tasks_data)} 个任务"

    def do(self) -> None:
        for td in self.tasks_data:
            tid = td.get("id")
            if tid is not None:
                self.db.delete_task(tid)

    def undo(self) -> None:
        for td in self.tasks_data:
            self.db.insert_task_from_dict(td)


class AddTaskCommand(Command):
    """添加单个新任务。"""

    def __init__(self, db, task_data: dict):
        self.db = db
        self.task_data = task_data
        self.created_id: int | None = None
        self.description = "添加任务"

    def do(self) -> None:
        self.created_id = self.db.insert_task_from_dict(self.task_data)

    def undo(self) -> None:
        if self.created_id is not None:
            self.db.delete_task(self.created_id)


class UpdateProgressCommand(Command):
    """调整任务进度。"""

    def __init__(self, db, task_id: int, old_progress: int, new_progress: int):
        self.db = db
        self.task_id = task_id
        self.old_progress = old_progress
        self.new_progress = new_progress
        self.description = f"调整进度到 {new_progress}%"

    def do(self) -> None:
        self.db.update_task_fields(self.task_id, {"progress": self.new_progress})

    def undo(self) -> None:
        self.db.update_task_fields(self.task_id, {"progress": self.old_progress})


class DuplicateTaskCommand(Command):
    """复制（克隆）一个任务。"""

    def __init__(self, db, new_task_data: dict):
        self.db = db
        self.new_task_data = new_task_data
        self.duplicated_id: int | None = None
        self.description = "复制任务"

    def do(self) -> None:
        self.duplicated_id = self.db.insert_task_from_dict(self.new_task_data)

    def undo(self) -> None:
        if self.duplicated_id is not None:
            self.db.delete_task(self.duplicated_id)


# ═══════════════════════════════════════════════════════
#  UndoManager
# ═══════════════════════════════════════════════════════

class UndoManager:
    """命令模式撤销/重做管理器。

    维护两个栈：undo_stack 和 redo_stack。
    - execute(command) 执行命令并压入 undo_stack，清空 redo_stack。
    - undo() 从 undo_stack 弹出、执行撤销、压入 redo_stack。
    - redo() 从 redo_stack 弹出、执行重做、压入 undo_stack。
    """

    def __init__(self, max_history: int = 50):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_history = max_history

    # ── 核心操作 ──

    def execute(self, command: Command) -> None:
        """执行命令并压入撤销栈。"""
        command.do()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        # 超出历史上限时裁剪最旧的记录
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

    def undo(self) -> str | None:
        """撤销最近一次操作，返回操作描述或 None（无可撤销项）。"""
        if self._undo_stack:
            cmd = self._undo_stack.pop()
            cmd.undo()
            self._redo_stack.append(cmd)
            return cmd.description
        return None

    def redo(self) -> str | None:
        """重做最近一次撤销，返回操作描述或 None（无可重做项）。"""
        if self._redo_stack:
            cmd = self._redo_stack.pop()
            cmd.redo()
            self._undo_stack.append(cmd)
            return cmd.description
        return None

    # ── 查询 ──

    def can_undo(self) -> bool:
        """是否有可撤销的操作。"""
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        """是否有可重做的操作。"""
        return bool(self._redo_stack)

    def undo_description(self) -> str | None:
        """返回最近可撤销操作的描述。"""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return None

    def redo_description(self) -> str | None:
        """返回最近可重做操作的描述。"""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return None

    # ── 管理 ──

    def clear(self) -> None:
        """清空所有撤销/重做历史。"""
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)
