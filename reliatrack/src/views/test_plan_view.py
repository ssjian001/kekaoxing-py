"""测试计划视图 — 任务列表 + 简化甘特图。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QAbstractItemView,
    QScrollArea,
    QFrame,
    QMenu,
    QMessageBox,
)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QAction

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    BLUE, GREEN, YELLOW, RED, PEACH, MAUVE, LAVENDER, TEAL, PINK,
)
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician


class _TaskTable(QTableWidget):
    """测试任务列表表格。"""

    COLUMNS = ["#", "名称", "类别", "天数", "开始天", "进度", "状态", "依赖"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 40)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self._tasks: list[TestTask] = []
        self._equipment_list: list[Equipment] = []
        self._technician_list: list[Technician] = []
        self._on_edit_callback = None  # callable(TestTask) | None
        self._on_delete_callback = None  # callable(TestTask) | None
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {BASE};
                color: {TEXT};
                gridline-color: {SURFACE1};
                border: 1px solid {SURFACE1};
                border-radius: 8px;
                font-size: 13px;
            }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:alternate {{ background-color: {MANTLE}; }}
            QHeaderView::section {{
                background-color: {SURFACE0};
                color: {SUBTEXT0};
                padding: 8px;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }}
        """)
        # 双击编辑
        self.cellDoubleClicked.connect(self._on_double_click)
        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_reference_data(
        self,
        equipment_list: list[Equipment],
        technician_list: list[Technician],
    ) -> None:
        """设置设备和人员列表，供弹窗使用。"""
        self._equipment_list = equipment_list
        self._technician_list = technician_list

    def set_callbacks(
        self,
        on_edit: "callable | None" = None,
        on_delete: "callable | None" = None,
    ) -> None:
        """设置编辑/删除回调。"""
        self._on_edit_callback = on_edit
        self._on_delete_callback = on_delete

    def _on_double_click(self, row: int, _col: int) -> None:
        task = self.get_task_at_row(row)
        if task and self._on_edit_callback:
            self._on_edit_callback(task)

    def _show_context_menu(self, pos) -> None:
        task = self.get_task_at_row(self.rowAt(pos.y()))
        if not task:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {MANTLE}; color: {TEXT};
                border: 1px solid {SURFACE1}; padding: 4px;
            }}
            QMenu::item {{ padding: 6px 24px; }}
            QMenu::item:selected {{ background-color: {SURFACE1}; }}
        """)
        act_edit = QAction("✏️ 编辑", self)
        act_edit.triggered.connect(lambda: self._on_edit_callback(task) if self._on_edit_callback else None)
        act_delete = QAction("🗑️ 删除", self)
        act_delete.triggered.connect(lambda: self._on_delete_callback(task) if self._on_delete_callback else None)
        menu.addAction(act_edit)
        menu.addAction(act_delete)
        menu.exec(self.viewport().mapToGlobal(pos))

    def set_tasks(self, tasks: list[TestTask]) -> None:
        self._tasks = tasks
        self.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            for col, val in enumerate([
                row + 1,
                task.name,
                task.category,
                task.duration,
                task.start_day,
                f"{task.progress:.0f}%",
                task.status,
                str(task.dependencies)[:20],
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 状态颜色
                if col == 6:
                    colors = {"completed": GREEN, "in_progress": YELLOW, "pending": SUBTEXT0}
                    item.setForeground(QColor(colors.get(val, TEXT)))
                self.setItem(row, col, item)

    def get_task_at_row(self, row: int) -> Optional[TestTask]:
        if 0 <= row < len(self._tasks):
            return self._tasks[row]
        return None


class _GanttWidget(QWidget):
    """简化版甘特图 — 基于 QWidget 自绘。"""

    # 类别 → 颜色
    CATEGORY_COLORS = {
        "env": BLUE,
        "mech": GREEN,
        "surf": PEACH,
        "pack": MAUVE,
        "": LAVENDER,
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tasks: list[TestTask] = []
        self._total_days: int = 30
        self._row_height: int = 36
        self._header_height: int = 28
        self._bar_height: int = 24
        self.setMinimumHeight(200)
        self.setStyleSheet(f"background-color: {BASE};")

    def set_tasks(self, tasks: list[TestTask], total_days: int = 30) -> None:
        self._tasks = tasks
        self._total_days = max(total_days, 1)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(800, max(200, len(self._tasks) * self._row_height + self._header_height + 20))

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._tasks:
            p = QPainter(self)
            p.setPen(QColor(SUBTEXT0))
            p.setFont(QFont("sans-serif", 14))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无任务数据")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        # 左边留给标签
        label_w = 200
        chart_w = w - label_w
        day_w = chart_w / self._total_days if self._total_days > 0 else 30

        # ── 表头（天数标尺）──
        p.fillRect(0, 0, w, self._header_height, QColor(SURFACE0))
        p.setPen(QColor(SUBTEXT0))
        p.setFont(QFont("sans-serif", 10))
        step = max(1, self._total_days // 15)
        for d in range(0, self._total_days + 1, step):
            x = label_w + d * day_w
            p.drawText(int(x) - 10, 0, 30, self._header_height,
                       Qt.AlignmentFlag.AlignCenter, f"D{d}")
            p.setPen(QColor(SURFACE1))
            p.drawLine(int(x), self._header_height, int(x), self.height())
            p.setPen(QColor(SUBTEXT0))

        # ── 任务条 ──
        p.setFont(QFont("sans-serif", 11))
        for i, task in enumerate(self._tasks):
            y = self._header_height + i * self._row_height

            # 交替行背景
            if i % 2 == 1:
                p.fillRect(0, y, w, self._row_height, QColor(MANTLE))

            # 任务名称标签
            p.setPen(QColor(TEXT))
            p.drawText(8, y, label_w - 16, self._row_height,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       task.name[:16])

            # 甘特条
            bar_x = label_w + task.start_day * day_w
            bar_w = task.duration * day_w
            bar_y = y + (self._row_height - self._bar_height) / 2

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


class TestPlanView(QWidget):
    """测试计划视图 — 左侧任务表 + 右侧甘特图。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        title = QLabel("📋 测试计划")
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("计划:"))
        self._plan_combo = QComboBox()
        self._plan_combo.setFixedWidth(200)
        self._plan_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {SURFACE0};
                color: {TEXT};
                border: 1px solid {SURFACE1};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {SURFACE0};
                color: {TEXT};
                selection-background-color: {SURFACE1};
            }}
        """)
        toolbar.addWidget(self._plan_combo)

        self._btn_schedule = QPushButton("🚀 自动排程")
        self._btn_schedule.setStyleSheet(f"""
            QPushButton {{
                background-color: {BLUE}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }}
        """)
        toolbar.addWidget(self._btn_schedule)

        toolbar.addSpacing(8)

        self._btn_add_task = QPushButton("➕ 添加任务")
        self._btn_add_task.setStyleSheet(f"""
            QPushButton {{
                background-color: {GREEN}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }}
        """)
        toolbar.addWidget(self._btn_add_task)

        self._btn_edit_task = QPushButton("✏️ 编辑任务")
        self._btn_edit_task.setStyleSheet(f"""
            QPushButton {{
                background-color: {YELLOW}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }}
        """)
        toolbar.addWidget(self._btn_edit_task)

        self._btn_delete_task = QPushButton("🗑️ 删除任务")
        self._btn_delete_task.setStyleSheet(f"""
            QPushButton {{
                background-color: {RED}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }}
        """)
        toolbar.addWidget(self._btn_delete_task)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 分割器：左表格 + 右甘特图
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._task_table = _TaskTable()
        splitter.addWidget(self._task_table)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._gantt = _GanttWidget()
        scroll.setWidget(self._gantt)
        splitter.addWidget(scroll)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {SURFACE1}; width: 2px; }}
            QScrollArea {{ border: 1px solid {SURFACE1}; border-radius: 8px; }}
        """)

        layout.addWidget(splitter)

    def refresh(self, tasks: list[TestTask], total_days: int = 30) -> None:
        self._task_table.set_tasks(tasks)
        self._gantt.set_tasks(tasks, total_days)
        self._gantt.setMinimumHeight(max(200, len(tasks) * 36 + 28))

    def set_plans(self, plan_names: list[str], plan_ids: list[int] | None = None) -> None:
        """设置计划下拉选项。"""
        self._plan_combo.clear()
        self._plan_combo.addItems(plan_names)
        self._plan_ids = plan_ids or list(range(len(plan_names)))

    def get_selected_plan_id(self) -> int | None:
        """获取当前选中计划的 ID。"""
        idx = self._plan_combo.currentIndex()
        if 0 <= idx < len(self._plan_ids):
            return self._plan_ids[idx]
        return None

    @property
    def selected_plan_index(self) -> int:
        return self._plan_combo.currentIndex()

    @property
    def task_table(self) -> _TaskTable:
        return self._task_table

    @property
    def btn_schedule(self) -> QPushButton:
        return self._btn_schedule

    @property
    def btn_add_task(self) -> QPushButton:
        return self._btn_add_task

    @property
    def btn_edit_task(self) -> QPushButton:
        return self._btn_edit_task

    @property
    def btn_delete_task(self) -> QPushButton:
        return self._btn_delete_task

    def setup_task_callbacks(
        self,
        on_add: "callable | None" = None,
        on_edit: "callable | None" = None,
        on_delete: "callable | None" = None,
    ) -> None:
        """设置任务增删改回调。

        外部调用此方法，将实际业务逻辑（打开弹窗、调用 Service 等）注入。
        """
        self._on_add_task = on_add
        self._on_edit_task = on_edit
        self._on_delete_task = on_delete

        # 工具栏按钮
        self._btn_add_task.clicked.connect(lambda: on_add() if on_add else None)
        self._btn_edit_task.clicked.connect(self._handle_toolbar_edit)
        self._btn_delete_task.clicked.connect(self._handle_toolbar_delete)

        # 表格右键 & 双击
        self._task_table.set_callbacks(
            on_edit=self._handle_table_edit,
            on_delete=self._handle_table_delete,
        )

    def _handle_toolbar_edit(self) -> None:
        row = self._task_table.currentRow()
        task = self._task_table.get_task_at_row(row)
        if task and self._on_edit_task:
            self._on_edit_task(task)
        elif not task:
            QMessageBox.information(
                self._task_table, "提示", "请先选中一行任务。"
            )

    def _handle_toolbar_delete(self) -> None:
        row = self._task_table.currentRow()
        task = self._task_table.get_task_at_row(row)
        if task:
            self._confirm_and_delete(task)
        else:
            QMessageBox.information(
                self._task_table, "提示", "请先选中一行任务。"
            )

    def _handle_table_edit(self, task: TestTask) -> None:
        if self._on_edit_task:
            self._on_edit_task(task)

    def _handle_table_delete(self, task: TestTask) -> None:
        self._confirm_and_delete(task)

    def _confirm_and_delete(self, task: TestTask) -> None:
        """弹出确认框后执行删除回调。"""
        reply = QMessageBox.warning(
            self._task_table,
            "确认删除",
            f"确定要删除任务「{task.name}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self._on_delete_task:
            self._on_delete_task(task)
