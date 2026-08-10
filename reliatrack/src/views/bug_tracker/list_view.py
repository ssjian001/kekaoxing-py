"""增强列表视图 — BugListView + FilterPanel + 批量操作 + Aging + FA/CAPA 内嵌面板。"""

from __future__ import annotations

from typing import Any, Optional

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
    PADDING_LARGE,
    SPACING_MEDIUM,
    VIEW_MARGINS,
)
from src.views.widgets.table_delegate import RowHighlightDelegate
from src.views.widgets.search_box import SearchBox
from src.styles.column_persistence import save_column_widths_debounced, restore_column_widths
from src.styles.constants import apply_column_specs, install_copy_handler
from src.styles.toast import ToastWidget
from src.styles.icon import set_icon, RI_REFRESH
from src.constants import ISSUE_STATUS_LABELS, SEVERITY_LABELS, PRIORITY_LABELS
from src.views.bug_tracker.detail_dialog import IssueDetailDialog
from src.views.widgets.bug_table import _BugTable

# 常量
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
    stats_updated = Signal(int, int)      # 筛选后 (total, open) 供父视图统计栏
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

        # 1. 筛选 + 工具栏合并为一行
        layout.addLayout(self._build_filter_toolbar())

        # 2. 主区域 — 水平分割：左=表格，右=FA/CAPA（垂直）
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
        self._btn_add_fa.setFixedHeight(26)
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
        self._btn_add_capa.setFixedHeight(26)
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

    def _build_filter_toolbar(self) -> QHBoxLayout:
        """筛选栏 + 工具栏合并为一行。
        
        左: [状态] [严重度] [优先级] [DRI] [清除]
        中: [搜索框]
        右: [全选] [批量操作] [刷新]
        """
        from PySide6.QtWidgets import QComboBox, QToolButton, QMenu
        from src.constants import ISSUE_STATUS_LABELS, SEVERITY_LABELS, PRIORITY_LABELS

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        _FILTER_W = 80  # 统一宽度

        # ── 左侧：筛选 ──
        self._filter_status = QComboBox()
        self._filter_status.setProperty("class", "filter-combo")
        self._filter_status.setFixedWidth(_FILTER_W)
        self._filter_status.setFixedHeight(26)
        self._filter_status.addItem("全部状态", "")
        for k, v in ISSUE_STATUS_LABELS.items():
            self._filter_status.addItem(v, k)
        self._filter_status.currentIndexChanged.connect(self._apply_filters)
        toolbar.addWidget(self._filter_status)

        self._filter_severity = QComboBox()
        self._filter_severity.setProperty("class", "filter-combo")
        self._filter_severity.setFixedWidth(_FILTER_W)
        self._filter_severity.setFixedHeight(26)
        self._filter_severity.addItem("全部严重度", "")
        for k, v in SEVERITY_LABELS.items():
            self._filter_severity.addItem(v, k)
        self._filter_severity.currentIndexChanged.connect(self._apply_filters)
        toolbar.addWidget(self._filter_severity)

        self._filter_priority = QComboBox()
        self._filter_priority.setProperty("class", "filter-combo")
        self._filter_priority.setFixedWidth(_FILTER_W)
        self._filter_priority.setFixedHeight(26)
        self._filter_priority.addItem("全部优先级", "")
        for k, v in PRIORITY_LABELS.items():
            self._filter_priority.addItem(v, k)
        self._filter_priority.currentIndexChanged.connect(self._apply_filters)
        toolbar.addWidget(self._filter_priority)

        self._filter_dri = QComboBox()
        self._filter_dri.setProperty("class", "filter-combo")
        self._filter_dri.setFixedWidth(_FILTER_W)
        self._filter_dri.setFixedHeight(26)
        self._filter_dri.setEditable(True)
        self._filter_dri.setPlaceholderText("DRI…")
        self._filter_dri.lineEdit().textChanged.connect(self._apply_filters)
        toolbar.addWidget(self._filter_dri)

        btn_clear = QPushButton("清除")
        btn_clear.setFixedWidth(60)
        btn_clear.setFixedHeight(26)
        btn_clear.setProperty("class", "action")
        btn_clear.clicked.connect(self._clear_filters)
        toolbar.addWidget(btn_clear)

        # ── 中间：搜索 ──
        self._search_input = SearchBox()
        self._search_input.setPlaceholderText("搜索标题/描述/根因…")
        self._search_input.setMinimumWidth(160)
        self._search_input.setMaximumWidth(260)
        self._search_input.textChanged.connect(self._apply_filters)
        toolbar.addWidget(self._search_input)

        # ── 右侧：操作按钮（CommandBar 自動溢出）──
        toolbar.addStretch()

        from src.views.widgets.command_bar import CommandBar
        action_bar = CommandBar()
        action_bar.setButtonTight(True)

        self._btn_select_all = QPushButton("全选")
        self._btn_select_all.setFixedHeight(26)
        self._btn_select_all.setProperty("class", "action")
        self._btn_select_all.setCheckable(True)
        self._btn_select_all.clicked.connect(self._on_select_all)
        action_bar.addWidget(self._btn_select_all)

        self._btn_batch = QToolButton()
        self._btn_batch.setText("批量操作")
        self._btn_batch.setFixedHeight(26)
        self._btn_batch.setProperty("class", "action")
        self._btn_batch.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        batch_menu = QMenu(self._btn_batch)
        self._act_batch_status = batch_menu.addAction("批量改状态")
        self._act_batch_status.triggered.connect(lambda: self._open_batch_dialog("改状态"))
        self._act_batch_assign = batch_menu.addAction("批量设置DRI")
        self._act_batch_assign.triggered.connect(lambda: self._open_batch_dialog("设置DRI"))
        self._btn_batch.setMenu(batch_menu)
        self._btn_batch.setEnabled(False)
        action_bar.addWidget(self._btn_batch)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setFixedHeight(26)
        btn_refresh.setProperty("class", "action")
        btn_refresh.clicked.connect(self.refresh_requested.emit)
        set_icon(btn_refresh, RI_REFRESH)
        action_bar.addWidget(btn_refresh)

        toolbar.addWidget(action_bar)
        toolbar.addSpacing(8)

        return toolbar

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
        self._filter_dri.setEditText("")
        self._search_input.clear()

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

    def focus_search(self) -> None:
        """/ 快捷键 — 聚焦搜索框。"""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def set_filters(self, filters: dict) -> None:
        """外部设置筛选条件（跨视图同步，看板→列表方向）。

        应用入参到控件后刷新；不修改入参中未提供的控件（保留当前值）。
        """
        if not filters:
            return
        if "status" in filters and filters["status"]:
            idx = self._filter_status.findData(filters["status"])
            if idx >= 0:
                self._filter_status.setCurrentIndex(idx)
        if "severity" in filters and filters["severity"]:
            idx = self._filter_severity.findData(filters["severity"])
            if idx >= 0:
                self._filter_severity.setCurrentIndex(idx)
        if "priority" in filters and filters["priority"] is not None:
            idx = self._filter_priority.findData(str(filters["priority"]))
            if idx >= 0:
                self._filter_priority.setCurrentIndex(idx)
        if "dri_name" in filters:
            self._filter_dri.setEditText(str(filters.get("dri_name", "")))
        if "keyword" in filters:
            self._search_input.setText(str(filters.get("keyword", "")))
        self._apply_filters()

    def _apply_filters(self) -> None:
        """根据筛选条件过滤并刷新表格。"""
        keyword = self._search_input.text().strip().lower()

        # 读取固定筛选条件
        status_val = self._filter_status.currentData()
        severity_val = self._filter_severity.currentData()
        priority_val = self._filter_priority.currentData()
        dri_text = self._filter_dri.currentText().strip().lower()

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
        # 连父视图的统计信息一起更新
        parent = self.parent()
        if parent and hasattr(parent, '_update_stats'):
            parent._update_stats()
        # 广播当前筛选条件，供看板等视图同步（列表→看板方向）
        self.filter_changed.emit(self._collect_filters())
        # 广播筛选后统计（顶部统计栏真实反映当前筛选结果）
        self.stats_updated.emit(len(filtered), sum(1 for i in filtered if i.status == "open"))

    def _collect_filters(self) -> dict[str, Any]:
        """收集当前筛选控件状态（供跨视图同步）。"""
        return {
            "status": self._filter_status.currentData() or "",
            "severity": self._filter_severity.currentData() or "",
            "priority": self._filter_priority.currentData(),
            "dri_name": self._filter_dri.currentText().strip(),
            "keyword": self._search_input.text().strip(),
        }

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
        """选中 Issue 时发射信号 + 同步 delegate 选中行。"""
        issue_id = self.get_selected_issue_id()
        self.issue_selected.emit(issue_id)

        # 同步 delegate 的 selected_rows
        selected = self._table.selectedIndexes()
        self._table._delegate.selected_rows = {idx.row() for idx in selected}
        self._table.viewport().update()

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
