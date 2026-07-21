"""测试计划视图 — 任务列表 + 简化甘特图。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Optional

from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QLabel,
    QComboBox,
    QFrame,
    QMenu,
    QMessageBox,
    QLineEdit,
    QScrollArea,
    QRadioButton,
    QButtonGroup,
    QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QSize

import src.styles.theme as _t
from src.styles.constants import VIEW_MARGINS, FONT_FAMILY
from src.constants import TASK_STATUS_LABELS
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician
from src.views.widgets.task_table import _TaskTable
from src.views.widgets.gantt_widget import _GanttWidget
from src.views.widgets.result_matrix import _ResultMatrixWidget
from src.views.widgets.command_bar import CommandBar
from src.views.widgets.search_box import SearchBox

class TestPlanView(QWidget):
    """测试计划视图 — 左侧任务表 + 右侧甘特图。"""

    # 转发甘特图拖拽信号
    task_moved = Signal(int, int)  # (task_id, new_start_day)

    show_archived: bool = False  # 是否显示已归档计划

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        # ── Row 1: 计划/任务管理 ──
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        # ── CommandBar（计划/任务/操作管理，自動溢出）──
        action_bar = CommandBar()
        action_bar.setButtonTight(True)

        # ── 分组 1: 计划管理 ──
        self._plan_menu = QMenu(self)
        self._act_add_plan = self._plan_menu.addAction("新建计划")
        self._act_edit_plan = self._plan_menu.addAction("编辑计划")
        self._plan_menu.addSeparator()
        self._act_unarchive_plan = self._plan_menu.addAction("取消归档")
        self._act_unarchive_plan.setVisible(False)
        self._act_archive_plan = self._plan_menu.addAction("归档")
        self._plan_menu.addSeparator()
        self._act_toggle_archived = self._plan_menu.addAction("查看归档")
        self._act_toggle_archived.setCheckable(True)

        self._btn_plan_manage = QToolButton()
        self._btn_plan_manage.setText("计划管理")
        self._btn_plan_manage.setMenu(self._plan_menu)
        self._btn_plan_manage.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_plan_manage.setProperty("class", "action")
        self._btn_plan_manage.setFixedHeight(26)
        self._btn_plan_manage.setToolTip("计划管理：新建、编辑、归档、查看归档")
        action_bar.addWidget(self._btn_plan_manage)

        action_bar.addSeparator()

        # ── 分组 2: 任务管理 ──
        self._task_menu = QMenu(self)
        self._act_add_task = self._task_menu.addAction("添加任务")
        self._act_edit_task = self._task_menu.addAction("编辑任务")
        self._act_delete_task = self._task_menu.addAction("删除任务")
        self._task_menu.addSeparator()
        self._act_import_tasks = self._task_menu.addAction("导入任务")
        self._act_import_from_plan = self._task_menu.addAction("从计划导入")

        self._btn_task_manage = QToolButton()
        self._btn_task_manage.setText("任务管理")
        self._btn_task_manage.setMenu(self._task_menu)
        self._btn_task_manage.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_task_manage.setProperty("class", "action")
        self._btn_task_manage.setFixedHeight(26)
        self._btn_task_manage.setToolTip("任务管理：增删改、导入")
        action_bar.addWidget(self._btn_task_manage)

        action_bar.addSeparator()

        # ── 分组 3: 操作 ──
        self._btn_record_result = QPushButton("录入结果")
        self._btn_record_result.setProperty("class", "primary")
        self._btn_record_result.setFixedHeight(26)
        self._btn_record_result.setToolTip("录入测试结果")
        action_bar.addWidget(self._btn_record_result)

        # 更多操作下拉（自動排程 / 快速加 / 總結報告 等低頻操作）
        self._more_menu = QMenu(self)
        self._act_schedule = self._more_menu.addAction("自动排程")
        self._act_quick_add = self._more_menu.addAction("快速加任务")
        self._more_menu.addSeparator()
        self._act_summary_report = self._more_menu.addAction("总结报告")
        self._btn_more = QToolButton()
        self._btn_more.setText("更多")
        self._btn_more.setMenu(self._more_menu)
        self._btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_more.setProperty("class", "action")
        self._btn_more.setFixedHeight(26)
        self._btn_more.setToolTip("自动排程、快速加任务、总结报告等")
        action_bar.addWidget(self._btn_more)

        row1.addWidget(action_bar)
        row1.addStretch()
        layout.addLayout(row1)

        # ── Row 2: 搜索/筛选 ──
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        # 计划下拉（移至筛选行，与搜索/日期放一起）
        row2.addWidget(QLabel("计划:"))
        self._plan_combo = QComboBox()
        self._plan_combo.setProperty("class", "filter-combo")
        self._plan_combo.setFixedWidth(160)
        self._plan_combo.setFixedHeight(26)
        row2.addWidget(self._plan_combo)

        # ── 分组 1: 搜索 + 筛选 ──
        self._search_edit = SearchBox()
        self._search_edit.setPlaceholderText("搜索任务名…")
        self._search_edit.setFixedSize(200, 26)
        from PySide6.QtCore import QSettings as _QSettings
        saved = _QSettings().value("ReliaTrack/task_search", "")
        if saved and isinstance(saved, str):
            self._search_edit.setText(saved)
        self._search_edit.textChanged.connect(self._on_task_search)
        row2.addWidget(self._search_edit)

        self._tech_filter_combo = QComboBox()
        self._tech_filter_combo.setProperty("class", "filter-combo")
        self._tech_filter_combo.setFixedWidth(100)
        self._tech_filter_combo.setFixedHeight(26)
        self._tech_filter_combo.addItem("全部技术员", None)
        self._tech_filter_combo.currentIndexChanged.connect(self._on_task_search)
        row2.addWidget(self._tech_filter_combo)

        # ── 分隔线 1 ──
        sep2a = QFrame()
        sep2a.setFrameShape(QFrame.Shape.VLine)
        sep2a.setFixedWidth(1)
        sep2a.setFixedHeight(20)
        sep2a.setProperty("class", "sep-vline")
        row2.addWidget(sep2a)

        # ── 分组 2: 日期范围 ──
        from PySide6.QtWidgets import QDateEdit as _QDE
        self._date_from = _QDE()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setSpecialValueText("不限")
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_from.setFixedWidth(170)
        self._date_from.setFixedHeight(26)
        self._date_from.dateChanged.connect(self._on_task_search)
        row2.addWidget(self._date_from)

        self._date_to = _QDE()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setSpecialValueText("不限")
        self._date_to.setDate(self._date_to.maximumDate())
        self._date_to.setFixedWidth(120)
        self._date_to.setFixedHeight(26)
        self._date_to.dateChanged.connect(self._on_task_search)
        row2.addWidget(self._date_to)

        # 重置
        self._btn_reset_filter = QPushButton("重置")
        self._btn_reset_filter.setFixedHeight(26)
        self._btn_reset_filter.setProperty("class", "action")
        self._btn_reset_filter.clicked.connect(self._reset_filters)
        row2.addWidget(self._btn_reset_filter)

        row2.addStretch()
        layout.addLayout(row2)

        # 摘要信息栏（今日工作 + 任务统计合并）
        self._summary_bar = QLabel()
        self._summary_bar.setProperty("class", "summary-bar")
        self._summary_bar.setWordWrap(False)
        self._summary_bar.setFixedHeight(26)
        layout.addWidget(self._summary_bar)

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

        # Tab 1: 甘特图（QScrollArea 包裹，支持大量任务纵向滚动）
        tab_gantt = QWidget()
        tab_gantt_layout = QVBoxLayout(tab_gantt)
        tab_gantt_layout.setContentsMargins(0, 0, 0, 0)
        # 甘特图模式切换栏（pills 按钮组）
        gantt_mode_bar = QHBoxLayout()
        gantt_mode_bar.setContentsMargins(4, 2, 4, 2)
        self._gantt_mode_planned = QPushButton("预计日期")
        self._gantt_mode_planned.setProperty("class", "pill")
        self._gantt_mode_planned.setCheckable(True)
        self._gantt_mode_planned.setChecked(True)
        self._gantt_mode_planned.setFixedHeight(26)
        self._gantt_mode_actual = QPushButton("实际日期")
        self._gantt_mode_actual.setProperty("class", "pill")
        self._gantt_mode_actual.setCheckable(True)
        self._gantt_mode_actual.setFixedHeight(26)
        self._gantt_mode_group = QButtonGroup(self)
        self._gantt_mode_group.addButton(self._gantt_mode_planned, 0)
        self._gantt_mode_group.addButton(self._gantt_mode_actual, 1)
        self._gantt_mode_group.idToggled.connect(self._on_gantt_mode_toggled)
        mode_label = QLabel("显示模式:")
        mode_label.setProperty("class", "subtext")
        gantt_mode_bar.addWidget(mode_label)
        gantt_mode_bar.addWidget(self._gantt_mode_planned)
        gantt_mode_bar.addWidget(self._gantt_mode_actual)
        gantt_mode_bar.addStretch()
        tab_gantt_layout.addLayout(gantt_mode_bar)
        self._gantt = _GanttWidget()
        self._gantt.setProperty("class", "bg-base")
        self._gantt.task_moved.connect(self.task_moved.emit)
        self._gantt_scroll = QScrollArea()
        self._gantt_scroll.setWidget(self._gantt)
        self._gantt_scroll.setWidgetResizable(True)
        self._gantt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gantt_scroll.setProperty("class", "scroll-base")
        self._gantt.bind_scroll_area(self._gantt_scroll)
        tab_gantt_layout.addWidget(self._gantt_scroll)
        self._sub_stacked.addWidget(tab_gantt)
        self._sub_tabs.addSegment("甘特图", tab_gantt)

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

        # 日期范围过滤（预计结束日期）
        today = date.today()
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
                    end_day = (t.start_day or 0) + t.duration
                    end_date = plan_start + timedelta(days=end_day - 1)
                    if d_from and end_date < d_from:
                        continue
                    if d_to and end_date > d_to:
                        continue
                    date_filtered.append(t)
                filtered = date_filtered
        self._task_table.set_tasks(
            filtered, self._last_technician_map, self._last_result_map,
            start_date=self._last_start_date,
            task_prefix=self._last_task_prefix,
        )
        self._gantt.set_tasks(filtered, start_date=self._last_start_date,
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
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_to.setDate(self._date_to.maximumDate())
        # _on_task_search 由控件信号自动触发

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
        self._on_task_search(self._search_edit.text())
        self._gantt.set_tasks(tasks, total_days, start_date,
                              equipment_map=equipment_map,
                              technician_map=technician_map,
                              task_prefix=task_prefix,
                              holidays=holidays)
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
            end_day = (task.start_day or 0) + task.duration
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

    def _update_stats(self, tasks: list[TestTask]) -> None:
        """更新任务统计：总数/完成/未完成/超期。"""
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        pending = total - completed
        # 超期
        from datetime import date
        today = date.today()
        overdue = 0
        for t in tasks:
            if t.status in ("completed", "done", "skipped", "failed"):
                continue
            # 超期判断基于预计结束日期
            if t.start_day is not None:
                from datetime import timedelta
                from src.models.test_plan import TestTask as _TT
                # 用计划开始日期推算
                plan_start = None
                if self._last_start_date:
                    try:
                        plan_start = date.fromisoformat(self._last_start_date)
                    except ValueError:
                        pass
                if plan_start:
                    end = plan_start + timedelta(days=t.start_day + t.duration - 1)
                    if end < today:
                        overdue += 1

        parts = [f"共 {total} 个任务"]
        has_stats = pending > 0 or completed > 0 or overdue > 0
        if pending > 0:
            parts.append(f"待完成 {pending}")
        if completed > 0:
            parts.append(f"已完成 {completed}")
        if overdue > 0:
            parts.append(f'<span style="color:{_t.RED}">{overdue} 个超期</span>')
        # 合并到摘要栏
        summary = self._summary_bar.text() if self._summary_bar.text() else ""
        if has_stats:
            sep = "  ·  " if summary else ""
            self._summary_bar.setText(summary + sep + "  |  ".join(parts))

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