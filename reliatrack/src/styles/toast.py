"""轻量 Toast 提示组件 — 替代状态栏和部分 QMessageBox。"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.styles.theme import (
    BASE,
    GREEN,
    PEACH,
    TEXT,
)


class ToastWidget(QWidget):
    """在屏幕底部中央短暂显示的提示条。

    用法：
        ToastWidget.show_toast(parent, "操作成功", ToastWidget.SUCCESS)
        ToastWidget.show_toast(parent, "删除失败", ToastWidget.ERROR)
    """

    SUCCESS = "success"
    ERROR = "error"
    INFO = "info"

    _COLORS = {
        SUCCESS: GREEN,
        ERROR: PEACH,
        INFO: BASE,
    }

    def __init__(
        self,
        parent: QWidget,
        message: str,
        level: str = INFO,
        duration_ms: int = 2500,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        bg_color = self._COLORS.get(level, BASE)
        self.setStyleSheet(
            f"background-color: {bg_color}; color: {TEXT}; "
            f"border-radius: 6px; padding: 8px 16px; font-size: 13px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # 淡出效果
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        # 定时淡出
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(400)
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)

        QTimer.singleShot(duration_ms, self._start_fadeout)
        self._fade_animation.finished.connect(self.close)

        self.adjustSize()
        self._center_on_parent(parent)
        self.show()

    def _start_fadeout(self) -> None:
        self._fade_animation.start()

    def _center_on_parent(self, parent: QWidget) -> None:
        if not parent:
            return
        parent_geo = parent.geometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + parent_geo.height() - self.height() - 40
        self.move(x, y)

    @classmethod
    def show_toast(
        cls,
        parent: QWidget,
        message: str,
        level: str = INFO,
        duration_ms: int = 2500,
    ) -> ToastWidget:
        """在父窗口上方显示 Toast 提示。"""
        toast = cls(parent, message, level, duration_ms)
        return toast
