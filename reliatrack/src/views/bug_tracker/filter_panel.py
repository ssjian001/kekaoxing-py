"""可折叠的 Issue 筛选面板 — FilterPanel。"""

from __future__ import annotations

import logging

logger = logging.getLogger("views.bug_tracker.filter_panel")

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.constants import (
    ISSUE_STATUS_OPTIONS,
    SEVERITY_UI_OPTIONS,
    PRIORITY_UI_OPTIONS,
)
from src.styles.constants import PADDING_SMALL


class FilterPanel(QFrame):
    """可折叠的筛选面板 — 状态/严重度/优先级/DRI/日期范围。"""

    filter_changed = Signal(dict)  # filters: dict

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "filter-panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_SMALL, PADDING_SMALL, PADDING_SMALL, PADDING_SMALL)
        layout.setSpacing(4)

        # ── 第一行: 状态/严重度/优先级 (checkbox 组，横向) ──
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # 状态
        row1.addWidget(self._make_group_label("状态"))
        self._status_checks: dict[str, QCheckBox] = {}
        for eng, chn in ISSUE_STATUS_OPTIONS:
            cb = QCheckBox(chn)
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[eng] = cb
            row1.addWidget(cb)

        row1.addSpacing(8)

        # 严重度
        row1.addWidget(self._make_group_label("严重度"))
        self._severity_checks: dict[str, QCheckBox] = {}
        for eng, chn in SEVERITY_UI_OPTIONS:
            cb = QCheckBox(chn)
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filter)
            self._severity_checks[eng] = cb
            row1.addWidget(cb)

        row1.addSpacing(8)

        # 优先级
        row1.addWidget(self._make_group_label("优先级"))
        self._priority_checks: dict[int, QCheckBox] = {}
        for pri, chn in PRIORITY_UI_OPTIONS:
            cb = QCheckBox(chn)
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filter)
            self._priority_checks[pri] = cb
            row1.addWidget(cb)

        row1.addStretch()
        layout.addLayout(row1)

        # ── 第二行: DRI / 日期范围 / 清空 ──
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(self._make_group_label("DRI"))
        self._dri_combo = QComboBox()
        self._dri_combo.setProperty("class", "filter-combo")
        self._dri_combo.setMinimumWidth(100)
        self._dri_combo.addItem("全部", None)
        self._dri_combo.currentIndexChanged.connect(self._emit_filter)
        row2.addWidget(self._dri_combo)

        row2.addSpacing(8)

        # 创建日期范围
        row2.addWidget(self._make_group_label("创建日期"))
        self._date_start = QDateEdit()
        self._date_start.setCalendarPopup(True)
        self._date_start.setDate(QDate.currentDate().addMonths(-1))
        self._date_start.setSpecialValueText("不限")
        self._date_start.dateChanged.connect(self._emit_filter)
        row2.addWidget(self._date_start)

        row2.addWidget(QLabel("–"))
        self._date_end = QDateEdit()
        self._date_end.setCalendarPopup(True)
        self._date_end.setDate(QDate.currentDate())
        self._date_end.setSpecialValueText("不限")
        self._date_end.dateChanged.connect(self._emit_filter)
        row2.addWidget(self._date_end)

        row2.addStretch()

        # 清空按钮
        btn_clear = QPushButton("清空筛选")
        btn_clear.setProperty("class", "action")
        btn_clear.setFixedHeight(26)
        btn_clear.clicked.connect(self._clear_filters)
        row2.addWidget(btn_clear)

        layout.addLayout(row2)

    def _make_group_label(self, text: str) -> QLabel:
        """创建分组标签。"""
        lbl = QLabel(text)
        lbl.setProperty("class", "filter-group-label")
        return lbl

    def set_dri_options(self, dri_names: list[str]) -> None:
        """设置 DRI 下拉选项（从现有 Issue 的 dri_name 去重填充）。"""
        current = self._dri_combo.currentData()
        self._dri_combo.clear()
        self._dri_combo.addItem("全部", None)
        for name in sorted(set(n for n in dri_names if n)):
            self._dri_combo.addItem(name, name)
        if current is not None:
            idx = self._dri_combo.findData(current)
            if idx >= 0:
                self._dri_combo.setCurrentIndex(idx)

    def get_filters(self) -> dict:
        """获取当前筛选条件。"""
        return {
            "status": [
                eng for eng, cb in self._status_checks.items()
                if cb.isChecked()
            ],
            "severity": [
                eng for eng, cb in self._severity_checks.items()
                if cb.isChecked()
            ],
            "priority": [
                pri for pri, cb in self._priority_checks.items()
                if cb.isChecked()
            ],
            "dri_name": self._dri_combo.currentData(),
            "date_start": self._date_start.date().toString("yyyy-MM-dd")
                if self._date_start.date() != self._date_start.minimumDate() else "",
            "date_end": self._date_end.date().toString("yyyy-MM-dd")
                if self._date_end.date() != self._date_end.minimumDate() else "",
        }

    def set_filters(self, filters: dict) -> None:
        """从外部设置筛选条件（跨视图同步）。"""
        status_list = filters.get("status", [])
        for eng, cb in self._status_checks.items():
            cb.setChecked(eng in status_list)

        sev_list = filters.get("severity", [])
        for eng, cb in self._severity_checks.items():
            cb.setChecked(eng in sev_list)

        pri_list = filters.get("priority", [])
        for pri, cb in self._priority_checks.items():
            cb.setChecked(pri in pri_list)

        dri_name = filters.get("dri_name")
        if dri_name is None:
            self._dri_combo.setCurrentIndex(0)
        else:
            idx = self._dri_combo.findData(dri_name)
            if idx >= 0:
                self._dri_combo.setCurrentIndex(idx)

        date_start = filters.get("date_start", "")
        if date_start:
            parsed = QDate.fromString(date_start, "yyyy-MM-dd")
            if parsed.isValid():
                self._date_start.setDate(parsed)

        date_end = filters.get("date_end", "")
        if date_end:
            parsed = QDate.fromString(date_end, "yyyy-MM-dd")
            if parsed.isValid():
                self._date_end.setDate(parsed)

    def _emit_filter(self) -> None:
        """发射筛选变更信号。"""
        self.filter_changed.emit(self.get_filters())

    def _clear_filters(self) -> None:
        """重置所有筛选条件为全选/不限。"""
        for cb in self._status_checks.values():
            cb.setChecked(True)
        for cb in self._severity_checks.values():
            cb.setChecked(True)
        for cb in self._priority_checks.values():
            cb.setChecked(True)
        self._dri_combo.setCurrentIndex(0)
        self._date_start.setDate(QDate.currentDate().addMonths(-1))
        self._date_end.setDate(QDate.currentDate())
        self._emit_filter()
