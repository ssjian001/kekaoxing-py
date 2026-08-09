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
from src.constants import TASK_STATUS_LABELS, PRIORITY_LABELS, TASK_CATEGORIES
from src.styles.column_persistence import (
    save_column_widths_debounced, restore_column_widths,
    save_sort_state, restore_sort_state,
)
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician


def _make_focus_out_filter(widget, on_focus_out):
    """创建焦点离开事件过滤器 — 就地编辑器失去焦点时触发提交。

    editingFinished 信号在部分焦点路径（如点击表格另一单元格）下不触发，
    用 eventFilter 拦截 FocusOut 事件作为兜底。返回的 filter 挂在 widget 上。
    """
    from PySide6.QtCore import QObject, QEvent

    class _FocusOutFilter(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.FocusOut:
                # 焦点转移到 combo popup 时不算真正离开
                if hasattr(event, "reason") and event.reason() == Qt.FocusReason.PopupFocusReason:
                    return False
                on_focus_out()
            return False

    filt = _FocusOutFilter(widget)
    widget.installEventFilter(filt)
    return filt


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
        self._empty_label = QLabel()
        self._empty_label.setTextFormat(Qt.TextFormat.RichText)
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

        # 名稱(1) / 類別(2) / 天數(3) — 就地編輯（無彈窗）
        if col == 1:
            self._edit_inline_name(row, task)
            return
        if col == 2:
            self._edit_inline_category(row, task)
            return
        if col == 3:
            self._edit_inline_duration(row, task)
            return
        # 进度(6) / 优先级(7) — 就地编辑（无弹窗）
        if col == 6:
            self._edit_inline_progress(row, task)
            return
        if col == 7:
            self._edit_inline_priority(row, task)
            return
        # 狀態(8) / 技術員(9) — 就地編輯
        if col == 8:
            self._edit_inline_status(row, task)
            return
        if col == 9:
            self._edit_inline_technician(row, task)
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
            # 兼容历史数据 "fail" → 统一为 "failed"
            _status_key = "failed" if task.status == "fail" else task.status
            status_text = self._STATUS_LABELS.get(_status_key, task.status)
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
                # 超期标记：预计开始(col4) 和 预计结束(col5) 文字标红 + 天数
                if is_overdue and planned_end_date is not None:
                    overdue_days = (today - planned_end_date).days
                    if col in (4, 5):
                        item.setForeground(QColor(_t.RED))
                        if col == 5:
                            item.setToolTip(f"已超期 {overdue_days} 天（预计结束: {planned_end_str}）")
                            if planned_end_str != "—":
                                item.setText(f"{planned_end_str}  超期{overdue_days}d")
                # 状态颜色 (col 8) — 兼容历史 "fail"
                if col == 8:
                    _color_key = "failed" if task.status == "fail" else task.status
                    item.setForeground(QColor(self._STATUS_COLORS.get(_color_key, _t.TEXT)))
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
            # 行背景：超期红 / 未指派技术员橘黄
            if task.status not in ("completed", "done"):
                row_bg = None
                if is_overdue and planned_end_date is not None:
                    bg_c = QColor(_t.RED)
                    bg_c.setAlpha(25)
                    row_bg = bg_c
                elif not task.technician_id:
                    bg_c = QColor(_t.YELLOW)
                    bg_c.setAlpha(35)
                    row_bg = bg_c
                if row_bg:
                    for c in range(self.columnCount()):
                        cell = self.item(row, c)
                        if cell:
                            cell.setBackground(row_bg)
        self.setSortingEnabled(True)
        self._update_empty_state()
        # 恢复列宽 & 排序状态（仅在首次数据加载后）
        restore_column_widths(self, self._persistence_key)
        restore_sort_state(self, self._persistence_key)

    def _update_empty_state(self) -> None:
        """控制空状态提示的显示/隐藏。"""
        if self.rowCount() == 0:
            self._empty_label.setText(
                '<div style="text-align:center;padding:32px;">'
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" '
                f'stroke="{_t.OVERLAY0}" stroke-width="1.5">'
                '<path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>'
                '<polyline points="13 2 13 9 20 9"/>'
                '</svg><br/>'
                f'<span style="color:{_t.OVERLAY0};font-size:14px;">暂无测试任务</span>'
                '</div>'
            )
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

    def _show_context_menu(self, pos: QPoint) -> None:
        """表格右键上下文菜单。"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        item = self.itemAt(pos)
        if not item:
            return

        row = item.row()
        task = self.get_task_at_row(row)
        if not task:
            return

        menu = QMenu(self)
        
        act_edit = menu.addAction("✏️ 编辑任务信息")
        
        menu.addSeparator()

        sub_status = menu.addMenu("🏷️ 快速修改状态")
        act_p = sub_status.addAction("进行中 (in_progress)")
        act_f = sub_status.addAction("已完成 (completed)")
        act_w = sub_status.addAction("待处理 (pending)")
        act_fail = sub_status.addAction("失败 (failed)")

        menu.addSeparator()
        act_del = menu.addAction("🗑️ 删除该任务")

        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == act_edit and self._on_edit_callback:
            self._on_edit_callback(task)
        elif action == act_del and self._on_delete_callback:
            self._on_delete_callback(task)
        elif action in (act_p, act_f, act_w, act_fail):
            status_map = {act_p: "in_progress", act_f: "completed", act_w: "pending", act_fail: "failed"}
            new_st = status_map[action]
            if self._on_status_advance_callback:
                self._on_status_advance_callback(task, new_st)

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

    def get_selected_task_ids(self) -> list[int]:
        """获取当前选中行的任务 ID 列表（排序安全）。"""
        ids: list[int] = []
        for idx in self.selectionModel().selectedRows():
            t = self.get_task_at_row(idx.row())
            if t and t.id is not None:
                ids.append(t.id)
        return ids

    # ── 批量编辑 ────────────────────────────────────────────

    def _edit_inline_progress(self, row: int, task: TestTask) -> None:
        """双击进度列 — 显示 QDoubleSpinBox 就地编辑。"""
        from PySide6.QtWidgets import QDoubleSpinBox
        from PySide6.QtCore import QTimer

        spin = QDoubleSpinBox()
        spin.setRange(0, 100)
        spin.setDecimals(0)
        spin.setSuffix("%")
        spin.setValue(task.progress)
        spin.selectAll()
        self.setCellWidget(row, 6, spin)
        spin.setFocus()

        def _commit() -> None:
            new_val = spin.value()
            # 用批量更新回調直接寫 DB（col=6 → progress），不要走 edit_callback 否則會彈完整編輯對話框
            if new_val != task.progress and self._batch_value_callback and task.id is not None:
                self._batch_value_callback([task.id], 6, str(int(new_val)))

        spin.editingFinished.connect(lambda: self._finish_inline_edit(spin, row, 6, task.id, _commit))
        spin.installEventFilter(_make_focus_out_filter(spin, lambda: self._finish_inline_edit(spin, row, 6, task.id, _commit)))
        QTimer.singleShot(50, spin.selectAll)

    def _edit_inline_priority(self, row: int, task: TestTask) -> None:
        """双击优先级列 — 显示下拉框就地编辑。"""
        from PySide6.QtWidgets import QComboBox
        from src.constants import PRIORITY_LABELS

        combo = QComboBox()
        combo.setProperty("class", "filter-combo")
        items = [(PRIORITY_LABELS.get(i, str(i)), i) for i in range(1, 6)]
        combo.addItems([label for label, _ in items])
        combo.setCurrentIndex(task.priority - 1)
        self.setCellWidget(row, 7, combo)
        combo.setFocus()
        combo.showPopup()

        def _commit() -> None:
            new_pri = items[combo.currentIndex()][1]
            if new_pri != task.priority and self._batch_value_callback and task.id is not None:
                # col=7 → priority，走批量更新回調直接寫 DB
                self._batch_value_callback([task.id], 7, str(new_pri))

        # activated 在用户选当前项时也触发（currentIndexChanged 不触发）；focusOut 兜底放弃选择
        combo.activated.connect(lambda _: self._finish_inline_edit(combo, row, 7, task.id, _commit))
        combo.installEventFilter(_make_focus_out_filter(combo, lambda: self._finish_inline_edit(combo, row, 7, task.id, _commit)))

    def _finish_inline_edit(self, widget, row: int, col: int, task_id: int | None,
                            commit: Callable[[], None]) -> None:
        """统一结束就地编辑：先提交数据，再延迟销毁控件。

        用 QTimer.singleShot(0, ...) 把 removeCellWidget 推到下一轮事件循环，
        避免在信号回调（currentIndexChanged/activated/editingFinished）中
        同步销毁正在处理事件的控件导致 popup 残留或焦点异常。
        commit 用闭包捕获各自逻辑，仅调用一次（防重入）。
        """
        if getattr(widget, "_inline_committed", False):
            return  # 防重入：editingFinished + focusOut 可能同时触发
        widget._inline_committed = True
        try:
            commit()
        finally:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.removeCellWidget(row, col))
            QTimer.singleShot(60, lambda: self.flash_row(task_id, 500) if task_id is not None else None)

    def _edit_inline_name(self, row: int, task: TestTask) -> None:
        """双击名称列 — 显示 QLineEdit 就地编辑。"""
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtCore import QEvent

        edit = QLineEdit(task.name)
        edit.selectAll()
        edit.setProperty("class", "cell-edit")
        self.setCellWidget(row, 1, edit)
        edit.setFocus()

        def _commit() -> None:
            new_val = edit.text().strip()
            if new_val and new_val != task.name and self._batch_value_callback and task.id is not None:
                self._batch_value_callback([task.id], 1, new_val)

        edit.editingFinished.connect(lambda: self._finish_inline_edit(edit, row, 1, task.id, _commit))
        edit.returnPressed.connect(lambda: self._finish_inline_edit(edit, row, 1, task.id, _commit))
        # focusOut 保险：editingFinished 在某些焦点路径下不触发
        edit.installEventFilter(_make_focus_out_filter(edit, lambda: self._finish_inline_edit(edit, row, 1, task.id, _commit)))

    def _edit_inline_category(self, row: int, task: TestTask) -> None:
        """双击类别列 — 显示下拉框就地编辑。"""
        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        combo.setProperty("class", "filter-combo")
        combo.addItems(TASK_CATEGORIES)
        idx = combo.findText(task.category) if task.category else 0
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.setCellWidget(row, 2, combo)
        combo.setFocus()
        combo.showPopup()
        initial_idx = combo.currentIndex()

        def _commit() -> None:
            if combo.currentIndex() == initial_idx:
                return  # 用户未改动，仅关闭编辑器
            new_cat = combo.currentText()
            if new_cat != task.category and self._batch_value_callback and task.id is not None:
                self._batch_value_callback([task.id], 2, new_cat)

        # activated 在用户选当前项时也触发（currentIndexChanged 不触发）；focusOut 兜底放弃选择
        combo.activated.connect(lambda _: self._finish_inline_edit(combo, row, 2, task.id, _commit))
        combo.installEventFilter(_make_focus_out_filter(combo, lambda: self._finish_inline_edit(combo, row, 2, task.id, _commit)))

    def _edit_inline_duration(self, row: int, task: TestTask) -> None:
        """双击天数列 — 显示 QSpinBox 就地编辑。"""
        from PySide6.QtWidgets import QSpinBox

        spin = QSpinBox()
        spin.setRange(1, 99)
        spin.setValue(max(1, task.duration))
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.selectAll()
        self.setCellWidget(row, 3, spin)
        spin.setFocus()

        def _commit() -> None:
            new_dur = spin.value()
            if new_dur != task.duration and self._batch_value_callback and task.id is not None:
                self._batch_value_callback([task.id], 3, str(new_dur))

        spin.editingFinished.connect(lambda: self._finish_inline_edit(spin, row, 3, task.id, _commit))
        spin.installEventFilter(_make_focus_out_filter(spin, lambda: self._finish_inline_edit(spin, row, 3, task.id, _commit)))

    def _edit_inline_status(self, row: int, task: TestTask) -> None:
        """双击状态列 — 显示下拉框就地编辑。"""
        from PySide6.QtWidgets import QComboBox
        from src.constants import TASK_STATUS_LABELS

        combo = QComboBox()
        combo.setProperty("class", "filter-combo")
        status_items = [(label, key) for key, label in TASK_STATUS_LABELS.items()]
        combo.addItems([label for label, _ in status_items])
        # 定位當前狀態（兼容历史数据 "fail" → 统一为 "failed"）
        for i, (_, key) in enumerate(status_items):
            if key == task.status or (task.status == "fail" and key == "failed"):
                combo.setCurrentIndex(i)
                break
        self.setCellWidget(row, 8, combo)
        combo.setFocus()
        combo.showPopup()
        initial_idx = combo.currentIndex()

        def _commit() -> None:
            if combo.currentIndex() == initial_idx:
                return  # 用户未改动，仅关闭编辑器
            new_status = status_items[combo.currentIndex()][1]
            if new_status != task.status and self._batch_value_callback and task.id is not None:
                self._batch_value_callback([task.id], 8, new_status)

        combo.activated.connect(lambda _: self._finish_inline_edit(combo, row, 8, task.id, _commit))
        combo.installEventFilter(_make_focus_out_filter(combo, lambda: self._finish_inline_edit(combo, row, 8, task.id, _commit)))

    def _edit_inline_technician(self, row: int, task: TestTask) -> None:
        """双击技术员列 — 显示下拉框就地编辑。"""
        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        combo.setProperty("class", "filter-combo")
        # 选项：未指派 + 已注入的技术员列表
        combo.addItem("— 未指派 —", None)
        for tech in self._technician_list:
            combo.addItem(tech.name if hasattr(tech, "name") else str(tech),
                          tech.id if hasattr(tech, "id") else None)
        # 定位當前
        if task.technician_id:
            for i in range(combo.count()):
                if combo.itemData(i) == task.technician_id:
                    combo.setCurrentIndex(i)
                    break
        self.setCellWidget(row, 9, combo)
        combo.setFocus()
        combo.showPopup()
        initial_idx = combo.currentIndex()

        def _commit() -> None:
            if combo.currentIndex() == initial_idx:
                return  # 用户未改动，仅关闭编辑器
            idx_ = combo.currentIndex()
            tech_id = combo.itemData(idx_)
            if self._batch_value_callback and task.id is not None:
                if tech_id is None:
                    self._batch_value_callback([task.id], 9, "")
                else:
                    tech_name = combo.itemText(idx_)
                    if tech_name != "— 未指派 —":
                        self._batch_value_callback([task.id], 9, tech_name)

        combo.activated.connect(lambda _: self._finish_inline_edit(combo, row, 9, task.id, _commit))
        combo.installEventFilter(_make_focus_out_filter(combo, lambda: self._finish_inline_edit(combo, row, 9, task.id, _commit)))

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
        from PySide6.QtGui import QBrush, QColor
        # 用透明 brush 清除背景，不能用 QColor()（無效顏色）
        # 否則暗色主題下行底色變黑（Qt 回退到系統 Base 角色）
        for col in range(self.columnCount()):
            cell = self.item(row, col)
            if cell:
                cell.setBackground(QBrush(Qt.GlobalColor.transparent))