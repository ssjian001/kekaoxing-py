"""仪表盘视图 — 项目 KPI 总览。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QFontMetrics,
    QLinearGradient,
)

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, MAUVE, PEACH,
    TEAL, LAVENDER, PINK, SKY,
)


# ═══════════════════════════════════════════════════════════════════
#  Catppuccin 配色盘（用于条形图）
# ═══════════════════════════════════════════════════════════════════

_BAR_COLORS = [
    "#89b4fa",  # Blue
    "#a6e3a1",  # Green
    "#f9e2af",  # Yellow
    "#f38ba8",  # Red
    "#cba6f7",  # Mauve
    "#fab387",  # Peach
    "#94e2d5",  # Teal
    "#b4befe",  # Lavender
    "#89dceb",  # Sky
    "#f5c2e7",  # Pink
]


# ═══════════════════════════════════════════════════════════════════
#  KPI 卡片
# ═══════════════════════════════════════════════════════════════════

class _KPICard(QFrame):
    """单个 KPI 卡片。"""

    def __init__(self, title: str, value: str, color: str = BLUE, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("kpi-card")
        self.setFixedHeight(100)
        self.setStyleSheet(f"""
            #kpi-card {{
                background-color: {SURFACE0};
                border-radius: 12px;
                border: 1px solid {SURFACE1};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 14px; border: none;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold; border: none;")
        layout.addWidget(value_label)

        layout.addStretch()


# ═══════════════════════════════════════════════════════════════════
#  QPainter 水平条形图
# ═══════════════════════════════════════════════════════════════════

class _BarChartWidget(QWidget):
    """使用 QPainter 绘制的水平条形图。

    Args:
        title: 图表标题。
        data: 标签→数值的映射。传入空字典时显示占位提示。
        parent: 父控件。
    """

    def __init__(
        self,
        title: str,
        data: dict[str, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._data: dict[str, int] = data or {}
        # 布局常量
        self._h_margin = 24
        self._v_margin = 16
        self._title_height = 32
        self._bar_height = 24
        self._bar_gap = 12
        self._label_width = 90
        self._value_width = 50
        self.setMinimumHeight(160)

    # ── 公开 API ──

    def set_data(self, data: dict[str, int]) -> None:
        """更新图表数据并刷新绘制。"""
        self._data = data
        self._adjust_size()
        self.update()

    # ── 内部 ──

    def _adjust_size(self) -> None:
        """根据数据条目数动态调整最小高度。"""
        n = len(self._data)
        if n == 0:
            self.setMinimumHeight(160)
        else:
            h = (
                self._v_margin
                + self._title_height
                + self._v_margin
                + n * self._bar_height
                + (n - 1) * self._bar_gap
                + self._v_margin
            )
            self.setMinimumHeight(h)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景
        painter.fillRect(0, 0, w, h, QColor(SURFACE0))

        # 标题
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(TEXT))
        painter.drawText(
            self._h_margin,
            self._v_margin,
            w - 2 * self._h_margin,
            self._title_height,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._title,
        )

        if not self._data:
            self._paint_empty(painter, w, h)
            return

        # 最大值（至少为 1 避免除零）
        max_val = max(max(self._data.values()), 1)
        bar_area_x = self._h_margin + self._label_width + 8
        bar_area_w = max(w - bar_area_x - self._value_width - self._h_margin, 20)

        # 条形字体
        bar_font = QFont()
        bar_font.setPointSize(11)
        painter.setFont(bar_font)

        colors = _BAR_COLORS
        y = self._v_margin + self._title_height + self._v_margin

        for i, (label, value) in enumerate(self._data.items()):
            # 标签
            painter.setPen(QColor(SUBTEXT1))
            painter.drawText(
                self._h_margin,
                y,
                self._label_width,
                self._bar_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

            # 条形
            color = QColor(colors[i % len(colors)])
            bar_w = int(bar_area_w * value / max_val) if max_val else 0
            bar_rect = QRectF(
                bar_area_x,
                y + (self._bar_height - 16) / 2,
                bar_w,
                16,
            )
            # 渐变条
            grad = QLinearGradient(bar_rect.topLeft(), bar_rect.topRight())
            grad.setColorAt(0, color)
            grad.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 180))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 4, 4)

            # 数值
            painter.setPen(QColor(TEXT))
            painter.drawText(
                bar_area_x + bar_w + 8,
                y,
                self._value_width,
                self._bar_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                str(value),
            )

            y += self._bar_height + self._bar_gap

        painter.end()

    def _paint_empty(self, painter: QPainter, w: int, h: int) -> None:
        """无数据时绘制占位提示。"""
        painter.setPen(QColor(SUBTEXT0))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(
            0, 0, w, h,
            Qt.AlignmentFlag.AlignCenter,
            "暂无数据",
        )


# ═══════════════════════════════════════════════════════════════════
#  仪表盘主视图
# ═══════════════════════════════════════════════════════════════════

