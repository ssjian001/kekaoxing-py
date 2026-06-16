"""增强列表视图 — BugListView + FilterPanel + 批量操作 + Aging 列。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.issue import Issue
from src.services.issue_service import IssueService
from src.styles.column_persistence import save_column_widths_debounced, restore_column_widths
from src.styles.constants import (
    ISSUE_SEVERITY_COLORS,
    ISSUE_STATUS_COLORS,
    PRIORITY_COLORS,
    PADDING_SMALL,
    PADDING_MEDIUM,
    PADDING_LARGE,
    SPACING_MEDIUM,
    VIEW_MARGINS,
    apply_column_specs,
    install_copy_handler,
)
from src.styles.toast import ToastWidget
from src.constants import ISSUE_STATUS_LABELS, SEVERITY_LABELS, PRIORITY_LABELS
from src.views.bug_tracker.detail_dialog import IssueDetailDialog

# ── Aging 色块阈值 ──────────────────────────────────────────────
_AGING_THRESHOLD_LOW = 3      # <3 天 → 绿色
_AGING_THRESHOLD_MID = 7      # 3-7 天 → 黄色, >7 天 → 红色


def _aging_color(days: int) -> str:
    """返回 Aging 天数对应的颜色。"""
    if days < _AGING_THRESHOLD_LOW:
        return _t.GREEN
    elif days <= _AGING_THRESHOLD_MID:
        return _t.YELLOW
    return _t.RED


# ── 列规格 ─────────────────────────────────────────────────────
_BUG_TABLE_SPECS = [
    ("", "fixed", 32),           # checkbox 列
    ("ID", "fixed", 50),
    ("标题", "interactive", 200),
    ("严重度", "interactive", 70),
    ("状态", "interactive", 80),
    ("优先级", "interactive", 60),
    ("指派人", "interactive", 80),
    ("Aging", "interactive", 70),
    ("创建时间", "interactive", 100),
    ("任务", "interactive", 80),
    ("样品", "interactive", 80),
]


# ═══════════════════════════════════════════════════════════════
#  _BugTable
# ═══════════════════════════════════════════════════════════════

class _BugTable(QTableWidget):
    """Bug 列表表格 — checkbox 列 + 排序 + 列宽持久化 + Aging 色块。"""

    card_double_clicked = Signal(int)  # issue_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_column_specs(self, _BUG_TABLE_SPECS, "bug_list_table")
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self._issues: list[Issue] = []
        self._issue_service: IssueService | None = None
        # checkbox 列不参与排序
        self.horizontalHeader().setSortIndicatorShown(True)

        # 信号
        self.doubleClicked.connect(self._on_double_click)

        # 列宽持久化已在 apply_column_specs 中通过 table_key 注册
        # 额外监听 checkbox 列宽变化
        self.horizontalHeader().sectionResized.connect(self._on_section_resized)

    def set_issue_service(self, service: IssueService) -> None:
        """注入 IssueService（用于 aging 计算）。"""
        self._issue_service = service

    def set_issues(self, issues: list[Issue]) -> None:
        """填充或刷新表格数据。"""
        self._issues = issues
        self.setSortingEnabled(False)
        self.setRowCount(len(issues))

        for row, issue in enumerate(issues):
            # Checkbox 列（col 0）
            chk_item = QTableWidgetItem()
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, issue.id)
            chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 0, chk_item)

            # 数据列（col 1+）
            for col, val in enumerate([
                issue.id,
                issue.title,
                SEVERITY_LABELS.get(issue.severity, issue.severity),
                ISSUE_STATUS_LABELS.get(issue.status, issue.status),
                PRIORITY_LABELS.get(issue.priority, f"P{issue.priority}"),
                getattr(issue, "dri_name", "") or "",
                "",  # Aging — 单独处理
                (issue.created_at or "")[:10],
                str(issue.task_id or ""),
                str(issue.sample_id or ""),
            ], start=1):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, issue.id)
                # 着色
                if col == 3:  # 严重度
                    item.setForeground(QColor(ISSUE_SEVERITY_COLORS.get(issue.severity, _t.TEXT)))
                elif col == 4:  # 状态
                    item.setForeground(QColor(ISSUE_STATUS_COLORS.get(issue.status, _t.TEXT)))
                elif col == 5:  # 优先级
                    item.setForeground(QColor(PRIORITY_COLORS.get(issue.priority, _t.TEXT)))
                self.setItem(row, col, item)

            # Aging 列（col 7）— 带色块 + 天数
            aging_days = self._get_aging_days(issue.id)
            aging_text = f"{aging_days}天" if aging_days >= 0 else "-"
            aging_item = QTableWidgetItem(aging_text)
            aging_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            aging_item.setData(Qt.ItemDataRole.UserRole, issue.id)
            color = _aging_color(aging_days) if aging_days >= 0 else _t.SUBTEXT0
            aging_item.setForeground(QColor(color))
            aging_item.setToolTip(f"当前状态停留 {aging_days} 天")
            self.setItem(row, 7, aging_item)

        self.setSortingEnabled(True)

    def _get_aging_days(self, issue_id: int) -> int:
        """通过 IssueService 获取 aging 天数。"""
        if self._issue_service is not None:
            try:
                return self._issue_service.get_aging_days(issue_id)
            except Exception:
                return 0
        return 0

    def _get_issue_id_at_row(self, row: int) -> Optional[int]:
        """通过 UserRole 安全获取 issue ID（排序安全）。"""
        if 0 <= row < self.rowCount():
            item = self.item(row, 0)
            if item is not None:
                uid = item.data(Qt.ItemDataRole.UserRole)
                if uid is not None:
                    return int(uid)
        return None

    def get_selected_issue_id(self) -> Optional[int]:
        return self._get_issue_id_at_row(self.currentRow())

    def get_checked_ids(self) -> list[int]:
        """获取已勾选的 issue ID 列表。"""
        ids: list[int] = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                uid = item.data(Qt.ItemDataRole.UserRole)
                if uid is not None:
                    ids.append(int(uid))
        return ids

    def select_all(self, checked: bool = True) -> None:
        """全选/取消全选。"""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item:
                item.setCheckState(state)

    def get_issue_by_id(self, issue_id: int) -> Optional[Issue]:
        """通过 ID 查找 Issue 对象。"""
        for issue in self._issues:
            if issue.id == issue_id:
                return issue
        return None

    def _on_double_click(self) -> None:
        """双击行 — 发射 card_double_clicked 信号。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is not None:
            self.card_double_clicked.emit(issue_id)

    def _on_section_resized(self, index: int, old_size: int, new_size: int) -> None:
        """列宽变化时持久化（仅 Interactive 列）。"""
        save_column_widths_debounced(self, "bug_list_table")


