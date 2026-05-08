"""仪表盘视图 — 左右两栏布局：A 区(测试状态) + B 区(测试结果)。"""

from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush

from src.styles.theme import (
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, MAUVE, PEACH,
)
from src.styles.constants import VIEW_MARGINS, CHART_COLORS, FONT_FAMILY

# ═══════════════════════════════════════════════════════════════════
#  通用工具
# ═══════════════════════════════════════════════════════════════════

_FONT_BODY = QFont(FONT_FAMILY.split(",")[0].strip(), 10)
_FONT_SMALL = QFont(FONT_FAMILY.split(",")[0].strip(), 9)
_FONT_KPI_VAL = QFont(FONT_FAMILY.split(",")[0].strip(), 18, QFont.Weight.Bold)


# ═══════════════════════════════════════════════════════════════════
#  KPI 卡片（紧凑版）
# ═══════════════════════════════════════════════════════════════════

class _KPICard(QFrame):
    """单个 KPI 卡片，点击可跳转到对应 Tab。"""

    def __init__(self, title: str, value: str, color: str = BLUE,
                 tab_index: int = -1, parent: QWidget | None = None):
        super().__init__(parent)
        self._tab_index = tab_index
        self.setObjectName("kpi-card")
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px; border: none;")
        layout.addWidget(title_lbl)

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold; border: none;"
        )
        layout.addWidget(self._value_lbl)

    def set_value(self, text: str) -> None:
        self._value_lbl.setText(text)

    def mousePressEvent(self, event):  # noqa: N802
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "card_clicked"):
                parent.card_clicked.emit(self._tab_index)
                break
            parent = parent.parent()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  环形图（Donut Chart）— QPainter 自绘
# ═══════════════════════════════════════════════════════════════════

class _DonutChart(QWidget):
    """环形图 — 居中绘制，图例在下方水平排列。

    数据通过 setData() 传入 dict[str, int]。
    """

    _RING_W = 16  # 环宽度

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setMinimumSize(180, 180)

    def setData(self, data: dict[str, int]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        if not self._data:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        total = sum(self._data.values())
        if total == 0:
            p.end()
            return

        # ── 环形图居中（上半部分 70%）──
        chart_h = int(h * 0.65)
        ring_size = min(w * 0.8, chart_h - 16)
        cx = w / 2
        cy = chart_h / 2
        outer_r = ring_size / 2
        inner_r = outer_r - self._RING_W
        rect_outer = QRectF(cx - outer_r, cy - outer_r, ring_size, ring_size)

        start_angle = 0
        items = list(self._data.items())

        # 背景环（浅灰）
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(SUBTEXT0 + "33"))
        p.drawEllipse(rect_outer)

        # 各扇形
        for i, (_, value) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            span = int(value / total * 360 * 16)
            p.setPen(QPen(QColor("#ffffff"), 1.5))
            p.setBrush(QBrush(color))
            p.drawPie(rect_outer, -start_angle, -span)
            start_angle += span

        # 挖空中心（覆盖背景色）
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(p.parentWidget().palette().window().color()
                          if self.parentWidget() else "#ffffff"))
        inner_rect = QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)
        p.drawEllipse(inner_rect)

        # 中心数字
        p.setPen(QColor(TEXT))
        p.setFont(QFont(FONT_FAMILY.split(",")[0].strip(), 14, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 40, cy - 14, 80, 28),
                   Qt.AlignmentFlag.AlignCenter, str(total))

        # ── 图例（下方水平排列）──
        legend_y = chart_h + 4
        p.setFont(_FONT_SMALL)
        col_w = w / max(len(items), 1)
        for i, (label, value) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            lx = col_w * i
            # 色块
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(lx + 4, legend_y, 8, 8), 2, 2)
            # 文字
            pct = value / total * 100
            p.setPen(QColor(SUBTEXT1))
            p.drawText(
                QRectF(lx + 16, legend_y - 3, col_w - 20, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{label} {value}({pct:.0f}%)",
            )

        p.end()


# ═══════════════════════════════════════════════════════════════════
#  进度环（Progress Ring）— QPainter 自绘
# ═══════════════════════════════════════════════════════════════════

class _ProgressRing(QWidget):
    """圆环进度指示器 — 中心显示百分比。

    Args:
        label: 环下方标签文字。
        color: 进度弧颜色。
    """

    _RING_W = 10

    def __init__(self, label: str, color: str = BLUE, parent: QWidget | None = None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._pct: float = 0.0
        self.setFixedSize(90, 90)

    def setPercent(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 6  # 留空间给底部标签
        outer_r = min(cx, cy) - 2
        inner_r = outer_r - self._RING_W
        rect = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)

        # 背景环
        p.setPen(QPen(QColor(SUBTEXT0 + "44"), self._RING_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)

        # 进度弧
        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), self._RING_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            span = int(self._pct / 100 * 360 * 16)
            p.drawArc(rect, 90 * 16, -span)

        # 中心百分比
        p.setPen(QColor(TEXT))
        p.setFont(QFont(FONT_FAMILY.split(",")[0].strip(), 12, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 30, cy - 10, 60, 20),
                   Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")

        # 底部标签
        p.setPen(QColor(SUBTEXT1))
        p.setFont(_FONT_SMALL)
        p.drawText(QRectF(0, h - 16, w, 14),
                   Qt.AlignmentFlag.AlignCenter, self._label)

        p.end()


# ═══════════════════════════════════════════════════════════════════
#  pyqtgraph 垂直条形图
# ═══════════════════════════════════════════════════════════════════

class _BarChart(QWidget):
    """pyqtgraph 垂直条形图。"""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QLabel(title)
        header.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        layout.addWidget(header)

        self._pw = pg.PlotWidget()
        self._pw.setBackground("transparent")
        self._pw.hideAxis("bottom")
        self._pw.hideAxis("left")
        self._pw.setMouseEnabled(False, False)
        self._pw.setMinimumHeight(120)
        layout.addWidget(self._pw)

    def setData(self, data: dict[str, int]) -> None:
        self._pw.clear()
        if not data:
            return

        labels = list(data.keys())
        values = list(data.values())
        n = len(values)
        colors = [QColor(CHART_COLORS[i % len(CHART_COLORS)]) for i in range(n)]

        x = list(range(n))
        bg = pg.BarGraphItem(x=x, height=values, width=0.5, brushes=colors)
        self._pw.addItem(bg)

        for i, (xi, val) in enumerate(zip(x, values)):
            txt = pg.TextItem(str(val), color=TEXT, anchor=(0.5, 1.0))
            txt.setFont(_FONT_SMALL)
            txt.setPos(xi, val)
            self._pw.addItem(txt)

        for i, label in enumerate(labels):
            txt = pg.TextItem(label, color=SUBTEXT1, anchor=(0.5, 0.0))
            txt.setFont(_FONT_SMALL)
            txt.setPos(i, 0)
            self._pw.addItem(txt)

        max_val = max(values) if values else 1
        self._pw.setXRange(-0.5, n - 0.5, padding=0)
        self._pw.setYRange(0, max_val * 1.2 if max_val > 0 else 1, padding=0)


# ═══════════════════════════════════════════════════════════════════
#  区块标题
# ═══════════════════════════════════════════════════════════════════

def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {TEXT}; font-size: 13px; font-weight: bold; "
        f"border-bottom: 1px solid {SUBTEXT0}44; padding-bottom: 3px;"
    )
    return lbl


# ═══════════════════════════════════════════════════════════════════
#  仪表盘主视图 — 左右两栏
# ═══════════════════════════════════════════════════════════════════

class DashboardData:
    """Dashboard 刷新数据封装 — A/B 两区字段。"""

    __slots__ = (
        # A 区 — 测试状态
        "task_total", "task_completed", "task_in_progress", "task_pending",
        "pass_rate", "failure_rate",
        "task_status_data",
        # B 区 — 测试结果
        "issue_count", "issue_closed_count",
        "capa_completion_rate", "failed_task_count",
        "issue_severity_data",
        # 筛选
        "project_name", "plan_name",
    )

    def __init__(self, **kwargs: object) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot, 0 if "count" in slot or "total" in slot
                                           else {} if "data" in slot
                                           else None))


