"""甘特图 Tab 组件 — 模式切换栏 + 甘特图 + 滚动区。

提取自 test_plan_view.py Tab 1 的 inline 代码。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.views.widgets.gantt_widget import _GanttWidget


class PlanGanttTab(QWidget):
    """甘特图 Tab：模式切换 + 甘特图 + 滚动区域。"""

    mode_toggled = Signal(int, bool)  # (btn_id, checked)
    task_moved = Signal(int, int)     # (task_id, new_start_day) — 转发

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 模式切换栏
        mode_bar = QHBoxLayout()
        mode_bar.setContentsMargins(4, 2, 4, 2)

        self._planned_btn = QPushButton("预计日期")
        self._planned_btn.setProperty("class", "pill")
        self._planned_btn.setCheckable(True)
        self._planned_btn.setChecked(True)
        self._planned_btn.setFixedHeight(26)

        self._actual_btn = QPushButton("实际日期")
        self._actual_btn.setProperty("class", "pill")
        self._actual_btn.setCheckable(True)
        self._actual_btn.setFixedHeight(26)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._planned_btn, 0)
        self._mode_group.addButton(self._actual_btn, 1)
        self._mode_group.idToggled.connect(self._on_mode_toggled)

        mode_label = QLabel("显示模式:")
        mode_label.setProperty("class", "subtext")
        mode_bar.addWidget(mode_label)
        mode_bar.addWidget(self._planned_btn)
        mode_bar.addWidget(self._actual_btn)
        mode_bar.addStretch()
        layout.addLayout(mode_bar)

        # 甘特图
        self._gantt = _GanttWidget()
        self._gantt.setProperty("class", "bg-base")
        self._gantt.task_moved.connect(self._on_gantt_moved)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._gantt)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setProperty("class", "scroll-base")
        self._gantt.bind_scroll_area(self._scroll)
        layout.addWidget(self._scroll)

    @property
    def gantt(self) -> _GanttWidget:
        return self._gantt

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll

    def _on_mode_toggled(self, btn_id: int, checked: bool) -> None:
        self.mode_toggled.emit(btn_id, checked)

    def _on_gantt_moved(self, task_id: int, new_day: int) -> None:
        self.task_moved.emit(task_id, new_day)
