"""Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,

    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QEvent, Qt, Signal

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    BLUE, GREEN, YELLOW, RED, PEACH, MAUVE, LAVENDER, PINK, OVERLAY0,
)
from src.models.issue import Issue, FARecord
from src.views.dialogs.issue_dialog import IssueEditDialog
from src.views.dialogs.fa_record_dialog import FARecordDialog
from src.styles.constants import TABLE_QSS, VIEW_MARGINS, ISSUE_STATUS_COLORS, ISSUE_SEVERITY_COLORS
from src.constants import SEVERITY_LABELS, ISSUE_STATUS_LABELS


class _IssueTable(QTableWidget):
    """Issue 列表表格。"""

    COLUMNS = ["ID", "标题", "严重度", "状态", "优先级", "根因", "创建时间"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 50)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self._issues: list[Issue] = []
        self._context_menu: QMenu | None = None

        self.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=12,
        ))

        # 信号
        self.doubleClicked.connect(self._on_double_click)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ── 数据 ───────────────────────────────────────────────────

    def set_issues(self, issues: list[Issue]) -> None:
        self._issues = issues
        self.setRowCount(len(issues))
        severity_labels = SEVERITY_LABELS
        status_labels = ISSUE_STATUS_LABELS
        for row, issue in enumerate(issues):
            for col, val in enumerate([
                issue.id,
                issue.title,
                severity_labels.get(issue.severity, issue.severity),
                status_labels.get(issue.status, issue.status),
                issue.priority,
                (issue.root_cause or "")[:15],
                (issue.created_at or "")[:10],
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 2:  # severity
                    item.setForeground(QColor(ISSUE_SEVERITY_COLORS.get(issue.severity, TEXT)))
                elif col == 3:  # status
                    item.setForeground(QColor(ISSUE_STATUS_COLORS.get(issue.status, TEXT)))
                self.setItem(row, col, item)

    def get_selected_issue_id(self) -> Optional[int]:
        row = self.currentRow()
        if 0 <= row < len(self._issues):
            return self._issues[row].id
        return None

    def get_selected_issue(self) -> Issue | None:
        """返回当前选中的 Issue 对象。"""
        row = self.currentRow()
        if 0 <= row < len(self._issues):
            return self._issues[row]
        return None

    # ── 右键菜单 ──────────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        if self._context_menu is None:
            self._context_menu = QMenu(self)
            self._act_edit = self._context_menu.addAction("编辑 Issue")
            self._act_delete = self._context_menu.addAction("删除 Issue")
            self._act_edit.triggered.connect(self._on_edit_action)
            self._act_delete.triggered.connect(self._on_delete_action)

        issue_id = self.get_selected_issue_id()
        self._act_edit.setEnabled(issue_id is not None)
        self._act_delete.setEnabled(issue_id is not None)
        self._context_menu.exec(self.viewport().mapToGlobal(pos))

    def _on_double_click(self) -> None:
        """双击行触发编辑。"""
        issue = self.get_selected_issue()
        if issue:
            view = self.parent_issue_view()
            if view:
                view._open_edit_dialog(issue)

    def _on_edit_action(self) -> None:
        issue = self.get_selected_issue()
        if issue:
            view = self.parent_issue_view()
            if view:
                view._open_edit_dialog(issue)

    def _on_delete_action(self) -> None:
        issue = self.get_selected_issue()
        if issue:
            view = self.parent_issue_view()
            if view:
                view._delete_issue(issue)

    def parent_issue_view(self) -> "IssueView | None":
        """向上查找到 IssueView 实例。"""
        p = self.parent()
        while p is not None and not isinstance(p, IssueView):
            p = p.parent()
        return p


class _FAPanel(QScrollArea):
    """FA 分析记录面板。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._records: list[FARecord] = []
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {BASE}; border: 1px solid {SURFACE1};
                border-radius: 8px;
            }}
        """)

    def set_fa_records(self, records: list[FARecord]) -> None:
        self._records = records
        # 清空
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        if not records:
            label = QLabel("选择一个 Issue 查看 FA 分析记录")
            label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 13px; padding: 12px;")
            self._layout.addWidget(label)
            return

        for i, rec in enumerate(records):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {SURFACE0}; border-radius: 8px;
                    border: 1px solid {SURFACE1};
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # 标题行
            header = QHBoxLayout()
            step_label = QLabel(f"Step {rec.step_no}")
            step_label.setStyleSheet(f"color: {BLUE}; font-weight: bold; font-size: 12px;")
            header.addWidget(step_label)

            method_label = QLabel(rec.method or "")
            method_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 13px;")
            header.addWidget(method_label)
            header.addStretch()
            card_layout.addLayout(header)

            # 步骤标题
            title = QLabel(rec.step_title or "")
            title.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
            card_layout.addWidget(title)

            # 描述
            desc = QLabel(rec.description or "")
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
            card_layout.addWidget(desc)

            # 发现
            if rec.findings:
                findings = QLabel(f"发现: {rec.findings}")
                findings.setWordWrap(True)
                findings.setStyleSheet(f"color: {PEACH}; font-size: 12px;")
                card_layout.addWidget(findings)

            self._layout.addWidget(card)


class IssueView(QWidget):
    """Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

    # ── 信号（替代旧钩子方法）──
    issue_saved = Signal(dict)          # Issue 保存/更新时发射 data: dict
    issue_deleted = Signal(int)         # Issue 删除时发射 issue_id
    issue_selected = Signal(object)     # Issue 选中时发射 issue_id (int | None)
    fa_record_added = Signal(dict)      # FA 记录添加时发射 data: dict

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project_list: list = []  # 项目列表，由 main.py 注入
        self._default_project_id: int | None = None  # 默认项目，由 main.py 注入
        self._task_list: list = []  # 任务列表，由 refresh_handlers 注入
        self._sample_list: list = []  # 样品列表，由 refresh_handlers 注入
        self._default_task_id: int | None = None
        self._default_sample_id: int | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        # 工具栏
        toolbar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索 Issue 标题 / 根因…")
        self._search_input.setMinimumWidth(160)
        toolbar.addWidget(self._search_input)

        self._btn_add = QPushButton("新建 Issue")
        self._btn_add.setProperty("class", "primary")
        toolbar.addWidget(self._btn_add)

        self._btn_add_fa = QPushButton("新建 FA 步骤")
        self._btn_add_fa.setProperty("class", "action")
        toolbar.addWidget(self._btn_add_fa)

        # attachment management: 附件按钮
        self._btn_attachments = QPushButton("附件")
        self._btn_attachments.setProperty("class", "action")
        toolbar.addWidget(self._btn_attachments)

        toolbar.addStretch()

        # 统计标签
        self._stats_label = QLabel("0 个 Issue")
        self._stats_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px;")
        toolbar.addWidget(self._stats_label)

        layout.addLayout(toolbar)

        self._issue_table = _IssueTable()
        layout.addWidget(self._issue_table, stretch=3)

        self._fa_panel = _FAPanel()
        layout.addWidget(self._fa_panel, stretch=2)

        # 空状态提示
        self._empty_label = QLabel("暂无 Issue 数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 14px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._issue_table)
        self._empty_label.hide()
        self._issue_table.installEventFilter(self)

        # ── 信号连接 ──
        self._btn_add.clicked.connect(self._open_create_dialog)
        self._btn_add_fa.clicked.connect(self._open_fa_dialog)
        # 选中 Issue 时自动加载 FA 记录
        self._issue_table.itemSelectionChanged.connect(self._on_issue_selection_changed)

    # ── 数据刷新 ──────────────────────────────────────────────

    def refresh(self, issues: list[Issue]) -> None:
        self._issue_table.set_issues(issues)
        open_count = sum(1 for i in issues if i.status == "open")
        analyzing = sum(1 for i in issues if i.status == "analyzing")
        self._stats_label.setText(f"{len(issues)} 个 Issue（{open_count} 待处理，{analyzing} 分析中）")
        self._update_empty_state()

    def refresh_fa(self, records: list[FARecord]) -> None:
        self._fa_panel.set_fa_records(records)

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def issue_table(self) -> _IssueTable:
        return self._issue_table

    @property
    def btn_add(self) -> QPushButton:
        return self._btn_add

    @property
    def btn_add_fa(self) -> QPushButton:
        return self._btn_add_fa

    @property
    def btn_attachments(self) -> QPushButton:  # attachment management
        """📎 附件管理按钮。"""
        return self._btn_attachments

    def get_selected_issue_id(self) -> Optional[int]:
        return self._issue_table.get_selected_issue_id()

    # ── Issue 新建/编辑/删除 ──────────────────────────────────

    def _open_create_dialog(self) -> None:
        """打开新建 Issue 弹窗。"""
        dlg = IssueEditDialog(
            issue=None,
            project_list=self._project_list,
            default_project_id=self._default_project_id,
            task_list=self._task_list,
            default_task_id=self._default_task_id,
            sample_list=self._sample_list,
            default_sample_id=self._default_sample_id,
            parent=self,
        )
        if dlg.exec():
            self.issue_saved.emit(dlg.get_data())

    def _open_edit_dialog(self, issue: Issue) -> None:
        """打开编辑 Issue 弹窗。"""
        dlg = IssueEditDialog(
            issue=issue,
            project_list=self._project_list,
            task_list=self._task_list,
            sample_list=self._sample_list,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            data["id"] = issue.id
            self.issue_saved.emit(data)

    def _delete_issue(self, issue: Issue) -> None:
        """删除 Issue（带确认）。"""
        reply = QMessageBox.warning(
            self,
            "确认删除",
            f"确定要删除 Issue #{issue.id} 「{issue.title}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if issue.id is None:
                raise ValueError("Cannot delete issue without id")
            self.issue_deleted.emit(issue.id)

    # ── FA 步骤 ──────────────────────────────────────────────

    def _open_fa_dialog(self) -> None:
        """打开新建 FA 步骤弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在左侧列表中选中一个 Issue。")
            return
        # 收集已有 step_no 用于自动递增
        existing_nos = [rec.step_no for rec in self._current_fa_records()]
        dlg = FARecordDialog(existing_step_nos=existing_nos, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["issue_id"] = issue_id
            self.fa_record_added.emit(data)

    # ── 选中变化 ──────────────────────────────────────────────

    def _on_issue_selection_changed(self) -> None:
        """选中 Issue 时触发加载 FA 记录。"""
        issue_id = self.get_selected_issue_id()
        self.issue_selected.emit(issue_id)

    def _current_fa_records(self) -> list[FARecord]:
        """返回当前 FA 面板中显示的记录列表。"""
        return self._fa_panel._records

    # ── 空状态 ──────────────────────────────────────────────

    def _update_empty_state(self) -> None:
        """根据表格行数显示/隐藏空状态提示。"""
        if self._issue_table.rowCount() == 0:
            self._empty_label.setGeometry(self._issue_table.viewport().rect())
            self._empty_label.show()
        else:
            self._empty_label.hide()

    def eventFilter(self, obj, event) -> bool:
        """监听表格缩放以更新空状态标签位置。"""
        if obj is self._issue_table and event.type() == QEvent.Type.Resize:
            self._empty_label.setGeometry(self._issue_table.viewport().rect())
        return super().eventFilter(obj, event)
