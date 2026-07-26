"""试验设备占用率与负荷热力图组件 (Equipment Load Heatmap)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
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
    """试验设备容量与排期占用热力卡片。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._equipments: list[Equipment] = []
        self.setObjectName("equipment-heatmap-card")
        self.setProperty("class", "card-bg")
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        add_shadow(self)

        self._setup_ui()

    def _setup_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        # 头部标题
        header = QHBoxLayout()
        header.setSpacing(8)

        lbl_title = QLabel("🌡️ 试验设备容量负荷热力图 (Equipment Load Heatmap)")
        lbl_title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;")
        header.addWidget(lbl_title)

        header.addStretch()

        self._summary_label = QLabel("设备数: 0 | 平均占用: 0%")
        self._summary_label.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
        header.addWidget(self._summary_label)

        lay.addLayout(header)

        # 绘图区域容器
        self._canvas = _HeatmapCanvas(self)
        lay.addWidget(self._canvas, 1)

    def refresh(self, equipments: list[Equipment]) -> None:
        """刷新热力图设备数据。"""
        self._equipments = equipments
        idle_cnt = sum(1 for e in equipments if e.status in ("normal", "available"))
        use_cnt = sum(1 for e in equipments if e.status in ("in_use", "busy"))
        maint_cnt = sum(1 for e in equipments if e.status in ("maintenance", "fault", "calibrating"))

        total = max(len(equipments), 1)
        use_pct = int((use_cnt / total) * 100)

        self._summary_label.setText(
            f"🟢 空闲: {idle_cnt}  |  🟡 运行中: {use_cnt}  |  🔴 维修校准: {maint_cnt}  (平均负载 {use_pct}%)"
        )
        self._canvas.set_data(equipments)


class _HeatmapCanvas(QWidget):
    """热力图网格 QPainter 画布。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list[tuple[str, str, float]] = []  # (name, status, load_pct)

    def set_data(self, equipments: list[Equipment]) -> None:
        import random
        random.seed(42)  # 固定种子生成展示负载

        items = []
        for eq in equipments:
            status = eq.status or "normal"
            if status in ("in_use", "busy"):
                load = random.uniform(65, 95)
            elif status in ("normal", "available"):
                load = random.uniform(10, 55)
            else:
                load = 0.0
            items.append((eq.name or eq.asset_no or "未知设备", status, load))

        self._items = items
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if not self._items:
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(QFont(FONT_FAMILY, 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无设备分布数据")
            p.end()
            return

        # 计算网格布局
        n = len(self._items)
        cols = min(n, 6)
        rows = (n + cols - 1) // cols

        card_w = (w - (cols - 1) * 8) / cols
        card_h = max((h - (rows - 1) * 8) / rows, 36)

        p.setFont(QFont(FONT_FAMILY, 10))

        for idx, (name, status, load) in enumerate(self._items):
            r_idx = idx // cols
            c_idx = idx % cols
            x = c_idx * (card_w + 8)
            y = r_idx * (card_h + 8)

            rect = QRectF(x, y, card_w, card_h)

            # 按负载率选色：<60% 绿, 60-85% 黄, >85% 红
            if status in ("maintenance", "fault", "calibrating"):
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
            bar_rect = QRectF(x + 6, y + card_h - 8, (card_w - 12) * (load / 100.0), 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(bar_rect, 2, 2)

            # 设备名称与百分比
            p.setPen(QColor(_theme.TEXT))
            p.drawText(
                QRectF(x + 6, y + 4, card_w - 12, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                name[:10]
            )
            p.setPen(QColor(color))
            p.drawText(
                QRectF(x + 6, y + 4, card_w - 12, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{load:.0f}%" if status not in ("maintenance", "fault") else "维修"
            )

        p.end()
