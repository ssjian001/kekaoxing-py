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
    QDateEdit,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QColor, QKeySequence

import src.styles.theme as _t
from src.styles.constants import TASK_STATUS_COLORS, PRIORITY_COLORS, FONT_FAMILY, apply_column_specs
from src.constants import TASK_STATUS_LABELS, PRIORITY_LABELS
from src.styles.column_persistence import (
    save_column_widths_debounced, restore_column_widths,
    save_sort_state, restore_sort_state,
)
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician

# 任务表列规格
_TASK_SPECS = [
    ("序号", "interactive", 70),
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

    _SHORTCUT_KEYS = {
        "edit": Qt.Key.Key_E,
        "delete": Qt.Key.Key_Delete,
        "start": Qt.Key.Key_S,
        "complete": Qt.Key.Key_F,
        "record": Qt.Key.Key_R,
    }

    _COL_BATCHABLE = {6: "progress", 7: "priority", 11: "actual_start_date", 12: "actual_end_date"}

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_column_specs(self, _TASK_SPECS, "task_table")
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
        self._on_actual_date_edit_callback: Callable[[int, str, str], None] | None = None  # (task_id, field, new_date)
        self._on_record_result_callback: Callable[[], None] | None = None
        self._batch_value_callback: Callable[[list[int], int, str], None] | None = None  # (task_ids, col, value)
        # 双击编辑
        self.cellDoubleClicked.connect(self._on_double_click)
        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        # 空状态提示
        self._empty_label = QLabel("暂无测试任务")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "empty-label")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self)
        self._empty_label.hide()
        self.viewport().installEventFilter(self)
        self._register_shortcuts()

        # 列宽 & 排序持久化
        self._persistence_key = "task_table"
        self.horizontalHeader().sectionResized.connect(
            lambda: save_column_widths_debounced(self, self._persistence_key)
        )
        self.horizontalHeader().sortIndicatorChanged.connect(
            lambda col, order: save_sort_state(self, self._persistence_key)
        )

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
        on_actual_date_edit: Callable[[int, str, str], None] | None = None,
        on_record_result: Callable[[], None] | None = None,
        on_batch_value: Callable[[list[int], int, str], None] | None = None,
    ) -> None:
        """设置编辑/删除/状态推进/实际日期编辑/录入结果回调。"""
        self._on_edit_callback = on_edit
        self._on_delete_callback = on_delete
        self._on_status_advance_callback = on_status_advance
        self._on_actual_date_edit_callback = on_actual_date_edit
        self._on_record_result_callback = on_record_result
        self._batch_value_callback = on_batch_value

    # ── 键盘快捷键（Widget 内生效） ──

    def _register_shortcuts(self) -> None:
        """注册表格内键盘快捷键（仅在表格有焦点时响应）。"""
        from PySide6.QtGui import QShortcut, QKeySequence
        from PySide6.QtCore import QCoreApplication as _QA

        # E = 编辑选中行
        self._sc_edit = QShortcut(QKeySequence(Qt.Key.Key_E), self)
        self._sc_edit.activated.connect(lambda: self._shortcut_trigger("edit"))
        # Delete = 删除选中行
        self._sc_del = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self._sc_del.activated.connect(lambda: self._shortcut_trigger("delete"))
        # S = 开始执行 / F = 标记完成
        self._sc_start = QShortcut(QKeySequence(Qt.Key.Key_S), self)
        self._sc_start.activated.connect(lambda: self._shortcut_trigger("start"))
        self._sc_comp = QShortcut(QKeySequence(Qt.Key.Key_F), self)
        self._sc_comp.activated.connect(lambda: self._shortcut_trigger("complete"))
        # R = 录入结果
        self._sc_rec = QShortcut(QKeySequence(Qt.Key.Key_R), self)
        self._sc_rec.activated.connect(lambda: self._shortcut_trigger("record"))

    def _shortcut_trigger(self, action: str) -> None:
        """键盘快捷键触发 → 对当前选中行执行对应操作。"""
        rows = self.selectionModel().selectedRows()
        if not rows:
            return
        # 取当前行首个任务
        row = rows[0].row()
        task = self.get_task_at_row(row)
        if not task:
            return
        if action == "edit" and self._on_edit_callback:
            self._on_edit_callback(task)
        elif action == "delete" and self._on_delete_callback:
            self._on_delete_callback(task)
        elif action == "start" and task.status == "pending" and self._on_status_advance_callback:
            self._on_status_advance_callback(task, "in_progress")
        elif action == "complete" and task.status == "in_progress" and self._on_status_advance_callback:
            self._on_status_advance_callback(task, "completed")
        elif action == "record" and task.status in ("in_progress", "completed", "failed") and self._on_record_result_callback:
            self._on_record_result_callback()

    def _on_double_click(self, row: int, col: int) -> None:
        task = self.get_task_at_row(row)
        if not task or task.id is None:
            return

        # 实际开始(11) / 实际完成(12) — 弹出日历快捷编辑
        if col in (11, 12) and self._on_actual_date_edit_callback:
            field = "actual_start_date" if col == 11 else "actual_end_date"
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
            from PySide6.QtCore import QDate
            dlg = QDialog(self)
            dlg.setWindowTitle("选择日期")
            dlg.setMinimumWidth(280)
            layout = QVBoxLayout(dlg)
            date_edit_type = QDateEdit()
            date_edit_type.setCalendarPopup(True)
            date_edit_type.setDisplayFormat("yyyy-MM-dd")
            date_edit_type.setSpecialValueText("清除日期")
            # 初始化为当前值或空
            current = getattr(task, field, "") or ""
            if current:
                qd = QDate.fromString(current, "yyyy-MM-dd")
                if qd.isValid():
                    date_edit_type.setDate(qd)
                else:
                    date_edit_type.setDate(QDate.currentDate())
                    date_edit_type.setSpecialValueText(" ")
            else:
                date_edit_type.clear()
            layout.addWidget(date_edit_type)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            layout.addWidget(buttons)
            if dlg.exec():
                new_date = date_edit_type.date().toString("yyyy-MM-dd") if date_edit_type.date().isValid() else ""
                self._on_actual_date_edit_callback(task.id, field, new_date)
            return

        # Original: open full edit dialog
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
            act_edit = QAction("编辑\tE", self)
            act_edit.triggered.connect(lambda: self._on_edit_callback(task) if self._on_edit_callback else None)
            act_delete = QAction("删除\tDel", self)
            act_delete.triggered.connect(lambda: self._on_delete_callback(task) if self._on_delete_callback else None)

            act_start: QAction | None = None
            act_complete: QAction | None = None
            act_record: QAction | None = None
            if task.status == "pending":
                act_start = QAction("开始执行\tS", self)
                act_start.triggered.connect(
                    lambda: self._on_status_advance_callback(task, "in_progress")
                    if self._on_status_advance_callback else None
                )
            elif task.status == "in_progress":
                act_complete = QAction("标记完成\tF", self)
                act_complete.triggered.connect(
                    lambda: self._on_status_advance_callback(task, "completed")
                    if self._on_status_advance_callback else None
                )
            # 进行中/已完成/失败的任务都可直接录入结果
            if task.status in ("in_progress", "completed", "failed") and self._on_record_result_callback:
                act_record = QAction("录入测试结果\tR", self)
                act_record.triggered.connect(
                    lambda: self._on_record_result_callback()
                )

            menu.addAction(act_edit)
            menu.addAction(act_delete)
            if act_start or act_complete or act_record:
                menu.addSeparator()
            if act_start:
                menu.addAction(act_start)
            if act_complete:
                menu.addAction(act_complete)
            if act_record:
                menu.addAction(act_record)
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
            menu.addSeparator()

            # 批量设置优先级
            act_batch_pri = QAction("批量设优先级…", self)
            act_batch_pri.triggered.connect(
                lambda: self._batch_set_field(selected_tasks, "priority")
            )
            menu.addAction(act_batch_pri)

            # 批量指派技术员
            act_batch_tech = QAction("批量指派技术员…", self)
            act_batch_tech.triggered.connect(
                lambda: self._batch_assign_technician(selected_tasks)
            )
            menu.addAction(act_batch_tech)
        
        menu.exec(self.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def _batch_set_field(self, tasks: list[TestTask], field: str) -> None:
        """批量设置选中任务的数字字段（如优先级）。"""
        if not self._batch_value_callback:
            return
        from PySide6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getInt(self, f"批量设{field}", f"请输入{field}值:", 3, 1, 5)
        if not ok:
            return
        for t in tasks:
            if t.id is not None:
                self._batch_value_callback([t.id], 7 if field == "priority" else -1, str(val))

    def _batch_assign_technician(self, tasks: list[TestTask]) -> None:
        """批量指派技术员。"""
        if not self._technician_list or not self._batch_value_callback:
            return
        from PySide6.QtWidgets import QInputDialog
        # 直接用技术员名称作为值，handler 通过 name 查找 id
        tech_names = [t.name for t in self._technician_list]
        val, ok = QInputDialog.getItem(self, "批量指派技术员", "选择技术员:", tech_names, 0, False)
        if not ok or not val:
            return
        for t in tasks:
            if t.id is not None:
                self._batch_value_callback([t.id], 9, val)

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
        today = date.today()
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
            planned_start_str: str = ""
            planned_end_str: str = ""
            planned_end_date: date | None = None
            if plan_start and task.start_day is not None:
                planned_start_date = plan_start + timedelta(days=task.start_day)
                planned_end_date = plan_start + timedelta(days=task.start_day + task.duration - 1)
                planned_start_str = planned_start_date.isoformat()
                planned_end_str = planned_end_date.isoformat()
            else:
                planned_start_str = str(task.start_day) if task.start_day else "—"
                planned_end_str = "—"
            # 判断是否超期：未完成且预计结束日期 < 今天
            is_overdue = (
                task.status not in ("completed", "done")
                and planned_end_date is not None
                and planned_end_date < today
            )
            values = [
                f"{task_prefix}-{row + 1:03d}" if task_prefix else (task.id or (row + 1)),
                task.name,
                task.category,
                task.duration,
                planned_start_str,
                planned_end_str,
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
                # 超期标记：预计开始(col4) 和 预计结束(col5) 文字标红
                if is_overdue and col in (4, 5):
                    item.setForeground(QColor(_t.RED))
                    if col == 5:
                        item.setToolTip(f"已超期（预计结束: {planned_end_str}）")
                # 状态颜色 (col 8)
                if col == 8:
                    item.setForeground(QColor(self._STATUS_COLORS.get(task.status, _t.TEXT)))
                # 优先级颜色 (col 7)
                elif col == 7:
                    item.setForeground(QColor(self._PRIORITY_COLORS.get(task.priority, _t.TEXT)))
                # 通过率着色 (col 10)
                elif col == 10 and total > 0:
                    if pass_count == total:
                        item.setForeground(QColor(_t.GREEN))
                    elif pass_count == 0:
                        item.setForeground(QColor(_t.RED))
                self.setItem(row, col, item)
        self.setSortingEnabled(True)
        self._update_empty_state()
        # 恢复列宽 & 排序状态（仅在首次数据加载后）
        restore_column_widths(self, self._persistence_key)
        restore_sort_state(self, self._persistence_key)

    def _update_empty_state(self) -> None:
        """控制空状态提示的显示/隐藏。"""
        if self.rowCount() == 0:
            self._empty_label.setGeometry(self.viewport().rect())
            self._empty_label.show()
            self._empty_label.raise_()
        else:
            self._empty_label.hide()

    def eventFilter(self, obj, event):
        """viewport resize 时同步空状态标签位置。"""
        if obj is self.viewport() and event.type() == event.Type.Resize:
            if self._empty_label.isVisible():
                self._empty_label.setGeometry(self.viewport().rect())
        return super().eventFilter(obj, event)

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

    # ── 批量编辑 ────────────────────────────────────────────

    def keyPressEvent(self, event: object) -> None:
        """拦截 Ctrl+V 进行批量粘贴，其余走默认。"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtWidgets import QApplication

        ev = event
        if isinstance(ev, QKeyEvent):
            mods = ev.modifiers()
            if ev.key() == Qt.Key.Key_V and mods == Qt.KeyboardModifier.ControlModifier:
                self._on_batch_paste()
                return
        super().keyPressEvent(ev)

    def _on_batch_paste(self) -> None:
        """从粘贴板获取内容，解析后批量应用到所有选中行。"""
        from PySide6.QtWidgets import QApplication

        rows = self.selectionModel().selectedRows()
        if not rows or not self._batch_value_callback:
            return

        # 获取焦点列（当前选中行的当前列）
        current = self.currentIndex()
        col = current.column()
        if col < 0:
            return

        # 获取旧值作 undo 参考
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            return

        # 收集选中行所有 task_id
        task_ids: list[int] = []
        for idx in rows:
            item = self.item(idx.row(), 0)
            if item:
                tid = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(tid, int):
                    task_ids.append(tid)

        if not task_ids:
            return

        # 按行数或全部应用同一个值
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if len(lines) >= 2:
            # 多行：逐行对应
            for i, idx in enumerate(rows):
                if i >= len(lines):
                    break
                item = self.item(idx.row(), 0)
                if item:
                    tid = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(tid, int):
                        self._batch_value_callback([tid], col, lines[i])
        else:
            # 单值：应用到所有选中行
            self._batch_value_callback(task_ids, col, text)

    def flash_row(self, task_id: int, duration_ms: int = 800) -> None:
        """闪烁指定任务所在行 — 用于撤销后视觉反馈。"""
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == task_id:
                from PySide6.QtCore import QTimer, QPropertyAnimation
                from PySide6.QtGui import QColor
                orig_bg = QColor(_t.SURFACE2)
                flash = QColor(_t.YELLOW)
                flash.setAlpha(120)
                for col in range(self.columnCount()):
                    cell = self.item(row, col)
                    if cell:
                        cell.setBackground(flash)
                QTimer.singleShot(duration_ms, lambda r=row: self._unflash_row(r))
                break

    def _unflash_row(self, row: int) -> None:
        """移除指定行的闪烁背景。"""
        for col in range(self.columnCount()):
            cell = self.item(row, col)
            if cell:
                cell.setBackground(QColor())  # 清除自定义背景