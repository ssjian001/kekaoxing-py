"""甘特图 Tab 组件 — 模式切换栏 + 控制按钮 + 甘特图 + 滚动区。

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
    """甘特图 Tab：模式切换 + 功能开关 + 甘特图 + 滚动区域。"""

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
        mode_bar.setSpacing(6)

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

        mode_bar.addSpacing(16)

        # 功能开关按钮: 依赖矢线 / 冲突检测 / 关键路径
        opt_label = QLabel("高级特性:")
        opt_label.setProperty("class", "subtext")
        mode_bar.addWidget(opt_label)

        self._btn_deps = QPushButton("依赖矢线")
        self._btn_deps.setProperty("class", "pill")
        self._btn_deps.setCheckable(True)
        self._btn_deps.setChecked(True)
        self._btn_deps.setFixedHeight(26)
        self._btn_deps.toggled.connect(self._on_options_changed)
        mode_bar.addWidget(self._btn_deps)

        self._btn_conflicts = QPushButton("冲突告警")
        self._btn_conflicts.setProperty("class", "pill")
        self._btn_conflicts.setCheckable(True)
        self._btn_conflicts.setChecked(True)
        self._btn_conflicts.setFixedHeight(26)
        self._btn_conflicts.toggled.connect(self._on_options_changed)
        mode_bar.addWidget(self._btn_conflicts)

        self._btn_critical = QPushButton("关键路径")
        self._btn_critical.setProperty("class", "pill")
        self._btn_critical.setCheckable(True)
        self._btn_critical.setChecked(False)
        self._btn_critical.setFixedHeight(26)
        self._btn_critical.toggled.connect(self._on_options_changed)
        mode_bar.addWidget(self._btn_critical)

        mode_bar.addSpacing(16)

        # 时间轴放缩滑块与视图范式选择
        zoom_label = QLabel("时间轴缩放:")
        zoom_label.setProperty("class", "subtext")
        mode_bar.addWidget(zoom_label)

        from PySide6.QtWidgets import QSlider, QComboBox
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(4, 150)
        self._zoom_slider.setValue(30)
        self._zoom_slider.setFixedWidth(90)
        self._zoom_slider.setToolTip("无级调节甘特图每日列宽 (支持 Ctrl + 滚轮)")
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        mode_bar.addWidget(self._zoom_slider)

        self._zoom_val_label = QLabel("100%")
        self._zoom_val_label.setProperty("class", "subtext")
        self._zoom_val_label.setFixedWidth(40)
        mode_bar.addWidget(self._zoom_val_label)

        self._view_mode_combo = QComboBox()
        self._view_mode_combo.setProperty("class", "filter-combo")
        self._view_mode_combo.addItem("日视图 (标准)", 30)
        self._view_mode_combo.addItem("周视图 (紧凑)", 12)
        self._view_mode_combo.addItem("月视图 (宏观)", 5)
        self._view_mode_combo.addItem("放大视角 (精细)", 75)
        self._view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        mode_bar.addWidget(self._view_mode_combo)

        mode_bar.addStretch()
        layout.addLayout(mode_bar)

        # 甘特图
        self._gantt = _GanttWidget()
        self._gantt.setProperty("class", "bg-base")
        self._gantt.task_moved.connect(self._on_gantt_moved)
        self._gantt.zoom_changed.connect(self._on_gantt_zoom_changed)


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

    def _on_options_changed(self) -> None:
        self._gantt.set_render_options(
            show_dependencies=self._btn_deps.isChecked(),
            show_conflicts=self._btn_conflicts.isChecked(),
            show_critical_path=self._btn_critical.isChecked(),
        )

    def _on_zoom_slider_changed(self, val: int) -> None:
        self._gantt.set_day_width(float(val))
        pct = int(val / 30.0 * 100)
        self._zoom_val_label.setText(f"{pct}%")

    def _on_view_mode_changed(self, index: int) -> None:
        val = self._view_mode_combo.currentData()
        if val:
            self._zoom_slider.setValue(int(val))

    def _on_gantt_zoom_changed(self, day_w: float) -> None:
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(int(day_w))
        self._zoom_slider.blockSignals(False)
        pct = int(day_w / 30.0 * 100)
        self._zoom_val_label.setText(f"{pct}%")

    def _on_gantt_moved(self, task_id: int, new_start_day: int) -> None:
        self.task_moved.emit(task_id, new_start_day)
