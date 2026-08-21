"""设备编辑弹窗 — 新建 / 编辑 Equipment。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)
from PySide6.QtCore import QDate

from src.models.common import Equipment
from src.views.dialogs.base_dialog import _BaseDialog


class EquipmentEditDialog(_BaseDialog):
    """设备新建 / 编辑弹窗。

    Parameters
    ----------
    equipment:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    """

    _EQUIPMENT_TYPES = ["温度箱", "振动台", "湿热箱", "盐雾箱", "其他"]
    _STATUS_OPTIONS = ["正常", "维修中", "停用"]
    _STATUS_MAP = {
        "正常": "available",
        "维修中": "maintenance",
        "停用": "offline",
    }
    _STATUS_REVERSE = {v: k for k, v in _STATUS_MAP.items()}

    def __init__(
        self,
        equipment: Equipment | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = equipment is not None
        super().__init__(
            "编辑设备" if is_edit else "新建设备",
            parent,
            width=440,
        )
        self._equipment = equipment

        # ── 基本信息 ──
        self._name_edit = self._add_text_field(
            "设备名称 *",
            default=equipment.name if equipment else "",
            placeholder="必填",
        )
        self._model_edit = self._add_text_field(
            "设备编号",
            default=equipment.model if equipment else "",
            placeholder="如：TH-001",
        )
        self._type_combo = self._add_combo_field(
            "设备类型",
            items=self._EQUIPMENT_TYPES,
            default=equipment.type if equipment else self._EQUIPMENT_TYPES[0],
        )

        self._add_separator()

        # ── 资产信息 ──
        self._asset_no_edit = self._add_text_field(
            "资产编号",
            default=equipment.asset_no if equipment else "",
            placeholder="资产编号",
        )
        self._manufacturer_edit = self._add_text_field(
            "制造商",
            default=equipment.manufacturer if equipment else "",
            placeholder="制造商",
        )
        self._accuracy_edit = self._add_text_field(
            "精度/不确定度",
            default=equipment.accuracy if equipment else "",
            placeholder="精度/不确定度",
        )
        self._location_edit = self._add_text_field(
            "存放位置",
            default=equipment.location if equipment else "",
            placeholder="如：实验室 A-01",
        )

        self._add_separator()

        # ── 校准信息 ──
        # 「未校准」开关（审计 #6）：QDateEdit 无法表达"空"，默认今天会被
        # get_data 当成真实校准日期写库（自动伪造）。勾选 = 显式无校准数据。
        self._never_calibrated_chk = self._add_checkbox_field(
            "未校准（无校准记录）",
            checked=not (equipment and equipment.calibration_date),
        )
        self._calibration_edit = self._add_date_field("校准日期")
        if equipment and equipment.calibration_date:
            d = QDate.fromString(equipment.calibration_date, "yyyy-MM-dd")
            if d.isValid():
                self._calibration_edit.setDate(d)
            else:
                self._calibration_edit.clear()

        self._next_calibration_edit = self._add_date_field("下次校准日期")
        if equipment and equipment.next_calibration_date:
            d = QDate.fromString(equipment.next_calibration_date, "yyyy-MM-dd")
            if d.isValid():
                self._next_calibration_edit.setDate(d)
            else:
                self._next_calibration_edit.clear()

        self._interval_spin = self._add_spin_field(
            "校准间隔(月)",
            min_val=1,
            max_val=60,
            default=equipment.calibration_interval_months if equipment else 12,
        )
        # 初始联动 + 勾选切换时禁用/启用日期与间隔输入
        self._on_never_calibrated_toggled(self._never_calibrated_chk.isChecked())
        self._never_calibrated_chk.toggled.connect(self._on_never_calibrated_toggled)

        self._add_separator()

        # ── 状态 ──
        status_label = self._STATUS_REVERSE.get(
            equipment.status, "正常"
        ) if equipment else "正常"
        self._status_combo = self._add_combo_field(
            "设备状态",
            items=self._STATUS_OPTIONS,
            default=status_label,
        )

    # ── 公开 API ───────────────────────────────────────────────

    def _on_never_calibrated_toggled(self, checked: bool) -> None:
        """勾选「未校准」时禁用校准日期相关输入，语义显式化。"""
        self._calibration_edit.setEnabled(not checked)
        self._next_calibration_edit.setEnabled(not checked)
        self._interval_spin.setEnabled(not checked)

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        # 未校准 = 显式空数据，不伪造日期（审计 #6）
        if self._never_calibrated_chk.isChecked():
            return {
                "name": self._name_edit.text().strip(),
                "model": self._model_edit.text().strip(),
                "type": self._type_combo.currentText(),
                "asset_no": self._asset_no_edit.text().strip(),
                "manufacturer": self._manufacturer_edit.text().strip(),
                "accuracy": self._accuracy_edit.text().strip(),
                "location": self._location_edit.text().strip(),
                "calibration_date": "",
                "next_calibration_date": "",
                "calibration_interval_months": 12,
                "status": self._STATUS_MAP.get(self._status_combo.currentText(), "available"),
            }

        cal_date = ""
        if self._calibration_edit.date().isValid():
            cal_date = self._calibration_edit.date().toString("yyyy-MM-dd")

        next_cal_date = ""
        if self._next_calibration_edit.date().isValid():
            next_cal_date = self._next_calibration_edit.date().toString("yyyy-MM-dd")

        # 自动计算下次校准：如果没手动填，则用校准日期 + 间隔
        interval = self._interval_spin.value()
        if not next_cal_date and cal_date:
            cal_qdate = self._calibration_edit.date()
            next_qdate = cal_qdate.addMonths(interval)
            next_cal_date = next_qdate.toString("yyyy-MM-dd")

        status_label = self._status_combo.currentText()
        return {
            "name": self._name_edit.text().strip(),
            "model": self._model_edit.text().strip(),
            "type": self._type_combo.currentText(),
            "asset_no": self._asset_no_edit.text().strip(),
            "manufacturer": self._manufacturer_edit.text().strip(),
            "accuracy": self._accuracy_edit.text().strip(),
            "location": self._location_edit.text().strip(),
            "calibration_date": cal_date,
            "next_calibration_date": next_cal_date,
            "calibration_interval_months": interval,
            "status": self._STATUS_MAP.get(status_label, "available"),
        }

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "校验失败", "设备名称为必填项，请输入。")
            self._name_edit.setFocus()
            return

        super().accept()
