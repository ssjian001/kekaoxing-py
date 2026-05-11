"""测试计划视图 — 任务列表 + 简化甘特图。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFrame,
    QMessageBox,
    QLineEdit,
    QScrollArea,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1, OVERLAY0,
    BLUE, GREEN, YELLOW, RED, PEACH, MAUVE, LAVENDER, TEAL,
)
from src.styles.constants import VIEW_MARGINS, FONT_FAMILY
from src.constants import TASK_STATUS_LABELS
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician
from src.views.widgets.task_table import _TaskTable
from src.views.widgets.gantt_widget import _GanttWidget
from src.views.widgets.result_matrix import _ResultMatrixWidget

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
        self._btn_add_plan.setToolTip("新建测试计划")
        toolbar.addWidget(self._btn_add_plan)

        self._btn_edit_plan = QPushButton("编辑计划")
        self._btn_edit_plan.setProperty("class", "action")
        self._btn_edit_plan.setFixedHeight(28)
        self._btn_edit_plan.setToolTip("编辑当前计划")
        toolbar.addWidget(self._btn_edit_plan)

        self._btn_schedule = QPushButton("自动排程")
        self._btn_schedule.setProperty("class", "action")
        self._btn_schedule.setFixedHeight(28)
        self._btn_schedule.setToolTip("自动排程（资源约束优化）")
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
        self._btn_add_task.setToolTip("添加测试任务")
        toolbar.addWidget(self._btn_add_task)

        self._btn_edit_task = QPushButton("编辑任务")
        self._btn_edit_task.setProperty("class", "action")
        self._btn_edit_task.setFixedHeight(28)
        self._btn_edit_task.setToolTip("编辑选中任务")
        toolbar.addWidget(self._btn_edit_task)

        self._btn_delete_task = QPushButton("删除任务")
        self._btn_delete_task.setProperty("class", "action")
        self._btn_delete_task.setFixedHeight(28)
        self._btn_delete_task.setToolTip("删除选中任务")
        toolbar.addWidget(self._btn_delete_task)

        # ── 搜索框 ──
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍 搜索任务名...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMaximumWidth(160)
        self._search_edit.textChanged.connect(self._on_task_search)
        toolbar.addWidget(self._search_edit)

        # ── 分隔线 ──
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color: {SURFACE1};")
        toolbar.addWidget(sep2)

        self._btn_import_tasks = QPushButton("导入任务")
        self._btn_import_tasks.setProperty("class", "action")
        self._btn_import_tasks.setFixedHeight(28)
        self._btn_import_tasks.setToolTip("从 Excel 批量导入任务")
        toolbar.addWidget(self._btn_import_tasks)

        self._btn_record_result = QPushButton("录入结果")
        self._btn_record_result.setProperty("class", "primary")
        self._btn_record_result.setFixedHeight(28)
        self._btn_record_result.setToolTip("录入测试结果")
        toolbar.addWidget(self._btn_record_result)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 今日工作摘要
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet(
            f"color: {SUBTEXT1}; font-size: 11px; padding: 2px 8px;"
            f" background: {SURFACE0}; border-radius: 4px;"
        )
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

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

        # Tab 2: 甘特图（QScrollArea 包裹，支持大量任务纵向滚动）
        tab_gantt = QWidget()
        tab_gantt_layout = QVBoxLayout(tab_gantt)
        tab_gantt_layout.setContentsMargins(0, 0, 0, 0)
        # 甘特图模式切换栏
        gantt_mode_bar = QHBoxLayout()
        gantt_mode_bar.setContentsMargins(4, 2, 4, 2)
        from PySide6.QtWidgets import QButtonGroup
        self._gantt_mode_planned = QRadioButton("预计日期")
        self._gantt_mode_actual = QRadioButton("实际日期")
        self._gantt_mode_planned.setChecked(True)
        gantt_mode_group = QButtonGroup(self)
        gantt_mode_group.addButton(self._gantt_mode_planned, 0)
        gantt_mode_group.addButton(self._gantt_mode_actual, 1)
        gantt_mode_group.idToggled.connect(self._on_gantt_mode_toggled)
        mode_label = QLabel("显示模式:")
        mode_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px;")
        gantt_mode_bar.addWidget(mode_label)
        gantt_mode_bar.addWidget(self._gantt_mode_planned)
        gantt_mode_bar.addWidget(self._gantt_mode_actual)
        gantt_mode_bar.addStretch()
        tab_gantt_layout.addLayout(gantt_mode_bar)
        self._gantt = _GanttWidget()
        self._gantt.setStyleSheet(f"background-color: {BASE}; border: 1px solid {SURFACE1}; border-radius: 6px;")
        self._gantt.task_moved.connect(self.task_moved.emit)
        self._gantt_scroll = QScrollArea()
        self._gantt_scroll.setWidget(self._gantt)
        self._gantt_scroll.setWidgetResizable(True)
        self._gantt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gantt_scroll.setStyleSheet(f"background-color: {BASE}; border: none;")
        self._gantt.bind_scroll_area(self._gantt_scroll)
        tab_gantt_layout.addWidget(self._gantt_scroll)
        self._sub_tabs.addTab(tab_gantt, "甘特图")

        # Tab 3: 结果矩阵（任务×样品 pass/fail 矩阵）
        tab_matrix = QWidget()
        tab_matrix_layout = QVBoxLayout(tab_matrix)
        tab_matrix_layout.setContentsMargins(0, 0, 0, 0)
        self._result_matrix = _ResultMatrixWidget()
        tab_matrix_layout.addWidget(self._result_matrix)
        self._sub_tabs.addTab(tab_matrix, "结果矩阵")

        # Tab 4: 失效模式分析
        from src.views.widgets.analysis_widget import _AnalysisWidget
        tab_analysis = QWidget()
        tab_analysis_layout = QVBoxLayout(tab_analysis)
        tab_analysis_layout.setContentsMargins(0, 0, 0, 0)
        self._analysis = _AnalysisWidget()
        tab_analysis_layout.addWidget(self._analysis)
        self._sub_tabs.addTab(tab_analysis, "分析")

        layout.addWidget(self._sub_tabs, stretch=1)

        # 全量任务缓存（用于搜索过滤）
        self._all_tasks_for_filter: list[TestTask] = []
        self._last_technician_map: dict[int, str] = {}
        self._last_result_map: dict[int, tuple[int, int]] = {}
        self._last_start_date: str = ""
        self._last_equipment_map: dict[int, str] = {}

    def _on_gantt_mode_toggled(self, btn_id: int, checked: bool) -> None:
        """甘特图预计/实际模式切换。"""
        if checked:
            self._gantt.set_mode(actual=(btn_id == 1))

    def _on_task_search(self, text: str) -> None:
        """根据搜索关键词过滤任务列表。"""
        text = text.strip().lower()
        if not text:
            filtered = self._all_tasks_for_filter
        else:
            filtered = [
                t for t in self._all_tasks_for_filter
                if text in (t.name or "").lower()
            ]
        self._task_table.set_tasks(
            filtered, self._last_technician_map, self._last_result_map,
            start_date=self._last_start_date,
        )
        self._gantt.set_tasks(filtered, start_date=self._last_start_date,
                              equipment_map=self._last_equipment_map)

    def refresh(
        self,
        tasks: list[TestTask],
        total_days: int = 30,
        technician_map: dict[int, str] | None = None,
        result_map: dict[int, tuple[int, int]] | None = None,
        start_date: str = "",
        matrix_results: list | None = None,
        sample_map: dict[int, str] | None = None,
        equipment_map: dict[int, str] | None = None,
        issues: list | None = None,
    ) -> None:
        self._all_tasks_for_filter = tasks
        self._last_technician_map = technician_map or {}
        self._last_result_map = result_map or {}
        self._last_start_date = start_date
        self._last_equipment_map = equipment_map or {}
        self._on_task_search(self._search_edit.text())
        self._gantt.set_tasks(tasks, total_days, start_date,
                              equipment_map=equipment_map)
        # 结果矩阵
        self._result_matrix.refresh(tasks, matrix_results or [], sample_map or {})
        # 失效模式分析
        self._analysis.refresh(tasks, matrix_results or [], issues or [], sample_map)
        self._update_summary_bar()

    @staticmethod
    def _compute_summary(
        tasks: list[TestTask],
        result_map: dict[int, tuple[int, int]],
        start_date: str,
    ) -> tuple[int, int, int]:
        """计算摘要指标: (到期数, 待录入数, 超期数)。

        到期: 预计结束日期 <= 今天且未完成。
        待录入: 有样品但结果数不足。
        超期: 预计结束日期 < 今天且未完成。
        """
        import json as _json

        if not start_date:
            return 0, 0, 0

        try:
            base = date.fromisoformat(start_date)
        except ValueError:
            return 0, 0, 0

        today = date.today()
        due_count = 0
        overdue_count = 0
        pending_result_count = 0

        for task in tasks:
            if task.status in ("completed", "skipped"):
                continue
            end_day = task.start_day + task.duration
            end_date = base + timedelta(days=end_day)

            # 超期
            if end_date < today:
                overdue_count += 1
            # 到期（含超期和今天到期）
            elif end_date == today:
                due_count += 1

            # 待录入: sample_ids 有内容但结果数不足
            if task.id is not None:
                try:
                    sids = _json.loads(task.sample_ids) if task.sample_ids else []
                except (ValueError, TypeError):
                    sids = []
                if sids:
                    pass_cnt, total_cnt = result_map.get(task.id, (0, 0))
                    if total_cnt < len(sids):
                        pending_result_count += 1

        return due_count, pending_result_count, overdue_count

    def _update_summary_bar(self) -> None:
        """更新今日工作摘要。"""
        tasks = self._all_tasks_for_filter
        if not tasks:
            self._summary_label.clear()
            return

        due, pending, overdue = self._compute_summary(
            tasks, self._last_result_map, self._last_start_date,
        )

        if not self._last_start_date:
            self._summary_label.setText("待办: 设定计划开始日期后显示摘要")
            return

        parts: list[str] = []
        if overdue > 0:
            parts.append(f'<span style="color:{RED}">{overdue} 个超期</span>')
        if due > 0:
            parts.append(f'<span style="color:{YELLOW}">{due} 个今天到期</span>')
        if pending > 0:
            parts.append(f'{pending} 个结果待录入')

        if not parts:
            self._summary_label.setText("待办: 全部正常")
        else:
            self._summary_label.setText("待办: " + " | ".join(parts))

    def set_plans(self, plan_names: list[str], plan_ids: list[int] | None = None) -> None:
        """设置计划下拉选项。"""
        self._plan_combo.blockSignals(True)
        self._plan_combo.clear()
        for i, name in enumerate(plan_names):
            self._plan_combo.addItem(name)
            self._plan_combo.setItemData(i, name, Qt.ItemDataRole.ToolTipRole)
        self._plan_ids = plan_ids or list(range(len(plan_names)))
        self._plan_combo.blockSignals(False)

    def set_plans_and_restore(
        self, plan_names: list[str], plan_ids: list[int], restore_id: int | None = None,
    ) -> None:
        """设置计划下拉选项并恢复选中（不触发信号）。

        Args:
            plan_names: 计划名称列表
            plan_ids: 计划 ID 列表（与 plan_names 等长）
            restore_id: 要恢复选中的计划 ID，None 则选第一项
        """
        self._plan_combo.blockSignals(True)
        self._plan_combo.clear()
        for i, name in enumerate(plan_names):
            self._plan_combo.addItem(name)
            self._plan_combo.setItemData(i, name, Qt.ItemDataRole.ToolTipRole)
        self._plan_ids = plan_ids or list(range(len(plan_names)))
        # 恢复选中
        restore_idx = 0
        if plan_ids and restore_id is not None:
            if restore_id in plan_ids:
                restore_idx = plan_ids.index(restore_id)
        if self._plan_combo.count() > 0:
            self._plan_combo.setCurrentIndex(restore_idx)
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

        # 工具栏按钮 — 先 disconnect 防止重复调用
        import warnings
        for btn in (self._btn_add_task, self._btn_edit_task, self._btn_delete_task):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    btn.clicked.disconnect()
                except RuntimeError:
                    pass
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


# ═══════════════════════════════════════════════════════════════════
#  结果矩阵（任务×样品 pass/fail 矩阵）
# ═══════════════════════════════════════════════════════════════════