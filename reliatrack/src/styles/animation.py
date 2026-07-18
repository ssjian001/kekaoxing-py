"""动效系统 — 事件过滤驱动的 hover/press 动画（参考 PyQt-Fluent-Widgets）。"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import QMouseEvent, QEnterEvent, QColor
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect


# ═══════════════════════════════════════════════════════════════════
#  AnimationBase — 事件过滤基类，自动拦截 hover/press/release
# ═══════════════════════════════════════════════════════════════════


class AnimationBase(QObject):
    """动画基类，通过事件过滤器驱动动画。

    子类重写 _on_hover/_on_leave/_on_press/_on_release 实现具体动画。
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)
        self._target = parent
        parent.installEventFilter(self)

    def _on_hover(self, e: QEnterEvent) -> None:
        pass

    def _on_leave(self, e: QEvent) -> None:
        pass

    def _on_press(self, e: QMouseEvent) -> None:
        pass

    def _on_release(self, e: QMouseEvent) -> None:
        pass

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self._target:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress:
                self._on_press(event)
            elif t == QEvent.Type.MouseButtonRelease:
                self._on_release(event)
            elif t == QEvent.Type.Enter:
                self._on_hover(event)
            elif t == QEvent.Type.Leave:
                self._on_leave(event)
        return super().eventFilter(obj, event)


# ═══════════════════════════════════════════════════════════════════
#  BackgroundAnimation — hover/press 背景色过渡
# ═══════════════════════════════════════════════════════════════════

class _BgColorObject(QObject):
    """辅助对象，提供给 QPropertyAnimation 动画背景色。"""

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._color = QColor(0, 0, 0, 0)

    def _get_color(self) -> QColor:
        return self._color

    def _set_color(self, color: QColor) -> None:
        self._color = color
        p = self.parent()
        if p and isinstance(p, QWidget):
            p.update()

    bg_color = Property(QColor, _get_color, _set_color)


class BackgroundAnimation(AnimationBase):
    """Widget hover/press 背景色过渡动画。

    用法：
        anim = BackgroundAnimation(widget)
        anim.normal_color = QColor(0, 0, 0, 0)
        anim.hover_color = QColor(0, 0, 0, 20)
        anim.press_color = QColor(0, 0, 0, 40)
    """

    HOVER_DURATION = 150
    PRESS_DURATION = 100

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.normal_color = QColor(0, 0, 0, 0)
        self.hover_color = QColor(0, 0, 0, 0)
        self.press_color = QColor(0, 0, 0, 0)

        self._bg_obj = _BgColorObject(self)
        self._ani = QPropertyAnimation(self._bg_obj, b"bg_color", self)
        self._ani.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate_to(self, color: QColor, duration: int) -> None:
        self._ani.stop()
        self._ani.setStartValue(self._bg_obj._get_color())
        self._ani.setEndValue(color)
        self._ani.setDuration(duration)
        self._ani.start()

    def _on_hover(self, e: QEnterEvent) -> None:
        self._animate_to(self.hover_color, self.HOVER_DURATION)

    def _on_leave(self, e: QEvent) -> None:
        self._animate_to(self.normal_color, self.HOVER_DURATION)

    def _on_press(self, e: QMouseEvent) -> None:
        self._animate_to(self.press_color, self.PRESS_DURATION)

    def _on_release(self, e: QMouseEvent) -> None:
        target = self.hover_color if self._target.underMouse() else self.normal_color
        self._animate_to(target, self.HOVER_DURATION)


# ═══════════════════════════════════════════════════════════════════
#  DropShadowAnimation — 卡片阴影 hover 淡入/淡出
# ═══════════════════════════════════════════════════════════════════


class DropShadowAnimation(AnimationBase):
    """卡片阴影 hover 动效：进入时阴影渐显，离开时渐消。

    用法：
        shadow = DropShadowAnimation(card_widget)
        shadow.setup(blur=16, offset_y=4, normal_alpha=0, hover_alpha=40)
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._blur = 16
        self._offset = QPoint(0, 4)
        self._normal_alpha = 0
        self._hover_alpha = 40
        self._shadow_effect: QGraphicsDropShadowEffect | None = None
        self._ani_color: QPropertyAnimation | None = None

    def setup(self, blur: int = 16, offset_y: int = 4,
              normal_alpha: int = 0, hover_alpha: int = 40) -> None:
        self._blur = blur
        self._offset = QPoint(0, offset_y)
        self._normal_alpha = normal_alpha
        self._hover_alpha = hover_alpha

    def _ensure_shadow(self) -> QGraphicsDropShadowEffect:
        if self._shadow_effect is None:
            self._shadow_effect = QGraphicsDropShadowEffect(self)
            self._shadow_effect.setBlurRadius(self._blur)
            self._shadow_effect.setOffset(self._offset)
            self._shadow_effect.setColor(QColor(0, 0, 0, self._normal_alpha))
            self._ani_color = QPropertyAnimation(
                self._shadow_effect, b"color", self)
            self._ani_color.setDuration(150)
            self._ani_color.setEasingCurve(QEasingCurve.Type.OutCubic)
        return self._shadow_effect

    def _animate_shadow_alpha(self, alpha: int) -> None:
        effect = self._ensure_shadow()
        self._target.setGraphicsEffect(effect)
        self._ani_color.stop()
        self._ani_color.setStartValue(effect.color())
        self._ani_color.setEndValue(QColor(0, 0, 0, alpha))
        self._ani_color.start()

    def _on_hover(self, e: QEnterEvent) -> None:
        self._animate_shadow_alpha(self._hover_alpha)

    def _on_leave(self, e: QEvent) -> None:
        self._animate_shadow_alpha(self._normal_alpha)
