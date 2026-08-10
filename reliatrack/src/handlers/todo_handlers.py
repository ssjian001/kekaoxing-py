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
        v.btn_edit.clicked.connect(self._on_todo_edit)
        v.btn_delete.clicked.connect(self._on_todo_delete)
        v.btn_archive.clicked.connect(self._on_todo_archive)
        v.quick_add_created.connect(self._on_todo_quick_add)
        v._direct_status_change.connect(self._on_todo_status_change)
        v.quadrant_changed.connect(self._on_todo_quadrant_changed)

    def _on_todo_quick_add(self, title: str, project_id: object) -> None:
        """快速添加待办（从顶部输入框）。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        data: dict[str, object] = {"title": title}
        if project_id is not None:
            data["project_id"] = project_id
        exec_crud(
            win=self._win,
            action=ctrl.todo_service.create,
            action_kwargs=data,
            toast_msg=f"待办「{title}」已创建",
            entity="todo",
            error_title="创建失败",
        )

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

    def _on_todo_archive(self) -> None:
        """归档或取消归档选中的待办。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        todo = self._win.todo_view.get_selected_todo()
        if todo is None:
            self._win.toast("请先选中一个待办事项", "info")
            return
        if todo.status != "done":
            self._win.toast("仅已完成的待办可以归档", "info")
            return
        if todo.id is None:
            return
        if todo.archived:
            ctrl.todo_service.unarchive(todo.id)
            self._win.toast(f"待办「{todo.title}」已取消归档", "success")
        else:
            ctrl.todo_service.archive(todo.id)
            self._win.toast(f"待办「{todo.title}」已归档", "success")
        self._win.schedule_throttled_refresh("todo")

    def _on_todo_status_change(self, todo_id: int, new_status: str) -> None:
        """看板拖拽后直接设置状态（非 toggle 循环）。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        todo = ctrl.todo_service.get(todo_id)
        if todo is None:
            return
        if todo.status == new_status:
            return
        ctrl.todo_service.update(todo_id, status=new_status)
        status_label = {"pending": "待处理", "in_progress": "进行中", "done": "已完成"}.get(new_status, new_status)
        self._win.toast(f"状态已更新为 {status_label}", "success")
        self._win.schedule_throttled_refresh("todo")

    def _on_todo_quadrant_changed(self, todo_id: int, new_quadrant: int) -> None:
        """四象限拖拽变更处理。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        ctrl.todo_service.update(todo_id, quadrant=new_quadrant)
        labels = {0: "未分类", 1: "重要紧急", 2: "重要不紧急", 3: "不重要紧急", 4: "不重要不紧急"}
        self._win.toast(f"象限已更新为 {labels.get(new_quadrant, '')}", "success")
        self._win.schedule_throttled_refresh("todo")
