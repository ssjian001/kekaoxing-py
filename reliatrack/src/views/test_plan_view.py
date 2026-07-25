"""测试计划视图 — 任务列表 + 简化甘特图。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Optional

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

import src.styles.theme as _t
from src.styles.constants import VIEW_MARGINS
from src.models.test_plan import TestTask
from src.views.widgets.task_table import _TaskTable
from src.views.widgets.result_matrix import _ResultMatrixWidget
from src.views.widgets.plan_toolbar import PlanToolbar
from src.views.widgets.plan_filter_bar import PlanFilterBar
from src.views.widgets.plan_summary import compute_summary, format_summary_text

class TestPlanView(QWidget):
    """测试计划视图 — 左侧任务表 + 右侧甘特图。"""

    __test__ = False

    # 转发甘特图拖拽信号
    task_moved = Signal(int, int)  # (task_id, new_start_day)

    show_archived: bool = False  # 是否显示已归档计划

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        # ── Row 1: 计划/任务管理 — 提取为 PlanToolbar ──
        self._toolbar = PlanToolbar(self)
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(self._toolbar.command_bar())
        row1.addStretch()
        layout.addLayout(row1)

        # 代理 toolbar 属性（保持外部引用不变）
        tb = self._toolbar
        self._plan_menu = tb._plan_menu
        self._act_add_plan = tb._act_add_plan
        self._act_edit_plan = tb._act_edit_plan
        self._act_unarchive_plan = tb._act_unarchive_plan
        self._act_archive_plan = tb._act_archive_plan
        self._act_toggle_archived = tb._act_toggle_archived
        self._btn_plan_manage = tb._btn_plan_manage
        self._task_menu = tb._task_menu
        self._act_add_task = tb._act_add_task
        self._act_edit_task = tb._act_edit_task
        self._act_delete_task = tb._act_delete_task
        self._act_import_tasks = tb._act_import_tasks
        self._act_import_from_plan = tb._act_import_from_plan
        self._btn_task_manage = tb._btn_task_manage
        self._btn_record_result = tb._btn_record_result
        self._more_menu = tb._more_menu
        self._act_schedule = tb._act_schedule
        self._act_quick_add = tb._act_quick_add
        self._act_summary_report = tb._act_summary_report
        self._btn_more = tb._btn_more

        # ── Row 2: 搜索/筛选 — 提取为 PlanFilterBar ──
        self._filter_bar = PlanFilterBar(self)
        layout.addWidget(self._filter_bar)

        # 代理 filter bar 属性
        fb = self._filter_bar
        self._plan_combo = fb._plan_combo
        self._search_edit = fb._search_edit
        self._tech_filter_combo = fb._tech_filter_combo
        self._status_filter_combo = fb._status_filter_combo
        self._category_filter_combo = fb._category_filter_combo
        self._date_from = fb._date_from
        self._date_to = fb._date_to
        self._btn_reset_filter = fb._btn_reset_filter
        self._summary_bar = fb._summary_bar

        # 连接筛选信号
        self._search_edit.textChanged.connect(self._on_task_search)
        self._tech_filter_combo.currentIndexChanged.connect(self._on_task_search)
        self._status_filter_combo.currentIndexChanged.connect(self._on_task_search)
        self._category_filter_combo.currentIndexChanged.connect(self._on_task_search)
        self._date_from.dateChanged.connect(self._on_task_search)
        self._date_to.dateChanged.connect(self._on_task_search)
        self._btn_reset_filter.clicked.connect(self._reset_filters)

        # 恢复搜索历史
        from PySide6.QtCore import QSettings as _QSettings
        saved = _QSettings().value("ReliaTrack/task_search", "")
        if saved and isinstance(saved, str):
            self._search_edit.setText(saved)

        # 子 Tab: 测试项 / 甘特图
        from src.views.widgets.segmented_widget import SegmentedWidget
        self._sub_stacked = QStackedWidget()
        self._sub_tabs = SegmentedWidget()

        # Tab 0: 任务表格
        tab_table = QWidget()
        tab_table_layout = QVBoxLayout(tab_table)
        tab_table_layout.setContentsMargins(0, 0, 0, 0)
        self._task_table = _TaskTable()
        tab_table_layout.addWidget(self._task_table)
        self._sub_stacked.addWidget(tab_table)
        self._sub_tabs.addSegment("测试项", tab_table)

        # Tab 1: 甘特图 — 提取为 PlanGanttTab
        from src.views.widgets.plan_gantt_tab import PlanGanttTab
        self._gantt_tab = PlanGanttTab(self)
        self._gantt_tab.mode_toggled.connect(self._on_gantt_mode_toggled)
        self._gantt_tab.task_moved.connect(self.task_moved.emit)
        self._sub_stacked.addWidget(self._gantt_tab)
        self._sub_tabs.addSegment("甘特图", self._gantt_tab)

        # 代理 gantt 属性
        self._gantt = self._gantt_tab.gantt

        # Tab 2: 结果矩阵（任务×样品 pass/fail 矩阵）
        tab_matrix = QWidget()
        tab_matrix_layout = QVBoxLayout(tab_matrix)
        tab_matrix_layout.setContentsMargins(0, 0, 0, 0)
        self._result_matrix = _ResultMatrixWidget(parent=self)
        self._result_matrix.set_on_result_changed(self._on_matrix_result_changed)
        tab_matrix_layout.addWidget(self._result_matrix)
        self._sub_stacked.addWidget(tab_matrix)
        self._sub_tabs.addSegment("结果矩阵", tab_matrix)

        # Tab 3: 失效模式分析
        from src.views.widgets.analysis_widget import _AnalysisWidget
        tab_analysis = QWidget()
        tab_analysis_layout = QVBoxLayout(tab_analysis)
        tab_analysis_layout.setContentsMargins(0, 0, 0, 0)
        self._analysis = _AnalysisWidget()
        tab_analysis_layout.addWidget(self._analysis)
        self._sub_stacked.addWidget(tab_analysis)
        self._sub_tabs.addSegment("分析", tab_analysis)

        # 聯繫 SegmentedWidget ↔ QStackedWidget
        self._sub_tabs.setStackedWidget(self._sub_stacked)
        self._sub_tabs.setCurrentIndex(0)

        layout.addWidget(self._sub_tabs)
        layout.addWidget(self._sub_stacked, stretch=1)

        # 全量任务缓存（用于搜索过滤）
        self._all_tasks_for_filter: list[TestTask] = []
        self._last_technician_map: dict[int, str] = {}
        self._last_result_map: dict[int, tuple[int, int]] = {}
        self._last_start_date: str = ""
        self._last_equipment_map: dict[int, str] = {}
        self._last_task_prefix: str = ""
        self._last_holidays: set[str] = set()

    def _on_gantt_mode_toggled(self, btn_id: int, checked: bool) -> None:
        """甘特图模式切换。"""
        if checked:
            self._gantt.set_mode(actual=(btn_id == 1))

    def _on_matrix_result_changed(self, task_id: int, sample_id: int, new_result: str) -> None:
        """结果矩阵双击编辑 — 委托给 plan_handlers 保存。"""
        if self._on_matrix_edit_callback:
            self._on_matrix_edit_callback(task_id, sample_id, new_result)

    def set_on_matrix_edit_callback(self, callback: Callable[[int, int, str], None] | None) -> None:
        """设置矩阵双击编辑回调（由 plan_handlers 在初始化时调用）。"""
        self._on_matrix_edit_callback = callback

    def _on_task_search(self, text: str = "") -> None:
        """根据搜索关键词、技术员、日期范围过滤任务列表。"""
        text = self._search_edit.text().strip().lower()
        from PySide6.QtCore import QSettings as _QSettings
        _QSettings().setValue("ReliaTrack/task_search", text)
        filtered = self._all_tasks_for_filter

        # 关键词过滤
        if text:
            filtered = [
                t for t in filtered
                if text in (t.name or "").lower()
            ]

        # 技术员过滤
        tech_id = self._tech_filter_combo.currentData()
        if tech_id is not None:
            filtered = [
                t for t in filtered
                if t.technician_id == tech_id
            ]

        # 状态过滤
        status_val = self._status_filter_combo.currentData()
        if status_val is not None:
            filtered = [
                t for t in filtered
                if t.status == status_val
            ]

        # 类别过滤
        cat_val = self._category_filter_combo.currentData()
        if cat_val is not None:
            filtered = [
                t for t in filtered
                if (t.category or "其他") == cat_val
            ]

        # 日期范围过滤（任务起止日期重叠校验）
        d_from = self._date_from.date().toPython() if self._date_from.date() > self._date_from.minimumDate() else None
        d_to = self._date_to.date().toPython() if self._date_to.date() < self._date_to.maximumDate() else None
        if d_from or d_to:
            plan_start = None
            try:
                plan_start = date.fromisoformat(self._last_start_date) if self._last_start_date else None
            except ValueError:
                pass
            if plan_start:
                date_filtered = []
                for t in filtered:
                    s_date = plan_start + timedelta(days=t.start_day)
                    e_date = plan_start + timedelta(days=t.start_day + max(t.duration, 1) - 1)
                    if d_from and e_date < d_from:
                        continue
                    if d_to and s_date > d_to:
                        continue
                    date_filtered.append(t)
                filtered = date_filtered

        self._task_table.set_tasks(
            filtered, self._last_technician_map, self._last_result_map,
            start_date=self._last_start_date,
            task_prefix=self._last_task_prefix,
        )
        total_d = getattr(self, '_last_total_days', 30)
        self._gantt.set_tasks(filtered, total_days=total_d, start_date=self._last_start_date,
                              equipment_map=self._last_equipment_map,
                              technician_map=self._last_technician_map,
                              task_prefix=self._last_task_prefix,
                              holidays=self._last_holidays)

        self._update_summary_bar()
        self._update_stats(filtered)

    def _reset_filters(self) -> None:
        """重置所有筛选条件到默认值。"""
        self._search_edit.clear()
        self._tech_filter_combo.setCurrentIndex(0)
        self._status_filter_combo.setCurrentIndex(0)
        self._category_filter_combo.setCurrentIndex(0)
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_to.setDate(self._date_to.maximumDate())
        self._on_task_search()


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
        task_prefix: str = "",
        holidays: set[str] | None = None,
    ) -> None:
        self._all_tasks_for_filter = tasks
        self._last_total_days = total_days
        self._last_technician_map = technician_map or {}
        self._last_result_map = result_map or {}
        self._last_start_date = start_date
        self._last_equipment_map = equipment_map or {}
        self._last_technician_map = technician_map or {}
        self._last_task_prefix = task_prefix
        self._last_holidays = holidays or set()
        # 更新技术员筛选下拉
        self._tech_filter_combo.blockSignals(True)
        selected = self._tech_filter_combo.currentData()
        self._tech_filter_combo.clear()
        self._tech_filter_combo.addItem("全部技术员", None)
        seen: set[int] = set()
        for t in tasks:
            if t.technician_id and t.technician_id not in seen:
                seen.add(t.technician_id)
                name = technician_map.get(t.technician_id, f"ID:{t.technician_id}")
                self._tech_filter_combo.addItem(name, t.technician_id)
        # 恢复选中
        if selected is not None:
            idx = self._tech_filter_combo.findData(selected)
            if idx >= 0:
                self._tech_filter_combo.setCurrentIndex(idx)
        self._tech_filter_combo.blockSignals(False)

        # 应用当前所有筛选条件并更新表格、甘特图和统计栏
        self._on_task_search()

        # 结果矩阵
        self._result_matrix.refresh(tasks, matrix_results or [], sample_map or {})
        # 失效模式分析
        self._analysis.refresh(tasks, matrix_results or [], issues or [], sample_map)
        self._update_summary_bar()


    def _compute_summary(
        self,
        tasks: list[TestTask],
        result_map: dict[int, tuple[int, int]],
        start_date: str,
    ) -> tuple[int, int, int]:
        """计算摘要指标: (到期数, 待录入数, 超期数)。"""
        return compute_summary(tasks, result_map, start_date)

    def _update_stats(self, tasks: list[TestTask]) -> None:
        """更新任务统计：总数/完成/未完成/超期。"""
        self._summary_bar.setText(
            format_summary_text(tasks, self._last_start_date, self._summary_bar.text())
        )

    def _update_summary_bar(self) -> None:
        """更新今日工作摘要。"""
        tasks = self._all_tasks_for_filter
        if not tasks:
            self._summary_bar.clear()
            return

        due, pending, overdue = self._compute_summary(
            tasks, self._last_result_map, self._last_start_date,
        )

        if not self._last_start_date:
            self._summary_bar.setText("待办: 设定计划开始日期后显示摘要")
            return

        parts: list[str] = []
        if overdue > 0:
            parts.append(f'<span style="color:{_t.RED}">{overdue} 个超期</span>')
        if due > 0:
            parts.append(f'<span style="color:{_t.YELLOW}">{due} 个今天到期</span>')
        if pending > 0:
            parts.append(f'{pending} 个结果待录入')

        if not parts:
            self._summary_bar.setText("待办: 全部正常")
        else:
            self._summary_bar.setText("待办: " + " | ".join(parts))

    def set_plans(self, plan_names: list[str], plan_ids: list[int] | None = None) -> None:
        """设置计划下拉选项。"""
        self._plan_combo.blockSignals(True)
        self._plan_combo.clear()
        for i, name in enumerate(plan_names):
            self._plan_combo.addItem(name)
            self._plan_combo.setItemData(i, name, Qt.ItemDataRole.ToolTipRole)
        self._plan_ids = plan_ids or list(range(len(plan_names)))
        self._plan_combo.blockSignals(False)
        # blockSignals 期间 index 可能变化，手动触发菜单更新
        self._plan_combo.currentIndexChanged.emit(self._plan_combo.currentIndex())

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
        # blockSignals 期间 index 可能变化，手动触发菜单更新
        self._plan_combo.currentIndexChanged.emit(self._plan_combo.currentIndex())

    def get_selected_plan_id(self) -> int | None:
        """获取当前选中计划的 ID。"""
        idx = self._plan_combo.currentIndex()
        if 0 <= idx < len(self._plan_ids):
            return self._plan_ids[idx]
        return None

    def select_plan_by_id(self, plan_id: int) -> None:
        """按 plan_id 选中本地 combo（響應全局篩選同步）。"""
        if plan_id in self._plan_ids:
            idx = self._plan_ids.index(plan_id)
            self._plan_combo.setCurrentIndex(idx)

    @property
    def selected_plan_index(self) -> int:
        return self._plan_combo.currentIndex()

    @property
    def task_table(self) -> _TaskTable:
        return self._task_table

    # ── 菜单 action 属性（供 handler 连接） ──
    @property
    def act_add_plan(self) -> QAction:
        return self._act_add_plan

    @property
    def act_edit_plan(self) -> QAction:
        return self._act_edit_plan

    @property
    def act_archive_plan(self) -> QAction:
        return self._act_archive_plan

    @property
    def act_unarchive_plan(self) -> QAction:
        return self._act_unarchive_plan

    @property
    def btn_schedule(self) -> QAction:
        return self._act_schedule

    @property
    def act_add_task(self) -> QAction:
        return self._act_add_task

    @property
    def act_edit_task(self) -> QAction:
        return self._act_edit_task

    @property
    def act_delete_task(self) -> QAction:
        return self._act_delete_task

    @property
    def act_import_tasks(self) -> QAction:
        return self._act_import_tasks

    @property
    def act_import_from_plan(self) -> QAction:
        return self._act_import_from_plan

    @property
    def btn_record_result(self) -> QPushButton:
        return self._btn_record_result

    @property
    def btn_quick_add(self) -> QAction:
        return self._act_quick_add

    @property
    def btn_summary_report(self) -> QAction:
        return self._act_summary_report

    def setup_task_callbacks(
        self,
        on_add: Callable[[], None] | None = None,
        on_edit: Callable[[TestTask], None] | None = None,
        on_delete: Callable[[TestTask], None] | None = None,
        on_status_advance: Callable[[TestTask, str], None] | None = None,
        on_actual_date_edit: Callable[[int, str, str], None] | None = None,
        on_record_result: Callable[[], None] | None = None,
        on_batch_value: Callable[[list[int], int, str], None] | None = None,
        technician_list: list | None = None,
        equipment_list: list | None = None,
    ) -> None:
        """设置任务增删改以及实际日期编辑回调。

        外部调用此方法，将实际业务逻辑（打开弹窗、调用 Service 等）注入。
        technician_list / equipment_list 用于右键菜单的批量指派等功能。
        """
        self._on_add_task = on_add
        self._on_edit_task = on_edit
        self._on_delete_task = on_delete

        # 注入參考數據（技術員/設備列表），供右鍵批量指派使用
        if technician_list is not None or equipment_list is not None:
            self._task_table.set_reference_data(
                equipment_list or [],
                technician_list or [],
            )

        # 表格右键 & 双击
        self._task_table.set_callbacks(
            on_edit=self._handle_table_edit,
            on_delete=self._handle_table_delete,
            on_status_advance=on_status_advance,
            on_actual_date_edit=on_actual_date_edit,
            on_record_result=on_record_result,
            on_batch_value=on_batch_value,
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

    def _on_toggle_archived(self, checked: bool) -> None:
        """显示/隐藏已归档计划切换。"""
        self.show_archived = checked
        self._act_toggle_archived.setChecked(checked)


# ═══════════════════════════════════════════════════════════════════
#  结果矩阵（任务×样品 pass/fail 矩阵）
# ═══════════════════════════════════════════════════════════════════