# ═══════════════════════════════════════════════════════════════
#  FilterPanel
# ═══════════════════════════════════════════════════════════════

class FilterPanel(QFrame):
    """可折叠的筛选面板 — 状态/严重度/优先级/指派人/日期范围。"""

    filter_changed = Signal(dict)  # filters: dict

    # 筛选选项
    STATUS_OPTIONS = [
        ("open", "待处理"),
        ("analyzing", "分析中"),
        ("verified", "已验证"),
        ("closed", "已关闭"),
    ]
    SEVERITY_OPTIONS = [
        ("critical", "严重"),
        ("major", "主要"),
        ("minor", "次要"),
        ("cosmetic", "外观"),
    ]
    PRIORITY_OPTIONS = [(f"P{i}", f"P{i}") for i in range(1, 6)]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "filter-panel")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM)
        layout.setSpacing(SPACING_MEDIUM)

        # 标题
        title = QLabel("筛选条件")
        title.setProperty("class", "panel-header")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        form = QVBoxLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        # ── 状态 ──
        form.addWidget(QLabel("状态"))
        self._status_checks: dict[str, QCheckBox] = {}
        status_group = QVBoxLayout()
        status_group.setSpacing(2)
        for eng, chn in self.STATUS_OPTIONS:
            cb = QCheckBox(chn)
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[eng] = cb
            status_group.addWidget(cb)
        form.addLayout(status_group)

        # ── 严重度 ──
        form.addWidget(QLabel("严重度"))
        self._severity_checks: dict[str, QCheckBox] = {}
        sev_group = QVBoxLayout()
        sev_group.setSpacing(2)
        for eng, chn in self.SEVERITY_OPTIONS:
            cb = QCheckBox(chn)
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filter)
            self._severity_checks[eng] = cb
            sev_group.addWidget(cb)
        form.addLayout(sev_group)

        # ── 优先级 ──
        form.addWidget(QLabel("优先级"))
        self._priority_checks: dict[str, QCheckBox] = {}
        pri_group = QVBoxLayout()
        pri_group.setSpacing(2)
        for eng, chn in self.PRIORITY_OPTIONS:
            cb = QCheckBox(chn)
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filter)
            self._priority_checks[eng] = cb
            pri_group.addWidget(cb)
        form.addLayout(pri_group)

        # ── 指派人 ──
        form.addWidget(QLabel("指派人"))
        self._assignee_combo = QComboBox()
        self._assignee_combo.addItem("全部")
        self._assignee_combo.currentIndexChanged.connect(self._emit_filter)
        form.addWidget(self._assignee_combo)

        # ── 创建日期范围 ──
        form.addWidget(QLabel("创建日期"))
        date_range = QHBoxLayout()
        self._date_start = QDateEdit()
        self._date_start.setCalendarPopup(True)
        self._date_start.setDate(QDate.currentDate().addMonths(-1))
        self._date_start.setSpecialValueText("不限")
        self._date_start.dateChanged.connect(self._emit_filter)
        date_range.addWidget(self._date_start)

        self._date_end = QDateEdit()
        self._date_end.setCalendarPopup(True)
        self._date_end.setDate(QDate.currentDate())
        self._date_end.setSpecialValueText("不限")
        self._date_end.dateChanged.connect(self._emit_filter)
        date_range.addWidget(self._date_end)
        form.addLayout(date_range)

        # ── 清空按钮 ──
        btn_clear = QPushButton("清空筛选")
        btn_clear.setProperty("class", "action")
        btn_clear.clicked.connect(self._clear_filters)
        form.addWidget(btn_clear)

        form.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

    def set_assignee_options(self, names: list[str]) -> None:
        """设置指派人下拉选项（由父视图注入）。"""
        current = self._assignee_combo.currentText()
        self._assignee_combo.clear()
        self._assignee_combo.addItem("全部")
        for name in names:
            if name:
                self._assignee_combo.addItem(name)
        idx = self._assignee_combo.findText(current)
        if idx >= 0:
            self._assignee_combo.setCurrentIndex(idx)

    def get_filters(self) -> dict:
        """获取当前筛选条件。"""
        return {
            "status": [
                eng for eng, cb in self._status_checks.items()
                if cb.isChecked()
            ],
            "severity": [
                eng for eng, cb in self._severity_checks.items()
                if cb.isChecked()
            ],
            "priority": [
                int(eng[1:]) for eng, cb in self._priority_checks.items()
                if cb.isChecked()
            ],
            "assignee": self._assignee_combo.currentText(),
            "date_start": self._date_start.date().toString("yyyy-MM-dd")
                if self._date_start.date() != self._date_start.minimumDate() else "",
            "date_end": self._date_end.date().toString("yyyy-MM-dd")
                if self._date_end.date() != self._date_end.minimumDate() else "",
        }

    def set_filters(self, filters: dict) -> None:
        """从外部设置筛选条件（跨视图同步）。"""
        status_list = filters.get("status", [])
        for eng, cb in self._status_checks.items():
            cb.setChecked(eng in status_list)

        sev_list = filters.get("severity", [])
        for eng, cb in self._severity_checks.items():
            cb.setChecked(eng in sev_list)

        pri_list = filters.get("priority", [])
        for eng, cb in self._priority_checks.items():
            pri_label = int(eng[1:])
            cb.setChecked(pri_label in pri_list)

        assignee = filters.get("assignee", "全部")
        idx = self._assignee_combo.findText(assignee)
        if idx >= 0:
            self._assignee_combo.setCurrentIndex(idx)

        date_start = filters.get("date_start", "")
        if date_start:
            parsed = QDate.fromString(date_start, "yyyy-MM-dd")
            if parsed.isValid():
                self._date_start.setDate(parsed)

        date_end = filters.get("date_end", "")
        if date_end:
            parsed = QDate.fromString(date_end, "yyyy-MM-dd")
            if parsed.isValid():
                self._date_end.setDate(parsed)

    def _emit_filter(self) -> None:
        """发射筛选变更信号。"""
        self.filter_changed.emit(self.get_filters())

    def _clear_filters(self) -> None:
        """重置所有筛选条件为全选/不限。"""
        for cb in self._status_checks.values():
            cb.setChecked(True)
        for cb in self._severity_checks.values():
            cb.setChecked(True)
        for cb in self._priority_checks.values():
            cb.setChecked(True)
        self._assignee_combo.setCurrentIndex(0)
        self._date_start.setDate(QDate.currentDate().addMonths(-1))
        self._date_end.setDate(QDate.currentDate())
        self._emit_filter()


