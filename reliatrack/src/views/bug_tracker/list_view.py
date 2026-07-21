"""增强列表视图 — BugListView + FilterPanel + 批量操作 + Aging + FA/CAPA 内嵌面板。"""

from __future__ import annotations

from typing import Optional

import logging
logger = logging.getLogger("views.bug_tracker.list_view")
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
from src.models.issue import Issue, FARecord, CAPARecord
from src.services.issue_service import IssueService
from src.views.bug_tracker.fa_capa_panels import FAPanel, CAPAPanel, CAPADialog
from src.views.bug_tracker.batch_dialog import BatchOperationDialog
from src.views.dialogs.fa_record_dialog import FARecordDialog
from src.views.dialogs.issue_dialog import IssueEditDialog
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QToolButton, QMessageBox
from src.styles.column_persistence import save_column_widths_debounced, restore_column_widths
from src.styles.constants import (
    AGING_THRESHOLD_LOW,
    AGING_THRESHOLD_MID,
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
# ── Aging 色块阈值 ──────────────────────────────────────────────
# 使用 styles.constants 中的 AGING_THRESHOLD_LOW / AGING_THRESHOLD_MID



def _aging_color(days: int) -> str:
    """返回 Aging 天数对应的颜色。"""
    if days < AGING_THRESHOLD_LOW:
        return _t.GREEN
    elif days <= AGING_THRESHOLD_MID:
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
    ("DRI", "interactive", 80),
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
        self._technician_map: dict[int, str] = {}  # 保留供 detail_dialog 活动日志翻译（DRI 列不再使用）
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

    def set_technician_map(self, tech_map: dict[int, str]) -> None:
        """注入 assignee_id → 人名映射（指派人列渲染用）。"""
        self._technician_map = tech_map

    def set_issues(self, issues: list[Issue]) -> None:
        """填充或刷新表格数据（Fix 5: 保留选中行 + checkbox 状态）。"""
        # 保存当前选中行 ID 和已勾选 ID
        saved_selected = self.get_selected_issue_id()
        saved_checks: set = set(self.get_checked_ids())

        self._issues = issues
        self.setSortingEnabled(False)
        self.setRowCount(len(issues))

        for row, issue in enumerate(issues):
            # Checkbox 列（col 0）— 恢复勾选状态
            chk_item = QTableWidgetItem()
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            check_state = (
                Qt.CheckState.Checked if issue.id in saved_checks
                else Qt.CheckState.Unchecked
            )
            chk_item.setCheckState(check_state)
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
                issue.dri_name or "",
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

        # 恢复选中行（排序后按 ID 查找新位置）
        if saved_selected is not None:
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == saved_selected:
                    self.setCurrentCell(row, 0)
                    break

    def _get_aging_days(self, issue_id: int) -> int:
        """通过 IssueService 获取 aging 天数。"""
        if self._issue_service is not None:
            try:
                return self._issue_service.get_aging_days(issue_id)
            except Exception:
                logger.exception("_get_aging_days() failed")
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
#  BugListView
# ═══════════════════════════════════════════════════════════════

_ISSUE_FILTER_FIELDS = {
    "status": ("狀態", "enum"),
    "severity": ("嚴重度", "enum"),
    "priority": ("優先級", "int"),
    "dri_name": ("DRI", "text"),
    "title": ("標題", "text"),
}

class BugListView(QWidget):
    """增强列表视图 — 筛选面板 + 表格 + 批量操作 + Aging 列。"""

    # ── 信号 ──
    card_double_clicked = Signal(int)     # Issue ID
    refresh_requested = Signal()          # 父视图刷新
    filter_changed = Signal(dict)         # 与其他视图共享筛选
    issue_saved = Signal(dict)            # Issue 保存/更新
    issue_deleted = Signal(int)           # Issue 删除
    issue_selected = Signal(object)       # Issue 选中 (int | None)
    fa_record_added = Signal(dict)        # FA 记录添加
    fa_record_edited = Signal(dict)       # FA 记录编辑
    fa_record_deleted = Signal(int)       # FA 记录删除
    capa_record_added = Signal(dict)      # CAPA 记录添加
    capa_record_edited = Signal(dict)     # CAPA 记录编辑
    capa_record_deleted = Signal(int)     # CAPA 记录删除
    export_8d_requested = Signal(int)     # 导出 8D 报告

    def __init__(
        self,
        issue_service: IssueService,
        parent: QWidget | None = None,
        undo_manager=None,
    ):
        super().__init__(parent)
        self._service = issue_service
        self._undo_manager = undo_manager
        self._all_issues: list[Issue] = []
        self._technician_map: dict[int, str] = {}
        self._filter_visible = True
        # 上下文数据（由 refresh_handlers 注入，供 Issue/FA/CAPA 弹窗使用）
        self._project_list: list = []
        self._default_project_id: int | None = None
        self._task_list: list = []
        self._default_task_id: int | None = None
        self._sample_list: list = []
        self._default_sample_id: int | None = None
        self._knowledge_list: list = []
        self._technician_list: list = []
        # FA/CAPA 当前面板数据缓存
        self._current_fa_records: list[FARecord] = []
        self._current_capa_records: list = []

        self._setup_ui()
        self._connect_signals()

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)
        layout.setSpacing(6)

        # 1. 筛选行（放上面）
        self._build_filter_row(layout)

        # 2. 工具栏行（搜索+操作按钮放右边）
        layout.addLayout(self._build_toolbar())

        # 3. 主区域 — 水平分割：左=表格，右=FA/CAPA（垂直）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setProperty("class", "list-splitter")

        # 左: Issue 表格
        self._table = _BugTable()
        self._table.set_issue_service(self._service)
        main_splitter.addWidget(self._table)

        # 右: FA 上 / CAPA 下（垂直分割）
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # FA 面板
        fa_widget = QWidget()
        fa_layout = QVBoxLayout(fa_widget)
        fa_layout.setContentsMargins(0, 0, 0, 0)
        fa_layout.setSpacing(4)
        fa_header = QHBoxLayout()
        fa_label = QLabel("FA 失效分析")
        fa_label.setProperty("class", "panel-header")
        fa_header.addWidget(fa_label)
        fa_header.addStretch()
        self._btn_add_fa = QPushButton("新建 FA")
        self._btn_add_fa.setProperty("class", "action")
        self._btn_add_fa.setFixedHeight(24)
        self._btn_add_fa.clicked.connect(self._open_fa_dialog)
        fa_header.addWidget(self._btn_add_fa)
        fa_layout.addLayout(fa_header)
        self._fa_panel = FAPanel()
        self._fa_panel.fa_edit_requested.connect(self._open_edit_fa_dialog)
        self._fa_panel.fa_delete_requested.connect(self._delete_fa_record)
        fa_layout.addWidget(self._fa_panel, stretch=1)
        right_splitter.addWidget(fa_widget)

        # CAPA 面板
        capa_widget = QWidget()
        capa_layout = QVBoxLayout(capa_widget)
        capa_layout.setContentsMargins(0, 0, 0, 0)
        capa_layout.setSpacing(4)
        capa_header = QHBoxLayout()
        capa_label = QLabel("CAPA 纠正预防措施")
        capa_label.setProperty("class", "panel-header")
        capa_header.addWidget(capa_label)
        capa_header.addStretch()
        self._btn_add_capa = QPushButton("新建 CAPA")
        self._btn_add_capa.setProperty("class", "action")
        self._btn_add_capa.setFixedHeight(24)
        self._btn_add_capa.clicked.connect(self._open_capa_dialog)
        capa_header.addWidget(self._btn_add_capa)
        capa_layout.addLayout(capa_header)
        self._capa_panel = CAPAPanel()
        self._capa_panel.capa_edit_requested.connect(self._open_edit_capa_dialog)
        self._capa_panel.capa_delete_requested.connect(self._confirm_delete_capa)
        capa_layout.addWidget(self._capa_panel, stretch=1)
        right_splitter.addWidget(capa_widget)

        right_splitter.setSizes([250, 250])
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        main_splitter.addWidget(right_splitter)

        # 初始比例: 表格 60% : 右侧 40%
        main_splitter.setSizes([600, 400])
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)
        self._splitter = main_splitter
        self._main_splitter = main_splitter

        layout.addWidget(main_splitter, stretch=1)

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
        toolbar.setSpacing(8)

        # 搜索框（左）
        self._search_input = QLineEdit()
        self._search_input.setFixedHeight(26)
        self._search_input.setPlaceholderText("搜索标题/描述/根因")
        self._search_input.setMinimumWidth(160)
        self._search_input.setMaximumWidth(260)
        self._search_input.textChanged.connect(self._apply_filters)
        toolbar.addWidget(self._search_input)

        toolbar.addStretch()

        # 操作按钮（右）
        # 全选/取消全选
        self._btn_select_all = QPushButton("全选")
        self._btn_select_all.setProperty("class", "action")
        self._btn_select_all.setCheckable(True)
        self._btn_select_all.clicked.connect(self._on_select_all)
        toolbar.addWidget(self._btn_select_all)

        # 批量操作下拉菜單
        from PySide6.QtWidgets import QToolButton, QMenu
        self._btn_batch = QToolButton()
        self._btn_batch.setText("批量操作")
        self._btn_batch.setProperty("class", "action")
        self._btn_batch.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        batch_menu = QMenu(self._btn_batch)
        self._act_batch_status = batch_menu.addAction("批量改状态")
        self._act_batch_status.triggered.connect(lambda: self._open_batch_dialog("改状态"))
        self._act_batch_assign = batch_menu.addAction("批量设置DRI")
        self._act_batch_assign.triggered.connect(lambda: self._open_batch_dialog("设置DRI"))
        self._btn_batch.setMenu(batch_menu)
        self._btn_batch.setEnabled(False)
        toolbar.addWidget(self._btn_batch)

        # 刷新按钮
        btn_refresh = QPushButton("刷新")
        btn_refresh.setProperty("class", "action")
        btn_refresh.clicked.connect(self.refresh_requested.emit)
        toolbar.addWidget(btn_refresh)

        # 统计标签
        self._stats_label = QLabel("0 个 Issue")
        self._stats_label.setProperty("class", "subtext")
        toolbar.addWidget(self._stats_label)

        return toolbar

    def _build_filter_row(self, parent: QVBoxLayout) -> None:
        """构建固定条件筛选行（替代 DynamicFilterPanel）。"""
        from PySide6.QtWidgets import QComboBox
        from src.constants import ISSUE_STATUS_LABELS, SEVERITY_LABELS, PRIORITY_LABELS

        row = QHBoxLayout()
        row.setSpacing(6)

        # 状态筛选
        self._filter_status = QComboBox()
        self._filter_status.setProperty("class", "filter-combo")
        self._filter_status.setFixedWidth(90)
        self._filter_status.setFixedHeight(26)
        self._filter_status.addItem("全部状态", "")
        for k, v in ISSUE_STATUS_LABELS.items():
            self._filter_status.addItem(v, k)
        self._filter_status.currentIndexChanged.connect(self._apply_filters)
        row.addWidget(self._filter_status)

        # 严重度筛选
        self._filter_severity = QComboBox()
        self._filter_severity.setProperty("class", "filter-combo")
        self._filter_severity.setFixedWidth(75)
        self._filter_severity.setFixedHeight(26)
        self._filter_severity.addItem("全部严重度", "")
        for k, v in SEVERITY_LABELS.items():
            self._filter_severity.addItem(v, k)
        self._filter_severity.currentIndexChanged.connect(self._apply_filters)
        row.addWidget(self._filter_severity)

        # 优先级筛选
        self._filter_priority = QComboBox()
        self._filter_priority.setProperty("class", "filter-combo")
        self._filter_priority.setFixedWidth(70)
        self._filter_priority.setFixedHeight(26)
        self._filter_priority.addItem("全部优先级", "")
        for k, v in PRIORITY_LABELS.items():
            self._filter_priority.addItem(v, k)
        self._filter_priority.currentIndexChanged.connect(self._apply_filters)
        row.addWidget(self._filter_priority)

        # DRI 搜索输入
        self._filter_dri = QLineEdit()
        self._filter_dri.setPlaceholderText("DRI…")
        self._filter_dri.setFixedWidth(80)
        self._filter_dri.setFixedHeight(26)
        self._filter_dri.textChanged.connect(self._apply_filters)
        row.addWidget(self._filter_dri)

        # 清除筛选
        btn_clear = QPushButton("清除")
        btn_clear.setProperty("class", "action")
        btn_clear.setFixedHeight(26)
        btn_clear.clicked.connect(self._clear_filters)
        row.addWidget(btn_clear)

        row.addStretch()

        parent.addLayout(row)

    # ── 信号连接 ──────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._table.card_double_clicked.connect(self._on_card_double_click)
        self._table.itemChanged.connect(self._on_table_item_changed)
        self._table.itemSelectionChanged.connect(self._on_issue_selection_changed)

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        """checkbox 状态变化时更新批量按钮状态。"""
        if item.column() == 0:
            has_checked = bool(self._table.get_checked_ids())
            self._btn_batch.setEnabled(has_checked)

    def _on_select_all(self, checked: bool) -> None:
        """全选/取消全选。"""
        self._table.select_all(checked)
        text = "取消全选" if checked else "全选"
        self._btn_select_all.setText(text)
        has_checked = bool(self._table.get_checked_ids()) if not checked else True
        self._btn_batch.setEnabled(has_checked)

    def _clear_filters(self) -> None:
        """清除所有筛选条件。"""
        self._filter_status.setCurrentIndex(0)
        self._filter_severity.setCurrentIndex(0)
        self._filter_priority.setCurrentIndex(0)
        self._filter_dri.clear()

    # ── 数据 ──────────────────────────────────────────────────

    def set_issues(self, issues: list[Issue]) -> None:
        """设置 Issue 列表（全量缓存，筛选后显示）。"""
        self._all_issues = issues
        self._apply_filters()

    def refresh(self) -> None:
        """从 IssueService 重新加载所有 Issue。"""
        issues = self._service.list_all() if self._service else []
        self.set_issues(issues)

    def set_technician_map(self, tech_map: dict[int, str]) -> None:
        """保留供 detail_dialog 活动日志翻译（DRI 列/筛选已改用 dri_name）。"""
        self._technician_map = tech_map
        self._table.set_technician_map(tech_map)

    def set_filters(self, filters: dict) -> None:
        """外部设置筛选条件（跨视图同步）。"""
        self._apply_filters()

    def _apply_filters(self) -> None:
        """根据筛选条件过滤并刷新表格。"""
        keyword = self._search_input.text().strip().lower()

        # 读取固定筛选条件
        status_val = self._filter_status.currentData()
        severity_val = self._filter_severity.currentData()
        priority_val = self._filter_priority.currentData()
        dri_text = self._filter_dri.text().strip().lower()

        filtered = []
        for issue in self._all_issues:
            # 搜索
            if keyword:
                search_text = f"{issue.title} {issue.description} {issue.root_cause}".lower()
                if keyword not in search_text:
                    continue
            # 状态
            if status_val and issue.status != status_val:
                continue
            # 严重度
            if severity_val and issue.severity != severity_val:
                continue
            # 优先级
            if priority_val and str(issue.priority) != str(priority_val):
                continue
            # DRI
            if dri_text and dri_text not in (issue.dri_name or "").lower():
                continue

            filtered.append(issue)

        self._table.set_issues(filtered)
        self._stats_label.setText(f"{len(filtered)} 个 Issue")

        # 空状态提示
        self._empty_label.setVisible(len(filtered) == 0)

    def _on_card_double_click(self, issue_id: int) -> None:
        """双击行 — 发射信号给父视图打开详情弹窗。"""
        self.card_double_clicked.emit(issue_id)

    # ── 批量操作 ──────────────────────────────────────────────

    def _open_batch_dialog(self, default_op: str) -> None:
        """打开批量操作对话框。"""
        ids = self._table.get_checked_ids()
        if not ids:
            ToastWidget.show_toast(self, "请先勾选 Issue", ToastWidget.WARNING)
            return

        dialog = BatchOperationDialog(ids, self._service, self,
                                      undo_manager=self._undo_manager,
                                      dri_names=[i.dri_name for i in self._all_issues])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            summary = dialog.result_summary()
            if summary:
                ToastWidget.show_toast(self, summary, ToastWidget.SUCCESS)
            # 刷新表格
            self._apply_filters()

    # ── 上下文数据注入（替代 IssueView.set_context_data）──

    def set_context_data(
        self,
        *,
        projects: list | None = None,
        default_project_id: int | None = None,
        samples: list | None = None,
        knowledge: list | None = None,
        tasks: list | None = None,
        technicians: list | None = None,
    ) -> None:
        """批量设置 Issue/FA/CAPA 弹窗所需的上下文数据。"""
        if projects is not None:
            self._project_list = projects
        if default_project_id is not None:
            self._default_project_id = default_project_id
        if samples is not None:
            self._sample_list = samples
        if knowledge is not None:
            self._knowledge_list = knowledge
        if tasks is not None:
            self._task_list = tasks
        if technicians is not None:
            self._technician_list = technicians

    # ── Issue 选中 → 加载 FA/CAPA ──

    def get_selected_issue_id(self) -> Optional[int]:
        """获取当前选中 Issue ID。"""
        return self._table.get_selected_issue_id()

    def refresh_fa(self, records: list[FARecord]) -> None:
        """刷新 FA 面板。"""
        self._current_fa_records = records
        self._fa_panel.set_fa_records(records)

    def refresh_capa(self, records: list) -> None:
        """刷新 CAPA 面板。"""
        self._current_capa_records = records
        self._capa_panel.set_capa_records(records)

    def _on_issue_selection_changed(self) -> None:
        """选中 Issue 时发射信号（由 issue_handlers 接收加载 FA/CAPA）。"""
        issue_id = self.get_selected_issue_id()
        self.issue_selected.emit(issue_id)

    # ── FA 步骤弹窗 ──

    def _open_fa_dialog(self) -> None:
        """新建 FA 步骤弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在列表中选中一个 Issue。")
            return
        existing_nos = [rec.step_no for rec in self._current_fa_records]
        dlg = FARecordDialog(existing_step_nos=existing_nos,
                             technician_list=self._technician_list, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["issue_id"] = issue_id
            self.fa_record_added.emit(data)
        dlg.deleteLater()

    def _open_edit_fa_dialog(self, fa_id: int) -> None:
        """编辑 FA 步骤弹窗。"""
        record = None
        for rec in self._current_fa_records:
            if rec.id == fa_id:
                record = rec
                break
        if record is None:
            return
        existing_nos = [rec.step_no for rec in self._current_fa_records]
        dlg = FARecordDialog(existing_step_nos=existing_nos,
                             technician_list=self._technician_list,
                             edit_record=record, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["id"] = fa_id
            data["issue_id"] = self.get_selected_issue_id()
            self.fa_record_edited.emit(data)
        dlg.deleteLater()

    def _delete_fa_record(self, fa_id: int) -> None:
        """删除 FA 记录。"""
        ret = QMessageBox.question(
            self, "确认删除",
            "确定要删除这条 FA 分析记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.fa_record_deleted.emit(fa_id)

    # ── CAPA 弹窗 ──

    def _open_capa_dialog(self) -> None:
        """新建 CAPA 弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在列表中选中一个 Issue。")
            return
        issue = self._table.get_issue_by_id(issue_id)
        dlg = CAPADialog(
            technician_list=self._technician_list,
            issue=issue,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            data["issue_id"] = issue_id
            self.capa_record_added.emit(data)
        dlg.deleteLater()

    def _open_edit_capa_dialog(self, record) -> None:
        """编辑 CAPA 弹窗。"""
        dlg = CAPADialog(
            technician_list=self._technician_list,
            capa_record=record,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            self.capa_record_edited.emit(data)
        dlg.deleteLater()

    def _confirm_delete_capa(self, record) -> None:
        """确认删除 CAPA 记录。"""
        if record.id is None:
            return
        reply = QMessageBox.warning(
            self, "确认删除",
            f"确定要删除该 CAPA 措施吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.capa_record_deleted.emit(record.id)

    # ── 新建/编辑/删除 Issue（IssueEditDialog）──

    def open_create_issue_dialog(self) -> None:
        """打开新建 Issue 弹窗。"""
        dlg = IssueEditDialog(
            issue=None,
            project_list=self._project_list,
            default_project_id=self._default_project_id,
            task_list=self._task_list,
            default_task_id=self._default_task_id,
            sample_list=self._sample_list,
            default_sample_id=self._default_sample_id,
            knowledge_list=self._knowledge_list,
            parent=self,
        )
        if dlg.exec():
            self.issue_saved.emit(dlg.get_data())
        dlg.deleteLater()

    def open_edit_issue_dialog(self) -> None:
        """打开编辑 Issue 弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在列表中选中一个 Issue。")
            return
        issue = self._table.get_issue_by_id(issue_id)
        if issue is None:
            return
        dlg = IssueEditDialog(
            issue=issue,
            project_list=self._project_list,
            task_list=self._task_list,
            sample_list=self._sample_list,
            knowledge_list=self._knowledge_list,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            data["id"] = issue.id
            self.issue_saved.emit(data)
        dlg.deleteLater()

    # ── 刷新主题 ──────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """主题切换回调。"""
        # FA/CAPA 面板有内联颜色，需重建卡片
        if hasattr(self, "_fa_panel"):
            self._fa_panel.refresh_theme()
        if hasattr(self, "_capa_panel"):
            self._capa_panel.refresh_theme()
