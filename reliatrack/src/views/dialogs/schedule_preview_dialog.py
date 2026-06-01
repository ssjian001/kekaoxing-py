"""排程预览对话框 — 展示排程前后对比、允许用户手动调整后确认或取消。

核心交互流程：
  1. 展示所有任务的排程前后 start_day 对比
  2. 用户可双击行手动编辑 start_day
  3. 冲突实时标红（依赖冲突/设备冲突）
  4. 点「确认应用」写 DB，点「取消」放弃
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.styles.constants import FONT_FAMILY, install_copy_handler
from src.models.test_plan import TestTask
from src.models.common import Equipment
from src.services.scheduler import (
    ScheduleConfig,
    build_dependency_map,
    can_place_at,
    _is_non_working,
    _iterate_work_days,
    _work_day_end,
)


# ═══════════════════════════════════════════════════════════════════
#  辅助：日期转换
# ═══════════════════════════════════════════════════════════════════

def _day_to_date(start_date: str, day_index: int) -> str:
    """将 day_index 转换为真实日期字符串。day_index 0 = start_date 当天。"""
    if not start_date or day_index <= 0:
        return "—"
    try:
        base = datetime.strptime(start_date, "%Y-%m-%d")
        return (base + timedelta(days=day_index)).strftime("%Y-%m-%d")
    except ValueError:
        return "—"


def _day_label(start_date: str, day_index: int) -> str:
    """返回 'Day N (YYYY-MM-DD)' 格式的标签。"""
    if day_index <= 0:
        return "未排"
    date_str = _day_to_date(start_date, day_index)
    return f"Day {day_index} ({date_str})"


# ═══════════════════════════════════════════════════════════════════
#  排程预览对话框
# ═══════════════════════════════════════════════════════════════════

class SchedulePreviewDialog(QDialog):
    """排程预览对话框。

    Parameters
    ----------
    preview_data : dict
        ``scheduler_service.preview_schedule()`` 的返回值。
    config : dict
        ``ScheduleConfigDialog.get_config()`` 的返回值。
    parent : QWidget
        父窗口。
    """

    # 信号：用户确认后的变更列表 [(task_id, new_start_day), ...]
    accepted_changes = Signal(list)

    # 表格列定义
    _COL_NAME = 0
    _COL_EQUIPMENT = 1
    _COL_DURATION = 2
    _COL_OLD_DATE = 3
    _COL_NEW_DATE = 4
    _COL_DELTA = 5
    _COL_CONFLICT = 6
    COLUMNS = ["任务名", "设备", "天数", "原始日期", "新日期", "变化", "冲突"]

    def __init__(
        self,
        preview_data: dict,
        config: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("排程预览")
        self.setMinimumWidth(780)
        self.setMaximumWidth(980)
        self.setMinimumHeight(500)
        self.setSizeGripEnabled(True)

        self._preview_data = preview_data
        self._config = config
        self._start_date: str = preview_data.get("start_date", "")
        self._tasks: list[TestTask] = preview_data.get("tasks", [])
        self._original_start_days: dict[int, int] = preview_data.get("original_start_days", {})
        self._report: dict = preview_data.get("report", {})
        self._equipment: list[Equipment] = preview_data.get("equipment", [])

        # 设备映射 {id: name}
        self._eq_map: dict[int, str] = {
            e.id: e.name for e in self._equipment if e.id is not None
        }

        # 用户手动锁定的任务
        self._user_locked_days: dict[int, int] = {}

        self._setup_ui()
        self._fill_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # ── 摘要区 ──
        summary = self._build_summary()
        layout.addWidget(summary)

        # ── 参数提示 ──
        params = self._build_params_label()
        layout.addWidget(params)

        # ── 预览表格 ──
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        install_copy_handler(self._table)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self._COL_NAME, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self._COL_EQUIPMENT, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self._COL_DURATION, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self._COL_OLD_DATE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self._COL_NEW_DATE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self._COL_DELTA, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self._COL_CONFLICT, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(self._COL_NAME, 180)
        self._table.setColumnWidth(self._COL_EQUIPMENT, 100)
        self._table.setColumnWidth(self._COL_DURATION, 50)
        self._table.setColumnWidth(self._COL_OLD_DATE, 140)
        self._table.setColumnWidth(self._COL_NEW_DATE, 140)
        self._table.setColumnWidth(self._COL_DELTA, 70)
        self._table.setColumnWidth(self._COL_CONFLICT, 120)

        self._table.setMinimumHeight(250)
        # 双击编辑
        self._table.cellDoubleClicked.connect(self._on_cell_double_click)

        layout.addWidget(self._table, stretch=1)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_reschedule = QPushButton("重新排程")
        self._btn_reschedule.setProperty("class", "action")
        self._btn_reschedule.setFixedWidth(100)
        self._btn_reschedule.clicked.connect(self._on_reschedule)
        btn_layout.addWidget(self._btn_reschedule)

        btn_layout.addStretch()

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setProperty("class", "action")
        self._btn_cancel.setFixedWidth(80)
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_apply = QPushButton("确认应用")
        self._btn_apply.setProperty("class", "primary")
        self._btn_apply.setFixedWidth(100)
        self._btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._btn_apply)

        layout.addLayout(btn_layout)

    def _build_summary(self) -> QWidget:
        """构建摘要卡片区（合并原 ScheduleReportDialog 的内容）。"""
        report = self._report
        total_days = report.get("total_days", 0)
        original_days = report.get("original_days", 0)
        improvement = report.get("improvement", 0.0)
        task_count = report.get("task_count", 0)
        updated_count = report.get("updated_count", 0)

        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        cards = [
            ("总工期", f"{total_days} 天", _t.BLUE),
            ("优化率", f"{improvement:+.0f}%", _t.GREEN if improvement >= 0 else _t.RED),
            ("任务数", f"{task_count}", _t.MAUVE),
            ("已调整", f"{updated_count}", _t.PEACH),
        ]
        for label, value, color in cards:
            card = QFrame()
            card.setProperty("class", "stat-card")
            card.setStyleSheet(f"border-left: 3px solid {color};")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(1)
            lbl = QLabel(label)
            lbl.setProperty("class", "hint-label")
            card_layout.addWidget(lbl)
            val_lbl = QLabel(value)
            val_lbl.setProperty("class", "stat-value")
            card_layout.addWidget(val_lbl)
            row.addWidget(card)

        return widget

    def _build_params_label(self) -> QLabel:
        """构建排程参数提示行。"""
        parts = []
        if self._config.get("skip_weekends"):
            parts.append("跳过周末")
        if self._config.get("skip_holidays"):
            parts.append("跳过节假日")
        if self._config.get("lock_existing"):
            parts.append("锁定已有排期")
        deadline = self._config.get("deadline", "")
        if deadline:
            parts.append(f"截止 {deadline}")
        text = " | ".join(parts) if parts else "无特殊参数"
        lbl = QLabel(text)
        lbl.setProperty("class", "hint-label")
        return lbl

    # ── 填充表格 ──

    def _fill_table(self) -> None:
        """根据当前 tasks 数据填充表格。"""
        self._table.setRowCount(len(self._tasks))

        for row, task in enumerate(self._tasks):
            task_id = task.id

            # 任务名
            name_item = QTableWidgetItem(task.name)
            name_item.setData(Qt.ItemDataRole.UserRole, task_id)
            if task.status == "completed":
                name_item.setForeground(QColor(_t.OVERLAY0))
            self._table.setItem(row, self._COL_NAME, name_item)

            # 设备
            eq_name = self._eq_map.get(task.equipment_id, "—") if task.equipment_id else "—"
            eq_item = QTableWidgetItem(eq_name)
            self._table.setItem(row, self._COL_EQUIPMENT, eq_item)

            # 持续天数
            dur_item = QTableWidgetItem(str(task.duration))
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self._COL_DURATION, dur_item)

            # 原始日期
            old_day = self._original_start_days.get(task_id, 0)
            old_item = QTableWidgetItem(_day_label(self._start_date, old_day))
            self._table.setItem(row, self._COL_OLD_DATE, old_item)

            # 新日期
            new_day = task.start_day
            new_item = QTableWidgetItem(_day_label(self._start_date, new_day))
            self._table.setItem(row, self._COL_NEW_DATE, new_item)

            # 变化
            delta = new_day - old_day if old_day > 0 and new_day > 0 else 0
            delta_text = f"{delta:+d}天" if delta != 0 else "—"
            delta_item = QTableWidgetItem(delta_text)
            delta_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if delta < 0:
                delta_item.setForeground(QColor(_t.GREEN))
            elif delta > 0:
                delta_item.setForeground(QColor(_t.RED))
            self._table.setItem(row, self._COL_DELTA, delta_item)

            # 冲突状态
            conflict_item = QTableWidgetItem("无冲突")
            conflict_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            conflict_item.setForeground(QColor(_t.GREEN))
            self._table.setItem(row, self._COL_CONFLICT, conflict_item)

            # 已完成任务灰色
            if task.status == "completed":
                for col in range(len(self.COLUMNS)):
                    item = self._table.item(row, col)
                    if item:
                        item.setForeground(QColor(_t.OVERLAY0))
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

        # 延迟检测冲突
        self._detect_conflicts()

    # ── 冲突检测 ──

    def _detect_conflicts(self) -> None:
        """检查所有任务的依赖、设备、非工作日和启动上限冲突，更新冲突列。"""
        # 构建依赖图
        dep_map = build_dependency_map(self._tasks)
        id_to_task = {t.id: t for t in self._tasks if t.id is not None}

        # 构建 timeline（简化：只检测设备重叠）
        # day_index → {eq_id: count}
        timeline: dict[int, dict[int, int]] = {}
        _holidays: set[str] = self._config.get("holidays", set())
        _skip_holidays: bool = self._config.get("skip_holidays", True)
        _skip_weekends: bool = self._config.get("skip_weekends", True)
        _daily_limit: int = self._config.get("daily_start_limit", 0)
        # 构建 starts 计数（用于 daily_start_limit 检查）
        starts: dict[int, int] = {}
        for task in self._tasks:
            if task.status == "completed" or task.start_day <= 0:
                continue
            starts[task.start_day] = starts.get(task.start_day, 0) + 1
            if task.equipment_id is None:
                continue
            days = _iterate_work_days(
                task.start_day, task.duration,
                _skip_weekends,
                self._start_date,
                _skip_holidays,
                _holidays,
            )
            for d in days:
                if d not in timeline:
                    timeline[d] = {}
                eq_id = task.equipment_id
                timeline[d][eq_id] = timeline[d].get(eq_id, 0) + 1

        for row, task in enumerate(self._tasks):
            if task.status == "completed" or task.start_day <= 0:
                continue

            has_dep_conflict = False
            has_eq_conflict = False
            has_non_working = False
            has_start_limit = False

            # 检查非工作日
            if _is_non_working(task.start_day, self._start_date,
                               _skip_weekends, _skip_holidays, _holidays):
                has_non_working = True

            # 检查每日启动上限
            if _daily_limit > 0 and starts.get(task.start_day, 0) > _daily_limit:
                has_start_limit = True

            # 检查依赖冲突
            for dep_id in dep_map.get(task.id or 0, []):
                dep_task = id_to_task.get(dep_id)
                if dep_task and dep_task.status != "completed" and dep_task.start_day > 0:
                    dep_end = _work_day_end(
                        dep_task.start_day, dep_task.duration,
                        _skip_weekends,
                        self._start_date,
                        _skip_holidays,
                        _holidays,
                    )
                    if task.start_day < dep_end:
                        has_dep_conflict = True
                        break

            # 检查设备冲突
            if task.equipment_id is not None:
                eq_id = task.equipment_id
                days = _iterate_work_days(
                    task.start_day, task.duration,
                    _skip_weekends,
                    self._start_date,
                    _skip_holidays,
                    _holidays,
                )
                for d in days:
                    usage = timeline.get(d, {}).get(eq_id, 0)
                    if usage > 1:
                        has_eq_conflict = True
                        break

            # 更新冲突列（按严重程度排序）
            conflict_item = self._table.item(row, self._COL_CONFLICT)
            if conflict_item:
                if has_dep_conflict:
                    conflict_item.setText("! 依赖冲突")
                    conflict_item.setForeground(QColor(_t.RED))
                elif has_eq_conflict:
                    conflict_item.setText("! 设备冲突")
                    conflict_item.setForeground(QColor(_t.YELLOW))
                elif has_non_working:
                    conflict_item.setText("! 非工作日")
                    conflict_item.setForeground(QColor(_t.PEACH))
                elif has_start_limit:
                    conflict_item.setText("! 启动数超限")
                    conflict_item.setForeground(QColor(_t.YELLOW))
                else:
                    conflict_item.setText("无冲突")
                    conflict_item.setForeground(QColor(_t.GREEN))

    # ── 用户交互 ──

    def _on_cell_double_click(self, row: int, col: int) -> None:
        """双击任务行弹出手动编辑 start_day 的小对话框。"""
        task = self._tasks[row] if row < len(self._tasks) else None
        if not task or task.status == "completed":
            return

        current_day = task.start_day

        # 弹出简易输入框
        dlg = _StartDayEditDialog(task.name, current_day, self._start_date, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_day = dlg.get_start_day()
            task.start_day = new_day
            self._user_locked_days[task.id] = new_day  # type: ignore[index]
            # 更新该行
            self._update_row(row)
            self._detect_conflicts()
        dlg.deleteLater()

    def _update_row(self, row: int) -> None:
        """更新指定行的显示内容。"""
        task = self._tasks[row]
        task_id = task.id

        # 新日期
        new_item = self._table.item(row, self._COL_NEW_DATE)
        if new_item:
            new_item.setText(_day_label(self._start_date, task.start_day))

        # 变化
        old_day = self._original_start_days.get(task_id, 0)
        delta = task.start_day - old_day if old_day > 0 and task.start_day > 0 else 0
        delta_item = self._table.item(row, self._COL_DELTA)
        if delta_item:
            delta_text = f"{delta:+d}天" if delta != 0 else "—"
            delta_item.setText(delta_text)
            if delta < 0:
                delta_item.setForeground(QColor(_t.GREEN))
            elif delta > 0:
                delta_item.setForeground(QColor(_t.RED))

    def _on_reschedule(self) -> None:
        """基于用户手动调整重新排程（发出信号请求外部重跑）。"""
        # 把用户锁定传入，请求外部重新排程
        self.done(2)  # 2 = 重新排程

    def get_user_locked_days(self) -> dict[int, int]:
        """返回用户手动锁定的 {task_id: start_day}。"""
        return dict(self._user_locked_days)

    def get_changes(self) -> list[tuple[int, int]]:
        """返回所有变化的 [(task_id, new_start_day), ...]。"""
        changes: list[tuple[int, int]] = []
        for task in self._tasks:
            if task.id is None or task.status == "completed":
                continue
            old_day = self._original_start_days.get(task.id, 0)
            if task.start_day != old_day:
                changes.append((task.id, task.start_day))
        return changes

    def _on_apply(self) -> None:
        """确认应用：发出变更信号并关闭。"""
        changes = self.get_changes()
        self.accepted_changes.emit(changes)
        self.accept()


# ═══════════════════════════════════════════════════════════════════
#  简易 start_day 编辑对话框
# ═══════════════════════════════════════════════════════════════════

class _StartDayEditDialog(QDialog):
    """手动编辑单个任务 start_day 的小弹窗。"""

    def __init__(
        self,
        task_name: str,
        current_day: int,
        start_date: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"调整开始日期 — {task_name}")
        self.setMinimumWidth(320)
        self.setMaximumWidth(520)
        self.setSizeGripEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 当前值提示
        current_label = QLabel(f"当前: {_day_label(start_date, current_day)}")
        current_label.setProperty("class", "subtext")
        layout.addWidget(current_label)

        # 输入
        form = QFormLayout()
        self._spin = QSpinBox()
        self._spin.setRange(0, 365)
        self._spin.setValue(current_day)
        self._spin.setMinimumWidth(100)
        form.addRow("开始日 (Day 索引):", self._spin)

        self._date_preview = QLabel(_day_label(start_date, current_day))
        self._date_preview.setProperty("class", "highlight-blue")
        form.addRow("对应日期:", self._date_preview)

        self._spin.valueChanged.connect(
            lambda v: self._date_preview.setText(_day_label(start_date, v))
        )

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setProperty("class", "action")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton("确定")
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        self._start_date = start_date

    def get_start_day(self) -> int:
        return self._spin.value()
