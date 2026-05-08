"""仪表盘视图 — A/B 两区布局：测试状态 + 测试结果。"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from src.styles.theme import (
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, MAUVE, PEACH,
)
from src.styles.constants import VIEW_MARGINS, CHART_COLORS, FONT_FAMILY


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


# ═══════════════════════════════════════════════════════════════════
#  KPI 卡片
# ═══════════════════════════════════════════════════════════════════

class _KPICard(QFrame):
    """单个 KPI 卡片，点击可跳转到对应 Tab。"""

    def __init__(self, title: str, value: str, color: str = BLUE, tab_index: int = -1, parent: QWidget | None = None):
        super().__init__(parent)
        self._tab_index = tab_index
        self.setObjectName("kpi-card")
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px; border: none;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold; border: none;")
        layout.addWidget(value_label)

    def mousePressEvent(self, event):  # noqa: N802
        """点击卡片发送跳转信号。"""
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "card_clicked"):
                parent.card_clicked.emit(self._tab_index)
                break
            parent = parent.parent()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  pyqtgraph 垂直条形图
# ═══════════════════════════════════════════════════════════════════

class _PyqtGraphBarChart(QWidget):
    """使用 pyqtgraph 绘制的垂直条形图。

    Args:
        title: 图表标题。
        parent: 父控件。
    """

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(title)
        header.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 0;"
        )
        layout.addWidget(header)

        self._pw = pg.PlotWidget()
        self._pw.setBackground("transparent")
        self._pw.hideAxis("bottom")
        self._pw.hideAxis("left")
        self._pw.setMouseEnabled(False, False)
        self._pw.setMinimumHeight(160)
        layout.addWidget(self._pw)

        self._labels: list[str] = []

    # ── 公开 API ──

    def setData(self, data: dict[str, int]) -> None:
        """更新图表数据并刷新绘制。"""
        self._pw.clear()
        if not data:
            return

        labels = list(data.keys())
        values = list(data.values())
        self._labels = labels

        n = len(values)
        colors = [QColor(CHART_COLORS[i % len(CHART_COLORS)]) for i in range(n)]

        x = list(range(n))
        bg = pg.BarGraphItem(
            x=x,
            height=values,
            width=0.6,
            brushes=colors,
        )
        self._pw.addItem(bg)

        # 在条形顶部显示数值
        for i, (xi, val) in enumerate(zip(x, values)):
            text_item = pg.TextItem(
                str(val),
                color=TEXT,
                anchor=(0.5, 1.0),
            )
            text_item.setFont(pg.QtGui.QFont(FONT_FAMILY.split(",")[0].strip(), 10))
            text_item.setPos(xi, val)
            self._pw.addItem(text_item)

        # 在底部显示分类标签
        for i, label in enumerate(labels):
            text_item = pg.TextItem(
                label,
                color=SUBTEXT1,
                anchor=(0.5, 0.0),
            )
            text_item.setFont(pg.QtGui.QFont(FONT_FAMILY.split(",")[0].strip(), 10))
            text_item.setPos(i, 0)
            self._pw.addItem(text_item)

        # 设置范围，留一些边距
        max_val = max(values) if values else 1
        self._pw.setXRange(-0.5, n - 0.5, padding=0)
        self._pw.setYRange(0, max_val * 1.15 if max_val > 0 else 1, padding=0)


# ═══════════════════════════════════════════════════════════════════
#  仪表盘主视图
# ═══════════════════════════════════════════════════════════════════

class DashboardView(QWidget):
    """仪表盘 — A/B 两区布局，KPI 卡片点击可跳转到对应 Tab。"""

    card_clicked = Signal(int)  # tab_index, 点击 KPI 卡片时发出

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        # 项目筛选指示器
        self._filter_label = QLabel("📋 全部项目")
        self._filter_label.setStyleSheet(
            f"color: {SUBTEXT0}; font-size: 13px; "
            f"background-color: {SUBTEXT0}22; border-radius: 6px; "
            f"padding: 4px 12px;"
        )
        layout.addWidget(self._filter_label)

        # ── A 区 — 测试状态 ──
        section_a_label = QLabel("测试状态")
        section_a_label.setStyleSheet(
            f"color: {TEXT}; font-size: 14px; font-weight: bold; padding: 8px 0 2px 0;"
        )
        layout.addWidget(section_a_label)

        # A 区 KPI 卡片（6 个，2行×3列）
        grid_a = QGridLayout()
        grid_a.setSpacing(8)

        self._card_task_total = _KPICard("测试任务数", "0", BLUE, tab_index=3)
        self._card_completed = _KPICard("已完成数", "0", GREEN, tab_index=3)
        self._card_in_progress = _KPICard("进行中数量", "0", YELLOW, tab_index=3)
        self._card_pending = _KPICard("待开始数量", "0", SUBTEXT1, tab_index=3)
        self._card_pass_rate = _KPICard("测试通过率", "—%", GREEN, tab_index=3)
        self._card_failure_rate = _KPICard("失效率", "—%", RED, tab_index=4)

        grid_a.addWidget(self._card_task_total, 0, 0)
        grid_a.addWidget(self._card_completed, 0, 1)
        grid_a.addWidget(self._card_in_progress, 0, 2)
        grid_a.addWidget(self._card_pending, 1, 0)
        grid_a.addWidget(self._card_pass_rate, 1, 1)
        grid_a.addWidget(self._card_failure_rate, 1, 2)

        layout.addLayout(grid_a)

        # A 区图表 — 任务状态分布
        self._chart_task_status = _PyqtGraphBarChart("任务状态分布")
        layout.addWidget(self._chart_task_status)

        # ── B 区 — 测试结果 ──
        section_b_label = QLabel("测试结果")
        section_b_label.setStyleSheet(
            f"color: {TEXT}; font-size: 14px; font-weight: bold; padding: 8px 0 2px 0;"
        )
        layout.addWidget(section_b_label)

        # B 区 KPI 卡片（4 个，1行×4列）
        grid_b = QHBoxLayout()
        grid_b.setSpacing(8)

        self._card_failed_task = _KPICard("Fail 项数", "0", RED, tab_index=3)
        self._card_issues = _KPICard("Issue 数", "0", PEACH, tab_index=4)
        self._card_issue_closed = _KPICard("Issue 闭环数", "0", BLUE, tab_index=4)
        self._card_capa_rate = _KPICard("CAPA 完成率", "—%", MAUVE, tab_index=4)

        grid_b.addWidget(self._card_failed_task)
        grid_b.addWidget(self._card_issues)
        grid_b.addWidget(self._card_issue_closed)
        grid_b.addWidget(self._card_capa_rate)

        layout.addLayout(grid_b)

        # B 区图表 — Issue 严重度分布
        self._chart_issue_severity = _PyqtGraphBarChart("Issue 严重度分布")
        layout.addWidget(self._chart_issue_severity)

        layout.addStretch()

    def refresh(self, data: DashboardData | None = None, **kwargs: object) -> None:
        """刷新 KPI 数据 + 图表数据。

        Args:
            data: DashboardData 封装对象（推荐）。
            **kwargs: 向后兼容，可直接传参数。
        """
        if data is None:
            data = DashboardData(**kwargs)

        # 解构到局部变量
        task_total = data.task_total
        task_completed = data.task_completed
        task_in_progress = data.task_in_progress
        task_pending = data.task_pending
        pass_rate = data.pass_rate
        failure_rate = data.failure_rate
        task_status_data = data.task_status_data or {}
        issue_count = data.issue_count
        issue_closed_count = data.issue_closed_count
        capa_completion_rate = data.capa_completion_rate
        failed_task_count = data.failed_task_count
        issue_severity_data = data.issue_severity_data or {}
        project_name = data.project_name
        plan_name = data.plan_name

        # 项目/计划筛选指示器
        if project_name and plan_name:
            self._filter_label.setText(f"📁 {project_name} / {plan_name}")
            self._filter_label.setStyleSheet(
                f"color: {BLUE}; font-size: 13px; font-weight: bold; "
                f"background-color: {SUBTEXT0}22; border-radius: 6px; "
                f"border: 1px solid {BLUE}; "
                f"padding: 4px 12px;"
            )
        elif project_name:
            self._filter_label.setText(f"📁 {project_name}")
            self._filter_label.setStyleSheet(
                f"color: {BLUE}; font-size: 13px; font-weight: bold; "
                f"background-color: {SUBTEXT0}22; border-radius: 6px; "
                f"border: 1px solid {BLUE}; "
                f"padding: 4px 12px;"
            )
        else:
            self._filter_label.setText("📋 全部项目")
            self._filter_label.setStyleSheet(
                f"color: {SUBTEXT0}; font-size: 13px; "
                f"background-color: {SUBTEXT0}22; border-radius: 6px; "
                f"padding: 4px 12px;"
            )

        # ── A 区 KPI 卡片 ──
        for card, val in [
            (self._card_task_total, task_total),
            (self._card_completed, task_completed),
            (self._card_in_progress, task_in_progress),
            (self._card_pending, task_pending),
            (self._card_pass_rate, f"{pass_rate:.0f}%" if pass_rate is not None else "—%"),
            (self._card_failure_rate, f"{failure_rate:.0f}%" if failure_rate is not None else "—%"),
        ]:
            labels = card.findChildren(QLabel)
            if len(labels) >= 2:
                labels[1].setText(str(val))

        # ── B 区 KPI 卡片 ──
        for card, val in [
            (self._card_failed_task, failed_task_count),
            (self._card_issues, issue_count),
            (self._card_issue_closed, issue_closed_count),
            (self._card_capa_rate, f"{capa_completion_rate:.0f}%" if capa_completion_rate is not None else "—%"),
        ]:
            labels = card.findChildren(QLabel)
            if len(labels) >= 2:
                labels[1].setText(str(val))

        # ── 图表 ──
        # 任务状态中文映射
        task_labels = {
            "pending": "待开始",
            "in_progress": "进行中",
            "completed": "已完成",
            "skipped": "已跳过",
            "failed": "失败",
        }
        self._chart_task_status.setData(
            {task_labels.get(k, k): v for k, v in task_status_data.items() if v > 0}
        )

        # Issue 严重度中文映射
        severity_labels = {
            "critical": "严重",
            "major": "主要",
            "minor": "次要",
            "cosmetic": "外观",
        }
        self._chart_issue_severity.setData(
            {severity_labels.get(k, k): v for k, v in issue_severity_data.items() if v > 0}
        )
