"""Project management handlers — add / edit / delete project slots."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.views.dialogs.project_edit_dialog import ProjectEditDialog

if TYPE_CHECKING:
    from main import MainWindow
    from src.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class ProjectHandlers:
    """Handles project CRUD operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        win._project_view.btn_add.clicked.connect(self._on_project_add)
        win._project_view.btn_edit.clicked.connect(self._on_project_edit)
        win._project_view.btn_delete.clicked.connect(self._on_project_delete)

    @staticmethod
    def _cascade_message(service: "ProjectService", project_id: int) -> str:
        """生成级联删除影响的统计描述。"""
        try:
            stats = service.cascade_stats(project_id)
        except Exception:
            return "关联数据将一并删除。\n"
        total = sum(stats.values())
        if total == 0:
            return ""
        parts = []
        labels = {"plans": "个测试计划", "tasks": "个任务", "samples": "个样品", "issues": "个 Issue"}
        for key, label in labels.items():
            if stats[key]:
                parts.append(f"{stats[key]} {label}")
        return f"将同时删除：{'、'.join(parts)}。\n"

    def _on_project_add(self) -> None:
        """新建项目。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.project_service:
            return
        dlg = ProjectEditDialog(parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.project_service.create(**data)
                self._win.toast(f"项目「{data['name']}」已创建", "success")
                self._win._ctrl.notify_data_changed("project")
            except Exception as e:
                logger.exception("创建失败")
                QMessageBox.critical(self._win, "创建失败", f"保存失败: {e}")

    def _on_project_edit(self) -> None:
        """编辑选中的项目。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.project_service:
            return
        proj = self._win._project_view.get_selected_project()
        if proj is None:
            self._win.toast("请先选中一个项目", "info")
            return
        dlg = ProjectEditDialog(project=proj, parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            proj_id = data.get("id")
            if proj_id is None:
                return
            update_data = {k: v for k, v in data.items() if k != "id"}
            try:
                ctrl.project_service.update(proj_id, **update_data)
                self._win.toast(f"项目「{data['name']}」已更新", "success")
                self._win._ctrl.notify_data_changed("project")
            except Exception as e:
                logger.exception("更新失败")
                QMessageBox.critical(self._win, "更新失败", f"保存失败: {e}")

    def _on_project_delete(self) -> None:
        """删除选中的项目。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.project_service:
            return
        proj = self._win._project_view.get_selected_project()
        if proj is None:
            self._win.toast("请先选中一个项目", "info")
            return
        reply = QMessageBox.question(
            self._win,
            "确认删除",
            f"确定要删除项目「{proj.name}」吗？\n"
            + self._cascade_message(ctrl.project_service, proj.id)
            + "此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if proj.id is None:
                raise ValueError("Project id is None")
            ctrl.project_service.delete(proj.id)
            self._win.toast(f"项目「{proj.name}」已删除", "success")
            self._win._ctrl.notify_data_changed("project")
        except ValueError as e:
            QMessageBox.warning(self._win, "删除失败", str(e))
        except Exception as e:
            logger.exception("删除失败")
            QMessageBox.critical(self._win, "删除失败", f"删除失败: {e}")