"""仪表盘卡片组件 — KPI 统计卡片 + 辅助指标 + 测试进度卡。

提取自 dashboard_view.py。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import (
    DASH_SUCCESS,
    DASH_DANGER,
    DASH_WARNING,
    DASH_PRIMARY,
    add_shadow,
)
from src.styles.animation import DropShadowAnimation, BackgroundAnimation
from src.views.widgets.dashboard_charts import _StackedBar


class _AuxCard(QFrame):
    """紧凑辅助指标: 标题 + 值。"""

    def __init__(self, title: str, value: str, parent: QWidget | None = None):
        super().__init__(parent)
        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 6, 12, 6)
        vl.setSpacing(0)
        self._title_label = QLabel(title)
        self._title_label.setProperty("class", "hint-label")
        vl.addWidget(self._title_label)
        self._value_label = QLabel(value)
        self._value_label.setProperty("class", "stat-value")
        vl.addWidget(self._value_label)

    def set_value(self, text: str) -> None:
        self._value_label.setText(text)


class _StatCard(QFrame):
    """现代 KPI 卡片: label / 大数字 / 百分比, 16px 圆角 + 柔阴影。"""

    def __init__(self, title: str, value: str = "0", color: str = DASH_PRIMARY,
                 tab_index: int = -1, parent: QWidget | None = None,
                 jump_data: dict | None = None):
        super().__init__(parent)
        self._tab_index = tab_index
        self._color = color
        self._jump_data = jump_data or {}
        self.setObjectName("stat-card")
        self.setProperty("class", "card-bg")
        self.setMinimumHeight(64)
        self.setMaximumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        add_shadow(self)
        self._shadow_anim = DropShadowAnimation(self)
        self._shadow_anim.setup(blur=20, offset_y=4, normal_alpha=0, hover_alpha=40)
        self._bg_anim = BackgroundAnimation(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)

        self._title_label = QLabel(title)
        self._title_label.setProperty("class", "subtext")
        lay.addWidget(self._title_label)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        row.addWidget(self._val)
        self._trend_label = QLabel("")
        self._trend_label.setStyleSheet(
            "font-size: 13px; border: none; background: transparent;"
        )
        self._trend_label.hide()
        row.addWidget(self._trend_label)
        row.addStretch()
        lay.addLayout(row)

    def set_value(self, text: str) -> None:
        self._val.setText(text)

    def set_trend(self, direction: str, text: str = "") -> None:
        if direction == "none":
            self._trend_label.hide()
            return
        symbols = {"up": "↑", "down": "↓", "flat": "→"}
        colors = {"up": DASH_SUCCESS, "down": DASH_DANGER, "flat": _theme.SUBTEXT0}
        sym = symbols.get(direction, "→")
        c = colors.get(direction, _theme.SUBTEXT0)
        display = f"{sym} {text}" if text else sym
        self._trend_label.setText(display)
        self._trend_label.setStyleSheet(
            f"color: {c}; font-size: 13px; border: none; background: transparent;"
        )
        self._trend_label.show()

    def enterEvent(self, event):  # noqa: N802
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setBlurRadius(20)
            shadow.setOffset(0, 4)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 2)
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        w = self.parent()
        while w is not None:
            if hasattr(w, "card_clicked"):
                w.card_clicked.emit(self._tab_index, self._jump_data or None)
                break
            w = w.parent()
        super().mousePressEvent(event)


class _TestProgressCard(QFrame):
    """测试进度摘要: 堆叠进度条 (PASS/FAIL/进行中/待开始) + 辅助指标。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "card-bg")
        self.setFixedHeight(88)
        add_shadow(self, blur=16, offset=3, opacity=20)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12)
        lay.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(4)
        self._title_label = QLabel("测试进度")
        self._title_label.setProperty("class", "text-bold")
        left.addWidget(self._title_label)

        self._stacked = _StackedBar()
        left.addWidget(self._stacked)

        legend = QHBoxLayout()
        legend.setSpacing(12)
        self._legend_labels: list[QLabel] = []
        self._legend_dots: list[QLabel] = []
        self._legend_color_keys: list[str] = []
        for label, key in [("PASS", "GREEN"), ("FAIL", "RED"),
                           ("进行中", "YELLOW"), ("待开始", "SUBTEXT0")]:
            color = getattr(_theme, key)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; border: none; background: transparent;")
            self._legend_dots.append(dot)
            self._legend_color_keys.append(key)
            lbl = QLabel(label)
            lbl.setProperty("class", "hint-label")
            self._legend_labels.append(lbl)
            legend.addWidget(dot)
            legend.addWidget(lbl)
        legend.addStretch()
        left.addLayout(legend)
        lay.addLayout(left, 3)

        right = QHBoxLayout()
        right.setSpacing(16)
        self._aux1 = self._mk_aux("测试通过率", "—%")
        self._aux2 = self._mk_aux("最后更新", "—")
        right.addWidget(self._aux1)
        right.addWidget(self._aux2)
        lay.addLayout(right, 2)

    @staticmethod
    def _mk_aux(title: str, value: str) -> _AuxCard:
        card = _AuxCard(title, value)
        card.setProperty("class", "card-bg-sm")
        card.setFixedHeight(56)
        return card

    def refresh(self, total: int, completed: int, pass_count: int, fail_count: int,
                in_progress: int, pass_rate: float | None,
                last_update: str | None) -> None:
        self._stacked.set_data(total, pass_count, fail_count, in_progress)
        self._aux1.set_value(f"{pass_rate:.1f}%" if pass_rate is not None else "—%")
        self._aux2.set_value(last_update or "—")
