"""平滑滚动引擎 — 模拟惯性滚动替代 Qt 默认 step scroll。

参考 Fluent-Widgets 的 SmoothScroll 实现，适配 PySide6。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt, QEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea, QAbstractScrollArea, QWidget


class SmoothScroll(QObject):
    """惯性滚动引擎。

    用法：
        scroll_area = QScrollArea()
        SmoothScroll(scroll_area)

    可通过 .multiplier（加速度系数，默认 2.0）和
    .duration（惯性持续 ms，默认 400）调手感。
    """

    multiplier = 2.0
    duration = 400
    steps = 20

    def __init__(self, widget: QScrollArea | QAbstractScrollArea):
        super().__init__(widget)
        self._widget = widget
        self._orient = Qt.Orientation.Vertical
        self._timer = QTimer(self)
        self._timer.setInterval(self.duration // self.steps)
        self._timer.timeout.connect(self._advance_step)

        self._step_count = 0
        self._current_step = 0
        self._step_distance = 0

        viewport = widget.viewport() if isinstance(widget, QAbstractScrollArea) else widget
        viewport.installEventFilter(self)

    def set_orientation(self, orient: Qt.Orientation) -> None:
        self._orient = orient

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and obj is self._get_viewport():
            self._on_wheel(event)
            return True
        return super().eventFilter(obj, event)

    def _get_viewport(self) -> QObject:
        if isinstance(self._widget, QAbstractScrollArea):
            return self._widget.viewport()
        return self._widget

    def _on_wheel(self, event: QEvent) -> None:
        wheel = event  # type: QWheelEvent
        delta = wheel.angleDelta().y()
        if delta == 0:
            return

        self._timer.stop()

        speed = delta * self.multiplier / 120.0
        step_dist = speed * 40.0 / self.steps
        self._step_distance = step_dist
        self._current_step = 0
        self._step_count = max(1, int(abs(speed) * 3))

        if self._step_count > 1:
            self._do_scroll(int(step_dist))
            self._current_step = 1
            self._timer.start()
        else:
            self._do_scroll(int(speed * 40.0))

    def _advance_step(self) -> None:
        if self._current_step >= self._step_count:
            self._timer.stop()
            return

        progress = self._current_step / self._step_count
        eased = 1 - (1 - progress) ** 2
        prev_eased = 1 - ((self._current_step - 1) / self._step_count) ** 2 \
            if self._current_step > 0 else 0
        step_pixels = int(self._step_distance * self._step_count * (eased - prev_eased))

        if step_pixels != 0:
            self._do_scroll(step_pixels)

        self._current_step += 1

    def _do_scroll(self, pixels: int) -> None:
        sb = self._widget.verticalScrollBar() \
            if self._orient == Qt.Orientation.Vertical \
            else self._widget.horizontalScrollBar()

        if sb is None:
            return

        cur = sb.value()
        max_val = sb.maximum()
        min_val = sb.minimum()
        sb.setValue(max(min_val, min(max_val, cur - pixels)))


def install_smooth_scroll(widget: QWidget) -> SmoothScroll | None:
    """给 QScrollArea / QAbstractScrollArea 安装平滑滚动。

    Returns:
        SmoothScroll 实例（可调整参数），或 None。
    """
    if isinstance(widget, (QScrollArea, QAbstractScrollArea)):
        return SmoothScroll(widget)
    return None
