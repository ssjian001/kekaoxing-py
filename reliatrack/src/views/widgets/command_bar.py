"""自動溢出命令欄 CommandBar — 按鈕過多時自動摺疊到「更多」菜單。

移植自 qfluentwidgets CommandBar，適配 PySide6 + Catppuccin 色板。
"""
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QPainter, QColor
from PySide6.QtWidgets import (
    QFrame, QToolButton, QMenu, QWidget, QHBoxLayout,
    QSizePolicy, QStyleOption, QStyle,
)

import src.styles.theme as _t


class _CommandButton(QToolButton):
    """命令欄按鈕 — 緊湊模式 36px，普通模式 48px。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "command-button")
        self.setMinimumHeight(26)
        self.setMaximumHeight(34)
        self.setIconSize(QSize(14, 14))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def sizeHint(self):
        tw = self.fontMetrics().horizontalAdvance(self.text())
        if self.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly:
            return QSize(36, 30)
        return QSize(tw + 40, 30)


class _CommandSeparator(QWidget):
    """命令欄豎線分隔符。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(1, 18)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_dark = _t.current_theme() == "dark"
        color = QColor(255, 255, 255, 30) if is_dark else QColor(0, 0, 0, 20)
        painter.setPen(color)
        h = self.height()
        painter.drawLine(0, 0, 0, h)


class CommandBar(QFrame):
    """命令欄 — 工具列按鈕，寬度不足時自動溢出隱藏 + 顯示「更多」按鈕。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions: list[QAction] = []
        self._widgets: list[QWidget] = []
        self._button_tight = True
        self._spacing = 4

        self._more_button = QToolButton(self)
        self._more_button.setText("更多")
        self._more_button.setProperty("class", "command-more")
        self._more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._more_button.setMinimumHeight(26)
        self._more_button.hide()

        self._more_menu = QMenu(self._more_button)
        self._more_button.setMenu(self._more_menu)

    def setButtonTight(self, tight: bool):
        self._button_tight = tight

    def addAction(self, action: QAction):
        self._actions.append(action)
        btn = self._build_button(action)
        self._widgets.append(btn)
        self._relayout()
        return btn

    def addSeparator(self):
        sep = _CommandSeparator(self)
        self._widgets.append(sep)
        self._relayout()

    def addWidget(self, widget: QWidget):
        self._widgets.append(widget)
        self._relayout()

    def clearActions(self):
        self._actions.clear()
        for w in self._widgets:
            w.deleteLater()
        self._widgets.clear()
        self._more_menu.clear()
        self._relayout()

    def removeAction(self, action: QAction):
        if action in self._actions:
            idx = self._actions.index(action)
            self._actions.remove(action)
            self._widgets[idx].deleteLater()
            self._widgets.pop(idx)
            self._relayout()

    def setIconSize(self, size: QSize):
        super().setIconSize(size)
        for w in self._widgets:
            if isinstance(w, QToolButton):
                w.setIconSize(size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event):
        super().showEvent(event)
        self._relayout()

    # ── 內部 ──

    def _build_button(self, action: QAction) -> QToolButton:
        btn = _CommandButton(self)
        btn.setDefaultAction(action)
        btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if action.icon() and not action.icon().isNull()
            else Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        return btn

    def _relayout(self):
        if not self.isVisible():
            return

        margin = self.contentsMargins()
        avail_w = self.width() - margin.left() - margin.right()
        x = margin.left()
        h = self.height()

        # 先隱藏全部
        for w in self._widgets:
            w.hide()
        self._more_button.hide()
        self._more_menu.clear()

        # 計算可用寬度
        more_w = self._more_button.sizeHint().width() + self._spacing if self._actions else 0
        visible: list[QWidget] = []
        for w in self._widgets:
            ww = w.sizeHint().width() + self._spacing
            if x + ww + (more_w if self._has_hidden() or x + ww < avail_w else 0) <= avail_w:
                visible.append(w)
                x += ww
            else:
                break

        # 放置可見按鈕
        x = margin.left()
        for w in visible:
            w.show()
            w.move(x, (h - w.height()) // 2)
            w.resize(w.sizeHint())
            x += w.width() + self._spacing

        # 處理溢出
        hidden = self._widgets[len(visible):]
        if hidden or (len(visible) < len(self._widgets)):
            for w in hidden:
                self._more_menu.addAction(w.defaultAction() if hasattr(w, 'defaultAction') else None)
            self._more_button.show()
            self._more_button.move(x, (h - self._more_button.height()) // 2)

    def _has_hidden(self) -> bool:
        return len(self._widgets) > len([w for w in self._widgets if w.isVisible()])
