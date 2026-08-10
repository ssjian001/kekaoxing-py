"""试验设备占用率与负荷热力图组件 (Equipment Load Heatmap) — 支持折叠、过滤与可滚动高容纳网格。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QSizePolicy,
)

import src.styles.theme as _theme
from src.styles.constants import (
    add_shadow,
    DASH_PRIMARY,
    DASH_SUCCESS,
    DASH_WARNING,
    DASH_DANGER,
    FONT_FAMILY,
)
from src.models.common import Equipment


class EquipmentLoadHeatmapWidget(QFrame):
    """试验设备容量与排期占用热力卡片 (支持折叠与状态二次过滤)。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._equipments: list[Equipment] = []
        self._task_ref_counts: dict[int, int] = {}
        self._filter_status: str = "all"
        self._is_collapsed: bool = False

        self.setObjectName("equipment-heatmap-card")
        self.setProperty("class", "card-bg")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        add_shadow(self)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._main_lay = QVBoxLayout(self)
        self._main_lay.setContentsMargins(14, 10, 14, 10)
        self._main_lay.setSpacing(8)

        # 头部栏
        header = QHBoxLayout()
        header.setSpacing(8)

        lbl_title = QLabel("🌡️ 试验设备容量负荷热力图")
        lbl_title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;")
        header.addWidget(lbl_title)

        # 状态过滤 Pill 按钮组
        self._btn_all = QPushButton("全部")
        self._btn_high = QPushButton("🔴 高负载/维护")
        self._btn_run = QPushButton("🟡 运行中")
        self._btn_idle = QPushButton("🟢 空闲")

        self._filter_btns = [
            (self._btn_all, "all"),
            (self._btn_high, "high"),
            (self._btn_run, "run"),
            (self._btn_idle, "idle"),
        ]

        for btn, code in self._filter_btns:
            btn.setProperty("class", "pill")
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")
            btn.clicked.connect(lambda _, c=code: self._on_filter_changed(c))
            header.addWidget(btn)

        self._btn_all.setChecked(True)

        header.addStretch()

        self._summary_label = QLabel("设备: 0 | 负载: 0%")
        self._summary_label.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
        header.addWidget(self._summary_label)

        # 折叠/展开按钮
        self._btn_collapse = QPushButton("🔼 折叠")
        self._btn_collapse.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_theme.SUBTEXT0}; border: none; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {_theme.TEXT}; }}"
        )
        self._btn_collapse.clicked.connect(self.toggle_collapse)
        header.addWidget(self._btn_collapse)

        self._main_lay.addLayout(header)

        # 滚动区域包裹 Canvas，防止海量设备挤压覆盖
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMaximumHeight(220)

        self._scroll.setMinimumHeight(100)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._canvas = _HeatmapCanvas(self)
        self._scroll.setWidget(self._canvas)

        self._main_lay.addWidget(self._scroll)

    def toggle_collapse(self) -> None:
        """展开/折叠热力图明细网格。"""
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self._scroll.hide()
            self._btn_collapse.setText("🔽 展开明细")
        else:
            self._scroll.show()
            self._btn_collapse.setText("🔼 折叠")

    def _on_filter_changed(self, code: str) -> None:
        self._filter_status = code
        for btn, c in self._filter_btns:
            btn.setChecked(c == code)
        self._apply_filter()

    def _apply_filter(self) -> None:
        if not self._equipments:
            return

        filtered = self._equipments
        if self._filter_status == "high":
            # 高负载/维护：维护中、离线，或被任务引用 >= 2 的设备
            filtered = [
                e for e in self._equipments
                if e.status in ("maintenance", "offline")
                or self._task_ref_counts.get(e.id, 0) >= 2
            ]
        elif self._filter_status == "run":
            # 运行中：被任务引用的设备（真实枚举里没有 in_use/busy 状态值）
            filtered = [
                e for e in self._equipments
                if self._task_ref_counts.get(e.id, 0) > 0
            ]
        elif self._filter_status == "idle":
            # 空闲：available 且无任务引用
            filtered = [
                e for e in self._equipments
                if e.status == "available"
                and self._task_ref_counts.get(e.id, 0) == 0
            ]

        self._canvas.set_data(filtered, self._task_ref_counts)

    def refresh(self, equipments: list[Equipment], task_ref_counts: dict[int, int] | None = None) -> None:
        """刷新热力图设备数据。

        Args:
            equipments: 设备列表。
            task_ref_counts: 设备 id → 被测试任务引用数（真实负载数据源）。
                为 None 时按 0 处理（无任务引用）。
        """
        self._equipments = equipments
        self._task_ref_counts = task_ref_counts or {}
        running = sum(1 for e in equipments if self._task_ref_counts.get(e.id, 0) > 0)
        maint_cnt = sum(1 for e in equipments if e.status in ("maintenance", "offline"))

        total = max(len(equipments), 1)
        use_pct = int((running / total) * 100)

        self._summary_label.setText(
            f"🟢 空闲: {total - running - maint_cnt}  |  🟡 运行中: {running}  |  🔴 维护: {maint_cnt}  (使用率 {use_pct}%)"
        )
        self._apply_filter()


