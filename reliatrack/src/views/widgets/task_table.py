"""测试计划视图 — 任务列表表格组件。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QHeaderView,
    QMenu,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QColor

from src.styles.theme import (
    MANTLE, BASE, SURFACE0, SURFACE1,
    TEXT, OVERLAY0,
    GREEN, RED, PEACH,
)
from src.styles.constants import TABLE_QSS, TASK_STATUS_COLORS, PRIORITY_COLORS, FONT_FAMILY, apply_column_specs
from src.constants import TASK_STATUS_LABELS, PRIORITY_LABELS
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician

# 任务表列规格
_TASK_SPECS = [
    ("#", "fixed", 40),
    ("名称", "interactive", 200),
    ("类别", "interactive", 80),
    ("天数", "interactive", 60),
    ("预计开始", "interactive", 100),
    ("预计结束", "interactive", 100),
    ("进度", "interactive", 60),
    ("优先级", "interactive", 60),
    ("状态", "interactive", 80),
    ("技术员", "interactive", 80),
    ("通过率", "interactive", 70),
    ("实际开始", "interactive", 100),
    ("实际完成", "interactive", 100),
]

class _TaskTable(QTableWidget):
    """测试任务列表表格。"""

    _STATUS_LABELS: dict[str, str] = TASK_STATUS_LABELS  # type: ignore[assignment]
    _STATUS_COLORS: dict[str, str] = TASK_STATUS_COLORS
    _PRIORITY_COLORS: dict[int, str] = PRIORITY_COLORS

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_column_specs(self, _TASK_SPECS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
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
        # 空状态提示
        self._empty_label = QLabel("暂无测试任务")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 14px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self)
        self._empty_label.hide()

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
        rows = self.selectionModel().selectedRows()
        if not rows:
            return
        
        menu = QMenu(self)
        
        if len(rows) == 1:
            # 单选 — 保持原有菜单
            task = self.get_task_at_row(rows[0].row())
            if not task:
                return
            act_edit = QAction("编辑", self)
            act_edit.triggered.connect(lambda: self._on_edit_callback(task) if self._on_edit_callback else None)
            act_delete = QAction("删除", self)
            act_delete.triggered.connect(lambda: self._on_delete_callback(task) if self._on_delete_callback else None)

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
        else:
            # 多选 — 批量操作
            selected_tasks = []
            for idx in rows:
                t = self.get_task_at_row(idx.row())
                if t:
                    selected_tasks.append(t)
            
            act_batch_start = QAction(f"批量开始执行 ({len(selected_tasks)} 项)", self)
            act_batch_start.triggered.connect(
                lambda: self._batch_status_advance(selected_tasks, "in_progress")
            )
            act_batch_complete = QAction(f"批量标记完成 ({len(selected_tasks)} 项)", self)
            act_batch_complete.triggered.connect(
                lambda: self._batch_status_advance(selected_tasks, "completed")
            )
            menu.addAction(act_batch_start)
            menu.addAction(act_batch_complete)
        
        menu.exec(self.viewport().mapToGlobal(pos))

    def _batch_status_advance(self, tasks: list[TestTask], new_status: str) -> None:
        """批量推进多个任务的状态。"""
        if not self._on_status_advance_callback:
            return
        for task in tasks:
            if (new_status == "in_progress" and task.status == "pending") or \
               (new_status == "completed" and task.status == "in_progress"):
                self._on_status_advance_callback(task, new_status)

    def set_tasks(
        self,
        tasks: list[TestTask],
        technician_map: dict[int, str] | None = None,
        result_map: dict[int, tuple[int, int]] | None = None,
        start_date: str = "",
        task_prefix: str = "",
    ) -> None:
        from datetime import date, timedelta
        self._tasks = tasks
        tech_map = technician_map or {}
        res_map = result_map or {}
        # 解析计划开始日期
        plan_start: date | None = None
        if start_date:
            try:
                plan_start = date.fromisoformat(start_date)
            except ValueError:
                plan_start = None
        self.setSortingEnabled(False)
        self.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            # 列: #, 名称, 类别, 天数, 预计开始, 预计结束, 进度, 优先级, 状态, 技术员, 通过率, 实际开始, 实际完成
            status_text = self._STATUS_LABELS.get(task.status, task.status)
            priority_text = PRIORITY_LABELS.get(task.priority, str(task.priority))
            tech_name = tech_map.get(task.technician_id, "") if task.technician_id else ""
            pass_count, total = res_map.get(task.id, (0, 0)) if task.id else (0, 0)
            rate_text = f"{pass_count}/{total}" if total > 0 else "—"
            # 计算预计日期
            if plan_start and task.start_day is not None:
                planned_start = (plan_start + timedelta(days=task.start_day)).isoformat()
                planned_end = (plan_start + timedelta(days=task.start_day + task.duration - 1)).isoformat()
            else:
                planned_start = str(task.start_day) if task.start_day else "—"
                planned_end = "—"
            values = [
                f"{task_prefix}-{row + 1:03d}" if task_prefix else (task.id or (row + 1)),
                task.name,
                task.category,
                task.duration,
                planned_start,
                planned_end,
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
                # 序号列存储 task.id 到 UserRole，排序后可通过 ID 定位
                if col == 0 and task.id is not None:
                    item.setData(Qt.ItemDataRole.UserRole, task.id)
                # 名称列 tooltip (col 1)
                if col == 1 and task.name:
                    item.setToolTip(task.name)
                # 状态颜色 (col 8)
                if col == 8:
                    item.setForeground(QColor(self._STATUS_COLORS.get(task.status, TEXT)))
                # 优先级颜色 (col 7)
                elif col == 7:
                    item.setForeground(QColor(self._PRIORITY_COLORS.get(task.priority, TEXT)))
                # 通过率着色 (col 10)
                elif col == 10 and total > 0:
                    if pass_count == total:
                        item.setForeground(QColor(GREEN))
                    elif pass_count == 0:
                        item.setForeground(QColor(RED))
                self.setItem(row, col, item)
        self.setSortingEnabled(True)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        """控制空状态提示的显示/隐藏。"""
        if self.rowCount() == 0:
            self._empty_label.setGeometry(self.viewport().rect())
            self._empty_label.show()
            self._empty_label.raise_()
        else:
            self._empty_label.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._empty_label.isVisible():
            self._empty_label.setGeometry(self.viewport().rect())

    def get_task_at_row(self, row: int) -> Optional[TestTask]:
        """获取指定视觉行对应的任务对象（排序安全）。"""
        item = self.item(row, 0)
        if item is None:
            return None
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id is not None:
            for t in self._tasks:
                if t.id == task_id:
                    return t
        # 回退：ID 未存储时用索引（如未排序的新数据）
        if 0 <= row < len(self._tasks):
            return self._tasks[row]
        return None