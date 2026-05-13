"""自定义 QProxyStyle：为 QCheckBox / QRadioButton 绘制 ✓ 和圆点。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle

from src.styles.theme import ACCENT, BG_INPUT


class CheckboxProxyStyle(QProxyStyle):
    """拦截 PE_IndicatorCheckBox / PE_IndicatorRadioButton 的绘制。"""

    def drawPrimitive(
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOptionButton,
        painter: QPainter,
        widget,
    ) -> None:
        if element == QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            self._draw_checkbox(option, painter)
            return
        if element == QStyle.PrimitiveElement.PE_IndicatorRadioButton:
            self._draw_radio(option, painter)
            return
        super().drawPrimitive(element, option, painter, widget)

    # ── CheckBox ──
    @staticmethod
    def _draw_checkbox(option: QStyleOptionButton, painter: QPainter) -> None:
        r = QRectF(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        checked = bool(option.state & QStyle.StateFlag.State_On)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        no_change = bool(option.state & QStyle.StateFlag.State_NoChange)

        if checked or no_change:
            # 蓝色圆角背景
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(ACCENT)))
            painter.drawRoundedRect(r, 3, 3)

            if checked:
                # 白色 ✓
                pen = QPen(QColor("#ffffff"))
                pen.setWidth(2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath()
                x0, y0 = r.x(), r.y()
                w, h = r.width(), r.height()
                path.moveTo(x0 + w * 0.22, y0 + h * 0.52)
                path.lineTo(x0 + w * 0.40, y0 + h * 0.72)
                path.lineTo(x0 + w * 0.78, y0 + h * 0.28)
                painter.drawPath(path)
            elif no_change:
                # 白色 — (半选)
                pen = QPen(QColor("#ffffff"))
                pen.setWidth(2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    r.x() + r.width() * 0.25,
                    r.center().y(),
                    r.right() - r.width() * 0.25,
                    r.center().y(),
                )
        else:
            # 未选中
            border_color = ACCENT if hover else "#CAC8CF"
            painter.setPen(QPen(QColor(border_color), 1.2))
            painter.setBrush(QBrush(QColor(BG_INPUT)))
            painter.drawRoundedRect(r, 3, 3)

        painter.restore()

    # ── RadioButton ──
    @staticmethod
    def _draw_radio(option: QStyleOptionButton, painter: QPainter) -> None:
        r = QRectF(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        checked = bool(option.state & QStyle.StateFlag.State_On)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        border_color = ACCENT if (checked or hover) else "#CAC8CF"
        painter.setPen(QPen(QColor(border_color), 1.2))
        painter.setBrush(QBrush(QColor(BG_INPUT)))
        painter.drawEllipse(r)

        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(ACCENT)))
            dot_r = QRectF(0, 0, r.width() * 0.45, r.height() * 0.45)
            dot_r.moveCenter(r.center())
            painter.drawEllipse(dot_r)

        painter.restore()
