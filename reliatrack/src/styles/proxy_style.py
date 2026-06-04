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
        # 先让 Fusion 画完整控件（外框+文本），不画默认箭头
        # 技巧：临时移除箭头状态，让 Fusion 跳过箭头绘制
        option2 = QStyleOptionSpinBox(option)
        option2.subControls = option.subControls & ~QStyle.SubControl.SC_SpinBoxUp
        option2.subControls = option2.subControls & ~QStyle.SubControl.SC_SpinBoxDown
        option2.activeSubControls = QStyle.SubControl.SC_None
        super().drawComplexControl(control, option2, painter, widget)

        disabled = bool(option.state & QStyle.StateFlag.State_Enabled) is False
        frame_bg = QColor(_theme.BG_INPUT)

        # 手动计算按钮区域：控件右侧，上下各半
        widget_rect = option.rect
        btn_w = widget_rect.width() * 0.20  # 右侧约 20% 宽度
        if btn_w < 16:
            btn_w = 16
        btn_h = widget_rect.height() / 2
        if btn_h < 10:
            btn_h = 10

        # 上箭头
        up_r = QRectF(
            widget_rect.right() - btn_w, widget_rect.top(),
            btn_w, btn_h,
        )
        hover_up = bool(option.state & QStyle.StateFlag.State_MouseOver) and bool(
            option.activeSubControls & QStyle.SubControl.SC_SpinBoxUp
        )
        self._draw_arrow_button(
            painter, up_r, up=True, hover=hover_up, disabled=disabled,
            bg_color=frame_bg,
        )

        # 下箭头
        down_r = QRectF(
            widget_rect.right() - btn_w, widget_rect.top() + btn_h,
            btn_w, btn_h,
        )
        hover_down = bool(option.state & QStyle.StateFlag.State_MouseOver) and bool(
            option.activeSubControls & QStyle.SubControl.SC_SpinBoxDown
        )
        self._draw_arrow_button(
            painter, down_r, up=False, hover=hover_down, disabled=disabled,
            bg_color=frame_bg,
        )

    # ── ComboBox ──

    def _draw_combobox(
        self,
        control: QStyle.ComplexControl,
        option: QStyleOptionComboBox,
        painter: QPainter,
        widget,
    ) -> None:
        # 先让 Fusion 画完整控件（外框+文本），不画默认箭头
        option2 = QStyleOptionComboBox(option)
        option2.subControls = option.subControls & ~QStyle.SubControl.SC_ComboBoxArrow
        option2.activeSubControls = QStyle.SubControl.SC_None
        super().drawComplexControl(control, option2, painter, widget)

        disabled = bool(option.state & QStyle.StateFlag.State_Enabled) is False
        frame_bg = QColor(_theme.BG_INPUT)

        # 手动计算箭头区域：右侧约 20%
        widget_rect = option.rect
        btn_w = widget_rect.width() * 0.20
        if btn_w < 16:
            btn_w = 16
        arrow_r = QRectF(
            widget_rect.right() - btn_w, widget_rect.top(),
            btn_w, widget_rect.height(),
        )
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        self._draw_arrow_button(
            painter, arrow_r, up=False, hover=hover, disabled=disabled,
            bg_color=frame_bg,
        )

    # ── 通用箭头绘制 ──

    @staticmethod
    def _draw_arrow_button(
        painter: QPainter,
        rect: QRectF,
        *,
        up: bool,
        hover: bool = False,
        disabled: bool = False,
        bg_color: QColor | None = None,
    ) -> None:
        """在给定矩形内画 +/- 标识。"""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if disabled:
            color = QColor(_theme.FG_MUTED)
            bg = QColor(_theme.BG_DARK)
        elif hover:
            color = QColor(_theme.ACCENT)
            bg = QColor(_theme.BG_HOVER)
        else:
            color = QColor(_theme.FG_PRIMARY)
            bg = bg_color or QColor(_theme.BG_INPUT)

        # 先用背景色清空按钮区域
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 3, 3)

        # 绘制 + 或 − 字符
        painter.setPen(QPen(color, 2))
        font = painter.font()
        font.setPixelSize(int(rect.height() * 0.75))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "+" if up else "−")
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
