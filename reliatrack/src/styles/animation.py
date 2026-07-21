"""动效系统 — 事件过滤驱动的 hover/press 动画（参考 PyQt-Fluent-Widgets）。"""

from __future__ import annotations

import src.styles.theme as _t

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
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
        if obj is getattr(self, '_target', None):
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

    使用主题变量设置颜色，自动适配亮/暗主题。
    set_theme_colors(normal_alpha, hover_alpha, press_alpha) 类方法一次性设置。

    用法：
        BackgroundAnimation.set_theme_colors(0, 12, 20)
        anim = BackgroundAnimation(widget)
    """

    # 类级别默认值，可在启动时一次设置
    _normal_alpha = 0
    _hover_alpha = 12
    _press_alpha = 20

    HOVER_DURATION = 150
    PRESS_DURATION = 100

    @classmethod
    def set_theme_colors(cls, normal: int = 0, hover: int = 12,
                         press: int = 20) -> None:
        """一次性设置所有背景动画的颜色。"""
        cls._normal_alpha = normal
        cls._hover_alpha = hover
        cls._press_alpha = press

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._bg_obj = _BgColorObject(self)
        self._ani = QPropertyAnimation(self._bg_obj, b"bg_color", self)
        self._ani.setEasingCurve(QEasingCurve.Type.OutCubic)
        # 首次更新颜色
        self._bg_obj._set_color(QColor(0, 0, 0, 0))

    def _hover_color(self) -> QColor:
        is_dark = _t.current_theme() == "dark"
        base = 255 if is_dark else 0
        return QColor(base, base, base, self._hover_alpha)

    def _press_color(self) -> QColor:
        is_dark = _t.current_theme() == "dark"
        base = 255 if is_dark else 0
        return QColor(base, base, base, self._press_alpha)

    def _normal_color(self) -> QColor:
        return QColor(0, 0, 0, self._normal_alpha)

    def _animate_to(self, color: QColor, duration: int) -> None:
        self._ani.stop()
        self._ani.setStartValue(self._bg_obj._get_color())
        self._ani.setEndValue(color)
        self._ani.setDuration(duration)
        self._ani.start()

    def _on_hover(self, e: QEnterEvent) -> None:
        self._animate_to(self._hover_color(), self.HOVER_DURATION)

    def _on_leave(self, e: QEvent) -> None:
        self._animate_to(self._normal_color(), self.HOVER_DURATION)

    def _on_press(self, e: QMouseEvent) -> None:
        self._animate_to(self._press_color(), self.PRESS_DURATION)

    def _on_release(self, e: QMouseEvent) -> None:
        target = self._hover_color() if self._target.underMouse() else self._normal_color()
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


# ═══════════════════════════════════════════════════════════════════
#  TranslateYAnimation — 按鈕 press 沉降 / release 回彈
# ═══════════════════════════════════════════════════════════════════


class _YObject(QObject):
    """Provide y property for QPropertyAnimation."""

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._y = 0.0

    def _get_y(self) -> float:
        return self._y

    def _set_y(self, y: float) -> None:
        self._y = y

    y = Property(float, _get_y, _set_y)


class TranslateYAnimation(AnimationBase):
    """按鈕按壓動畫：press 時 widget 向下偏移，release 彈回。

    用法：
        anim = TranslateYAnimation(button, offset=2)
    """

    def __init__(self, parent: QWidget, offset: float = 1.5):
        super().__init__(parent)
        self._offset = offset
        self._y_obj = _YObject(self)
        self._ani_press = QPropertyAnimation(self._y_obj, b"y", self)
        self._ani_press.setDuration(80)
        self._ani_press.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._ani_release = QPropertyAnimation(self._y_obj, b"y", self)
        self._ani_release.setDuration(200)
        self._ani_release.setEasingCurve(QEasingCurve.Type.OutBack)
        self._ani_release.valueChanged.connect(self._update_pos)
        self._ani_press.valueChanged.connect(self._update_pos)
        self._original_pos: QPoint | None = None

    def _update_pos(self, y: float) -> None:
        if self._original_pos is None:
            self._original_pos = self._target.pos()
        self._target.move(self._original_pos.x(),
                         int(self._original_pos.y() + y))

    def _on_press(self, e: QMouseEvent) -> None:
        if self._original_pos is None:
            self._original_pos = self._target.pos()
        self._ani_release.stop()
        self._ani_press.stop()
        self._ani_press.setStartValue(self._y_obj._get_y())
        self._ani_press.setEndValue(self._offset)
        self._ani_press.start()

    def _on_release(self, e: QMouseEvent) -> None:
        self._ani_press.stop()
        self._ani_release.setStartValue(self._y_obj._get_y())
        self._ani_release.setEndValue(0.0)
        self._ani_release.start()

    def _on_leave(self, e: QEvent) -> None:
        # 離開按鈕時立即歸位
        self._ani_press.stop()
        self._ani_release.stop()
        self._y_obj._set_y(0.0)
        if self._original_pos is not None:
            self._target.move(self._original_pos)
