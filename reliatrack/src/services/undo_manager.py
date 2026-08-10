"""撤销/重做框架 — 基于命令模式 (Command Pattern)。

适配 ReliaTrack Repository 层，不再直接操作旧 Database 对象。

用法:
    undo_mgr = UndoManager()
    undo_mgr.execute(MoveTaskCommand(task_repo, task_id, old_day, new_day))
    undo_mgr.undo()
    undo_mgr.redo()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Command 基类
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
#  通用字段更新命令
# ═══════════════════════════════════════════════════════════════════

class UpdateFieldCommand(Command):
    """更新任意实体的指定字段（通用版）。"""

    def __init__(
        self,
        repo: Any,
        entity_id: int,
        field: str,
        old_value: Any,
        new_value: Any,
        entity_name: str = "实体",
    ):
        self._repo = repo
        self._entity_id = entity_id
        self._field = field
        self._old_value = old_value
        self._new_value = new_value
        self.description = f"更新{entity_name} {field}"

    def do(self) -> None:
        self._repo.update(self._entity_id, **{self._field: self._new_value})

    def undo(self) -> None:
        self._repo.update(self._entity_id, **{self._field: self._old_value})


class MoveTaskCommand(UpdateFieldCommand):
    """移动任务到新的开始天。"""

    def __init__(self, task_repo: Any, task_id: int, old_day: int, new_day: int):
        super().__init__(task_repo, task_id, "start_day", old_day, new_day, "任务")
        self.description = f"移动任务到第{new_day}天"


class UpdateProgressCommand(UpdateFieldCommand):
    """调整任务进度。"""

    def __init__(self, task_repo: Any, task_id: int, old_progress: float, new_progress: float):
        super().__init__(task_repo, task_id, "progress", old_progress, new_progress, "任务")
        self.description = f"调整进度到 {new_progress}%"


class UpdateTaskStatusCommand(UpdateFieldCommand):
    """更新任务状态。"""

    def __init__(self, task_repo: Any, task_id: int, old_status: str, new_status: str):
        super().__init__(task_repo, task_id, "status", old_status, new_status, "任务")
        self.description = f"更新任务状态为 {new_status}"


# ═══════════════════════════════════════════════════════════════════
#  增删命令
# ═══════════════════════════════════════════════════════════════════

class AddEntityCommand(Command):
    """添加实体（通用版）。"""

    def __init__(self, repo: Any, data: dict[str, Any], entity_name: str = "实体"):
        self._repo = repo
        self._data = data
        self._created_id: int | None = None
        self.description = f"添加{entity_name}"
        self._entity_name = entity_name

    def do(self) -> None:
        self._created_id = self._repo.insert(**self._data)

    def undo(self) -> None:
        if self._created_id is not None:
            self._repo.delete(self._created_id)


class BatchScheduleCommand(Command):
    """批量更新任务排程（支持撤销/重做整个排程操作）。"""

    def __init__(self, task_repo: Any, changes: list[tuple[int, int, int]]) -> None:
        """
        Parameters
        ----------
        task_repo : TestTaskRepository
            任务仓库。
        changes : list[tuple[int, int, int]]
            [(task_id, old_start_day, new_start_day), ...]
        """
        self._task_repo = task_repo
        self._changes = changes
        self.description = "自动排程"

    def do(self) -> None:
        """执行所有 new_start_day 更新。"""
        updates = [(tid, new_day) for tid, _old, new_day in self._changes]
        if updates:
            self._task_repo.bulk_update_start_day(updates)

    def undo(self) -> None:
        """恢复所有 old_start_day。"""
        restores = [(tid, old_day) for tid, old_day, _new in self._changes]
        if restores:
            self._task_repo.bulk_update_start_day(restores)

    def redo(self) -> None:
        """重新执行 new_start_day 更新。"""
        self.do()


class DeleteEntityCommand(Command):
    """删除实体并保存数据用于恢复。

    撤销时恢复原始 ID，保持关联数据（如 issues.task_id）的引用完整性。
    """

    def __init__(self, repo: Any, entity_id: int, entity_name: str = "实体",
                 _cascade_children: bool = False):
        self._repo = repo
        self._entity_id = entity_id
        self._entity_name = entity_name
        self._cascade_children = _cascade_children
        # 先读取当前数据用于撤销恢复
        entity = repo.get_by_id(entity_id)
        self._saved_data: dict[str, Any] = {}
        if entity:
            # 保留 id 用于恢复时显式插入，保证关联数据不断裂
            self._saved_data = {
                k: v for k, v in entity.__dict__.items()
            }
        self.description = f"删除{entity_name}"

    def do(self) -> None:
        self._repo.delete(self._entity_id)

    def undo(self) -> None:
        if self._cascade_children:
            logger.warning(
                "DeleteEntityCommand.undo: entity=%s id=%d had cascade children; "
                "parent record will be restored but child references may have been "
                "set to NULL by ON DELETE SET NULL",
                self._entity_name, self._entity_id,
            )
        if self._saved_data and self._saved_data.get("id") is not None:
            # 检查原 ID 是否已被新记录占用
            existing = self._repo.get_by_id(self._saved_data["id"])
            if existing is not None:
                # ID 冲突：不传 id，让 autoincrement 分配新 ID
                safe_data = {k: v for k, v in self._saved_data.items() if k != "id"}
                self._repo.insert(**safe_data)
                logger.warning(
                    "DeleteEntityCommand.undo: original id=%d already occupied, "
                    "re-inserted with auto-generated id",
                    self._saved_data["id"],
                )
            else:
                # 显式插入原始 ID，保持外键引用完整性
                self._repo.insert(**self._saved_data)


# ═══════════════════════════════════════════════════════════════════
#  复合命令
# ═══════════════════════════════════════════════════════════════════

class MacroCommand(Command):
    """复合命令 — 封装多个子命令，undo/redo 倒序执行。"""

    def __init__(self, commands: list[Command], description: str = ""):
        self._commands = list(commands)
        self.description = description or f"复合操作({len(commands)}步)"

    def do(self) -> None:
        for cmd in self._commands:
            cmd.do()

    def undo(self) -> None:
        for cmd in reversed(self._commands):
            cmd.undo()

    def redo(self) -> None:
        for cmd in self._commands:
            cmd.redo() if hasattr(cmd, 'redo') else cmd.do()


class BatchEditSamplesCommand(Command):
    """批量编辑样品字段（支持撤销/重做）。

    在一个事务中更新多个样品的多个字段。
    """

    def __init__(
        self,
        sample_repo: Any,
        changes: list[tuple[int, dict[str, Any], dict[str, Any]]],
    ) -> None:
        """
        Parameters
        ----------
        sample_repo : SampleRepository
            样品仓库。
        changes : list[tuple[int, dict, dict]]
            [(sample_id, {field: old_value}, {field: new_value}), ...]
        """
        self._repo = sample_repo
        self._changes = changes
        self.description = f"批量编辑 {len(changes)} 个样品"

    def do(self) -> None:
        """执行所有字段更新。"""
        for sample_id, _old, new_vals in self._changes:
            self._repo.update(sample_id, **new_vals)

    def undo(self) -> None:
        """恢复所有旧值。"""
        for sample_id, old_vals, _new in self._changes:
            self._repo.update(sample_id, **old_vals)

    def redo(self) -> None:
        """重新执行更新。"""
        self.do()


class SoftDeleteCommand(Command):
    """软删除实体（标记 is_deleted=1），撤销时恢复。

    适用于实现了 soft_delete() 和 restore() 方法的 Repository（如 IssueRepository）。
    """

    def __init__(self, repo: Any, entity_id: int, entity_name: str = "实体"):
        if not (hasattr(repo, "soft_delete") and hasattr(repo, "restore")):
            raise TypeError(
                f"SoftDeleteCommand requires a repository with "
                f"soft_delete/restore methods, got {type(repo).__name__}"
            )
        self._repo = repo
        self._entity_id = entity_id
        self._entity_name = entity_name
        self.description = f"删除{entity_name}"

    def do(self) -> None:
        self._repo.soft_delete(self._entity_id)

    def undo(self) -> None:
        self._repo.restore(self._entity_id)

    def redo(self) -> None:
        self.do()


class TransitionIssueStatusCommand(Command):
    """Issue 状态转换命令（看板拖拽/UI 触发，可撤销）。

    do() 通过 service.transition_status() 执行完整校验（状态机+FA记录+resolution）。
    undo() 直接回写旧状态（跳过校验——回到合法历史状态）并记录撤销日志。
    """

    def __init__(self, service: Any, issue_id: int,
                 old_status: str, new_status: str, operator: str = "") -> None:
        self._service = service
        self._issue_id = issue_id
        self._old_status = old_status
        self._new_status = new_status
        self._operator = operator
        self.description = f"Issue #{issue_id}: {old_status} → {new_status}"

    def do(self) -> None:
        self._service.transition_status(self._issue_id, self._new_status,
                                         operator=self._operator)

    def undo(self) -> None:
        # 直接回写旧状态 + 标记撤销来源
        self._service.update(self._issue_id,
                             operator=f"{self._operator}(undo)",
                             status=self._old_status)

    def redo(self) -> None:
        self.do()


# ═══════════════════════════════════════════════════════════════════
#  UndoManager
# ═══════════════════════════════════════════════════════════════════

class UndoManager:
    """命令模式撤销/重做管理器。

    维护两个栈：undo_stack 和 redo_stack。
    - execute(command) 执行命令并压入 undo_stack，清空 redo_stack。
    - undo() 从 undo_stack 弹出、执行撤销、压入 redo_stack。
    - redo() 从 redo_stack 弹出、执行重做、压入 undo_stack。
    """

    def __init__(self, max_history: int = 50) -> None:
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_history = max_history

    def execute(self, command: Command) -> None:
        """执行命令并压入撤销栈。

        若 do() 抛异常，命令不入栈（保持栈一致性），异常向上传播由调用方处理。
        """
        command.do()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

    def record(self, command: Command) -> None:
        """记录已执行的命令（不重复执行 do()），清空 redo_stack。

        用于命令的 do() 已在外部执行（如 list_view 批量操作更新 DB），
        只需入栈 + 清空 redo_stack 的场景。
        """
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

    def undo(self) -> str | None:
        """撤销最近一次操作，返回操作描述或 None。

        undo() 失败时命令压回 undo 栈（不丢失、可重试），异常向上传播。
        """
        if self._undo_stack:
            cmd = self._undo_stack[-1]
            try:
                cmd.undo()
            except Exception:
                logger.exception("Undo failed for command: %s", getattr(cmd, "description", cmd))
                raise
            self._undo_stack.pop()
            self._redo_stack.append(cmd)
            return cmd.description
        return None

    def redo(self) -> str | None:
        """重做最近一次撤销，返回操作描述或 None。

        redo() 失败时命令压回 redo 栈（不丢失、可重试），异常向上传播。
        """
        if self._redo_stack:
            cmd = self._redo_stack[-1]
            try:
                cmd.redo()
            except Exception:
                logger.exception("Redo failed for command: %s", getattr(cmd, "description", cmd))
                raise
            self._redo_stack.pop()
            self._undo_stack.append(cmd)
            return cmd.description
        return None

    def peek_undo(self) -> Command | None:
        """查看 undo 栈顶命令但不弹出。"""
        return self._undo_stack[-1] if self._undo_stack else None

    def peek_redo(self) -> Command | None:
        """查看 redo 栈顶命令但不弹出。"""
        return self._redo_stack[-1] if self._redo_stack else None

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo_description(self) -> str | None:
        return self._undo_stack[-1].description if self._undo_stack else None

    def redo_description(self) -> str | None:
        return self._redo_stack[-1].description if self._redo_stack else None

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)
