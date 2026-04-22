"""数据看板页面 — Dashboard Widget

独立的 QWidget 页面，用于展示项目统计和可视化。
使用 QPainter 自绘所有图表（不依赖 matplotlib）。

布局（QScrollArea 内垂直排列）:
  1. 总览卡片行（4 张水平卡片）
  2. 分类进度条
  3. 每周工作量柱状图
  4. 即将到期任务列表
  5. 设备利用率排行
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QApplication,
)
from PySide6.QtCore import Qt, QRectF, QSize, QPointF, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QFontMetrics,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
)

# ═══════════════════════════════════════════════════════════════════════
#  Catppuccin Mocha 色板
# ═══════════════════════════════════════════════════════════════════════
COL_BASE: str = "#11111b"
COL_MANTLE: str = "#181825"
COL_SURFACE0: str = "#313244"
COL_SURFACE1: str = "#45475a"
COL_SURFACE2: str = "#585b70"
COL_OVERLAY0: str = "#6c7086"
COL_TEXT: str = "#cdd6f4"
COL_SUBTEXT: str = "#a6adc8"
COL_BLUE: str = "#89b4fa"
COL_RED: str = "#f38ba8"
COL_YELLOW: str = "#f9e2af"
COL_GREEN: str = "#a6e3a1"
COL_ORANGE: str = "#fab387"
COL_TEAL: str = "#94e2d5"
COL_MAUVE: str = "#cba6f7"

SECTION_DEFAULT_COLORS: dict[str, str] = {
    "env": "#4FC3F7",
    "mech": "#81C784",
    "surf": "#FFB74D",
    "pack": "#BA68C8",
}

SECTION_DEFAULT_LABELS: dict[str, str] = {
    "env": "环境测试",
    "mech": "机械测试",
    "surf": "表面/材料测试",
    "pack": "包装测试",
}


def _qcolor(hex_color: str, alpha: int = 255) -> QColor:
    """Parse hex color string to QColor."""
    c = QColor(hex_color)
    if alpha < 255:
        c.setAlpha(alpha)
    return c


def _get_section_label(section_key: str, sections: list) -> str:
    """获取分类中文标签。"""
    for s in sections:
        if isinstance(s, dict) and s.get("key") == section_key:
            return s.get("label", section_key)
    return SECTION_DEFAULT_LABELS.get(section_key, section_key)


def _get_section_color(section_key: str, sections: list) -> str:
    """获取分类颜色。"""
    for s in sections:
        if isinstance(s, dict) and s.get("key") == section_key:
            return s.get("color", SECTION_DEFAULT_COLORS.get(section_key, COL_BLUE))
    return SECTION_DEFAULT_COLORS.get(section_key, COL_BLUE)


def _round_rect(path: QPainterPath, rect: QRectF, radius: float) -> QPainterPath:
    """Add a rounded rectangle to path."""
    path.addRoundedRect(rect, radius, radius)
    return path


# ═══════════════════════════════════════════════════════════════════════
#  1. 总览卡片
# ═══════════════════════════════════════════════════════════════════════

class _OverviewCard(QWidget):
    """单张总览卡片：图标 + 大数字 + 说明文字。"""

    def __init__(self, icon: str, value: str = "—", label: str = "", parent=None):
        super().__init__(parent)
        self.icon = icon
        self._value = value
        self._label = label
        self.setFixedHeight(90)

    def set_data(self, value: str, label: str):
        self._value = value
        self._label = label
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景
        bg = _qcolor(COL_MANTLE)
        path = QPainterPath()
        _round_rect(path, QRectF(0, 0, w, h), 10)
        p.fillPath(path, QBrush(bg))

        # 边框
        pen = QPen(_qcolor(COL_SURFACE0), 1)
        p.setPen(pen)
        p.drawPath(path)

        # 图标
        icon_font = QFont()
        icon_font.setPixelSize(28)
        p.setFont(icon_font)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawText(12, 34, self.icon)

        # 大数字
        value_font = QFont()
        value_font.setPixelSize(26)
        value_font.setBold(True)
        p.setFont(value_font)
        p.setPen(_qcolor(COL_TEXT))
        p.drawText(48, 42, self._value)

        # 说明
        label_font = QFont()
        label_font.setPixelSize(13)
        p.setFont(label_font)
        p.setPen(_qcolor(COL_OVERLAY0))
        p.drawText(48, 68, self._label)

        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  2. 分类进度条区域
# ═══════════════════════════════════════════════════════════════════════

class _SectionProgressWidget(QWidget):
    """分类进度条绘制区域。"""

    BAR_HEIGHT: int = 14
    ROW_HEIGHT: int = 44

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []  # [{key, label, color, done, total}]
        self.setMinimumHeight(60)

    def set_data(self, data: list[dict]):
        self._data = data
        # 重新计算高度
        h = 40 + len(data) * self.ROW_HEIGHT
        self.setFixedHeight(max(h, 60))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 标题
        title_font = QFont()
        title_font.setPixelSize(16)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(_qcolor(COL_TEXT))
        p.drawText(0, 24, "分类进度")

        y = 40
        bar_w = w - 220  # 左侧标签120 + 右侧百分比80 + 间距20
        bar_x = 140

        for item in self._data:
            label = item.get("label", "")
            color = item.get("color", COL_BLUE)
            done = item.get("done", 0)
            total = item.get("total", 0)
            pct = done / total if total > 0 else 0.0

            # 颜色圆点
            dot_color = _qcolor(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(dot_color))
            p.drawEllipse(12, y + 6, 10, 10)

            # 分类名
            name_font = QFont()
            name_font.setPixelSize(13)
            p.setFont(name_font)
            p.setPen(_qcolor(COL_TEXT))
            p.drawText(28, y + 16, label)

            # 进度条背景
            bar_rect = QRectF(bar_x, y + 3, bar_w, self.BAR_HEIGHT)
            bg_path = QPainterPath()
            _round_rect(bg_path, bar_rect, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.fillPath(bg_path, QBrush(_qcolor(COL_SURFACE0)))

            # 进度条填充
            if pct > 0:
                fill_w = max(bar_w * pct, self.BAR_HEIGHT)
                fill_rect = QRectF(bar_x, y + 3, fill_w, self.BAR_HEIGHT)
                grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
                fill_color = _qcolor(color)
                grad.setColorAt(0, fill_color)
                lighter = QColor(fill_color)
                lighter.setAlpha(180)
                grad.setColorAt(1, lighter)
                fill_path = QPainterPath()
                _round_rect(fill_path, fill_rect, 7)
                p.fillPath(fill_path, QBrush(grad))

            # 百分比文字
            pct_font = QFont()
            pct_font.setPixelSize(13)
            pct_font.setBold(True)
            p.setFont(pct_font)
            p.setPen(_qcolor(COL_SUBTEXT))
            pct_text = f"{done}/{total} ({pct * 100:.0f}%)"
            p.drawText(bar_x + bar_w + 12, y + 16, pct_text)

            y += self.ROW_HEIGHT

        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  3. 每周工作量柱状图
# ═══════════════════════════════════════════════════════════════════════

class _WeeklyChartWidget(QWidget):
    """每周工作量柱状图（QPainter 自绘）。"""

    CHART_TOP: int = 40
    CHART_BOTTOM_PAD: int = 36
    SIDE_PAD: int = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._week_data: list[dict] = []  # [{label, value}]
        self._hover_index: int = -1
        self.setMinimumHeight(220)
        self.setMouseTracking(True)

    def set_data(self, week_data: list[dict]):
        self._week_data = week_data
        n = len(week_data)
        self.setFixedHeight(max(220, 40 + 140 + 36))
        self.update()

    def _bar_rect(self, idx: int) -> QRectF:
        n = len(self._week_data)
        if n == 0:
            return QRectF()
        w = self.width()
        chart_left = self.SIDE_PAD
        chart_right = w - 20
        chart_width = chart_right - chart_left
        bar_gap = max(chart_width * 0.15 / n, 4)
        total_gaps = bar_gap * (n + 1)
        bar_w = (chart_width - total_gaps) / n
        bar_x = chart_left + bar_gap + idx * (bar_w + bar_gap)
        chart_h = 140
        chart_top = self.CHART_TOP
        return QRectF(bar_x, chart_top, bar_w, chart_h)

    def mouseMoveEvent(self, event):
        old = self._hover_index
        self._hover_index = -1
        for i in range(len(self._week_data)):
            r = self._bar_rect(i)
            if r.contains(QPointF(event.position())):
                self._hover_index = i
                break
        if self._hover_index != old:
            self.update()

    def leaveEvent(self, event):
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 标题
        title_font = QFont()
        title_font.setPixelSize(16)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(_qcolor(COL_TEXT))
        p.drawText(0, 24, "工作量分布（按周）")

        if not self._week_data:
            hint_font = QFont()
            hint_font.setPixelSize(13)
            p.setFont(hint_font)
            p.setPen(_qcolor(COL_OVERLAY0))
            p.drawText(self.SIDE_PAD, self.CHART_TOP + 70, "暂无数据")
            p.end()
            return

        chart_left = self.SIDE_PAD
        chart_right = w - 20
        chart_top = self.CHART_TOP
        chart_h = 140
        chart_bottom = chart_top + chart_h

        max_val = max((d["value"] for d in self._week_data), default=1)
        if max_val <= 0:
            max_val = 1

        # Y 轴网格线 + 刻度
        grid_font = QFont()
        grid_font.setPixelSize(11)
        p.setFont(grid_font)
        p.setPen(_qcolor(COL_SURFACE0))

        for i in range(5):
            y = chart_top + chart_h - (chart_h * i / 4)
            p.drawLine(int(chart_left), int(y), int(chart_right), int(y))
            val = max_val * i / 4
            p.setPen(_qcolor(COL_OVERLAY0))
            p.drawText(0, int(y) + 4, f"{val:.0f}")
            p.setPen(_qcolor(COL_SURFACE0))

        # 柱子
        n = len(self._week_data)
        bar_gap = max((chart_right - chart_left) * 0.15 / n, 4)
        total_gaps = bar_gap * (n + 1)
        bar_w = (chart_right - chart_left - total_gaps) / n

        for i, item in enumerate(self._week_data):
            bar_x = chart_left + bar_gap + i * (bar_w + bar_gap)
            val = item.get("value", 0)
            bar_h = (val / max_val) * chart_h
            bar_y = chart_bottom - bar_h

            # 柱子渐变
            is_hover = (i == self._hover_index)
            grad = QLinearGradient(bar_x, bar_y, bar_x, chart_bottom)
            if is_hover:
                grad.setColorAt(0, _qcolor("#b4d0ff"))
                grad.setColorAt(1, _qcolor(COL_BLUE))
            else:
                grad.setColorAt(0, _qcolor(COL_BLUE, 220))
                grad.setColorAt(1, _qcolor("#5a8fe0", 180))

            bar_rect = QRectF(bar_x, bar_y, bar_w, bar_h)
            if bar_h > 0:
                path = QPainterPath()
                _round_rect(path, bar_rect, min(4, bar_w / 3))
                p.setPen(Qt.PenStyle.NoPen)
                p.fillPath(path, QBrush(grad))

            # 数值标签（柱子上方）
            if val > 0:
                val_font = QFont()
                val_font.setPixelSize(11)
                val_font.setBold(True)
                p.setFont(val_font)
                p.setPen(_qcolor(COL_TEXT))
                val_text = f"{val:.0f}"
                fm = QFontMetrics(val_font)
                tw = fm.horizontalAdvance(val_text)
                p.drawText(int(bar_x + bar_w / 2 - tw / 2), int(bar_y - 6), val_text)

            # X 轴标签
            label_font = QFont()
            label_font.setPixelSize(11)
            p.setFont(label_font)
            p.setPen(_qcolor(COL_SUBTEXT))
            label = item.get("label", "")
            fm = QFontMetrics(label_font)
            tw = fm.horizontalAdvance(label)
            p.drawText(int(bar_x + bar_w / 2 - tw / 2), int(chart_bottom + 20), label)

        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  4. 即将到期任务列表
# ═══════════════════════════════════════════════════════════════════════

class _UpcomingTasksWidget(QWidget):
    """即将到期任务列表（7天内）。"""

    ROW_HEIGHT: int = 36
    jump_to_task = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[dict] = []
        self.setMinimumHeight(80)
        self.setMouseTracking(True)

    def set_data(self, tasks: list[dict]):
        self._tasks = tasks[:10]
        self._task_ids = [t.get("task_id", 0) for t in self._tasks]
        h = 40 + len(self._tasks) * self.ROW_HEIGHT
        self.setFixedHeight(max(h, 80))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 标题
        title_font = QFont()
        title_font.setPixelSize(16)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(_qcolor(COL_TEXT))
        p.drawText(0, 24, "📅 即将到期（7天内）")

        if not self._tasks:
            hint_font = QFont()
            hint_font.setPixelSize(13)
            p.setFont(hint_font)
            p.setPen(_qcolor(COL_OVERLAY0))
            p.drawText(12, 64, "暂无即将到期的任务")
            p.end()
            return

        y = 44
        for t in self._tasks:
            status = t.get("status", "normal")  # "overdue", "today", "normal"

            # 行背景（交替）
            row_idx = self._tasks.index(t)
            if row_idx % 2 == 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(_qcolor(COL_MANTLE, 100)))
                row_rect = QRectF(0, y - 4, w, self.ROW_HEIGHT)
                p.drawRect(row_rect.toRect())

            # 颜色
            if status == "overdue":
                text_col = _qcolor(COL_RED)
            elif status == "today":
                text_col = _qcolor(COL_YELLOW)
            else:
                text_col = _qcolor(COL_TEXT)

            font = QFont()
            font.setPixelSize(12)

            x = 12
            # 编号
            p.setFont(font)
            p.setPen(_qcolor(COL_OVERLAY0))
            num_text = t.get("num", "")
            fm = QFontMetrics(font)
            num_w = fm.horizontalAdvance(num_text) + 12
            p.drawText(x, y + 14, num_text)
            x += num_w

            # 名称
            p.setPen(text_col)
            name_text = t.get("name", "")
            name_w = fm.horizontalAdvance(name_text) + 16
            p.drawText(x, y + 14, name_text)
            x += name_w

            # 分类标签（彩色背景）
            section_label = t.get("section_label", "")
            section_color = t.get("section_color", COL_BLUE)
            tag_w = fm.horizontalAdvance(section_label) + 12
            tag_rect = QRectF(x, y, tag_w, 20)
            tag_path = QPainterPath()
            _round_rect(tag_path, tag_rect, 4)
            tag_color = _qcolor(section_color, 50)
            p.setPen(Qt.PenStyle.NoPen)
            p.fillPath(tag_path, QBrush(tag_color))
            p.setPen(_qcolor(section_color))
            p.drawText(int(x + 6), y + 14, section_label)
            x += tag_w + 12

            # 结束日期
            p.setPen(text_col)
            date_text = t.get("end_date", "")
            date_w = fm.horizontalAdvance(date_text) + 12
            p.drawText(x, y + 14, date_text)
            x += date_w

            # 进度
            prog_text = t.get("progress_text", "0%")
            prog_color = text_col if status == "normal" else _qcolor("#e64553")
            p.setPen(prog_color)
            p.drawText(x, y + 14, prog_text)

            y += self.ROW_HEIGHT

        p.end()

    def _task_at_y(self, y: int) -> int:
        """根据 y 坐标返回任务索引，-1 表示无"""
        if y < 44:
            return -1
        idx = (y - 44) // self.ROW_HEIGHT
        if 0 <= idx < len(self._tasks):
            return idx
        return -1

    def mouseDoubleClickEvent(self, event):
        """双击任务行跳转到甘特图"""
        idx = self._task_at_y(event.position().y())
        if 0 <= idx < len(getattr(self, '_task_ids', [])):
            task_id = self._task_ids[idx]
            if task_id:
                self.jump_to_task.emit(task_id)

    def mouseMoveEvent(self, event):
        """悬停时显示手形光标"""
        idx = self._task_at_y(event.position().y())
        if idx >= 0:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)


# ═══════════════════════════════════════════════════════════════════════
#  5. 设备利用率排行
# ═══════════════════════════════════════════════════════════════════════

class _DeviceUtilWidget(QWidget):
    """设备利用率排行。"""

    BAR_HEIGHT: int = 14
    ROW_HEIGHT: int = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self.setMinimumHeight(60)

    def set_data(self, data: list[dict]):
        self._data = data
        h = 40 + len(data) * self.ROW_HEIGHT
        self.setFixedHeight(max(h, 60))
        self.update()

    @staticmethod
    def _util_color(pct: float) -> str:
        """根据利用率返回颜色。"""
        if pct > 100:
            return COL_RED
        elif pct > 80:
            return COL_ORANGE
        elif pct > 50:
            return COL_YELLOW
        return COL_GREEN

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 标题
        title_font = QFont()
        title_font.setPixelSize(16)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(_qcolor(COL_TEXT))
        p.drawText(0, 24, "🔧 设备利用率")

        if not self._data:
            hint_font = QFont()
            hint_font.setPixelSize(13)
            p.setFont(hint_font)
            p.setPen(_qcolor(COL_OVERLAY0))
            p.drawText(12, 64, "暂无设备利用率数据（请先执行排程）")
            p.end()
            return

        y = 40
        bar_w = w - 200
        bar_x = 160

        for item in self._data:
            name = item.get("name", "")
            pct = item.get("utilization", 0.0)
            color = self._util_color(pct)

            # 设备名
            name_font = QFont()
            name_font.setPixelSize(13)
            p.setFont(name_font)
            p.setPen(_qcolor(COL_TEXT))
            p.drawText(12, y + 14, name)

            # 进度条背景
            bar_rect = QRectF(bar_x, y + 1, bar_w, self.BAR_HEIGHT)
            bg_path = QPainterPath()
            _round_rect(bg_path, bar_rect, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.fillPath(bg_path, QBrush(_qcolor(COL_SURFACE0)))

            # 进度条填充（最大显示到 120% 宽度）
            display_pct = min(pct, 120.0)
            fill_pct = display_pct / 100.0
            if fill_pct > 0:
                fill_w = max(bar_w * fill_pct, self.BAR_HEIGHT)
                fill_rect = QRectF(bar_x, y + 1, fill_w, self.BAR_HEIGHT)
                grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
                fill_color = _qcolor(color)
                grad.setColorAt(0, fill_color)
                lighter = QColor(fill_color)
                lighter.setAlpha(180)
                grad.setColorAt(1, lighter)
                fill_path = QPainterPath()
                _round_rect(fill_path, fill_rect, 7)
                p.fillPath(fill_path, QBrush(grad))

            # 百分比
            pct_font = QFont()
            pct_font.setPixelSize(13)
            pct_font.setBold(True)
            p.setFont(pct_font)
            p.setPen(_qcolor(color))
            p.drawText(bar_x + bar_w + 10, y + 14, f"{pct:.1f}%")

            y += self.ROW_HEIGHT

        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  仪表盘主控件
# ═══════════════════════════════════════════════════════════════════════

class DashboardWidget(QWidget):
    """数据看板页面。

    用法::

        dashboard = DashboardWidget()
        dashboard.update_data(tasks, sections, schedule_result, start_date)
    """

    jump_to_task = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 数据缓存
        self._tasks: list = []
        self._sections: list = []
        self._schedule_result: Optional[dict] = None
        self._start_date: Optional[str] = None

        self._build_ui()

    def _build_ui(self):
        """构建 UI 布局。"""
        # 外层 QScrollArea
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background-color: {COL_BASE};
                border: none;
            }}
            """
        )

        # 内容容器
        self._container = QWidget()
        self._container.setStyleSheet(f"background-color: {COL_BASE};")
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(16, 16, 16, 24)
        self._main_layout.setSpacing(20)

        # ── 1. 总览卡片行 ──
        self._card_tasks = _OverviewCard("📋", "—", "总任务 / 已完成")
        self._card_duration = _OverviewCard("📅", "—", "预计总工期")
        self._card_progress = _OverviewCard("📊", "—", "整体进度")
        self._card_overdue = _OverviewCard("⚠️", "—", "逾期/风险任务")

        cards_layout = QHBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)
        cards_layout.addWidget(self._card_tasks)
        cards_layout.addWidget(self._card_duration)
        cards_layout.addWidget(self._card_progress)
        cards_layout.addWidget(self._card_overdue)
        self._main_layout.addLayout(cards_layout)

        # ── 2. 分类进度条 ──
        self._section_progress = _SectionProgressWidget()
        self._main_layout.addWidget(self._section_progress)

        # ── 3. 每周工作量柱状图 ──
        self._weekly_chart = _WeeklyChartWidget()
        self._main_layout.addWidget(self._weekly_chart)

        # ── 4. 即将到期任务列表 ──
        self._upcoming_tasks = _UpcomingTasksWidget()
        self._upcoming_tasks.jump_to_task.connect(self.jump_to_task)
        self._main_layout.addWidget(self._upcoming_tasks)

        # ── 5. 设备利用率排行 ──
        self._device_util = _DeviceUtilWidget()
        self._main_layout.addWidget(self._device_util)

        self._main_layout.addStretch()

        self._scroll.setWidget(self._container)

        # 最外层布局
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

    # ────────────────────────────────────────────────────────────────
    #  数据更新
    # ────────────────────────────────────────────────────────────────

    def update_data(
        self,
        tasks: list,
        sections: list,
        schedule_result: dict = None,
        start_date=None,
    ):
        """更新看板数据并刷新显示。

        Parameters
        ----------
        tasks : list
            Task 对象列表。
        sections : list
            Section 字典列表，每项含 key, label, color。
        schedule_result : dict, optional
            排程结果，含 report.device_utilization 等。
        start_date : str, optional
            项目开始日期（YYYY-MM-DD）。
        """
        self._tasks = tasks
        self._sections = sections or []
        self._schedule_result = schedule_result
        self._start_date = start_date

        # 空状态提示
        if not tasks:
            self._card_tasks.set_data("0/0", "总任务 / 已完成")
            self._card_duration.set_data("—", "预计总工期")
            self._card_progress.set_data("—", "整体进度")
            self._card_overdue.set_data("0", "逾期/风险任务")
            self._section_progress.set_data([])
            self._weekly_chart.set_data([])
            self._upcoming_tasks.set_data([])
            self._device_util.set_data([])
            return

        self._update_overview_cards()
        self._update_section_progress()
        self._update_weekly_chart()
        self._update_upcoming_tasks()
        self._update_device_utilization()

    def _get_field(self, obj, name: str, default=0):
        """安全读取对象或字典的属性。"""
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    # ── 总览卡片 ──

    def _update_overview_cards(self):
        tasks = self._tasks

        # 总任务 / 已完成
        total = len(tasks)
        completed = sum(1 for t in tasks if self._get_field(t, "done", False))
        self._card_tasks.set_data(
            f"{completed}/{total}",
            "总任务 / 已完成",
        )

        # 预计总工期
        max_end = 0
        for t in tasks:
            sd = self._get_field(t, "start_day", 0)
            dur = self._get_field(t, "duration", 0)
            max_end = max(max_end, sd + dur)
        self._card_duration.set_data(f"{max_end} 天", "预计总工期")

        # 整体进度
        if total > 0:
            avg_prog = sum(self._get_field(t, "progress", 0) for t in tasks) / total
        else:
            avg_prog = 0.0
        self._card_progress.set_data(f"{avg_prog:.1f}%", "整体进度")

        # 逾期/风险任务
        overdue_count = self._count_overdue()
        self._card_overdue.set_data(str(overdue_count), "逾期/风险任务")

    def _count_overdue(self) -> int:
        """计算逾期/风险任务数（progress < 100 且已过预计结束天）。"""
        if not self._start_date:
            return 0
        try:
            start = datetime.strptime(self._start_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            return 0

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = 0
        for t in self._tasks:
            prog = self._get_field(t, "progress", 0)
            if prog >= 100:
                continue
            sd = self._get_field(t, "start_day", 0)
            dur = self._get_field(t, "duration", 0)
            end_day = sd + dur
            if end_day <= 0:
                continue
            end_date = start + timedelta(days=end_day)
            if end_date < today:
                count += 1
        return count

    # ── 分类进度 ──

    def _update_section_progress(self):
        """统计每个分类的任务完成情况。"""
        section_map: dict[str, dict] = {}

        for t in self._tasks:
            section_key = self._get_field(t, "section", "")
            if isinstance(section_key, object) and hasattr(section_key, "value"):
                section_key = section_key.value

            if section_key not in section_map:
                section_map[section_key] = {
                    "key": section_key,
                    "label": _get_section_label(section_key, self._sections),
                    "color": _get_section_color(section_key, self._sections),
                    "done": 0,
                    "total": 0,
                }
            section_map[section_key]["total"] += 1
            if self._get_field(t, "done", False):
                section_map[section_key]["done"] += 1

        data = list(section_map.values())
        self._section_progress.set_data(data)

    # ── 每周工作量柱状图 ──

    def _update_weekly_chart(self):
        """统计每周（7天一周）的任务天数总和。"""
        tasks = self._tasks

        # 收集所有有工期的任务的天数分布
        day_workload: dict[int, float] = {}

        for t in tasks:
            sd = self._get_field(t, "start_day", 0)
            dur = self._get_field(t, "duration", 0)
            if dur <= 0 or sd < 0:
                continue
            for d in range(sd, sd + dur):
                day_workload[d] = day_workload.get(d, 0) + 1.0

        if not day_workload:
            self._weekly_chart.set_data([])
            return

        max_day = max(day_workload.keys())
        total_days = max_day + 1

        # 按周聚合（7天一周）
        if total_days <= 28:
            # 数据量少，按天显示
            week_data = []
            for d in range(total_days):
                val = day_workload.get(d, 0)
                week_data.append({"label": f"D{d + 1}", "value": val})
        else:
            # 按周显示
            num_weeks = (total_days + 6) // 7
            week_data = []
            for w in range(num_weeks):
                start_d = w * 7
                end_d = min(start_d + 7, total_days)
                total_load = sum(day_workload.get(d, 0) for d in range(start_d, end_d))
                week_data.append({"label": f"第{w + 1}周", "value": total_load})

        self._weekly_chart.set_data(week_data)

    # ── 即将到期任务 ──

    def _update_upcoming_tasks(self):
        """列出未来 7 天内到期的任务。"""
        if not self._start_date:
            self._upcoming_tasks.set_data([])
            return

        try:
            start = datetime.strptime(self._start_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            self._upcoming_tasks.set_data([])
            return

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deadline_limit = today + timedelta(days=7)

        upcoming = []
        for t in self._tasks:
            prog = self._get_field(t, "progress", 0)
            if prog >= 100:
                continue

            sd = self._get_field(t, "start_day", 0)
            dur = self._get_field(t, "duration", 0)
            end_day = sd + dur
            if end_day <= 0:
                continue

            end_date = start + timedelta(days=end_day)

            # 判断是否在范围内（过去到未来7天）
            if end_date > deadline_limit:
                continue

            # 状态判断
            if end_date < today:
                status = "overdue"
            elif end_date == today:
                status = "today"
            else:
                status = "normal"

            # 确定分类
            section_key = self._get_field(t, "section", "")
            if isinstance(section_key, object) and hasattr(section_key, "value"):
                section_key = section_key.value

            upcoming.append({
                "task_id": self._get_field(t, "id", 0),
                "num": self._get_field(t, "num", ""),
                "name": self._get_field(t, "name_cn", self._get_field(t, "name_en", "")),
                "section_label": _get_section_label(section_key, self._sections),
                "section_color": _get_section_color(section_key, self._sections),
                "end_date": end_date.strftime("%m-%d"),
                "progress_text": f"{prog:.0f}%",
                "status": status,
                "sort_date": end_date,
            })

        # 按到期日期升序排列
        upcoming.sort(key=lambda x: x["sort_date"])
        self._upcoming_tasks.set_data(upcoming)

    # ── 设备利用率 ──

    def _update_device_utilization(self):
        """从排程结果读取设备利用率。"""
        data = []
        if self._schedule_result:
            report = self._schedule_result.get("report", self._schedule_result)
            utils = report.get("device_utilization", [])
            # 按利用率降序
            data = sorted(utils, key=lambda x: x.get("utilization", 0), reverse=True)

        self._device_util.set_data(data)
