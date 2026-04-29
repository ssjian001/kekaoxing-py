"""技术员编辑弹窗 — 新建 / 编辑 Technician。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)

from src.models.common import Technician
from src.views.dialogs.base_dialog import _BaseDialog


class TechnicianEditDialog(_BaseDialog):
    """技术员新建 / 编辑弹窗。

    Parameters
    ----------
    technician:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    """

    _DEPARTMENTS = ["测试部", "研发部", "质量部", "其他"]

    def __init__(
        self,
        technician: Technician | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = technician is not None
        super().__init__(
            "编辑技术员" if is_edit else "新建技术员",
            parent,
            width=420,
        )
        self._technician = technician

        # ── 基本信息 ──
        self._name_edit = self._add_text_field(
            "姓名 *",
            default=technician.name if technician else "",
            placeholder="必填",
        )
        self._employee_id_edit = self._add_text_field(
            "工号",
            default=technician.employee_id if technician else "",
            placeholder="如：EMP001",
        )
        self._department_combo = self._add_combo_field(
            "部门",
            items=self._DEPARTMENTS,
            default=technician.department if technician else self._DEPARTMENTS[0],
        )
        self._role_edit = self._add_text_field(
            "职位",
            default=technician.role if technician else "",
            placeholder="如：DQE / QE / 测试员",
        )
        self._phone_edit = self._add_text_field(
            "联系方式",
            default=technician.phone if technician else "",
            placeholder="手机号或分机号",
        )
        self._email_edit = self._add_text_field(
            "邮箱",
            default=technician.email if technician else "",
            placeholder="如：zhangsan@company.com",
        )

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        return {
            "name": self._name_edit.text().strip(),
            "employee_id": self._employee_id_edit.text().strip(),
            "department": self._department_combo.currentText(),
            "role": self._role_edit.text().strip(),
            "phone": self._phone_edit.text().strip(),
            "email": self._email_edit.text().strip(),
        }

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "校验失败", "姓名为必填项，请输入。")
            self._name_edit.setFocus()
            return
        super().accept()