class DashboardView(QWidget):
    """仪表盘 — KPI 总览页。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        # 标题
        title = QLabel("📊 项目总览")
        title.setStyleSheet(f"color: {TEXT}; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # 项目筛选指示器
        self._filter_label = QLabel("📋 全部项目")
        self._filter_label.setStyleSheet(
            f"color: {SUBTEXT0}; font-size: 13px; "
            f"background-color: {SURFACE1}; border-radius: 6px; "
            f"padding: 4px 12px;"
        )
        layout.addWidget(self._filter_label)

        # KPI 卡片网格
        grid = QGridLayout()
        grid.setSpacing(16)

        self._card_tasks = _KPICard("测试任务", "0", BLUE)
        self._card_completed = _KPICard("已完成", "0", GREEN)
        self._card_in_progress = _KPICard("进行中", "0", YELLOW)
        self._card_pending = _KPICard("待开始", "0", SUBTEXT1)
        self._card_issues = _KPICard("Issue 数", "0", PEACH)
        self._card_equipment = _KPICard("设备数", "0", MAUVE)
        self._card_samples = _KPICard("样品数", "0", TEAL)

        grid.addWidget(self._card_tasks, 0, 0)
        grid.addWidget(self._card_completed, 0, 1)
        grid.addWidget(self._card_in_progress, 0, 2)
        grid.addWidget(self._card_pending, 1, 0)
        grid.addWidget(self._card_issues, 1, 1)
        grid.addWidget(self._card_equipment, 1, 2)
        grid.addWidget(self._card_samples, 2, 0)

        layout.addLayout(grid)

        # ── 图表区域 ──
        chart_grid = QGridLayout()
        chart_grid.setSpacing(16)

        self._chart_task_status = _BarChartWidget("任务状态分布")
        self._chart_sample_status = _BarChartWidget("样品状态分布")
        self._chart_issue_severity = _BarChartWidget("Issue 严重度分布")

        chart_grid.addWidget(self._chart_task_status, 0, 0)
        chart_grid.addWidget(self._chart_sample_status, 0, 1)
        chart_grid.addWidget(self._chart_issue_severity, 0, 2)

        layout.addLayout(chart_grid)
        layout.addStretch()

    def refresh(
        self,
        task_total: int = 0,
        task_completed: int = 0,
        task_in_progress: int = 0,
        task_pending: int = 0,
        issue_count: int = 0,
        equipment_count: int = 0,
        sample_count: int = 0,
        project_name: str | None = None,
        task_status_data: dict[str, int] | None = None,
        sample_status_data: dict[str, int] | None = None,
        issue_severity_data: dict[str, int] | None = None,
    ) -> None:
        """刷新 KPI 数据 + 图表数据。

        Args:
            task_total / task_completed / task_in_progress / task_pending / issue_count / equipment_count:
                KPI 卡片数值。
            sample_count: 样品总数。
            project_name: 当前筛选的项目名称（None 表示全部项目）。
            task_status_data:    {"pending": n, "in_progress": n, "completed": n, "skipped": n}
            sample_status_data:  {"in_stock": n, "checked_out": n, "in_test": n, ...}
            issue_severity_data: {"critical": n, "major": n, "minor": n, "cosmetic": n}
        """
        # 项目筛选指示器
        if project_name:
            self._filter_label.setText(f"📁 {project_name}")
            self._filter_label.setStyleSheet(
                f"color: {BLUE}; font-size: 13px; font-weight: bold; "
                f"background-color: {SURFACE1}; border-radius: 6px; "
                f"border: 1px solid {BLUE}; "
                f"padding: 4px 12px;"
            )
        else:
            self._filter_label.setText("📋 全部项目")
            self._filter_label.setStyleSheet(
                f"color: {SUBTEXT0}; font-size: 13px; "
                f"background-color: {SURFACE1}; border-radius: 6px; "
                f"padding: 4px 12px;"
            )

        # KPI 卡片
        for card, val in [
            (self._card_tasks, task_total),
            (self._card_completed, task_completed),
            (self._card_in_progress, task_in_progress),
            (self._card_pending, task_pending),
            (self._card_issues, issue_count),
            (self._card_equipment, equipment_count),
            (self._card_samples, sample_count),
        ]:
            labels = card.findChildren(QLabel)
            if len(labels) >= 2:
                labels[1].setText(str(val))

        # 图表
        self._refresh_charts(
            task_status_data or {},
            sample_status_data or {},
            issue_severity_data or {},
        )

    # ── 图表刷新 ──

    def _refresh_charts(
        self,
        task_status: dict[str, int],
        sample_status: dict[str, int],
        issue_severity: dict[str, int],
    ) -> None:
        """将原始英文 key 映射为中文标签，更新条形图。"""
        # 任务状态中文映射
        task_labels = {
            "pending": "待开始",
            "in_progress": "进行中",
            "completed": "已完成",
            "skipped": "已跳过",
        }
        self._chart_task_status.set_data(
            {task_labels.get(k, k): v for k, v in task_status.items() if v > 0}
        )

        # 样品状态中文映射
        sample_labels = {
            "in_stock": "在库",
            "checked_out": "已借出",
            "in_test": "测试中",
            "suspended": "暂停",
            "scrapped": "已报废",
            "returned": "已归还",
        }
        self._chart_sample_status.set_data(
            {sample_labels.get(k, k): v for k, v in sample_status.items() if v > 0}
        )

        # Issue 严重度中文映射
        severity_labels = {
            "critical": "严重",
            "major": "主要",
            "minor": "次要",
            "cosmetic": "外观",
        }
        self._chart_issue_severity.set_data(
            {severity_labels.get(k, k): v for k, v in issue_severity.items() if v > 0}
        )
