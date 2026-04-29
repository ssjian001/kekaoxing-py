"""排程参数配置弹窗 -- 设置自动排程的参数。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from src.views.dialogs.base_dialog import _BaseDialog


class _EquipmentRow(QWidget):
    """单行设备容量配置 (设备名 + 并行数)。"""

    def __init__(
        self,
        equipment_id: int,
        equipment_name: str,
        capacity: int = 1,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._equipment_id = equipment_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 设备名（只读）
        name_label = QLabel(equipment_name)
        name_label.setMinimumWidth(120)
        name_label.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
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
        self._form.addRow(self._chk_skip_weekends)

        # -- lock_existing --
        self._chk_lock_existing = QCheckBox("锁定已有排期")
        self._chk_lock_existing.setChecked(False)
        self._form.addRow(self._chk_lock_existing)

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
            f"color: {BLUE}; font-size: 12px; font-weight: bold;"
        )
        self._form.addRow(header)

        for eq in equipment_list:
            eq_id = getattr(eq, "id", None)
            eq_name = getattr(eq, "name", str(eq_id))
            if eq_id is None:
                continue
            row = _EquipmentRow(eq_id, eq_name, capacity=1)
            self._equipment_rows.append(row)
            self._form.addRow(row)

    # -- public API --

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
            "lock_existing": self._chk_lock_existing.isChecked(),
            "deadline": self._deadline_edit.text().strip(),
            "equipment_capacity": equipment_capacity,
        }

    def accept(self) -> None:
        """校验截止日期格式后关闭弹窗。"""
        deadline = self._deadline_edit.text().strip()
        if deadline:
            try:
                from datetime import datetime
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "格式错误",
                    "截止日期格式不正确，请使用 YYYY-MM-DD 格式。",
                )
                self._deadline_edit.setFocus()
                return

        super().accept()