# ═══════════════════════════════════════════════════════════════
#  BatchOperationDialog
# ═══════════════════════════════════════════════════════════════

class BatchOperationDialog(QDialog):
    """批量操作对话框 — 改状态/改严重度/改优先级/指派。"""

    def __init__(
        self,
        issue_ids: list[int],
        issue_service: IssueService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._issue_ids = issue_ids
        self._service = issue_service

        self.setWindowTitle(f"批量操作 — 已选 {len(issue_ids)} 个 Issue")
        self.setMinimumSize(400, 300)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._result_summary: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE)
        layout.setSpacing(SPACING_MEDIUM)

        # 已选列表
        layout.addWidget(QLabel(f"已选 {len(self._issue_ids)} 个 Issue:"))
        id_list = QListWidget()
        id_list.setMaximumHeight(120)
        for iid in self._issue_ids[:20]:
            item = QListWidgetItem(f"#{iid}")
            id_list.addItem(item)
        if len(self._issue_ids) > 20:
            id_list.addItem(f"... 还有 {len(self._issue_ids) - 20} 个")
        layout.addWidget(id_list)

        # 操作类型
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("操作:"))
        self._op_combo = QComboBox()
        self._op_combo.addItems(["改状态", "改严重度", "改优先级", "指派"])
        self._op_combo.currentTextChanged.connect(self._update_value_widget)
        op_row.addWidget(self._op_combo, stretch=1)
        layout.addLayout(op_row)

        # 目标值
        val_row = QHBoxLayout()
        val_row.addWidget(QLabel("目标值:"))
        self._value_combo = QComboBox()
        self._value_combo.setMinimumWidth(140)
        val_row.addWidget(self._value_combo, stretch=1)
        layout.addLayout(val_row)
        self._update_value_widget(self._op_combo.currentText())

        # 按钮
        btn_box = QDialogButtonBox()
        btn_cancel = btn_box.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        btn_cancel.clicked.connect(self.reject)
        self._btn_confirm = btn_box.addButton("确认执行", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_confirm.clicked.connect(self._execute_batch)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _update_value_widget(self, operation: str) -> None:
        """根据操作类型更新目标值下拉选项。"""
        self._value_combo.clear()
        if operation == "改状态":
            for eng, chn in [("open", "待处理"), ("analyzing", "分析中"),
                             ("verified", "已验证"), ("closed", "已关闭")]:
                self._value_combo.addItem(chn, eng)
        elif operation == "改严重度":
            for eng, chn in [("critical", "严重"), ("major", "主要"),
                             ("minor", "次要"), ("cosmetic", "外观")]:
                self._value_combo.addItem(chn, eng)
        elif operation == "改优先级":
            for i in range(1, 6):
                self._value_combo.addItem(f"P{i}", i)
        elif operation == "指派":
            self._value_combo.setEditable(True)
            self._value_combo.setPlaceholderText("输入指派人 ID")

    def _execute_batch(self) -> None:
        """执行批量操作，逐个 issue 调用 update()。"""
        operation = self._op_combo.currentText()
        target_value = self._value_combo.currentData()
        if target_value is None and self._value_combo.isEditable():
            try:
                target_value = int(self._value_combo.currentText())
            except (ValueError, TypeError):
                ToastWidget.show_toast(self, "请输入有效的指派人 ID", ToastWidget.ERROR)
                return

        # 映射操作 → kwargs field
        field_map = {
            "改状态": "status",
            "改严重度": "severity",
            "改优先级": "priority",
            "指派": "assignee_id",
        }
        field = field_map.get(operation, "")
        if not field:
            return

        updated = 0
        failed = 0
        for issue_id in self._issue_ids:
            try:
                self._service.update(issue_id, operator="batch", **{field: target_value})
                updated += 1
            except Exception:
                failed += 1

        self._result_summary = f"已更新 {updated} 条，失败 {failed} 条"
        ToastWidget.show_toast(self.parent(), self._result_summary,
                               ToastWidget.SUCCESS if failed == 0 else ToastWidget.WARNING)
        self.accept()

    def result_summary(self) -> str:
        return self._result_summary


# ═══════════════════════════════════════════════════════════════
#  BugListView
# ═══════════════════════════════════════════════════════════════

class BugListView(QWidget):
    """增强列表视图 — 筛选面板 + 表格 + 批量操作 + Aging 列。"""

    # ── 信号 ──
    card_double_clicked = Signal(int)     # Issue ID
    refresh_requested = Signal()          # 父视图刷新
    filter_changed = Signal(dict)         # 与其他视图共享筛选

    def __init__(
        self,
        issue_service: IssueService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._service = issue_service
        self._all_issues: list[Issue] = []
        self._technician_names: list[str] = []
        self._filter_visible = True

        self._setup_ui()
        self._connect_signals()

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)
        layout.setSpacing(SPACING_MEDIUM)

        # 1. 顶部工具栏
        layout.addLayout(self._build_toolbar())

        # 2. 主区域 (QSplitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setProperty("class", "list-splitter")

        # 左: 筛选面板
        self._filter_panel = FilterPanel()
        splitter.addWidget(self._filter_panel)

        # 右: 表格
        self._table = _BugTable()
        self._table.set_issue_service(self._service)
        splitter.addWidget(self._table)

        # 初始比例
        splitter.setSizes([220, 800])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self._splitter = splitter

        layout.addWidget(splitter, stretch=1)

        # 空状态提示
        self._empty_label = QLabel("暂无 Issue 数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "empty-label")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(SPACING_MEDIUM)

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索标题/描述/根因")
        self._search_input.setMinimumWidth(200)
        self._search_input.textChanged.connect(self._apply_filters)
        toolbar.addWidget(self._search_input)

        # 筛选切换按钮
        self._btn_filter = QPushButton("筛选")
        self._btn_filter.setProperty("class", "action")
        self._btn_filter.setCheckable(True)
        self._btn_filter.setChecked(True)
        self._btn_filter.clicked.connect(self._toggle_filter_panel)
        toolbar.addWidget(self._btn_filter)

        # 全选/取消全选
        self._btn_select_all = QPushButton("全选")
        self._btn_select_all.setProperty("class", "action")
        self._btn_select_all.setCheckable(True)
        self._btn_select_all.clicked.connect(self._on_select_all)
        toolbar.addWidget(self._btn_select_all)

        # 批量操作按钮
        self._btn_batch_status = QPushButton("批量改状态")
        self._btn_batch_status.setProperty("class", "action")
        self._btn_batch_status.setEnabled(False)
        self._btn_batch_status.clicked.connect(lambda: self._open_batch_dialog("改状态"))
        toolbar.addWidget(self._btn_batch_status)

        self._btn_batch_assign = QPushButton("批量指派")
        self._btn_batch_assign.setProperty("class", "action")
        self._btn_batch_assign.setEnabled(False)
        self._btn_batch_assign.clicked.connect(lambda: self._open_batch_dialog("指派"))
        toolbar.addWidget(self._btn_batch_assign)

        # 刷新按钮
        btn_refresh = QPushButton("刷新")
        btn_refresh.setProperty("class", "action")
        btn_refresh.clicked.connect(self.refresh_requested.emit)
        toolbar.addWidget(btn_refresh)

        toolbar.addStretch()

        # 统计标签
        self._stats_label = QLabel("0 个 Issue")
        self._stats_label.setProperty("class", "subtext")
        toolbar.addWidget(self._stats_label)

        return toolbar

    # ── 信号连接 ──────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._filter_panel.filter_changed.connect(self._apply_filters)
        self._table.card_double_clicked.connect(self._on_card_double_click)
        self._table.itemChanged.connect(self._on_table_item_changed)

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        """checkbox 状态变化时更新批量按钮状态。"""
        if item.column() == 0:
            has_checked = bool(self._table.get_checked_ids())
            self._btn_batch_status.setEnabled(has_checked)
            self._btn_batch_assign.setEnabled(has_checked)

    def _on_select_all(self, checked: bool) -> None:
        """全选/取消全选。"""
        self._table.select_all(checked)
        text = "取消全选" if checked else "全选"
        self._btn_select_all.setText(text)
        has_checked = bool(self._table.get_checked_ids()) if not checked else True
        self._btn_batch_status.setEnabled(has_checked)
        self._btn_batch_assign.setEnabled(has_checked)

    def _toggle_filter_panel(self) -> None:
        """展开/收起左侧筛选面板。"""
        self._filter_visible = self._btn_filter.isChecked()
        self._filter_panel.setVisible(self._filter_visible)
        # 调整 splitter 大小
        if self._filter_visible:
            sizes = self._splitter.sizes()
            sizes[0] = 220
            sizes[1] = max(sizes[1] - 220, 400)
            self._splitter.setSizes(sizes)
        else:
            sizes = self._splitter.sizes()
            sizes[1] = sizes[0] + sizes[1]
            sizes[0] = 0
            self._splitter.setSizes(sizes)

    # ── 数据 ──────────────────────────────────────────────────

    def set_issues(self, issues: list[Issue]) -> None:
        """设置 Issue 列表（全量缓存，筛选后显示）。"""
        self._all_issues = issues
        self._apply_filters()

    def refresh(self) -> None:
        """从 IssueService 重新加载所有 Issue。"""
        issues = self._service.list_all() if self._service else []
        self.set_issues(issues)

    def set_technician_names(self, names: list[str]) -> None:
        """设置指派人名称列表。"""
        self._technician_names = names
        self._filter_panel.set_assignee_options(names)

    def set_filters(self, filters: dict) -> None:
        """外部设置筛选条件（跨视图同步）。"""
        self._filter_panel.set_filters(filters)
        self._apply_filters()

    def _apply_filters(self) -> None:
        """根据筛选条件过滤并刷新表格。"""
        filters = self._filter_panel.get_filters()
        keyword = self._search_input.text().strip().lower()

        # 发射筛选信号（供其他视图同步）
        self.filter_changed.emit(filters)

        filtered = []
        for issue in self._all_issues:
            # 搜索
            if keyword:
                search_text = f"{issue.title} {issue.description} {issue.root_cause}".lower()
                if keyword not in search_text:
                    continue

            # 状态
            if filters["status"] and issue.status not in filters["status"]:
                continue

            # 严重度
            if filters["severity"] and issue.severity not in filters["severity"]:
                continue

            # 优先级
            if filters["priority"] and issue.priority not in filters["priority"]:
                continue

            # 指派人
            assignee_filter = filters["assignee"]
            if assignee_filter and assignee_filter != "全部":
                dri = getattr(issue, "dri_name", "") or ""
                if dri != assignee_filter:
                    continue

            # 创建日期范围
            date_start = filters.get("date_start", "")
            date_end = filters.get("date_end", "")
            created = (issue.created_at or "")[:10]
            if date_start and created < date_start:
                continue
            if date_end and created > date_end:
                continue

            filtered.append(issue)

        self._table.set_issues(filtered)
        self._stats_label.setText(f"{len(filtered)} 个 Issue")

        # 空状态提示
        self._empty_label.setVisible(len(filtered) == 0)

    def _on_card_double_click(self, issue_id: int) -> None:
        """双击打开详情弹窗。"""
        from src.views.bug_tracker.detail_dialog import IssueDetailDialog

        issue = self._table.get_issue_by_id(issue_id)
        if not issue:
            return
        # 先发射信号（父视图可能拦截）
        self.card_double_clicked.emit(issue_id)

        dialog = IssueDetailDialog(issue, self._service, self)
        dialog.exec()

    # ── 批量操作 ──────────────────────────────────────────────

    def _open_batch_dialog(self, default_op: str) -> None:
        """打开批量操作对话框。"""
        ids = self._table.get_checked_ids()
        if not ids:
            ToastWidget.show_toast(self, "请先勾选 Issue", ToastWidget.WARNING)
            return

        dialog = BatchOperationDialog(ids, self._service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            summary = dialog.result_summary()
            if summary:
                ToastWidget.show_toast(self, summary, ToastWidget.SUCCESS)
            # 刷新表格
            self._apply_filters()

    # ── 刷新主题 ──────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """主题切换回调 — 未内联颜色的控件无需刷新。"""
        # 表格通过 QSS 自动刷新
        # 筛选面板通过 QSS 自动刷新
        pass
