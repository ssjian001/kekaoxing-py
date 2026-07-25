"""轻量 Toast 提示组件 — 替代状态栏和部分 QMessageBox。"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,
    QLabel,
    QHBoxLayout,
    QWidget,
)

import src.styles.theme as _t


class ToastWidget(QWidget):
    """在屏幕底部中央短暂显示的悬浮 Pill 提示条。

    用法：
        ToastWidget.show_toast(parent, "操作成功", ToastWidget.SUCCESS)
        ToastWidget.show_toast(parent, "删除失败", ToastWidget.ERROR)
        ToastWidget.show_toast(parent, "注意", ToastWidget.WARNING)
    """

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    _ICON_MAP = {
        SUCCESS: "✓",
        ERROR: "✕",
        WARNING: "⚠",
        INFO: "ℹ",
    }

    @classmethod
    def _colors(cls) -> dict[str, str]:
        """动态读取主题色，主题切换后自动生效。"""
        return {
            cls.SUCCESS: _t.GREEN,
            cls.ERROR: _t.RED,
            cls.WARNING: _t.PEACH,
            cls.INFO: _t.ACCENT,
        }

    # 多 Toast 堆叠偏移计数
    _active_count: int = 0

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

        accent_color = self._colors().get(level, _t.ACCENT)
        icon_str = self._ICON_MAP.get(level, "ℹ")

        # 内部容器，用于设置悬浮 Shadow
        container = QWidget(self)
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {_t.BG_CARD};
                border: 1px solid {_t.BORDER};
                border-left: 4px solid {accent_color};
                border-radius: 8px;
            }}
        """)

        # 容器布局
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(14, 8, 16, 8)
        c_layout.setSpacing(10)

        # 图标 Icon
        icon_label = QLabel(icon_str)
        icon_label.setStyleSheet(f"color: {accent_color}; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        c_layout.addWidget(icon_label)

        # 文本
        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"color: {_t.FG_PRIMARY}; font-size: 13px; font-weight: 500; border: none; background: transparent;")
        c_layout.addWidget(msg_label)

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(container)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 40 if _t.current_theme() == "light" else 100))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)

        # 淡出效果
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        # 定时淡出
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(350)
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)

        QTimer.singleShot(duration_ms, self._start_fadeout)
        self._fade_animation.finished.connect(self._on_finished)

        # 堆叠偏移
        ToastWidget._active_count += 1
        self._stack_idx = ToastWidget._active_count

        self.adjustSize()
        self._center_on_parent(parent)
        self.show()

    def _start_fadeout(self) -> None:
        self._fade_animation.start()

    def _on_finished(self) -> None:
        ToastWidget._active_count = max(0, ToastWidget._active_count - 1)
        self.close()

    def _center_on_parent(self, parent: QWidget) -> None:
        if not parent:
            return
        geo = parent.geometry()
        pt = parent.mapToGlobal(geo.topLeft())
        x = pt.x() + (geo.width() - self.width()) // 2
        y = pt.y() + geo.height() - 70 - (self._stack_idx - 1) * 44
        self.move(x, y)

    @classmethod
    def show_toast(
        cls,
        parent: QWidget,
        message: str,
        level: str = INFO,
        duration_ms: int = 2500,
    ) -> ToastWidget:
        return cls(parent, message, level, duration_ms)
