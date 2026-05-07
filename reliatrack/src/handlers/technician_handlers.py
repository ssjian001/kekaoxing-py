"""Technician management handlers — add / edit / delete technician slots."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.services.import_service import import_technicians
from src.views.dialogs.batch_import_dialog import BatchImportDialog
from src.views.dialogs.technician_edit_dialog import TechnicianEditDialog

if TYPE_CHECKING:
    from main import MainWindow

logger = logging.getLogger(__name__)


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
        v.btn_import.clicked.connect(self._on_technician_import)

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

    def _on_technician_import(self) -> None:
        """批量导入技术员。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.technician_service:
            return

        field_map = [
            ("姓名（必填）", "name"),
            ("工号", "employee_id"),
            ("职位", "role"),
            ("部门", "department"),
            ("联系方式", "phone"),
            ("邮箱", "email"),
        ]
        required = ["name"]
        guess_keywords = {
            "name": ["姓名", "名字", "名称", "name", "技术员"],
            "employee_id": ["工号", "员工编号", "employee", "employee_id", "编号"],
            "role": ["职位", "岗位", "角色", "role"],
            "department": ["部门", "department", "dept"],
            "phone": ["联系方式", "电话", "手机", "phone", "tel"],
            "email": ["邮箱", "邮件", "email", "邮件地址"],
        }

        dlg = BatchImportDialog(
            parent=self._win,
            title="导入技术员",
            field_map=field_map,
            required_fields=required,
            guess_keywords=guess_keywords,
            result_msg_labels=("成功导入", "跳过（姓名为空或重复）"),
            on_import=lambda rows: import_technicians(rows, ctrl.technician_service),
        )
        dlg.exec()
        if dlg.was_imported():
            ctrl.notify_data_changed("technician")