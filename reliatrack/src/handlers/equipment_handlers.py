"""Equipment management handlers — add / edit / delete equipment slots."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

if TYPE_CHECKING:
    from main import MainWindow


class EquipmentHandlers:
    """Handles equipment CRUD operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def _on_equipment_add(self) -> None:
        """新建设备。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        dlg = EquipmentEditDialog(parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.equipment_service.create(**data)
                self._win.statusBar().showMessage(
                    f"✅ 设备「{data['name']}」已创建", 5000
                )
                self._win._ctrl.notify_data_changed("equipment")
            except Exception as e:
                QMessageBox.critical(self._win, "创建失败", f"保存失败: {e}")

    def _on_equipment_edit(self) -> None:
        """编辑选中的设备。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        eq = self._win._equipment_view.get_selected_equipment()
        if eq is None:
            self._win.statusBar().showMessage("⚠️ 请先选中一个设备", 5000)
            return
        dlg = EquipmentEditDialog(equipment=eq, parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            try:
                assert eq.id is not None
                ctrl.equipment_service.update(eq.id, **data)
                self._win.statusBar().showMessage(
                    f"✅ 设备「{data['name']}」已更新", 5000
                )
                self._win._ctrl.notify_data_changed("equipment")
            except Exception as e:
                QMessageBox.critical(self._win, "更新失败", f"保存失败: {e}")

    def _on_equipment_delete(self) -> None:
        """删除选中的设备。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        eq = self._win._equipment_view.get_selected_equipment()
        if eq is None:
            self._win.statusBar().showMessage("⚠️ 请先选中一个设备", 5000)
            return
        reply = QMessageBox.question(
            self._win,
            "确认删除",
            f"确定要删除设备「{eq.name}」({eq.model}) 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            assert eq.id is not None
            ctrl.equipment_service.delete(eq.id)
            self._win.statusBar().showMessage(
                f"✅ 设备「{eq.name}」已删除", 5000
            )
            self._win._ctrl.notify_data_changed("equipment")
        except ValueError as e:
            QMessageBox.warning(self._win, "删除失败", str(e))
        except Exception as e:
            QMessageBox.critical(self._win, "删除失败", f"删除失败: {e}")
