"""Technician management handlers — add / edit / delete technician slots."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.views.dialogs.technician_edit_dialog import TechnicianEditDialog

if TYPE_CHECKING:
    from main import MainWindow


class TechnicianHandlers:
    """Handles technician CRUD operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win._technician_view
        v.btn_add.clicked.connect(self._on_technician_add)
        v.btn_edit.clicked.connect(self._on_technician_edit)
        v.btn_delete.clicked.connect(self._on_technician_delete)

    def _on_technician_add(self) -> None:
        """新建技术员。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.technician_service:
            return
        dlg = TechnicianEditDialog(parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.technician_service.create(**data)
                self._win.toast(f"技术员「{data['name']}」已创建", "success")
                self._win._ctrl.notify_data_changed("technician")
            except Exception as e:
                QMessageBox.critical(self._win, "创建失败", f"保存失败: {e}")

    def _on_technician_edit(self) -> None:
        """编辑选中的技术员。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.technician_service:
            return
        tech = self._win._technician_view.get_selected_technician()
        if tech is None:
            self._win.toast("请先选中一个技术员", "info")
            return
        dlg = TechnicianEditDialog(technician=tech, parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            try:
                if tech.id is None:
                    raise ValueError("技术员 ID 不能为空")
                ctrl.technician_service.update(tech.id, **data)
                self._win.toast(f"技术员「{data['name']}」已更新", "success")
                self._win._ctrl.notify_data_changed("technician")
            except Exception as e:
                QMessageBox.critical(self._win, "更新失败", f"保存失败: {e}")

    def _on_technician_delete(self) -> None:
        """删除选中的技术员。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.technician_service:
            return
        tech = self._win._technician_view.get_selected_technician()
        if tech is None:
            self._win.toast("请先选中一个技术员", "info")
            return
        reply = QMessageBox.question(
            self._win,
            "确认删除",
            f"确定要删除技术员「{tech.name}」({tech.employee_id or tech.department}) 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if tech.id is None:
                raise ValueError("技术员 ID 不能为空")
            ctrl.technician_service.delete(tech.id)
            self._win.toast(f"技术员「{tech.name}」已删除", "success")
            self._win._ctrl.notify_data_changed("technician")
        except ValueError as e:
            QMessageBox.warning(self._win, "删除失败", str(e))
        except Exception as e:
            QMessageBox.critical(self._win, "删除失败", f"删除失败: {e}")