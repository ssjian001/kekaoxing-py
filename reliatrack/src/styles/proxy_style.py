"""自定义 QProxyStyle：为 QCheckBox / QRadioButton 绘制 ✓ 和圆点。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle

from src.styles.theme import ACCENT, MANTLE, SURFACE2


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
        # 留 2px 内边距，让 ✓ 不贴边
        r.adjust(2, 2, -2, -2)
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
                # 白色 ✓ — 粗笔宽 + 圆角端点
                pen = QPen(QColor(MANTLE))
                pen.setWidthF(3.5)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath()
                x0, y0 = r.x(), r.y()
                w, h = r.width(), r.height()
                path.moveTo(x0 + w * 0.20, y0 + h * 0.52)
                path.lineTo(x0 + w * 0.40, y0 + h * 0.74)
                path.lineTo(x0 + w * 0.80, y0 + h * 0.26)
                painter.drawPath(path)
            elif no_change:
                # 白色 — (半选)
                pen = QPen(QColor(MANTLE))
                pen.setWidthF(3.0)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    r.x() + r.width() * 0.25,
                    r.center().y(),
                    r.right() - r.width() * 0.25,
                    r.center().y(),
                )
        else:
            # 未选中 — 透明填充 + 可见边框
            border_color = QColor(ACCENT) if hover else QColor(SURFACE2)
            painter.setPen(QPen(border_color, 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r, 4, 4)

        painter.restore()

    # ── RadioButton ──
    @staticmethod
    def _draw_radio(option: QStyleOptionButton, painter: QPainter) -> None:
        r = QRectF(option.rect)
        r.adjust(1, 1, -1, -1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        checked = bool(option.state & QStyle.StateFlag.State_On)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        border_color = QColor(ACCENT) if (checked or hover) else QColor(SURFACE2)
        painter.setPen(QPen(border_color, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(r)

        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(ACCENT)))
            dot_r = QRectF(0, 0, r.width() * 0.45, r.height() * 0.45)
            dot_r.moveCenter(r.center())
            painter.drawEllipse(dot_r)

        painter.restore()
