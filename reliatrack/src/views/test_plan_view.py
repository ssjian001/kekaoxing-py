"""测试计划视图 — 任务列表 + 简化甘特图。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QComboBox,
    QAbstractItemView,
    QFrame,
    QMenu,
    QMessageBox,
)
from PySide6.QtCore import Qt, QRect, QSize, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QAction, QMouseEvent, QWheelEvent

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    BLUE, GREEN, YELLOW, RED, PEACH, MAUVE, LAVENDER,
)
from src.styles.constants import TABLE_QSS, VIEW_MARGINS, TASK_STATUS_COLORS, PRIORITY_COLORS
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician


class _TaskTable(QTableWidget):
    """测试任务列表表格。"""

    COLUMNS = ["#", "名称", "类别", "天数", "开始", "进度", "优先级", "状态", "技术员", "通过率", "实际开始", "实际完成"]

    _STATUS_LABELS: dict[str, str] = {
        "pending": "待开始",
        "in_progress": "进行中",
        "completed": "已完成",
        "skipped": "已跳过",
    }
    _STATUS_COLORS: dict[str, str] = TASK_STATUS_COLORS
    _PRIORITY_COLORS: dict[int, str] = PRIORITY_COLORS

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)   # #
        self.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)   # 优先级
        self.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)   # 技术员
        self.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)   # 通过率
        self.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.Fixed)  # 实际开始
        self.horizontalHeader().setSectionResizeMode(11, QHeaderView.ResizeMode.Fixed)  # 实际完成
        self.setColumnWidth(0, 32)
        self.setColumnWidth(6, 50)
        self.setColumnWidth(8, 70)
        self.setColumnWidth(9, 60)
        self.setColumnWidth(10, 90)
        self.setColumnWidth(11, 90)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self._tasks: list[TestTask] = []
        self._equipment_list: list[Equipment] = []
        self._technician_list: list[Technician] = []
        self._on_edit_callback: Callable[[TestTask], None] | None = None
        self._on_delete_callback: Callable[[TestTask], None] | None = None
        self._on_status_advance_callback: Callable[[TestTask, str], None] | None = None
        self.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=12,
        ))
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
        on_edit: Callable[[TestTask], None] | None = None,
        on_delete: Callable[[TestTask], None] | None = None,
        on_status_advance: Callable[[TestTask, str], None] | None = None,
    ) -> None:
        """设置编辑/删除/状态推进回调。"""
        self._on_edit_callback = on_edit
        self._on_delete_callback = on_delete
        self._on_status_advance_callback = on_status_advance

    def _on_double_click(self, row: int, _col: int) -> None:
        task = self.get_task_at_row(row)
        if task and self._on_edit_callback:
            self._on_edit_callback(task)

    def _show_context_menu(self, pos) -> None:
        task = self.get_task_at_row(self.rowAt(pos.y()))
        if not task:
            return
        menu = QMenu(self)
        act_edit = QAction("编辑", self)
        act_edit.triggered.connect(lambda: self._on_edit_callback(task) if self._on_edit_callback else None)
        act_delete = QAction("删除", self)
        act_delete.triggered.connect(lambda: self._on_delete_callback(task) if self._on_delete_callback else None)

        # 状态快捷推进
        act_start: QAction | None = None
        act_complete: QAction | None = None
        if task.status == "pending":
            act_start = QAction("开始执行", self)
            act_start.triggered.connect(
                lambda: self._on_status_advance_callback(task, "in_progress")
                if self._on_status_advance_callback else None
            )
        elif task.status == "in_progress":
            act_complete = QAction("标记完成", self)
            act_complete.triggered.connect(
                lambda: self._on_status_advance_callback(task, "completed")
                if self._on_status_advance_callback else None
            )

        menu.addAction(act_edit)
        menu.addAction(act_delete)
        if act_start or act_complete:
            menu.addSeparator()
        if act_start:
            menu.addAction(act_start)
        if act_complete:
            menu.addAction(act_complete)
        menu.exec(self.viewport().mapToGlobal(pos))

    def set_tasks(
        self,
        tasks: list[TestTask],
        technician_map: dict[int, str] | None = None,
        result_map: dict[int, tuple[int, int]] | None = None,
    ) -> None:
        self._tasks = tasks
        tech_map = technician_map or {}
        res_map = result_map or {}
        self.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            # 列: #, 名称, 类别, 天数, 开始, 进度, 优先级, 状态, 技术员, 通过率, 实际开始, 实际完成
            status_text = self._STATUS_LABELS.get(task.status, task.status)
            priority_text = {"1": "P1", "2": "P2", "3": "P3", "4": "P4", "5": "P5"}.get(str(task.priority), str(task.priority))
            tech_name = tech_map.get(task.technician_id, "") if task.technician_id else ""
            pass_count, total = res_map.get(task.id, (0, 0)) if task.id else (0, 0)
            rate_text = f"{pass_count}/{total}" if total > 0 else "—"
            values = [
                row + 1,
                task.name,
                task.category,
                task.duration,
                task.start_day,
                f"{task.progress:.0f}%",
                priority_text,
                status_text,
                tech_name,
                rate_text,
                task.actual_start_date or "—",
                task.actual_end_date or "—",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 名称列 tooltip (col 1)
                if col == 1 and task.name:
                    item.setToolTip(task.name)
                # 状态颜色 (col 7)
                if col == 7:
                    item.setForeground(QColor(self._STATUS_COLORS.get(task.status, TEXT)))
                # 优先级颜色 (col 6)
                elif col == 6:
                    item.setForeground(QColor(self._PRIORITY_COLORS.get(task.priority, TEXT)))
                # 通过率着色 (col 9)
                elif col == 9 and total > 0:
                    if pass_count == total:
                        item.setForeground(QColor(GREEN))
                    elif pass_count == 0:
                        item.setForeground(QColor(RED))
                self.setItem(row, col, item)

    def get_task_at_row(self, row: int) -> Optional[TestTask]:
        if 0 <= row < len(self._tasks):
            return self._tasks[row]
        return None


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

    _LABEL_W = 200  # 左侧标签列宽度
    _MIN_DAY_W = 6  # 最小每天像素宽度
    _MAX_DAY_W = 80  # 最大每天像素宽度

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tasks: list[TestTask] = []
        self._total_days: int = 30
        self._row_height: int = 28
        self._header_height: int = 24
        self._bar_height: int = 18
        self._day_w: float = 30.0  # 每天像素宽度（可缩放）
        self.setMinimumHeight(150)
        self.setMouseTracking(True)  # 悬浮提示需要
        self.setStyleSheet(f"background-color: {BASE};")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 拖拽状态
        self._drag_task_idx: int | None = None
        self._drag_offset_x: int = 0
        self._drag_start_day: int = 0
        self._hover_task_idx: int | None = None

    def set_tasks(self, tasks: list[TestTask], total_days: int = 30) -> None:
        self._tasks = tasks
        self._total_days = max(total_days, 1)
        self.update()

    def _chart_w(self) -> int:
        return max(self.width() - self._LABEL_W, 100)

    def sizeHint(self) -> QSize:
        return QSize(800, max(200, len(self._tasks) * self._row_height + self._header_height + 20))

    # ── 布局计算辅助 ──

    def _bar_rect(self, idx: int) -> QRect:
        """返回第 idx 个任务条的 QRect。"""
        task = self._tasks[idx]
        x = self._LABEL_W + task.start_day * self._day_w
        y = self._header_height + idx * self._row_height + (self._row_height - self._bar_height) / 2
        return QRect(int(x), int(y), int(task.duration * self._day_w), self._bar_height)

    def _hit_test(self, pos: QPoint) -> int | None:
        """返回鼠标位置下的任务索引，没有则 None。"""
        for i in range(len(self._tasks)):
            if self._bar_rect(i).contains(pos):
                return i
        return None

    # ── 事件处理 ──

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        pos = event.position().toPoint()

        if self._drag_task_idx is not None:
            # 拖拽中 — 更新 cursor 并实时预览
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            # 计算新 start_day
            bar = self._bar_rect(self._drag_task_idx)
            dx = pos.x() - self._drag_offset_x - bar.x()
            new_day = self._drag_start_day + round(dx / self._day_w)
            new_day = max(0, new_day)
            # 临时移动任务以预览
            task = self._tasks[self._drag_task_idx]
            task.start_day = new_day
            self.update()
            return

        # 悬浮检测
        idx = self._hit_test(pos)
        if idx != self._hover_task_idx:
            self._hover_task_idx = idx
            if idx is not None:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                task = self._tasks[idx]
                tooltip = (
                    f"{task.name}\n"
                    f"类别: {task.category or '-'}\n"
                    f"工期: {task.duration} 天\n"
                    f"开始: D{task.start_day} → D{task.start_day + task.duration}\n"
                    f"进度: {task.progress:.0f}%\n"
                    f"状态: {task.status}"
                )
                self.setToolTip(tooltip)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip("")

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(event.position().toPoint())
            if idx is not None:
                self._drag_task_idx = idx
                self._drag_offset_x = event.position().toPoint().x() - self._bar_rect(idx).x()
                self._drag_start_day = self._tasks[idx].start_day
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._drag_task_idx is not None:
            task = self._tasks[self._drag_task_idx]
            new_day = task.start_day
            if task.id is not None and new_day != self._drag_start_day:
                self.task_moved.emit(task.id, new_day)
            self._drag_task_idx = None
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
            p.setFont(QFont("sans-serif", 12))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无任务数据")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        label_w = self._LABEL_W
        chart_w = w - label_w

        # ── 表头（天数标尺）──
        p.fillRect(0, 0, w, self._header_height, QColor(SURFACE0))
        p.setPen(QColor(SUBTEXT1))
        p.setFont(QFont("sans-serif", 9))
        step = max(1, self._total_days // 15)
        for d in range(0, self._total_days + 1, step):
            x = label_w + d * self._day_w
            p.drawText(int(x) - 10, 0, 30, self._header_height,
                       Qt.AlignmentFlag.AlignCenter, f"D{d}")
            p.setPen(QColor(SURFACE1))
            p.drawLine(int(x), self._header_height, int(x), self.height())
            p.setPen(QColor(SUBTEXT0))

        # ── 任务条 ──
        p.setFont(QFont("sans-serif", 10))
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
            bar_x = label_w + task.start_day * self._day_w
            bar_w = task.duration * self._day_w
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

    # 转发甘特图拖拽信号
    task_moved = Signal(int, int)  # (task_id, new_start_day)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        # ── 计划操作组 ──
        toolbar.addWidget(QLabel("计划:"))
        self._plan_combo = QComboBox()
        self._plan_combo.setFixedWidth(180)
        toolbar.addWidget(self._plan_combo)

        self._btn_add_plan = QPushButton("新建计划")
        self._btn_add_plan.setProperty("class", "action")
        self._btn_add_plan.setFixedHeight(28)
        toolbar.addWidget(self._btn_add_plan)

        self._btn_edit_plan = QPushButton("编辑计划")
        self._btn_edit_plan.setProperty("class", "action")
        self._btn_edit_plan.setFixedHeight(28)
        toolbar.addWidget(self._btn_edit_plan)

        self._btn_schedule = QPushButton("自动排程")
        self._btn_schedule.setProperty("class", "action")
        self._btn_schedule.setFixedHeight(28)
        toolbar.addWidget(self._btn_schedule)

        # ── 分隔线 ──
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet(f"color: {SURFACE1};")
        toolbar.addWidget(sep1)

        # ── 任务操作组 ──
        self._btn_add_task = QPushButton("添加任务")
        self._btn_add_task.setProperty("class", "action")
        self._btn_add_task.setFixedHeight(28)
        toolbar.addWidget(self._btn_add_task)

        self._btn_edit_task = QPushButton("编辑任务")
        self._btn_edit_task.setProperty("class", "action")
        self._btn_edit_task.setFixedHeight(28)
        toolbar.addWidget(self._btn_edit_task)

        self._btn_delete_task = QPushButton("删除任务")
        self._btn_delete_task.setProperty("class", "action")
        self._btn_delete_task.setFixedHeight(28)
        toolbar.addWidget(self._btn_delete_task)

        self._btn_import_tasks = QPushButton("导入任务")
        self._btn_import_tasks.setProperty("class", "action")
        self._btn_import_tasks.setFixedHeight(28)
        toolbar.addWidget(self._btn_import_tasks)

        self._btn_record_result = QPushButton("录入结果")
        self._btn_record_result.setProperty("class", "primary")
        self._btn_record_result.setFixedHeight(28)
        toolbar.addWidget(self._btn_record_result)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 子 Tab: 测试项 / 甘特图
        from PySide6.QtWidgets import QTabWidget
        self._sub_tabs = QTabWidget()
        self._sub_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {SURFACE1}; border-radius: 4px; background: {BASE}; }}
            QTabBar::tab {{ padding: 4px 16px; background: {SURFACE0}; color: {TEXT}; border: 1px solid {SURFACE1}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {BASE}; font-weight: bold; }}
        """)

        # Tab 1: 任务表格
        tab_table = QWidget()
        tab_table_layout = QVBoxLayout(tab_table)
        tab_table_layout.setContentsMargins(0, 0, 0, 0)
        self._task_table = _TaskTable()
        tab_table_layout.addWidget(self._task_table)
        self._sub_tabs.addTab(tab_table, "测试项")

        # Tab 2: 甘特图
        tab_gantt = QWidget()
        tab_gantt_layout = QVBoxLayout(tab_gantt)
        tab_gantt_layout.setContentsMargins(0, 0, 0, 0)
        self._gantt = _GanttWidget()
        self._gantt.setStyleSheet(f"background-color: {BASE}; border: 1px solid {SURFACE1}; border-radius: 6px;")
        self._gantt.task_moved.connect(self.task_moved.emit)
        tab_gantt_layout.addWidget(self._gantt)
        self._sub_tabs.addTab(tab_gantt, "甘特图")

        layout.addWidget(self._sub_tabs, stretch=1)

    def refresh(
        self,
        tasks: list[TestTask],
        total_days: int = 30,
        technician_map: dict[int, str] | None = None,
        result_map: dict[int, tuple[int, int]] | None = None,
    ) -> None:
        self._task_table.set_tasks(tasks, technician_map, result_map)
        self._gantt.set_tasks(tasks, total_days)
        self._gantt.setMinimumHeight(max(150, len(tasks) * 28 + 24))

    def set_plans(self, plan_names: list[str], plan_ids: list[int] | None = None) -> None:
        """设置计划下拉选项。"""
        self._plan_combo.blockSignals(True)
        self._plan_combo.clear()
        for i, name in enumerate(plan_names):
            self._plan_combo.addItem(name)
            self._plan_combo.setItemData(i, name, Qt.ItemDataRole.ToolTipRole)
        self._plan_ids = plan_ids or list(range(len(plan_names)))
        self._plan_combo.blockSignals(False)

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
    def btn_add_plan(self) -> QPushButton:
        return self._btn_add_plan

    @property
    def btn_edit_plan(self) -> QPushButton:
        return self._btn_edit_plan

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

    @property
    def btn_import_tasks(self) -> QPushButton:
        return self._btn_import_tasks

    @property
    def btn_record_result(self) -> QPushButton:
        return self._btn_record_result

    def setup_task_callbacks(
        self,
        on_add: Callable[[], None] | None = None,
        on_edit: Callable[[TestTask], None] | None = None,
        on_delete: Callable[[TestTask], None] | None = None,
        on_status_advance: Callable[[TestTask, str], None] | None = None,
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
            on_status_advance=on_status_advance,
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