class DashboardView(QWidget):
    """仪表盘 — 左右两栏：A 区(测试状态) + B 区(测试结果)。"""

    card_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*VIEW_MARGINS)
        root.setSpacing(6)

        # 项目筛选指示器
        self._filter_label = QLabel("全部项目")
        self._filter_label.setStyleSheet(
            f"color: {SUBTEXT0}; font-size: 12px; "
            f"background-color: {SUBTEXT0}22; border-radius: 4px; "
            f"padding: 3px 10px;"
        )
        root.addWidget(self._filter_label)

        # ── 左右两栏 ──
        columns = QHBoxLayout()
        columns.setSpacing(12)

        # ═══ 左栏 — A 区：测试状态 ═══
        col_a = QVBoxLayout()
        col_a.setSpacing(6)
        col_a.addWidget(_section_title("测试状态"))

        # KPI 卡片 2×3
        grid_a = QGridLayout()
        grid_a.setSpacing(6)
        self._card_task_total = _KPICard("任务数", "0", BLUE, 3)
        self._card_completed = _KPICard("已完成", "0", GREEN, 3)
        self._card_in_progress = _KPICard("进行中", "0", YELLOW, 3)
        self._card_pending = _KPICard("待开始", "0", SUBTEXT1, 3)
        self._card_pass_rate = _KPICard("通过率", "—%", GREEN, 3)
        self._card_failure_rate = _KPICard("失效率", "—%", RED, 4)

        grid_a.addWidget(self._card_task_total, 0, 0)
        grid_a.addWidget(self._card_completed, 0, 1)
        grid_a.addWidget(self._card_in_progress, 0, 2)
        grid_a.addWidget(self._card_pending, 1, 0)
        grid_a.addWidget(self._card_pass_rate, 1, 1)
        grid_a.addWidget(self._card_failure_rate, 1, 2)
        col_a.addLayout(grid_a)

        # 环形图
        self._donut_status = _DonutChart()
        col_a.addWidget(self._donut_status, 1)  # stretch=1 填满剩余空间

        columns.addLayout(col_a, 1)  # stretch=1

        # ═══ 右栏 — B 区：测试结果 ═══
        col_b = QVBoxLayout()
        col_b.setSpacing(6)
        col_b.addWidget(_section_title("测试结果"))

        # KPI 卡片 2×2
        grid_b = QGridLayout()
        grid_b.setSpacing(6)
        self._card_failed_task = _KPICard("Fail 项数", "0", RED, 3)
        self._card_issues = _KPICard("Issue 数", "0", PEACH, 4)
        self._card_issue_closed = _KPICard("Issue 闭环", "0", BLUE, 4)
        self._card_capa_rate = _KPICard("CAPA 完成率", "—%", MAUVE, 4)

        grid_b.addWidget(self._card_failed_task, 0, 0)
        grid_b.addWidget(self._card_issues, 0, 1)
        grid_b.addWidget(self._card_issue_closed, 1, 0)
        grid_b.addWidget(self._card_capa_rate, 1, 1)
        col_b.addLayout(grid_b)

        # 条形图 — Issue 严重度分布
        self._chart_severity = _BarChart("Issue 严重度分布")
        col_b.addWidget(self._chart_severity)

        # 进度环行 — Issue 闭环率 + CAPA 完成率
        rings_row = QHBoxLayout()
        rings_row.setSpacing(12)
        self._ring_issue_close = _ProgressRing("Issue 闭环率", BLUE)
        self._ring_capa = _ProgressRing("CAPA 完成率", MAUVE)
        rings_row.addWidget(self._ring_issue_close)
        rings_row.addWidget(self._ring_capa)
        rings_row.addStretch()
        col_b.addLayout(rings_row)

        col_b.addStretch()

        columns.addLayout(col_b, 1)  # stretch=1

        root.addLayout(columns)

    # ── 刷新 ──

    def refresh(self, data: DashboardData | None = None, **kwargs: object) -> None:
        """刷新 KPI 数据 + 图表数据。"""
        if data is None:
            data = DashboardData(**kwargs)

        task_total = data.task_total
        task_status_data = data.task_status_data or {}
        issue_severity_data = data.issue_severity_data or {}
        issue_count = data.issue_count
        issue_closed_count = data.issue_closed_count

        # ── 筛选指示器 ──
        if data.project_name and data.plan_name:
            self._filter_label.setText(f"{data.project_name} / {data.plan_name}")
            self._filter_label.setStyleSheet(
                f"color: {BLUE}; font-size: 12px; font-weight: bold; "
                f"background-color: {SUBTEXT0}22; border-radius: 4px; "
                f"border: 1px solid {BLUE}; padding: 3px 10px;"
            )
        elif data.project_name:
            self._filter_label.setText(f"{data.project_name}")
            self._filter_label.setStyleSheet(
                f"color: {BLUE}; font-size: 12px; font-weight: bold; "
                f"background-color: {SUBTEXT0}22; border-radius: 4px; "
                f"border: 1px solid {BLUE}; padding: 3px 10px;"
            )
        else:
            self._filter_label.setText("全部项目")
            self._filter_label.setStyleSheet(
                f"color: {SUBTEXT0}; font-size: 12px; "
                f"background-color: {SUBTEXT0}22; border-radius: 4px; "
                f"padding: 3px 10px;"
            )

        # ── A 区 KPI ──
        self._card_task_total.set_value(str(task_total))
        self._card_completed.set_value(str(data.task_completed))
        self._card_in_progress.set_value(str(data.task_in_progress))
        self._card_pending.set_value(str(data.task_pending))
        self._card_pass_rate.set_value(
            f"{data.pass_rate:.0f}%" if data.pass_rate is not None else "—%"
        )
        self._card_failure_rate.set_value(
            f"{data.failure_rate:.0f}%" if data.failure_rate is not None else "—%"
        )

        # ── B 区 KPI ──
        self._card_failed_task.set_value(str(data.failed_task_count))
        self._card_issues.set_value(str(issue_count))
        self._card_issue_closed.set_value(str(issue_closed_count))
        self._card_capa_rate.set_value(
            f"{data.capa_completion_rate:.0f}%" if data.capa_completion_rate is not None else "—%"
        )

        # ── A 区环形图 ──
        task_labels = {
            "pending": "待开始", "in_progress": "进行中",
            "completed": "已完成", "skipped": "已跳过", "failed": "失败",
        }
        self._donut_status.setData(
            {task_labels.get(k, k): v for k, v in task_status_data.items() if v > 0}
        )

        # ── B 区条形图 ──
        severity_labels = {
            "critical": "严重", "major": "主要",
            "minor": "次要", "cosmetic": "外观",
        }
        self._chart_severity.setData(
            {severity_labels.get(k, k): v for k, v in issue_severity_data.items() if v > 0}
        )

        # ── B 区进度环 ──
        issue_close_pct = (issue_closed_count / issue_count * 100) if issue_count else 0
        self._ring_issue_close.setPercent(issue_close_pct)
        self._ring_capa.setPercent(
            data.capa_completion_rate if data.capa_completion_rate is not None else 0
        )
