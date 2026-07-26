"""测试计划筛选栏组件 — 计划下拉/搜索/技术员/状态/类别/日期范围。

提取自 test_plan_view.py row2 + summary_bar，封装为独立 QWidget。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.views.widgets.search_box import SearchBox


class PlanFilterBar(QWidget):
    """测试计划筛选行：计划下拉、搜索、技术员、状态、类别、日期范围 + 摘要栏。"""

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
        self._search_edit.setFixedSize(160, 26)
        row.addWidget(self._search_edit)

        # 技术员筛选
        self._tech_filter_combo = QComboBox()
        self._tech_filter_combo.setProperty("class", "filter-combo")
        self._tech_filter_combo.setFixedWidth(100)
        self._tech_filter_combo.setFixedHeight(26)
        self._tech_filter_combo.addItem("全部技术员", None)
        row.addWidget(self._tech_filter_combo)

        # 状态筛选
        self._status_filter_combo = QComboBox()
        self._status_filter_combo.setProperty("class", "filter-combo")
        self._status_filter_combo.setFixedWidth(95)
        self._status_filter_combo.setFixedHeight(26)
        self._status_filter_combo.addItem("全部状态", None)
        self._status_filter_combo.addItem("待开始", "pending")
        self._status_filter_combo.addItem("进行中", "in_progress")
        self._status_filter_combo.addItem("已完成", "completed")
        self._status_filter_combo.addItem("已跳过", "skipped")
        row.addWidget(self._status_filter_combo)

        # 类别筛选
        self._category_filter_combo = QComboBox()
        self._category_filter_combo.setProperty("class", "filter-combo")
        self._category_filter_combo.setFixedWidth(95)
        self._category_filter_combo.setFixedHeight(26)
        self._category_filter_combo.addItem("全部类别", None)
        self._category_filter_combo.addItem("环境试验", "环境试验")
        self._category_filter_combo.addItem("机械试验", "机械试验")
        self._category_filter_combo.addItem("表面处理", "表面处理")
        self._category_filter_combo.addItem("包装", "包装")
        self._category_filter_combo.addItem("其他", "其他")
        row.addWidget(self._category_filter_combo)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setProperty("class", "sep-vline")
        row.addWidget(sep)

        # 日期范围
        row.addWidget(QLabel("日期:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setSpecialValueText("不限")
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_from.setFixedWidth(120)
        self._date_from.setFixedHeight(26)
        row.addWidget(self._date_from)

        to_lbl = QLabel("至")
        to_lbl.setProperty("class", "subtext")
        row.addWidget(to_lbl)

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

        # 统计面板
        self._summary_bar = QLabel("")
        self._summary_bar.setProperty("class", "summary-bar")
        row.addWidget(self._summary_bar)

        layout.addLayout(row)

        # 搜索历史气泡行
        from src.views.widgets.search_history_chips import SearchHistoryChips
        self._chips = SearchHistoryChips("tasks", self)
        self._chips.chip_clicked.connect(self._on_chip_clicked)
        layout.addWidget(self._chips)

    def _on_chip_clicked(self, keyword: str) -> None:
        self._search_edit.setText(keyword)

    def save_search_keyword(self, keyword: str) -> None:
        if hasattr(self, '_chips'):
            self._chips.save_keyword(keyword)
