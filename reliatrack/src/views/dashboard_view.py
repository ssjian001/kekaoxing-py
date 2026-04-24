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
from PySide6.QtCore import Qt

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, MAUVE, PEACH,
)


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
        title_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 13px; border: none;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none;")
        layout.addWidget(value_label)

        layout.addStretch()


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
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # KPI 卡片网格
        grid = QGridLayout()
        grid.setSpacing(16)

        self._card_tasks = _KPICard("测试任务", "0", BLUE)
        self._card_completed = _KPICard("已完成", "0", GREEN)
        self._card_in_progress = _KPICard("进行中", "0", YELLOW)
        self._card_pending = _KPICard("待开始", "0", SUBTEXT1)
        self._card_issues = _KPICard("Issue 数", "0", PEACH)
        self._card_equipment = _KPICard("设备数", "0", MAUVE)

        grid.addWidget(self._card_tasks, 0, 0)
        grid.addWidget(self._card_completed, 0, 1)
        grid.addWidget(self._card_in_progress, 0, 2)
        grid.addWidget(self._card_pending, 1, 0)
        grid.addWidget(self._card_issues, 1, 1)
        grid.addWidget(self._card_equipment, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()

    def refresh(self, task_total: int = 0, task_completed: int = 0,
                task_in_progress: int = 0, task_pending: int = 0,
                issue_count: int = 0, equipment_count: int = 0) -> None:
        """刷新 KPI 数据。"""
        for card, val in [
            (self._card_tasks, task_total),
            (self._card_completed, task_completed),
            (self._card_in_progress, task_in_progress),
            (self._card_pending, task_pending),
            (self._card_issues, issue_count),
            (self._card_equipment, equipment_count),
        ]:
            labels = card.findChildren(QLabel)
            if len(labels) >= 2:
                labels[1].setText(str(val))
