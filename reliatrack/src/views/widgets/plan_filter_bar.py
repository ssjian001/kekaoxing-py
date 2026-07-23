"""测试计划筛选栏组件 — 计划下拉/搜索/技术员/日期范围。

提取自 test_plan_view.py row2 + summary_bar，封装为独立 QWidget。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.views.widgets.search_box import SearchBox


class PlanFilterBar(QWidget):
    """测试计划筛选行：计划下拉、搜索、技术员、日期范围 + 摘要栏。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Row: 搜索/筛选 ──
        row = QHBoxLayout()
        row.setSpacing(4)

        row.addWidget(QLabel("计划:"))
        self._plan_combo = QComboBox()
        self._plan_combo.setProperty("class", "filter-combo")
        self._plan_combo.setFixedWidth(160)
        self._plan_combo.setFixedHeight(26)
        row.addWidget(self._plan_combo)

        # 搜索框
        self._search_edit = SearchBox()
        self._search_edit.setPlaceholderText("搜索任务名…")
        self._search_edit.setFixedSize(200, 26)
        row.addWidget(self._search_edit)

        self._tech_filter_combo = QComboBox()
        self._tech_filter_combo.setProperty("class", "filter-combo")
        self._tech_filter_combo.setFixedWidth(100)
        self._tech_filter_combo.setFixedHeight(26)
        self._tech_filter_combo.addItem("全部技术员", None)
        row.addWidget(self._tech_filter_combo)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setProperty("class", "sep-vline")
        row.addWidget(sep)

        # 日期范围
        from PySide6.QtWidgets import QDateEdit

        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setSpecialValueText("不限")
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_from.setFixedWidth(170)
        self._date_from.setFixedHeight(26)
        row.addWidget(self._date_from)

        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setSpecialValueText("不限")
        self._date_to.setDate(self._date_to.maximumDate())
        self._date_to.setFixedWidth(120)
        self._date_to.setFixedHeight(26)
        row.addWidget(self._date_to)

        self._btn_reset_filter = QPushButton("重置")
        self._btn_reset_filter.setFixedHeight(26)
        self._btn_reset_filter.setProperty("class", "action")
        row.addWidget(self._btn_reset_filter)

        row.addStretch()
        layout.addLayout(row)

        # 摘要信息栏
        self._summary_bar = QLabel()
        self._summary_bar.setProperty("class", "summary-bar")
        self._summary_bar.setWordWrap(False)
        self._summary_bar.setFixedHeight(26)
        layout.addWidget(self._summary_bar)
