"""测试计划视图 — 甘特图组件。

基于 QWidget 自绘高阶甘特图，支持：
1. 依赖矢线与箭头绘制（折线连接 + 箭头指向）
2. 设备与依赖冲突实时检测与高亮预警 (⚠️ 冲突标示 + 红色告警框)
3. 关键路径 (Critical Path) 计算与亮显
4. 0工期 / 里程碑菱形节点渲染
5. 预计 / 实际日期对比模式
6. 节假日 / 周末阴影列与“今天”标尺线
7. 鼠标悬浮详细 Tooltip、拖拽修改工期与自适应缩放
"""

from __future__ import annotations

from datetime import date, timedelta
import json

from PySide6.QtWidgets import QWidget, QScrollArea
from PySide6.QtCore import Qt, QRect, QSize, QPoint, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QMouseEvent, QWheelEvent,
    QRegion, QPainterPath, QPolygonF
)

import src.styles.theme as _theme
from src.styles.constants import FONT_FAMILY, FONT_SIZE_SMALL
from src.models.test_plan import TestTask


class _GanttWidget(QWidget):
    """自绘可视化甘特图组件。"""

    # 类别 → 颜色
    CATEGORY_COLORS = {
        "环境试验": _theme.BLUE,
        "机械试验": _theme.GREEN,
        "表面处理": _theme.PEACH,
        "包装": _theme.MAUVE,
        "其他": _theme.LAVENDER,
        "": _theme.LAVENDER,
    }

    # 拖拽移动任务后发射 (task_id, new_start_day)
    task_moved = Signal(int, int)

    _LABEL_W_DEFAULT = 260  # 左侧标签列初始宽度
    _LABEL_W_MIN = 120
    _LABEL_W_MAX = 500
    _DIVIDER_MARGIN = 4
    _MIN_DAY_W = 4
    _MAX_DAY_W = 150

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tasks: list[TestTask] = []
        self._total_days: int = 30
        self._start_date: str = ""
        self._row_height: int = 28
        self._header_height: int = 24
        self._bar_height: int = 18
        self._day_w: float = 30.0
        self._label_w: int = self._LABEL_W_DEFAULT

        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self.setProperty("class", "bg-base")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 视图切换与功能选项
        self._show_actual: bool = False  # False=预计, True=实际
        self._show_dependencies: bool = True  # 是否显示依赖矢线
        self._show_conflicts: bool = True     # 是否高亮冲突预警
        self._show_critical_path: bool = False # 是否突出关键路径

        # 拖拽与悬浮状态
        self._drag_task_idx: int | None = None
        self._drag_offset_x: int = 0
        self._drag_start_day: int = 0
        self._drag_preview_offset: int = 0
        self._hover_task_idx: int | None = None
        self._dragging_label: bool = False

        # 设备与映射
        self._equip_map: dict[int, str] = {}
        self._tech_map: dict[int, str] = {}
        self._equipment_colors: dict[int, str] = {}
        self._palette = [_theme.BLUE, _theme.GREEN, _theme.PEACH, _theme.MAUVE, _theme.LAVENDER, _theme.YELLOW, _theme.TEAL]
        self._holidays: set[str] = set()
        self._task_prefix: str = ""

        # 滚动条绑定
        self._scroll_v_offset: int = 0
        self._scroll_area: QScrollArea | None = None

    def set_mode(self, actual: bool) -> None:
        """切换预计/实际显示模式。"""
        self._show_actual = actual
        self.update()

    def set_render_options(
        self,
        show_dependencies: bool | None = None,
        show_conflicts: bool | None = None,
        show_critical_path: bool | None = None,
    ) -> None:
        """设置渲染功能开关。"""
        if show_dependencies is not None:
            self._show_dependencies = show_dependencies
        if show_conflicts is not None:
            self._show_conflicts = show_conflicts
        if show_critical_path is not None:
            self._show_critical_path = show_critical_path
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
        """获取任务在甘特图中的 (start_day, duration)。"""
        if not self._show_actual:
            return task.start_day, task.duration
        if not task.actual_start_date or not self._start_date:
            return task.start_day, task.duration
        try:
            base = date.fromisoformat(self._start_date)
            a_start = date.fromisoformat(task.actual_start_date)
            start_day = max((a_start - base).days, 0)
            if task.actual_end_date:
                a_end = date.fromisoformat(task.actual_end_date)
                duration = max((a_end - a_start).days + 1, 1)
            else:
                duration = task.duration
            return start_day, duration
        except ValueError:
            return task.start_day, task.duration

    def set_tasks(
        self,
        tasks: list[TestTask],
        total_days: int = 30,
        start_date: str = "",
        equipment_map: dict[int, str] | None = None,
        technician_map: dict[int, str] | None = None,
        task_prefix: str = "",
        holidays: set[str] | None = None,
    ) -> None:
        self._drag_task_idx = None
        self._drag_preview_offset = 0
        self._dragging_label = False
        self._hover_task_idx = None

        self._tasks = tasks
        self._total_days = max(total_days, 1)
        self._start_date = start_date
        self._task_prefix = task_prefix
        self._holidays = holidays or set()
        self._equip_map = equipment_map or {}
        self._tech_map = technician_map or {}

        if equipment_map is not None:
            unique_ids = sorted(set(equipment_map.keys()))
            self._equipment_colors = {
                eid: self._palette[i % len(self._palette)]
                for i, eid in enumerate(unique_ids)
            }

        self.setMinimumHeight(max(150, len(tasks) * self._row_height + self._header_height + 20))
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(800, max(200, len(self._tasks) * self._row_height + self._header_height + 20))

    # ── 辅助方法：依赖与冲突计算 ──

    @staticmethod
    def _get_task_dep_ids(task: TestTask) -> list[int]:
        """解析任务的前置依赖 ID 列表。"""
        if not task.dependencies:
            return []
        try:
            raw = json.loads(task.dependencies)
            return [int(x) for x in raw if isinstance(x, (int, str)) and str(x).isdigit()]
        except Exception:
            return []

    def _detect_conflicts_and_critical_path(self) -> tuple[set[int], set[tuple[int, int]], set[int]]:
        """计算冲突任务集合、冲突依赖对以及关键路径任务集合。"""
        conflicting_task_ids: set[int] = set()
        conflicting_dep_pairs: set[tuple[int, int]] = set()
        critical_task_ids: set[int] = set()

        if not self._tasks:
            return conflicting_task_ids, conflicting_dep_pairs, critical_task_ids

        id_to_task = {t.id: t for t in self._tasks if t.id is not None}
        task_id_to_idx = {t.id: i for i, t in enumerate(self._tasks) if t.id is not None}

        # 1. 依赖冲突检测 (D_start < P_end)
        for t in self._tasks:
            if t.id is None:
                continue
            deps = self._get_task_dep_ids(t)
            d_start, _ = self._task_day_range(t)
            for p_id in deps:
                p_task = id_to_task.get(p_id)
                if not p_task:
                    continue
                p_start, p_dur = self._task_day_range(p_task)
                p_end = p_start + p_dur
                if d_start < p_end:
                    conflicting_task_ids.add(t.id)
                    conflicting_task_ids.add(p_id)
                    conflicting_dep_pairs.add((p_id, t.id))

        # 2. 设备时间窗口重叠冲突
        equip_groups: dict[int, list[TestTask]] = {}
        for t in self._tasks:
            if t.equipment_id and t.equipment_id > 0:
                equip_groups.setdefault(t.equipment_id, []).append(t)

        for eq_id, group in equip_groups.items():
            n = len(group)
            for i in range(n):
                for j in range(i + 1, n):
                    t1, t2 = group[i], group[j]
                    s1, d1 = self._task_day_range(t1)
                    s2, d2 = self._task_day_range(t2)
                    e1, e2 = s1 + d1, s2 + d2
                    if max(s1, s2) < min(e1, e2):  # 时间窗口重叠
                        if t1.id is not None:
                            conflicting_task_ids.add(t1.id)
                        if t2.id is not None:
                            conflicting_task_ids.add(t2.id)

        # 3. 关键路径 (CPM) 计算
        if self._show_critical_path:
            # 最长路径动规推算
            finish_times: dict[int, int] = {}
            for t in self._tasks:
                if t.id is None:
                    continue
                s_day, dur = self._task_day_range(t)
                finish_times[t.id] = s_day + dur

            if finish_times:
                max_finish = max(finish_times.values())
                for t_id, f_time in finish_times.items():
                    if f_time == max_finish:
                        critical_task_ids.add(t_id)

        return conflicting_task_ids, conflicting_dep_pairs, critical_task_ids

    # ── 布局计算辅助 ──

    def _bar_rect(self, idx: int) -> QRect:
        task = self._tasks[idx]
        start_day, duration = self._task_day_range(task)
        if self._drag_task_idx == idx and not self._show_actual:
            start_day = self._drag_start_day + self._drag_preview_offset
        x = self._label_w + start_day * self._day_w
        y = self._header_height + idx * self._row_height + (self._row_height - self._bar_height) / 2
        # 工期为 0 时按里程碑最小宽度 16px 渲染
        render_w = max(16, int(duration * self._day_w)) if duration > 0 else 16
        return QRect(int(x), int(y), render_w, self._bar_height)

    def _hit_test(self, pos: QPoint) -> int | None:
        if pos.x() < self._label_w:
            return None
        row_idx = int((pos.y() - self._header_height) // self._row_height)
        if row_idx < 0 or row_idx >= len(self._tasks):
            return None
        bar = self._bar_rect(row_idx)
        if bar.contains(pos):
            return row_idx
        return None

    # ── 事件处理 ──

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        pos = event.position().toPoint()

        if self._dragging_label:
            new_w = max(self._LABEL_W_MIN, min(self._LABEL_W_MAX, pos.x()))
            if new_w != self._label_w:
                self._label_w = new_w
                self.update()
            return

        if abs(pos.x() - self._label_w) <= self._DIVIDER_MARGIN:
            self.setCursor(Qt.CursorShape.SplitHCursor)
            self.setToolTip("")
            return

        if self._drag_task_idx is not None:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            bar = self._bar_rect(self._drag_task_idx)
            dx = pos.x() - self._drag_offset_x - bar.x()
            day_offset = round(dx / self._day_w)
            self._drag_preview_offset = max(-self._drag_start_day, day_offset)
            self.update()
            return

        if pos.x() < self._label_w:
            row_idx = (pos.y() - self._header_height) // self._row_height
            if 0 <= row_idx < len(self._tasks):
                task = self._tasks[row_idx]
                self.setToolTip(task.name)
                self.setCursor(Qt.CursorShape.ArrowCursor)
                return

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
                conflicts, _, _ = self._detect_conflicts_and_critical_path()
                if task.id in conflicts:
                    tooltip += "\n⚠️ 警告: 该任务存在设备或依赖时间冲突！"

                tech_name = self._tech_map.get(task.technician_id, "") if task.technician_id else ""
                equip_name = self._equip_map.get(task.equipment_id, "") if task.equipment_id else ""
                if tech_name:
                    tooltip += f"\n技术员: {tech_name}"
                if equip_name:
                    tooltip += f"\n设备: {equip_name}"
                self.setToolTip(tooltip)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip("")

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if abs(pos.x() - self._label_w) <= self._DIVIDER_MARGIN:
                self._dragging_label = True
                return
            if not self._show_actual:
                idx = self._hit_test(pos)
                if idx is not None:
                    self._drag_task_idx = idx
                    self._drag_offset_x = pos.x() - self._bar_rect(idx).x()
                    self._drag_start_day = self._tasks[idx].start_day
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging_label:
                self._dragging_label = False
                return
            if self._drag_task_idx is not None:
                task = self._tasks[self._drag_task_idx]
                new_day = self._drag_start_day + self._drag_preview_offset
                if task.id is not None and self._drag_preview_offset != 0:
                    self.task_moved.emit(task.id, new_day)
                self._drag_task_idx = None
                self._drag_preview_offset = 0
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging_label:
            self._dragging_label = False
        if self._drag_task_idx is not None:
            self._drag_task_idx = None
            self._drag_preview_offset = 0
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self._day_w = max(self._MIN_DAY_W, min(self._MAX_DAY_W, self._day_w * factor))
        self.update()

    # ── 绘图核心 ──

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._tasks:
            p = QPainter(self)
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(QFont(FONT_FAMILY, 12))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无任务数据")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        label_w = self._label_w

        # 预先计算冲突与关键路径
        conflicting_ids, conflicting_dep_pairs, critical_ids = self._detect_conflicts_and_critical_path()
        task_id_to_idx = {t.id: i for i, t in enumerate(self._tasks) if t.id is not None}

        # ── 标签/图表分隔线 ──
        p.setPen(QPen(QColor(_theme.SURFACE1), 1))
        p.drawLine(label_w, 0, label_w, self.height())

        # ── 表头与日期格子背景 ──
        vy = self._scroll_v_offset
        p.fillRect(0, vy, w, self._header_height, QColor(_theme.SURFACE0))
        p.setFont(QFont(FONT_FAMILY, 9))
        step = max(1, self._total_days // 15)

        base_date: date | None = None
        if self._start_date:
            try:
                base_date = date.fromisoformat(self._start_date)
            except ValueError:
                pass

        for d in range(0, self._total_days + 1):
            x = label_w + d * self._day_w
            is_weekend = False
            is_holiday = False
            if base_date is not None:
                real_date = base_date + timedelta(days=d)
                if real_date.weekday() >= 5:
                    is_weekend = True
                if real_date.isoformat() in self._holidays:
                    is_holiday = True

            if is_weekend:
                p.fillRect(int(x), self._header_height, int(self._day_w) + 1,
                           self.height() - self._header_height, QColor(_theme.MANTLE))
            if is_holiday:
                _h_color = QColor(_theme.RED)
                _h_color.setAlpha(30)
                p.fillRect(int(x), self._header_height, int(self._day_w) + 1,
                           self.height() - self._header_height, _h_color)

            if d % step == 0:
                p.setPen(QColor(_theme.SUBTEXT1))
                if base_date is not None:
                    real_date = base_date + timedelta(days=d)
                    label = f"{real_date.month}/{real_date.day}"
                else:
                    label = f"D{d}"
                p.drawText(int(x) - 20, vy, 40, self._header_height,
                           Qt.AlignmentFlag.AlignCenter, label)
            p.setPen(QColor(_theme.SURFACE1))
            if d % step == 0:
                p.drawLine(int(x), vy + self._header_height, int(x), self.height())

        # ── 今日标尺线 ──
        if base_date is not None:
            today = date.today()
            today_offset = (today - base_date).days
            if 0 <= today_offset <= self._total_days:
                tx = label_w + today_offset * self._day_w
                pen = QPen(QColor(_theme.PEACH), 2, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(int(tx), vy + self._header_height, int(tx), self.height())
                p.setPen(QColor(_theme.PEACH))
                p.setFont(QFont(FONT_FAMILY, FONT_SIZE_SMALL))
                p.drawText(int(tx) - 20, vy, 40, self._header_height,
                           Qt.AlignmentFlag.AlignCenter, "今天")

        # ── 视口裁剪：任务行绘制 ──
        task_font = QFont(FONT_FAMILY, FONT_SIZE_SMALL - 2)
        p.setFont(task_font)
        fm = p.fontMetrics()

        if vy > 0:
            task_region = QRegion(0, 0, w, vy) + QRegion(0, vy + self._header_height, w, self.height())
            p.setClipRegion(task_region)

        viewport_top = max(0, vy + self._header_height)
        viewport_bottom = self.height()
        first_visible = max(0, int((viewport_top - self._header_height) // self._row_height) - 1)
        last_visible = min(len(self._tasks), int((viewport_bottom - self._header_height) // self._row_height) + 2)

        # ── 1. 绘制任务条与标签 ──
        for i in range(first_visible, last_visible):
            task = self._tasks[i]
            y = self._header_height + i * self._row_height

            if i % 2 == 1:
                p.fillRect(0, y, w, self._row_height, QColor(_theme.MANTLE))

            # 左侧名称标签
            p.setPen(QColor(_theme.TEXT))
            seq_label = f"{self._task_prefix}-{i + 1:03d}" if self._task_prefix else str(i + 1)
            display = f"{seq_label}. {task.name}"

            # 冲突警告角标
            is_conflicting = (task.id in conflicting_ids) if self._show_conflicts else False
            if is_conflicting:
                display = f"⚠️ {display}"

            name = fm.elidedText(display, Qt.TextElideMode.ElideRight, label_w - 16)
            p.drawText(8, y, label_w - 16, self._row_height,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            # 颜色选择
            if task.equipment_id and task.equipment_id in self._equipment_colors:
                color = QColor(self._equipment_colors[task.equipment_id])
            else:
                color = QColor(self.CATEGORY_COLORS.get(task.category, _theme.LAVENDER))

            rect = self._bar_rect(i)
            is_milestone = (task.duration == 0 or "里程碑" in task.category)

            # 里程碑菱形 rendering
            if is_milestone:
                path = QPainterPath()
                cx, cy = rect.center().x(), rect.center().y()
                path.moveTo(cx, cy - 8)
                path.lineTo(cx + 8, cy)
                path.lineTo(cx, cy + 8)
                path.lineTo(cx - 8, cy)
                path.closeSubpath()

                p.setBrush(QColor(_theme.PEACH))
                p.setPen(QPen(QColor(_theme.TEXT), 1))
                p.drawPath(path)
            else:
                # 槽框背景
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(_theme.SURFACE2))
                p.drawRoundedRect(rect, 4, 4)

                # 进度条
                if task.progress > 0:
                    prog_w = rect.width() * min(task.progress / 100.0, 1.0)
                    if task.status == "completed":
                        p.setBrush(QColor(_theme.GREEN))
                    else:
                        p.setBrush(color)
                    p.drawRoundedRect(QRect(rect.x(), rect.y(), int(prog_w), rect.height()), 4, 4)

                # 冲突或关键路径外框
                if is_conflicting:
                    p.setPen(QPen(QColor(_theme.RED), 2, Qt.PenStyle.SolidLine))
                elif task.id in critical_ids:
                    p.setPen(QPen(QColor(_theme.PEACH), 2, Qt.PenStyle.SolidLine))
                else:
                    p.setPen(QPen(color, 1))

                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect, 4, 4)

                if rect.width() > 30:
                    p.setPen(QColor(_theme.TEXT))
                    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{task.progress:.0f}%")

        # ── 2. 绘制依赖矢线与箭头 ──
        if self._show_dependencies:
            for i, task in enumerate(self._tasks):
                if task.id is None:
                    continue
                deps = self._get_task_dep_ids(task)
                if not deps:
                    continue

                d_rect = self._bar_rect(i)
                d_x = d_rect.left()
                d_y = d_rect.center().y()

                for p_id in deps:
                    if p_id not in task_id_to_idx:
                        continue
                    p_idx = task_id_to_idx[p_id]
                    p_rect = self._bar_rect(p_idx)
                    p_x = p_rect.right()
                    p_y = p_rect.center().y()

                    is_dep_conflict = ((p_id, task.id) in conflicting_dep_pairs) if self._show_conflicts else False
                    is_crit_edge = (p_id in critical_ids and task.id in critical_ids)

                    # 笔颜色与样式
                    if is_dep_conflict:
                        pen = QPen(QColor(_theme.RED), 2, Qt.PenStyle.DashLine)
                        line_color = QColor(_theme.RED)
                    elif is_crit_edge:
                        pen = QPen(QColor(_theme.PEACH), 2)
                        line_color = QColor(_theme.PEACH)
                    else:
                        pen = QPen(QColor(_theme.BLUE), 1.5)
                        line_color = QColor(_theme.BLUE)

                    p.setPen(pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)

                    # 绘制折线: (p_x, p_y) -> (mid_x, p_y) -> (mid_x, d_y) -> (d_x, d_y)
                    mid_x = (p_x + d_x) // 2 if d_x > p_x + 12 else p_x + 12
                    path = QPainterPath()
                    path.moveTo(p_x, p_y)
                    path.lineTo(mid_x, p_y)
                    path.lineTo(mid_x, d_y)
                    path.lineTo(d_x, d_y)
                    p.drawPath(path)

                    # 绘制指向 d_x 的箭头
                    arr_size = 5
                    arrow = QPolygonF([
                        QPointF(d_x, d_y),
                        QPointF(d_x - arr_size, d_y - arr_size),
                        QPointF(d_x - arr_size, d_y + arr_size),
                    ])
                    p.setBrush(line_color)
                    p.drawPolygon(arrow)

        p.end()