"""切換開關 SwitchButton — 自繪滑塊帶動畫。

移植自 qfluentwidgets SwitchButton，適配 PySide6 + Catppuccin 色板。
使用 QPropertyAnimation 實現滑塊滑動動畫。
"""
from PySide6.QtCore import Qt, QPropertyAnimation, QRectF, Property, Signal
from PySide6.QtGui import QPainter, QColor, QBrush
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

import src.styles.theme as _t


class _Indicator(QWidget):
    """開關滑塊指示器 — 自繪圓角背景 + 圓形滑塊。"""

    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 22)
        self._checked = False
        self._slider_x = 4.0   # 滑塊位置（未選中）
        self._hover = False
        self._pressed = False

        self._slide_ani = QPropertyAnimation(self, b"slider_x", self)
        self._slide_ani.setDuration(120)

    @Property(float)
    def slider_x(self):
        return self._slider_x

    @slider_x.setter
    def slider_x(self, val: float):
        self._slider_x = val
        self.update()

    def _checked_slider_x(self) -> float:
        return self.width() - self._circle_diam() - 4.0

    def _circle_diam(self) -> float:
        return self.height() - 8.0

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if checked == self._checked:
            return
        self._checked = checked
        target = self._checked_slider_x() if checked else 4.0
        self._slide_ani.setEndValue(target)
        self._slide_ani.start()
        self.toggled.emit(checked)

    def enterEvent(self, event):   self._hover = True; self.update()
    def leaveEvent(self, event):   self._hover = False; self.update()
    def mousePressEvent(self, event):   self._pressed = True; self.update()
    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.setChecked(not self._checked)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_dark = _t.current_theme() == "dark"
        rect = self.rect()

        # ── 背景 ──
        if self._checked:
            base = _t.ACCENT
            bg = QColor(base)
            if self._pressed:
                bg = bg.darker(120)
            elif self._hover:
                bg = bg.lighter(110)
        else:
            if self._pressed:
                bg = QColor(255, 255, 255, 18) if is_dark else QColor(0, 0, 0, 23)
            elif self._hover:
                bg = QColor(255, 255, 255, 10) if is_dark else QColor(0, 0, 0, 15)
            else:
                bg = QColor(0, 0, 0, 0)

        r = rect.height() / 2
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), r, r)

        # ── 滑塊圓圈 ──
        d = self._circle_diam()
        x = self._slider_x
        y = (rect.height() - d) / 2
        if self._checked:
            slider_color = QColor(Qt.GlobalColor.black if is_dark else Qt.GlobalColor.white)
        else:
            slider_color = QColor(255, 255, 255, 201) if is_dark else QColor(0, 0, 0, 156)
        painter.setBrush(slider_color)
        painter.drawEllipse(QRectF(x, y, d, d))


class SwitchButton(QWidget):
    """切換開關 — 左側滑塊 + 右側文字標籤。"""

    toggled = Signal(bool)

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._indicator = _Indicator(self)
        self._label = QLabel(text, self)
        self._label.setProperty("class", "caption")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._indicator)
        layout.addWidget(self._label)
        layout.addStretch()

        self._indicator.toggled.connect(self.toggled)

    def isChecked(self) -> bool:
        return self._indicator.isChecked()

    def setChecked(self, checked: bool):
        self._indicator.setChecked(checked)

    def setText(self, text: str):
        self._label.setText(text)
