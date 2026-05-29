"""排程参数配置弹窗 -- 设置自动排程的参数。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QPushButton,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.styles.theme import (
    BASE,
    SURFACE0,
    SURFACE1,
    SURFACE2,
    MANTLE,
    TEXT,
    SUBTEXT0,
    SUBTEXT1,
    BLUE,
)
import src.styles.theme as _t
from src.views.dialogs.base_dialog import _BaseDialog


class _EquipmentRow(QWidget):
    """单行设备容量配置 (设备名 + 资产号 + 并行数)。"""

    def __init__(
        self,
        equipment_id: int,
        equipment_name: str,
        asset_no: str = "",
        capacity: int = 1,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._equipment_id = equipment_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 设备名（含资产号）
        display = f"{equipment_name} ({asset_no})" if asset_no else equipment_name
        name_label = QLabel(display)
        name_label.setMinimumWidth(120)
        name_label.setMaximumWidth(200)
        name_label.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        name_label.setToolTip(f"{equipment_name}\n{asset_no}" if asset_no else equipment_name)
        layout.addWidget(name_label)

        # 并行数
        self._spin = QSpinBox()
        self._spin.setRange(1, 20)
        self._spin.setValue(capacity)
        self._spin.setMinimumWidth(60)
        layout.addWidget(self._spin)

    @property
    def equipment_id(self) -> int:
        return self._equipment_id

    @property
    def capacity(self) -> int:
        return self._spin.value()


logger = logging.getLogger(__name__)


class ScheduleConfigDialog(_BaseDialog):
    """排程参数配置弹窗。

    Parameters
    ----------
    equipment_list :
        设备列表，用于生成设备并行数配置行。
        若为 None 或空列表则不显示设备容量配置区域。
    parent :
        父窗口。
    """

    def __init__(
        self,
        equipment_list: list | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("排程参数配置", parent=parent, width=480)

        self._equipment_rows: list[_EquipmentRow] = []

        # -- skip_weekends --
        self._chk_skip_weekends = QCheckBox("跳过周末")
        self._chk_skip_weekends.setChecked(True)
        self._form.addRow("排班规则", self._chk_skip_weekends)

        # -- skip_holidays --
        skip_holiday_row = QHBoxLayout()
        self._chk_skip_holidays = QCheckBox("跳过法定节假日")
        self._chk_skip_holidays.setChecked(True)
        skip_holiday_row.addWidget(self._chk_skip_holidays)

        self._btn_manage_holidays = QPushButton("管理...")
        self._btn_manage_holidays.setProperty("class", "action")
        self._btn_manage_holidays.clicked.connect(self._on_manage_holidays)
        self._chk_skip_holidays.toggled.connect(
            lambda checked: self._btn_manage_holidays.setEnabled(checked)
        )
        skip_holiday_row.addWidget(self._btn_manage_holidays)
        skip_holiday_row.addStretch()
        self._form.addRow(skip_holiday_row)

        # -- lock_existing --
        self._chk_lock_existing = QCheckBox("锁定已有排期")
        self._chk_lock_existing.setChecked(False)
        self._form.addRow("锁定规则", self._chk_lock_existing)

        # -- daily_start_limit --
        limit_row = QHBoxLayout()
        limit_label = QLabel("每日启动上限：")
        limit_label.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        limit_row.addWidget(limit_label)

        self._spin_daily_limit = QSpinBox()
        self._spin_daily_limit.setRange(0, 999)
        self._spin_daily_limit.setValue(0)
        self._spin_daily_limit.setSpecialValueText("不限")
        self._spin_daily_limit.setToolTip("每天最多启动的新测试项数，0 表示不限制")
        self._spin_daily_limit.setMinimumWidth(80)
        limit_row.addWidget(self._spin_daily_limit)

        limit_hint = QLabel("（0 = 不限制）")
        limit_hint.setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 11px;")
        limit_row.addWidget(limit_hint)
        limit_row.addStretch()
        self._form.addRow(limit_row)

        # -- deadline --
        self._deadline_edit = QLineEdit()
        self._deadline_edit.setPlaceholderText("YYYY-MM-DD（可选，留空不限）")
        self._form.addRow("截止日期", self._deadline_edit)

        # -- equipment_capacity --
        self._setup_equipment_section(equipment_list or [])

    # -- private helpers --

    def _setup_equipment_section(self, equipment_list: list) -> None:
        """构建设备容量配置区域。"""
        if not equipment_list:
            return

        self._add_separator()

        header = QLabel("设备并行数上限")
        header.setStyleSheet(
            f"color: {_t.BLUE}; font-size: 12px; font-weight: bold;"
        )
        self._form.addRow(header)

        for eq in equipment_list:
            eq_id = getattr(eq, "id", None)
            eq_name = getattr(eq, "name", str(eq_id))
            if eq_id is None:
                continue
            row = _EquipmentRow(eq_id, eq_name, asset_no=getattr(eq, "asset_no", ""), capacity=1)
            self._equipment_rows.append(row)
            self._form.addRow(row)

    # -- public API --

    def set_holiday_service(self, svc: object) -> None:
        """注入 HolidayService，供「管理...」按钮打开节假日管理弹窗。"""
        self._holiday_service = svc

    def _on_manage_holidays(self) -> None:
        """打开节假日管理弹窗。"""
        svc = getattr(self, "_holiday_service", None)
        if svc is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "节假日服务不可用。")
            return
        from src.views.dialogs.holiday_manage_dialog import HolidayManageDialog
        dlg = HolidayManageDialog(svc, parent=self)
        dlg.exec()
        dlg.deleteLater()

    def get_config(self) -> dict:
        """返回排程配置字典。

        Returns
        -------
        dict with keys:
            skip_weekends : bool
            lock_existing : bool
            deadline : str
            equipment_capacity : dict[int, int]
        """
        equipment_capacity: dict[int, int] = {}
        for row in self._equipment_rows:
            equipment_capacity[row.equipment_id] = row.capacity

        return {
            "skip_weekends": self._chk_skip_weekends.isChecked(),
            "skip_holidays": self._chk_skip_holidays.isChecked(),
            "lock_existing": self._chk_lock_existing.isChecked(),
            "daily_start_limit": self._spin_daily_limit.value(),
            "deadline": self._deadline_edit.text().strip(),
            "equipment_capacity": equipment_capacity,
        }

    def accept(self) -> None:
        """校验截止日期格式后关闭弹窗。"""
        deadline = self._deadline_edit.text().strip()
        if deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                QMessageBox.warning(
                    self, "格式错误",
                    "截止日期格式不正确，请使用 YYYY-MM-DD 格式。",
                )
                self._deadline_edit.setFocus()
                return

        super().accept()