class _HeatmapCanvas(QWidget):
    """热力图网格 QPainter 画布 (支持自适应网格行高与流动布局)。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list[tuple[str, str, float]] = []

    def set_data(self, equipments: list[Equipment], task_ref_counts: dict[int, int] | None = None) -> None:
        task_ref_counts = task_ref_counts or {}

        items = []
        for eq in equipments:
            status = eq.status or "available"
            ref_count = task_ref_counts.get(eq.id or -1, 0)
            # 真实负载：被任务引用数 → 负载百分比（1 个任务约 60%，2+ 满载）
            load = min(ref_count * 60, 100.0) if ref_count > 0 else 0.0
            items.append((eq.name or eq.asset_no or "未知设备", status, load))

        self._items = items
        self._recalculate_height()
        self.update()

    def _recalculate_height(self) -> None:
        w = max(self.width(), 400)
        card_w, card_h, gap = 125, 40, 8
        cols = max(1, (w - gap) // (card_w + gap))
        rows = (len(self._items) + cols - 1) // cols if self._items else 1
        needed_h = rows * (card_h + gap) + gap
        self.setMinimumHeight(max(needed_h, 80))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._recalculate_height()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if not self._items:
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(QFont(FONT_FAMILY, 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无对应状态设备")
            p.end()
            return

        card_w, card_h, gap = 125, 40, 8
        cols = max(1, (w - gap) // (card_w + gap))

        p.setFont(QFont(FONT_FAMILY, 9))

        for idx, (name, status, load) in enumerate(self._items):
            r_idx = idx // cols
            c_idx = idx % cols
            x = gap + c_idx * (card_w + gap)
            y = gap + r_idx * (card_h + gap)

            rect = QRectF(x, y, card_w, card_h)

            if status in ("maintenance", "offline"):
                color = QColor(DASH_DANGER)
                bg_color = QColor(DASH_DANGER)
                bg_color.setAlpha(25)
            elif load >= 85:
                color = QColor(DASH_DANGER)
                bg_color = QColor(DASH_DANGER)
                bg_color.setAlpha(35)
            elif load >= 60:
                color = QColor(DASH_WARNING)
                bg_color = QColor(DASH_WARNING)
                bg_color.setAlpha(35)
            else:
                color = QColor(DASH_SUCCESS)
                bg_color = QColor(DASH_SUCCESS)
                bg_color.setAlpha(35)

            p.setPen(QPen(QColor(_theme.SURFACE1), 1))
            p.setBrush(QBrush(bg_color))
            p.drawRoundedRect(rect, 6, 6)

            # 填充负载指示条
            bar_w = max((card_w - 12) * (load / 100.0), 2)
            bar_rect = QRectF(x + 6, y + card_h - 7, bar_w, 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(bar_rect, 1.5, 1.5)

            # 设备名称与百分比
            p.setPen(QColor(_theme.TEXT))
            p.drawText(
                QRectF(x + 6, y + 3, card_w - 12, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                name[:9]
            )
            p.setPen(QColor(color))
            p.drawText(
                QRectF(x + 6, y + 3, card_w - 12, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{load:.0f}%" if status not in ("maintenance", "offline") else "维修"
            )

        p.end()
