"""待办事项 Handler — 轻量 CRUD + 状态切换。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.handlers.crud_helpers import exec_crud
from src.views.dialogs.todo_edit_dialog import TodoEditDialog

if TYPE_CHECKING:
    from main import MainWindow

logger = logging.getLogger(__name__)


class TodoHandlers:
    """Handles todo CRUD operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win.todo_view
        v.btn_add.clicked.connect(self._on_todo_add)
        v.btn_edit.clicked.connect(self._on_todo_edit)
        v.btn_delete.clicked.connect(self._on_todo_delete)
        v.toggle_requested.connect(self._on_todo_toggle)

    def _on_todo_add(self) -> None:
        """新建待办事项。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        default_project = self._win.todo_view.get_selected_project_id()
        dlg = TodoEditDialog(
            parent=self._win,
            projects=ctrl.project_service.list_all() if ctrl.project_service else [],
            default_project_id=default_project,
        )
        if dlg.exec():
            data = dlg.get_data()
            exec_crud(
                win=self._win,
                action=ctrl.todo_service.create,
                action_kwargs=data,
                toast_msg=f"待办「{data.get('title', '')}」已创建",
                entity="todo",
                error_title="创建失败",
            )
        dlg.deleteLater()

    def _on_todo_edit(self) -> None:
        """编辑选中的待办事项。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        todo = self._win.todo_view.get_selected_todo()
        if todo is None:
            self._win.toast("请先选中一个待办事项", "info")
            return
        dlg = TodoEditDialog(
            todo=todo,
            parent=self._win,
            projects=ctrl.project_service.list_all() if ctrl.project_service else [],
        )
        try:
            if dlg.exec():
                data = dlg.get_data()
                if todo.id is None:
                    QMessageBox.warning(self._win, "更新失败", "Todo id is None")
                    return
                exec_crud(
                    win=self._win,
                    action=ctrl.todo_service.update,
                    action_args=(todo.id,),
                    action_kwargs=data,
                    toast_msg=f"待办「{data.get('title', '')}」已更新",
                    entity="todo",
                    error_title="更新失败",
                )
        finally:
            dlg.deleteLater()

    def _on_todo_delete(self) -> None:
        """删除选中的待办事项。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        todo = self._win.todo_view.get_selected_todo()
        if todo is None:
            self._win.toast("请先选中一个待办事项", "info")
            return
        reply = QMessageBox.question(
            self._win,
            "确认删除",
            f"确定要删除待办「{todo.title}」吗？\n此操作可通过 Ctrl+Z 撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if todo.id is None:
            QMessageBox.warning(self._win, "删除失败", "Todo id is None")
            return
        cmd = ctrl.todo_service.create_delete_command(todo.id)
        exec_crud(
            win=self._win,
            action=ctrl.todo_service.delete,
            action_args=(todo.id,),
            toast_msg=f"待办「{todo.title}」已删除",
            entity="todo",
            error_title="删除失败",
            catch_value_error=True,
            undo_command=cmd,
        )

    def _on_todo_toggle(self, todo_id: int) -> None:
        """切换待办状态。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        new_status = ctrl.todo_service.toggle_status(todo_id)
        if new_status:
            status_label = {
                "pending": "待处理", "in_progress": "进行中", "done": "已完成",
            }.get(new_status, new_status)
            self._win.toast(f"状态已切换为 {status_label}", "success")
            self._win.schedule_throttled_refresh("todo")
