"""测试计划视图 — 甘特图组件。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PySide6.QtWidgets import QWidget, QScrollArea
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QMouseEvent, QWheelEvent, QRegion

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    BLUE, GREEN, YELLOW, RED, PEACH, MAUVE, LAVENDER, TEAL,
)
from src.styles.constants import FONT_FAMILY
from src.models.test_plan import TestTask

class _GanttWidget(QWidget):
    """简化版甘特图 — 基于 QWidget 自绘。

    支持鼠标悬浮提示、滚轮缩放、任务条拖拽移动。
    """

    # 类别 → 颜色
    CATEGORY_COLORS = {
        "环境试验": BLUE,
        "机械试验": GREEN,
        "表面处理": PEACH,
        "包装": MAUVE,
        "其他": LAVENDER,
        "": LAVENDER,
    }

    # 拖拽移动任务后发射 (task_id, new_start_day)
    task_moved = Signal(int, int)

    _LABEL_W_DEFAULT = 260  # 左侧标签列初始宽度（可拖拽调节）
    _LABEL_W_MIN = 120
    _LABEL_W_MAX = 500
    _DIVIDER_MARGIN = 4  # 拖拽热区宽度
    _MIN_DAY_W = 4  # 最小每天像素宽度（极度缩小）
    _MAX_DAY_W = 150  # 最大每天像素宽度（极度放大）

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tasks: list[TestTask] = []
        self._total_days: int = 30
        self._start_date: str = ""  # 计划开始日期 (YYYY-MM-DD)
        self._row_height: int = 28
        self._header_height: int = 24
        self._bar_height: int = 18
        self._day_w: float = 30.0  # 每天像素宽度（可缩放）
        self._label_w: int = self._LABEL_W_DEFAULT  # 当前标签列宽度
        self.setMinimumHeight(150)
        self.setMouseTracking(True)  # 悬浮提示需要
        self.setStyleSheet(f"background-color: {BASE};")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 拖拽状态
        self._drag_task_idx: int | None = None
        self._show_actual: bool = False  # False=预计, True=实际
        self._drag_offset_x: int = 0
        self._drag_start_day: int = 0
        self._drag_preview_offset: int = 0  # 拖拽预览偏移（不直接改 model）
        self._hover_task_idx: int | None = None

        # 标签列拖拽调节
        self._dragging_label: bool = False

        # 设备颜色映射：equipment_id → 颜色
        self._equipment_map: dict[int, str] = {}  # {equipment_id: equipment_name}
        self._equipment_colors: dict[int, str] = {}  # {equipment_id: color_hex}
        self._palette = [BLUE, GREEN, PEACH, MAUVE, LAVENDER, YELLOW, TEAL]

        # 表头冻结：连接父级 QScrollArea 的垂直滚动
        self._scroll_v_offset: int = 0

    def set_mode(self, actual: bool) -> None:
        """切换预计/实际显示模式。"""
        self._show_actual = actual
        self.update()

    def bind_scroll_area(self, scroll_area: QScrollArea) -> None:
        """连接 QScrollArea 的垂直滚动信号，用于表头冻结。"""
        bar = scroll_area.verticalScrollBar()
        bar.valueChanged.connect(self._on_scroll)
        self._scroll_area = scroll_area

    def _on_scroll(self, value: int) -> None:
        """垂直滚动时更新偏移并重绘。"""
        self._scroll_v_offset = value
        self.update()

    def _task_day_range(self, task: TestTask) -> tuple[int, int]:
        """获取任务在甘特图中的 (start_day, duration)。

        实际模式下：用 actual_start_date/actual_end_date 相对于 _start_date 计算。
        """
        if not self._show_actual:
            return task.start_day, task.duration
        # 实际模式
        if not task.actual_start_date or not self._start_date:
            return task.start_day, task.duration  # 无实际数据则 fallback 到预计
        try:
            base = date.fromisoformat(self._start_date)
            a_start = date.fromisoformat(task.actual_start_date)
            start_day = max((a_start - base).days, 0)  # 不允许负数偏移
            if task.actual_end_date:
                a_end = date.fromisoformat(task.actual_end_date)
                duration = max((a_end - a_start).days + 1, 1)
            else:
                duration = task.duration
            return start_day, duration
        except ValueError:
            return task.start_day, task.duration

    def set_tasks(self, tasks: list[TestTask], total_days: int = 30,
                  start_date: str = "",
                  equipment_map: dict[int, str] | None = None) -> None:
        self._tasks = tasks
        self._total_days = max(total_days, 1)
        self._start_date = start_date
        if equipment_map is not None:
            self._equipment_map = equipment_map
            # 按 equipment_id 分配颜色
            unique_ids = sorted(set(equipment_map.keys()))
            self._equipment_colors = {
                eid: self._palette[i % len(self._palette)]
                for i, eid in enumerate(unique_ids)
            }
        self.setMinimumHeight(max(150, len(tasks) * self._row_height + self._header_height + 20))
        self.updateGeometry()
        self.update()

    def _chart_w(self) -> int:
        return max(self.width() - self._label_w, 100)

    def sizeHint(self) -> QSize:
        return QSize(800, max(200, len(self._tasks) * self._row_height + self._header_height + 20))

    # ── 布局计算辅助 ──

    def _bar_rect(self, idx: int) -> QRect:
        """返回第 idx 个任务条的 QRect。"""
        task = self._tasks[idx]
        start_day, duration = self._task_day_range(task)
        if self._drag_task_idx == idx and not self._show_actual:
            start_day = self._drag_start_day + self._drag_preview_offset  # 拖拽预览
        x = self._label_w + start_day * self._day_w
        y = self._header_height + idx * self._row_height + (self._row_height - self._bar_height) / 2
        return QRect(int(x), int(y), int(duration * self._day_w), self._bar_height)

    def _hit_test(self, pos: QPoint) -> int | None:
        """返回鼠标位置下的任务索引，没有则 None。"""
        for i in range(len(self._tasks)):
            if self._bar_rect(i).contains(pos):
                return i
        return None

    # ── 事件处理 ──

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        pos = event.position().toPoint()

        # 标签列宽度拖拽中
        if self._dragging_label:
            new_w = max(self._LABEL_W_MIN, min(self._LABEL_W_MAX, pos.x()))
            if new_w != self._label_w:
                self._label_w = new_w
                self.update()
            return

        # 检测是否在标签/图表分隔线附近 → 显示 SplitHCursor
        if abs(pos.x() - self._label_w) <= self._DIVIDER_MARGIN:
            self.setCursor(Qt.CursorShape.SplitHCursor)
            self.setToolTip("")
            return

        if self._drag_task_idx is not None:
            # 拖拽中 — 更新 cursor 并实时预览
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            # 计算预览偏移量（不直接改 task model）
            bar = self._bar_rect(self._drag_task_idx)
            dx = pos.x() - self._drag_offset_x - bar.x()
            day_offset = round(dx / self._day_w)
            self._drag_preview_offset = max(-self._drag_start_day, day_offset)
            self.update()
            return

        # 标签区域 hover — 显示完整任务名 tooltip
        if pos.x() < self._label_w:
            row_idx = (pos.y() - self._header_height) // self._row_height
            if 0 <= row_idx < len(self._tasks):
                task = self._tasks[row_idx]
                self.setToolTip(task.name)
                self.setCursor(Qt.CursorShape.ArrowCursor)
                return

        # 悬浮检测（甘特条）
        idx = self._hit_test(pos)
        if idx != self._hover_task_idx:
            self._hover_task_idx = idx
            if idx is not None:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                task = self._tasks[idx]
                s_day, dur = self._task_day_range(task)
                mode_prefix = "实际" if self._show_actual else "预计"
                tooltip = (
                    f"{task.name}\n"
                    f"类别: {task.category or '-'}\n"
                    f"工期: {dur} 天\n"
                    f"{mode_prefix}开始: D{s_day} → D{s_day + dur}\n"
                    f"进度: {task.progress:.0f}%\n"
                    f"状态: {task.status}"
                )
                self.setToolTip(tooltip)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip("")

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            # 标签列分隔线拖拽
            if abs(pos.x() - self._label_w) <= self._DIVIDER_MARGIN:
                self._dragging_label = True
                return
            # 甘特条拖拽（仅预计模式）
            if not self._show_actual:
                idx = self._hit_test(pos)
                if idx is not None:
                    self._drag_task_idx = idx
                    self._drag_offset_x = pos.x() - self._bar_rect(idx).x()
                    self._drag_start_day = self._tasks[idx].start_day
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            # 结束标签列拖拽
            if self._dragging_label:
                self._dragging_label = False
                return
            # 结束甘特条拖拽
            if self._drag_task_idx is not None:
                task = self._tasks[self._drag_task_idx]
                new_day = self._drag_start_day + self._drag_preview_offset
                if task.id is not None and self._drag_preview_offset != 0:
                    self.task_moved.emit(task.id, new_day)
                self._drag_task_idx = None
                self._drag_preview_offset = 0
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        """鼠标离开 widget 时重置所有拖拽状态，防止卡死。"""
        if self._dragging_label:
            self._dragging_label = False
        if self._drag_task_idx is not None:
            self._drag_task_idx = None
            self._drag_preview_offset = 0
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        """滚轮缩放天宽度。"""
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self._day_w = max(self._MIN_DAY_W, min(self._MAX_DAY_W, self._day_w * factor))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._tasks:
            p = QPainter(self)
            p.setPen(QColor(SUBTEXT0))
            p.setFont(QFont(FONT_FAMILY, 12))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无任务数据")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        label_w = self._label_w
        chart_w = w - label_w

        # ── 标签/图表分隔线 ──
        p.setPen(QPen(QColor(SURFACE1), 1))
        p.drawLine(label_w, 0, label_w, self.height())

        # ── 表头（天数标尺）— 冻结在滚动位置顶部 ──
        vy = self._scroll_v_offset  # 表头固定 Y 坐标
        p.fillRect(0, vy, w, self._header_height, QColor(SURFACE0))
        p.setPen(QColor(SUBTEXT1))
        p.setFont(QFont(FONT_FAMILY, 9))
        step = max(1, self._total_days // 15)

        # 周末列背景 — 计算哪些天是周末
        weekend_days: set[int] = set()
        base_date: date | None = None
        if self._start_date:
            try:
                base_date = date.fromisoformat(self._start_date)
            except ValueError:
                pass

        for d in range(0, self._total_days + 1):
            x = label_w + d * self._day_w
            # 判断是否周末
            is_weekend = False
            if base_date is not None:
                real_date = base_date + timedelta(days=d)
                if real_date.weekday() >= 5:  # 5=Sat, 6=Sun
                    is_weekend = True
                    weekend_days.add(d)
            if is_weekend:
                # 周末列浅色背景
                p.fillRect(int(x), self._header_height, int(self._day_w) + 1,
                           self.height() - self._header_height, QColor(MANTLE))

            if d % step == 0:
                p.setPen(QColor(SUBTEXT1))
                if base_date is not None:
                    real_date = base_date + timedelta(days=d)
                    label = f"{real_date.month}/{real_date.day}"
                else:
                    label = f"D{d}"
                p.drawText(int(x) - 20, vy, 40, self._header_height,
                           Qt.AlignmentFlag.AlignCenter, label)
            p.setPen(QColor(SURFACE1))
            if d % step == 0:
                p.drawLine(int(x), vy + self._header_height, int(x), self.height())
            p.setPen(QColor(SUBTEXT0))

        # ── 今日线 ──
        if base_date is not None:
            today = date.today()
            today_offset = (today - base_date).days
            if 0 <= today_offset <= self._total_days:
                tx = label_w + today_offset * self._day_w
                pen = QPen(QColor(PEACH), 2, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(int(tx), vy + self._header_height, int(tx), self.height())
                # "今天" 标签
                p.setPen(QColor(PEACH))
                p.setFont(QFont(FONT_FAMILY, 8))
                p.drawText(int(tx) - 20, vy, 40, self._header_height,
                           Qt.AlignmentFlag.AlignCenter, "今天")

        # ── 任务条 ──
        p.setFont(QFont(FONT_FAMILY, 8))
        # 画任务时排除冻结表头区域，防止任务内容覆盖表头
        clip_rect = event.rect()
        if vy > 0:
            # 任务区域：表头下方
            task_region = QRegion(0, 0, w, vy) + QRegion(0, vy + self._header_height, w, self.height())
            p.setClipRegion(task_region)
        for i, task in enumerate(self._tasks):
            y = self._header_height + i * self._row_height

            # 交替行背景
            if i % 2 == 1:
                p.fillRect(0, y, w, self._row_height, QColor(MANTLE))

            # 序号 + 任务名称标签 — 8pt 字体，根据可用宽度自动省略
            p.setPen(QColor(TEXT))
            p.setFont(QFont(FONT_FAMILY, 8))
            fm = p.fontMetrics()
            display = f"{i + 1}. {task.name}"
            name = fm.elidedText(display, Qt.TextElideMode.ElideRight, label_w - 16)
            p.drawText(8, y, label_w - 16, self._row_height,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       name)

            # 甘特条
            s_day, dur = self._task_day_range(task)
            bar_x = label_w + s_day * self._day_w
            bar_w = dur * self._day_w
            bar_y = y + (self._row_height - self._bar_height) / 2

            # 颜色：优先按设备着色，无设备时按类别
            if task.equipment_id and task.equipment_id in self._equipment_colors:
                color = QColor(self._equipment_colors[task.equipment_id])
            else:
                color = QColor(self.CATEGORY_COLORS.get(task.category, LAVENDER))

            # 背景（总条）
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(SURFACE2))
            p.drawRoundedRect(QRect(int(bar_x), int(bar_y), int(bar_w), self._bar_height), 4, 4)

            # 进度条
            if task.progress > 0:
                prog_w = bar_w * min(task.progress / 100.0, 1.0)
                if task.status == "completed":
                    p.setBrush(QColor(GREEN))
                else:
                    p.setBrush(color)
                p.drawRoundedRect(QRect(int(bar_x), int(bar_y), int(prog_w), self._bar_height), 4, 4)

            # 边框
            p.setPen(QPen(color, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRect(int(bar_x), int(bar_y), int(bar_w), self._bar_height), 4, 4)

            # 进度文字
            if bar_w > 30:
                p.setPen(QColor(CRUST))
                p.drawText(QRect(int(bar_x), int(bar_y), int(bar_w), self._bar_height),
                           Qt.AlignmentFlag.AlignCenter, f"{task.progress:.0f}%")

        p.end()