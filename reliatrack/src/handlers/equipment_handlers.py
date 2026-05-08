"""Equipment management handlers — add / edit / delete equipment slots."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.services.import_service import import_equipment
from src.views.dialogs.batch_import_dialog import BatchImportDialog
from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

if TYPE_CHECKING:
    from main import MainWindow

logger = logging.getLogger(__name__)


class EquipmentHandlers:
    """Handles equipment CRUD operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win._equipment_view
        v.btn_add.clicked.connect(self._on_equipment_add)
        v.btn_edit.clicked.connect(self._on_equipment_edit)
        v.btn_delete.clicked.connect(self._on_equipment_delete)
        v.btn_import.clicked.connect(self._on_equipment_import)

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
                self._win.toast(f"设备「{data['name']}」已创建", "success")
                self._win._ctrl.notify_data_changed("equipment")
            except Exception as e:
                logger.exception("创建失败")
                QMessageBox.critical(self._win, "创建失败", f"保存失败: {e}")

    def _on_equipment_edit(self) -> None:
        """编辑选中的设备。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        eq = self._win._equipment_view.get_selected_equipment()
        if eq is None:
            self._win.toast("请先选中一个设备", "info")
            return
        dlg = EquipmentEditDialog(equipment=eq, parent=self._win)
        if dlg.exec():
            data = dlg.get_data()
            try:
                if eq.id is None:
                    raise ValueError("Equipment id is None")
                ctrl.equipment_service.update(eq.id, **data)
                self._win.toast(f"设备「{data['name']}」已更新", "success")
                self._win._ctrl.notify_data_changed("equipment")
            except Exception as e:
                logger.exception("更新失败")
                QMessageBox.critical(self._win, "更新失败", f"保存失败: {e}")

    def _on_equipment_delete(self) -> None:
        """删除选中的设备。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        eq = self._win._equipment_view.get_selected_equipment()
        if eq is None:
            self._win.toast("请先选中一个设备", "info")
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
            if eq.id is None:
                raise ValueError("Equipment id is None")
            ctrl.equipment_service.delete(eq.id)
            self._win.toast(f"设备「{eq.name}」已删除", "success")
            self._win._ctrl.notify_data_changed("equipment")
        except ValueError as e:
            QMessageBox.warning(self._win, "删除失败", str(e))
        except Exception as e:
            logger.exception("删除失败")
            QMessageBox.critical(self._win, "删除失败", f"删除失败: {e}")

    def _on_equipment_import(self) -> None:
        """批量导入设备。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return

        field_map = [
            ("设备名称（必填）", "name"),
            ("资产编号", "asset_no"),
            ("设备类型", "type"),
            ("型号", "model"),
            ("制造商", "manufacturer"),
            ("精度/不确定度", "accuracy"),
            ("存放位置", "location"),
            ("状态", "status"),
            ("校准日期", "calibration_date"),
            ("下次校准日期", "next_calibration_date"),
        ]
        required = ["name"]
        guess_keywords = {
            "name": ["名称", "设备名称", "设备名", "name", "设备"],
            "asset_no": ["资产编号", "asset", "asset_no", "资产号", "编号"],
            "type": ["类型", "设备类型", "type", "类别"],
            "model": ["型号", "model", "规格"],
            "manufacturer": ["制造商", "厂家", "manufacturer", "生产厂", "供应商"],
            "accuracy": ["精度", "不确定度", "accuracy", "准确度"],
            "location": ["位置", "存放位置", "库位", "location"],
            "status": ["状态", "status", "设备状态"],
            "calibration_date": ["校准日期", "校准", "calibration", "calibration_date"],
            "next_calibration_date": ["下次校准", "next", "next_calibration", "下次校准日期"],
        }

        dlg = BatchImportDialog(
            parent=self._win,
            title="导入设备",
            field_map=field_map,
            required_fields=required,
            guess_keywords=guess_keywords,
            result_msg_labels=("成功导入", "跳过（名称空或重复）"),
            on_import=lambda rows: import_equipment(rows, ctrl.equipment_service),
        )
        dlg.exec()
        if dlg.was_imported():
            ctrl.notify_data_changed("equipment")