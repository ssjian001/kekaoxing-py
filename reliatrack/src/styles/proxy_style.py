"""自定义代理样式 — 绘制带 ✓ 勾号的 CheckBox 和带圆点的 Radio Button。

全局 QSS 中 QCheckBox/QRadioButton 的 indicator:checked 只设了背景色，
看起来是纯色块。此 ProxyStyle 在 drawPrimitive 中绘制 ✓ / • 图标。
"""

from __future__ import annotations

from PySide6.QtWidgets import QProxyStyle
from PySide6.QtGui import QPainter, QPen, QBrush
from PySide6.QtCore import Qt, QRectF

from src.styles.theme import ACCENT


class CheckboxProxyStyle(QProxyStyle):
    """为 QCheckBox 和 QRadioButton 绘制自定义 indicator。"""

    def drawPrimitive(
        self, element: int, option, painter: QPainter, widget=None
    ) -> None:
        # PE_IndicatorCheckBox = 9, PE_IndicatorRadioButton = 10
        if element == 9:  # QStyle.PrimitiveElement.PE_IndicatorCheckBox
            self._draw_checkbox(option, painter)
            return
        if element == 10:  # QStyle.PrimitiveElement.PE_IndicatorRadioButton
            self._draw_radio(option, painter)
            return
        super().drawPrimitive(element, option, painter, widget)

    # ── CheckBox ──────────────────────────────────────────────────

    def _draw_checkbox(self, option, painter: QPainter) -> None:
        r = QRectF(option.rect)
        # 背景
        if option.state & 0x00000010:  # State_On (checked)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ACCENT))
            painter.drawRoundedRect(r, 3, 3)
            # 画 ✓
            pen = QPen("#ffffff")
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            margin = r.width() * 0.25
            check_rect = r.adjusted(margin, margin, -margin, -margin)
            # ✓ 路径：左下 → 中间 → 右上
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.moveTo(check_rect.left(), check_rect.center().y())
            path.lineTo(check_rect.center().x(), check_rect.bottom())
            path.lineTo(check_rect.right(), check_rect.top())
            painter.drawPath(path)
        elif option.state & 0x00000008:  # State_NoChange (tristate)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ACCENT))
            painter.drawRoundedRect(r, 3, 3)
            # 画 —
            pen = QPen("#ffffff")
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            margin = r.width() * 0.25
            painter.drawLine(
                int(r.left() + margin),
                int(r.center().y()),
                int(r.right() - margin),
                int(r.center().y()),
            )
        else:
            # unchecked
            from src.styles.theme import BG_INPUT, SURFACE1
            painter.setPen(QPen(SURFACE1, 1))
            painter.setBrush(QBrush(BG_INPUT))
            painter.drawRoundedRect(r, 3, 3)

        # hover 高亮边框
        if option.state & 0x00000100:  # State_Hover
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)

    # ── RadioButton ───────────────────────────────────────────────

    def _draw_radio(self, option, painter: QPainter) -> None:
        r = QRectF(option.rect)
        from src.styles.theme import BG_INPUT, SURFACE1

        if option.state & 0x00000010:  # checked
            # 外圈
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(QBrush(BG_INPUT))
            painter.drawEllipse(r)
            # 内圆点
            dot_r = r.width() * 0.25
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ACCENT))
            painter.drawEllipse(r.center(), dot_r, dot_r)
        else:
            painter.setPen(QPen(SURFACE1, 1))
            painter.setBrush(QBrush(BG_INPUT))
            painter.drawEllipse(r)

        # hover
        if option.state & 0x00000100:  # State_Hover
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))
