"""自定义代理样式 — 绘制带 ✓ 勾号的 CheckBox 和带圆点的 RadioButton。

全局 QSS 中 indicator:checked 只设了背景色，看起来是纯色块。
此 ProxyStyle 在 drawPrimitive 中绘制 ✓ / • 图标。
"""

from __future__ import annotations

from PySide6.QtWidgets import QProxyStyle, QStyle
from PySide6.QtGui import QPainter, QPainterPath, QPen, QBrush
from PySide6.QtCore import Qt, QRectF

from src.styles.theme import ACCENT, BG_INPUT, SURFACE1

# PySide6 枚举值（Qt6 与 Qt5 不同）
_PE_CHECKBOX = QStyle.PrimitiveElement.PE_IndicatorCheckBox
_PE_RADIO = QStyle.PrimitiveElement.PE_IndicatorRadioButton
_STATE_ON = QStyle.StateFlag.State_On
_STATE_NOCHANGE = QStyle.StateFlag.State_NoChange
_STATE_MOUSEOVER = QStyle.StateFlag.State_MouseOver


class CheckboxProxyStyle(QProxyStyle):
    """为 QCheckBox 和 QRadioButton 绘制自定义 indicator。"""

    def drawPrimitive(
        self, element: QStyle.PrimitiveElement, option, painter: QPainter, widget=None
    ) -> None:
        if element == _PE_CHECKBOX:
            self._draw_checkbox(option, painter)
            return
        if element == _PE_RADIO:
            self._draw_radio(option, painter)
            return
        super().drawPrimitive(element, option, painter, widget)

    # ── CheckBox ──────────────────────────────────────────────────

    def _draw_checkbox(self, option, painter: QPainter) -> None:
        r = QRectF(option.rect)
        state = option.state

        if state & _STATE_ON:
            # 蓝底
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ACCENT))
            painter.drawRoundedRect(r, 3, 3)
            # 白色 ✓
            pen = QPen("#ffffff")
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            margin = r.width() * 0.25
            cr = r.adjusted(margin, margin, -margin, -margin)
            path = QPainterPath()
            path.moveTo(cr.left(), cr.center().y())
            path.lineTo(cr.center().x(), cr.bottom())
            path.lineTo(cr.right(), cr.top())
            painter.drawPath(path)

        elif state & _STATE_NOCHANGE:
            # 蓝底 + 横线（tristate）
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ACCENT))
            painter.drawRoundedRect(r, 3, 3)
            pen = QPen("#ffffff")
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            margin = r.width() * 0.25
            painter.drawLine(
                int(r.left() + margin), int(r.center().y()),
                int(r.right() - margin), int(r.center().y()),
            )
        else:
            # unchecked：白底灰边
            painter.setPen(QPen(SURFACE1, 1))
            painter.setBrush(QBrush(BG_INPUT))
            painter.drawRoundedRect(r, 3, 3)

        # hover 高亮
        if state & _STATE_MOUSEOVER:
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)

    # ── RadioButton ───────────────────────────────────────────────

    def _draw_radio(self, option, painter: QPainter) -> None:
        r = QRectF(option.rect)
        state = option.state

        if state & _STATE_ON:
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(QBrush(BG_INPUT))
            painter.drawEllipse(r)
            dot_r = r.width() * 0.25
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ACCENT))
            painter.drawEllipse(r.center(), dot_r, dot_r)
        else:
            painter.setPen(QPen(SURFACE1, 1))
            painter.setBrush(QBrush(BG_INPUT))
            painter.drawEllipse(r)

        if state & _STATE_MOUSEOVER:
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))
