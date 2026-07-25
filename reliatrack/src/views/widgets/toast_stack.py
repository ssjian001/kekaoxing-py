"""右上角动态 Toast 叠放通知组件 (Toast Notification Stack)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGraphicsDropShadowEffect,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY, DASH_SUCCESS, DASH_WARNING, DASH_DANGER


class _ToastCard(QFrame):
    """单个 Toast 消息卡片。"""

    closed = Signal(object)

    def __init__(self, message: str, level: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.message = message
        self.level = level
        self._setup_ui()

        # 3 秒自动倒计时关闭
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(3200)
        self._timer.timeout.connect(self._on_close)
        self._timer.start()

    def _setup_ui(self) -> None:
        self.setFixedWidth(320)
        self.setFixedHeight(48)
        self.setObjectName("toast-card")

        icons = {"success": "✅", "info": "ℹ️", "warning": "⚠️", "error": "❌"}
        colors = {"success": DASH_SUCCESS, "info": DASH_PRIMARY, "warning": DASH_WARNING, "error": DASH_DANGER}

        color = colors.get(self.level, DASH_PRIMARY)
        icon = icons.get(self.level, "ℹ️")

        self.setStyleSheet(
            f"QFrame#toast-card {{"
            f"  background: {_theme.BASE};"
            f"  border-left: 4px solid {color};"
            f"  border-top: 1px solid {_theme.SURFACE1};"
            f"  border-right: 1px solid {_theme.SURFACE1};"
            f"  border-bottom: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 8px;"
            f"}}"
        )
        add_shadow(self)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        lay.addWidget(lbl_icon)

        lbl_msg = QLabel(self.message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet(f"color: {_theme.TEXT}; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        lay.addWidget(lbl_msg, 1)

        btn_close = QPushButton("✖", self)
        btn_close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_theme.SUBTEXT0}; border: none; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {_theme.TEXT}; }}"
        )
        btn_close.clicked.connect(self._on_close)
        lay.addWidget(btn_close)

    def _on_close(self) -> None:
        self._timer.stop()
        self.closed.emit(self)


class ToastNotificationStack(QWidget):
    """右上角 Toast 叠放容器。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cards: list[_ToastCard] = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def show_toast(self, message: str, level: str = "info") -> None:
        """弹出一条新 Toast 卡片。"""
        card = _ToastCard(message, level, self)
        card.closed.connect(self._remove_toast)
        self._cards.append(card)
        card.show()
        self._reposition()

    def _remove_toast(self, card: _ToastCard) -> None:
        if card in self._cards:
            self._cards.remove(card)
            card.hide()
            card.deleteLater()
            self._reposition()

    def _reposition(self) -> None:
        if not self.parent():
            return
        pw, ph = self.parent().width(), self.parent().height()
        top_offset = 60
        card_w, card_h = 320, 48
        gap = 8

        self.setGeometry(pw - card_w - 20, top_offset, card_w, len(self._cards) * (card_h + gap) + 10)

        for i, card in enumerate(self._cards):
            card.move(0, i * (card_h + gap))
