"""自定义 QProxyStyle：为 QCheckBox / QRadioButton / SpinBox / DateEdit / ComboBox 绘制控件。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QProxyStyle,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
)

import src.styles.theme as _theme


class CheckboxProxyStyle(QProxyStyle):
    """拦截 CheckBox / RadioButton / SpinBox / ComboBox 的绘制。"""

    # ── 入口 ──

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

    def drawComplexControl(
        self,
        control: QStyle.ComplexControl,
        option,
        painter: QPainter,
        widget,
    ) -> None:
        # SpinBox / DateEdit / TimeEdit / DateTimeEdit
        if control == QStyle.ComplexControl.CC_SpinBox:
            self._draw_spinbox(control, option, painter, widget)
            return
        # ComboBox 下拉箭头
        if control == QStyle.ComplexControl.CC_ComboBox:
            self._draw_combobox(control, option, painter, widget)
            return
        super().drawComplexControl(control, option, painter, widget)

    # ── SpinBox ──

    def _draw_spinbox(
        self,
        control: QStyle.ComplexControl,
        option: QStyleOptionSpinBox,
        painter: QPainter,
        widget,
    ) -> None:
        # 画完整控件（外框+文本），不画默认箭头
        option2 = QStyleOptionSpinBox(option)
        option2.subControls = option.subControls & ~QStyle.SubControl.SC_SpinBoxUp
        option2.subControls = option2.subControls & ~QStyle.SubControl.SC_SpinBoxDown
        option2.activeSubControls = QStyle.SubControl.SC_None
        super().drawComplexControl(control, option2, painter, widget)

        disabled = bool(option.state & QStyle.StateFlag.State_Enabled) is False
        widget_rect = option.rect

        # 按钮画在控件内部右侧，避免 border-radius 裁剪
        btn_w = 18
        btn_h = widget_rect.height() / 2

        up_r = QRectF(
            widget_rect.right() - btn_w - 2, widget_rect.top() + 1,
            btn_w, btn_h - 1,
        )
        down_r = QRectF(
            widget_rect.right() - btn_w - 2, widget_rect.top() + btn_h,
            btn_w, btn_h - 1,
        )
        hover_up = bool(option.state & QStyle.StateFlag.State_MouseOver) and bool(
            option.activeSubControls & QStyle.SubControl.SC_SpinBoxUp
        )
        hover_down = bool(option.state & QStyle.StateFlag.State_MouseOver) and bool(
            option.activeSubControls & QStyle.SubControl.SC_SpinBoxDown
        )
        self._draw_arrow_button(painter, up_r, up=True, hover=hover_up, disabled=disabled)
        self._draw_arrow_button(painter, down_r, up=False, hover=hover_down, disabled=disabled)

    # ── ComboBox ──

    def _draw_combobox(
        self,
        control: QStyle.ComplexControl,
        option: QStyleOptionComboBox,
        painter: QPainter,
        widget,
    ) -> None:
        # 画完整控件，不画默认箭头
        option2 = QStyleOptionComboBox(option)
        option2.subControls = option.subControls & ~QStyle.SubControl.SC_ComboBoxArrow
        option2.activeSubControls = QStyle.SubControl.SC_None
        super().drawComplexControl(control, option2, painter, widget)

        disabled = bool(option.state & QStyle.StateFlag.State_Enabled) is False
        widget_rect = option.rect

        # 向下箭头画在控件内部右侧
        btn_w = 18
        arrow_r = QRectF(
            widget_rect.right() - btn_w - 2, widget_rect.top() + 1,
            btn_w, widget_rect.height() - 2,
        )
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        self._draw_arrow_button(painter, arrow_r, up=False, hover=hover, disabled=disabled)

    # ── 通用箭头绘制 ──

    @staticmethod
    def _draw_arrow_button(
        painter: QPainter,
        rect: QRectF,
        *,
        up: bool,
        hover: bool = False,
        disabled: bool = False,
    ) -> None:
        """在给定矩形内画 +/− 几何图形（不依赖字体）。"""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if disabled:
            color = QColor(_theme.FG_MUTED)
            bg = QColor(_theme.SURFACE1)
        elif hover:
            color = QColor(_theme.MANTLE)
            bg = QColor(_theme.ACCENT).lighter(120)
        else:
            color = QColor(_theme.MANTLE)
            bg = QColor(_theme.ACCENT)

        # 先画大红底确认绘制区域
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#FF0000")))
        painter.drawRect(rect)

        # 白色几何 ＋ 或 −
        inner = rect.adjusted(3, 3, -3, -3)
        cx = inner.center().x()
        cy = inner.center().y()
        thick = max(2.0, inner.width() * 0.16)

        painter.setBrush(QBrush(QColor("#FFFFFF")))

        # 横杠（minus/plus 共用）
        painter.drawRect(QRectF(cx - thick * 3, cy - thick / 2,
                                thick * 6, thick))
        if up:
            # 竖杠（仅 plus）
            painter.drawRect(QRectF(cx - thick / 2, cy - thick * 3,
                                    thick, thick * 6))

        painter.restore()

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
            painter.setBrush(QBrush(QColor(_theme.ACCENT)))
            painter.drawRoundedRect(r, 3, 3)

            if checked:
                # 白色 ✓ — 粗笔宽 + 圆角端点
                pen = QPen(QColor(_theme.MANTLE))
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
                pen = QPen(QColor(_theme.MANTLE))
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
            border_color = QColor(_theme.ACCENT) if hover else QColor(_theme.SURFACE2)
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

        border_color = QColor(_theme.ACCENT) if (checked or hover) else QColor(_theme.SURFACE2)
        painter.setPen(QPen(border_color, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(r)

        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(_theme.ACCENT)))
            dot_r = QRectF(0, 0, r.width() * 0.45, r.height() * 0.45)
            dot_r.moveCenter(r.center())
            painter.drawEllipse(dot_r)

        painter.restore()
