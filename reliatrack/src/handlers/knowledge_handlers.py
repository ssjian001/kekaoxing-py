"""Knowledge base management handlers — add / edit / delete knowledge entries."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.handlers.crud_helpers import exec_crud
from src.views.dialogs.knowledge_edit_dialog import KnowledgeEditDialog

if TYPE_CHECKING:
    from main import MainWindow

logger = logging.getLogger(__name__)


class KnowledgeHandlers:
    """Handles knowledge base CRUD operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win._knowledge_view
        v.btn_add.clicked.connect(self._on_knowledge_add)
        v.btn_edit.clicked.connect(self._on_knowledge_edit)
        v.btn_delete.clicked.connect(self._on_knowledge_delete)

    def _on_knowledge_add(self) -> None:
        """新建知识条目。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        dlg = KnowledgeEditDialog(parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            exec_crud(
                win=self._win,
                action=ctrl.knowledge_service.create,
                action_kwargs=data,
                toast_msg=f"知识条目「{data['failure_mode']}」已创建",
                entity="knowledge",
                error_title="创建失败",
            )
        dlg.deleteLater()

    def _on_knowledge_edit(self) -> None:
        """编辑选中的知识条目。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        entry = self._win._knowledge_view.get_selected_entry()
        if entry is None:
            self._win.toast("请先选中一个知识条目", "info")
            return
        dlg = KnowledgeEditDialog(entry=entry, parent=self._win)
        try:
            if dlg.exec():
                data = dlg.get_data()
                if entry.id is None:
                    QMessageBox.warning(self._win, "更新失败", "Knowledge entry id is None")
                    return
                exec_crud(
                    win=self._win,
                    action=ctrl.knowledge_service.update,
                    action_args=(entry.id,),
                    action_kwargs=data,
                    toast_msg=f"知识条目「{data['failure_mode']}」已更新",
                    entity="knowledge",
                    error_title="更新失败",
                )
        finally:
            dlg.deleteLater()

    def _on_knowledge_delete(self) -> None:
        """删除选中的知识条目。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        entry = self._win._knowledge_view.get_selected_entry()
        if entry is None:
            self._win.toast("请先选中一个知识条目", "info")
            return
        reply = QMessageBox.question(
            self._win,
            "确认删除",
            f"确定要删除知识条目「{entry.failure_mode}」({entry.category}) 吗？\n此操作可通过 Ctrl+Z 撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if entry.id is None:
            QMessageBox.warning(self._win, "删除失败", "Knowledge entry id is None")
            return
        cmd = ctrl.knowledge_service.create_delete_command(entry.id)
        exec_crud(
            win=self._win,
            action=ctrl.knowledge_service.delete,
            action_args=(entry.id,),
            toast_msg=f"知识条目「{entry.failure_mode}」已删除",
            entity="knowledge",
            error_title="删除失败",
            catch_value_error=True,
            undo_command=cmd,
        )
