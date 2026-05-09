"""Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
from src.models.issue import Issue, FARecord, CAPARecord
from src.views.dialogs.issue_dialog import IssueEditDialog
from src.views.dialogs.fa_record_dialog import FARecordDialog
from src.styles.constants import TABLE_QSS, VIEW_MARGINS, ISSUE_STATUS_COLORS, ISSUE_SEVERITY_COLORS, apply_column_specs
from src.constants import SEVERITY_LABELS, ISSUE_STATUS_LABELS
from src.views.dialogs.base_dialog import _BaseDialog

# Issue 表列规格: (表头, 模式, 默认宽度)
#   fixed=固定 / content=按内容 / stretch=填满 / interactive=可拖拽
_ISSUE_SPECS = [
    ("ID", "fixed", 50),
    ("标题", "interactive", 200),
    ("严重度", "interactive", 70),
    ("状态", "interactive", 80),
    ("优先级", "interactive", 70),
    ("根因", "interactive", 120),
    ("解决方案", "interactive", 140),
    ("创建时间", "interactive", 100),
]


class _IssueTable(QTableWidget):
    """Issue 列表表格。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_column_specs(self, _ISSUE_SPECS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
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
        self.setSortingEnabled(False)
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
                (issue.resolution or "")[:20],
                (issue.created_at or "")[:10],
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, issue.id)
                elif col == 2:  # severity
                    item.setForeground(QColor(ISSUE_SEVERITY_COLORS.get(issue.severity, TEXT)))
                elif col == 3:  # status
                    item.setForeground(QColor(ISSUE_STATUS_COLORS.get(issue.status, TEXT)))
                self.setItem(row, col, item)
        self.setSortingEnabled(True)

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

    def get_selected_issue(self) -> Issue | None:
        """返回当前选中的 Issue 对象（排序安全）。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            return None
        for issue in self._issues:
            if issue.id == issue_id:
                return issue
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

            # 可能原因（鱼骨图分类）
            if rec.possible_cause:
                cause = QLabel(f"可能原因: {rec.possible_cause}")
                cause.setWordWrap(True)
                cause.setStyleSheet(f"color: {MAUVE}; font-size: 12px;")
                card_layout.addWidget(cause)

            # 原因分类 + 确认状态
            meta_parts = []
            if rec.cause_category:
                meta_parts.append(f"分类: {rec.cause_category}")
            confirmed_labels = {0: "待定", 1: "确认", 2: "排除"}
            confirmed_colors = {0: SUBTEXT0, 1: GREEN, 2: RED}
            confirmed_label = confirmed_labels.get(rec.confirmed, "待定")
            confirmed_color = confirmed_colors.get(rec.confirmed, SUBTEXT0)
            meta_parts.append(f"状态: {confirmed_label}")
            meta_text = "  |  ".join(meta_parts)
            meta = QLabel(meta_text)
            meta.setStyleSheet(f"color: {confirmed_color}; font-size: 11px;")
            card_layout.addWidget(meta)

            self._layout.addWidget(card)


class IssueView(QWidget):
    """Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

    # ── 信号（替代旧钩子方法）──
    issue_saved = Signal(dict)          # Issue 保存/更新时发射 data: dict
    issue_deleted = Signal(int)         # Issue 删除时发射 issue_id
    issue_selected = Signal(object)     # Issue 选中时发射 issue_id (int | None)
    fa_record_added = Signal(dict)      # FA 记录添加时发射 data: dict
    capa_record_added = Signal(dict)    # CAPA 记录添加时发射 data: dict
    capa_record_edited = Signal(dict)   # CAPA 记录编辑时发射 data: dict
    capa_record_deleted = Signal(int)   # CAPA 记录删除时发射 capa_id
    export_8d_requested = Signal(int)   # 导出 8D 报告时发射 issue_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project_list: list = []  # 项目列表，由 main.py 注入
        self._default_project_id: int | None = None  # 默认项目，由 main.py 注入
        self._task_list: list = []  # 任务列表，由 refresh_handlers 注入
        self._sample_list: list = []  # 样品列表，由 refresh_handlers 注入
        self._knowledge_list: list = []  # 知识库条目，由 refresh_handlers 注入
        self._default_task_id: int | None = None
        self._default_sample_id: int | None = None
        self._technician_list: list = []  # 技术员列表，由 refresh_handlers 注入
        self._all_issues: list[Issue] = []  # 筛选前的完整列表缓存
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

        # 状态筛选
        self._status_filter = QComboBox()
        self._status_filter.addItems(["全部状态", "待处理", "分析中", "已验证", "已关闭"])
        self._status_filter.setFixedWidth(100)
        self._status_filter.setToolTip("按状态筛选")
        toolbar.addWidget(self._status_filter)

        # 严重度筛选
        self._severity_filter = QComboBox()
        self._severity_filter.addItems(["全部严重度", "严重", "主要", "次要", "外观"])
        self._severity_filter.setFixedWidth(110)
        self._severity_filter.setToolTip("按严重度筛选")
        toolbar.addWidget(self._severity_filter)

        self._btn_add = QPushButton("新建 Issue")
        self._btn_add.setProperty("class", "primary")
        self._btn_add.setToolTip("新建 Issue (Ctrl+N)")
        toolbar.addWidget(self._btn_add)

        self._btn_add_fa = QPushButton("新建 FA 步骤")
        self._btn_add_fa.setProperty("class", "action")
        self._btn_add_fa.setToolTip("添加 FA 分析步骤")
        toolbar.addWidget(self._btn_add_fa)

        # CAPA 按钮
        self._btn_add_capa = QPushButton("新建 CAPA")
        self._btn_add_capa.setProperty("class", "action")
        self._btn_add_capa.setToolTip("添加纠正预防措施")
        toolbar.addWidget(self._btn_add_capa)

        # 导出 8D 报告按钮
        self._btn_export_8d = QPushButton("导出 8D 报告")
        self._btn_export_8d.setProperty("class", "action")
        self._btn_export_8d.setToolTip("将选中的 Issue 导出为 8D 报告 (PDF)")
        toolbar.addWidget(self._btn_export_8d)

        # attachment management: 附件按钮
        self._btn_attachments = QPushButton("附件")
        self._btn_attachments.setProperty("class", "action")
        self._btn_attachments.setToolTip("管理附件")
        toolbar.addWidget(self._btn_attachments)

        toolbar.addStretch()

        # 统计标签
        self._stats_label = QLabel("0 个 Issue")
        self._stats_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px;")
        toolbar.addWidget(self._stats_label)

        layout.addLayout(toolbar)

        self._issue_table = _IssueTable()
        layout.addWidget(self._issue_table, stretch=3)

        # FA + CAPA 左右排列
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        # 左: FA 面板
        fa_col = QVBoxLayout()
        fa_col.setSpacing(4)
        self._fa_label = QLabel("FA 失效分析")
        self._fa_label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 0;")
        fa_col.addWidget(self._fa_label)
        self._fa_panel = _FAPanel()
        fa_col.addWidget(self._fa_panel, stretch=1)

        # 右: CAPA 面板
        capa_col = QVBoxLayout()
        capa_col.setSpacing(4)
        self._capa_label = QLabel("CAPA 纠正预防措施")
        self._capa_label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: bold; padding: 4px 0;")
        capa_col.addWidget(self._capa_label)
        self._capa_panel = _CAPAPanel()
        capa_col.addWidget(self._capa_panel, stretch=1)

        bottom_row.addLayout(fa_col, stretch=1)
        bottom_row.addLayout(capa_col, stretch=1)
        layout.addLayout(bottom_row, stretch=2)

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
        self._btn_add_capa.clicked.connect(self._open_capa_dialog)
        self._btn_export_8d.clicked.connect(self._on_export_8d)
        # 选中 Issue 时自动加载 FA 记录
        self._issue_table.itemSelectionChanged.connect(self._on_issue_selection_changed)
        # 筛选联动
        self._search_input.textChanged.connect(self._apply_filters)
        self._status_filter.currentIndexChanged.connect(self._apply_filters)
        self._severity_filter.currentIndexChanged.connect(self._apply_filters)

    # ── 数据刷新 ──────────────────────────────────────────────

    def refresh(self, issues: list[Issue]) -> None:
        self._all_issues = issues
        self._apply_filters()

    def _apply_filters(self) -> None:
        """根据搜索文本 + 状态 + 严重度筛选 Issue 列表。"""
        # 状态映射
        _STATUS_MAP = {"待处理": "open", "分析中": "analyzing", "已验证": "verified", "已关闭": "closed"}
        _SEVERITY_MAP = {"严重": "critical", "主要": "major", "次要": "minor", "外观": "cosmetic"}

        status_val = _STATUS_MAP.get(self._status_filter.currentText())
        severity_val = _SEVERITY_MAP.get(self._severity_filter.currentText())
        search_text = self._search_input.text().strip().lower()

        filtered = self._all_issues
        if status_val:
            filtered = [i for i in filtered if i.status == status_val]
        if severity_val:
            filtered = [i for i in filtered if i.severity == severity_val]
        if search_text:
            filtered = [i for i in filtered
                        if search_text in (i.title or "").lower()
                        or search_text in (i.root_cause or "").lower()
                        or search_text in (i.resolution or "").lower()]

        self._issue_table.set_issues(filtered)
        open_count = sum(1 for i in filtered if i.status == "open")
        analyzing = sum(1 for i in filtered if i.status == "analyzing")
        total = len(self._all_issues)
        shown = len(filtered)
        if total == shown:
            self._stats_label.setText(f"{total} 个 Issue（{open_count} 待处理，{analyzing} 分析中）")
        else:
            self._stats_label.setText(f"{shown}/{total} 个 Issue（{open_count} 待处理，{analyzing} 分析中）")
        self._update_empty_state()

    def refresh_fa(self, records: list[FARecord]) -> None:
        self._fa_panel.set_fa_records(records)

    def refresh_capa(self, records: list) -> None:
        """刷新 CAPA 面板。"""
        self._capa_panel.set_capa_records(records)

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
    def btn_add_capa(self) -> QPushButton:
        return self._btn_add_capa

    @property
    def btn_export_8d(self) -> QPushButton:
        """8D 报告导出按钮。"""
        return self._btn_export_8d

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
            knowledge_list=self._knowledge_list,
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
            knowledge_list=self._knowledge_list,
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
        dlg = FARecordDialog(existing_step_nos=existing_nos,
                             technician_list=self._technician_list, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["issue_id"] = issue_id
            self.fa_record_added.emit(data)

    def _open_capa_dialog(self) -> None:
        """打开新建 CAPA 弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在左侧列表中选中一个 Issue。")
            return
        dlg = _CAPADialog(technician_list=self._technician_list, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["issue_id"] = issue_id
            self.capa_record_added.emit(data)

    def _open_edit_capa_dialog(self, record) -> None:
        """打开编辑 CAPA 弹窗。"""
        dlg = _CAPADialog(
            technician_list=self._technician_list,
            capa_record=record,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            self.capa_record_edited.emit(data)

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

    def _on_export_8d(self) -> None:
        """导出 8D 报告。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在左侧列表中选中一个 Issue。")
            return
        self.export_8d_requested.emit(issue_id)

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


# ═══════════════════════════════════════════════════════════════════
#  CAPA 面板 + 弹窗
# ═══════════════════════════════════════════════════════════════════

class _CAPAPanel(QScrollArea):
    """CAPA 纠正预防措施面板。"""

    _STATUS_LABELS = {
        "pending": ("待执行", SUBTEXT0),
        "in_progress": ("进行中", YELLOW),
        "completed": ("已完成", GREEN),
        "verified": ("已验证", BLUE),
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
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
        # 初始占位
        label = QLabel("选择一个 Issue 查看 CAPA 记录")
        label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 13px; padding: 12px;")
        self._layout.addWidget(label)

    def set_capa_records(self, records: list) -> None:
        """刷新 CAPA 记录卡片。"""
        # 清空
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        if not records:
            label = QLabel("暂无 CAPA 记录")
            label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 13px; padding: 12px;")
            self._layout.addWidget(label)
            return

        for rec in records:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {SURFACE0}; border-radius: 8px;
                    border: 1px solid {SURFACE1};
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # 状态行
            status_label_text, status_color = self._STATUS_LABELS.get(
                rec.status, ("未知", SUBTEXT0)
            )
            header = QHBoxLayout()
            status_lbl = QLabel(status_label_text)
            status_lbl.setStyleSheet(f"color: {status_color}; font-weight: bold; font-size: 12px;")
            header.addWidget(status_lbl)
            if rec.due_date:
                due_lbl = QLabel(f"截止: {rec.due_date}")
                due_lbl.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px;")
                header.addWidget(due_lbl)
            header.addStretch()

            # 编辑/删除按钮
            btn_edit = QPushButton("编辑")
            btn_edit.setFixedHeight(24)
            btn_edit.setStyleSheet(f"color: {BLUE}; font-size: 11px; border: none; padding: 2px 6px;")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.clicked.connect(lambda checked, r=rec: self._on_edit_capa(r))
            header.addWidget(btn_edit)

            btn_del = QPushButton("删除")
            btn_del.setFixedHeight(24)
            btn_del.setStyleSheet(f"color: {RED}; font-size: 11px; border: none; padding: 2px 6px;")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, r=rec: self._on_delete_capa(r))
            header.addWidget(btn_del)

            card_layout.addLayout(header)

            # 措施内容
            action_lbl = QLabel(rec.action or "")
            action_lbl.setWordWrap(True)
            action_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
            card_layout.addWidget(action_lbl)

            # 负责人
            assignee_name = getattr(rec, 'assignee_name', '') or ''
            if assignee_name:
                assignee_lbl = QLabel(f"负责人: {assignee_name}")
                assignee_lbl.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px;")
                card_layout.addWidget(assignee_lbl)

            # PDCA 字段：根因分析
            root_cause = getattr(rec, 'root_cause', '') or ''
            if root_cause:
                rc_lbl = QLabel(f"根因分析: {root_cause}")
                rc_lbl.setWordWrap(True)
                rc_lbl.setStyleSheet(f"color: {MAUVE}; font-size: 11px;")
            else:
                rc_lbl = QLabel("根因分析: 待填写")
                rc_lbl.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px; font-style: italic;")
            card_layout.addWidget(rc_lbl)

            # PDCA 字段：效果验证
            effectiveness = getattr(rec, 'effectiveness', '') or ''
            if effectiveness:
                eff_lbl = QLabel(f"效果验证: {effectiveness}")
                eff_lbl.setWordWrap(True)
                eff_lbl.setStyleSheet(f"color: {GREEN}; font-size: 11px;")
            else:
                eff_lbl = QLabel("效果验证: 待填写")
                eff_lbl.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px; font-style: italic;")
            card_layout.addWidget(eff_lbl)

            # PDCA 字段：改善追踪
            follow_up = getattr(rec, 'follow_up', '') or ''
            if follow_up:
                fu_lbl = QLabel(f"改善追踪: {follow_up}")
                fu_lbl.setWordWrap(True)
                fu_lbl.setStyleSheet(f"color: {LAVENDER}; font-size: 11px;")
            else:
                fu_lbl = QLabel("改善追踪: 待填写")
                fu_lbl.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px; font-style: italic;")
            card_layout.addWidget(fu_lbl)

            # 验证结果
            if rec.verification_result:
                v_lbl = QLabel(f"验证: {rec.verification_result}")
                v_lbl.setWordWrap(True)
                v_lbl.setStyleSheet(f"color: {GREEN}; font-size: 11px;")
                card_layout.addWidget(v_lbl)

            self._layout.addWidget(card)

    def _on_edit_capa(self, record) -> None:
        """触发编辑 CAPA 记录。"""
        view = self.parent_issue_view()
        if view:
            view._open_edit_capa_dialog(record)

    def _on_delete_capa(self, record) -> None:
        """触发删除 CAPA 记录。"""
        view = self.parent_issue_view()
        if view:
            view._confirm_delete_capa(record)

    def parent_issue_view(self) -> "IssueView | None":
        """向上查找到 IssueView 实例。"""
        p = self.parent()
        while p is not None and not isinstance(p, IssueView):
            p = p.parent()
        return p


class _CAPADialog(_BaseDialog):
    """新建/编辑 CAPA 记录弹窗。"""

    _STATUS_OPTIONS = [
        ("待执行", "pending"),
        ("进行中", "in_progress"),
        ("已完成", "completed"),
        ("已验证", "verified"),
    ]

    def __init__(self, technician_list: list | None = None,
                 capa_record: CAPARecord | None = None,
                 parent: QWidget | None = None):
        is_edit = capa_record is not None
        title = "编辑 CAPA 措施" if is_edit else "新建 CAPA 措施"
        super().__init__(title, parent, width=520)

        self._capa_record = capa_record
        self._technician_list = technician_list or []
        self._action_edit = self._add_text_area(
            "措施描述",
            default=(capa_record.action or "") if is_edit else "",
            placeholder="描述纠正或预防措施",
        )
        self._due_date_edit = self._add_date_field("截止日期")

        # 负责人（自由输入）
        self._assignee_edit = self._add_text_field(
            "负责人",
            default=(capa_record.assignee_name or "") if is_edit else "",
            placeholder="输入负责人姓名",
        )

        status_labels = [label for label, _ in self._STATUS_OPTIONS]
        default_status = ""
        if is_edit:
            status_val = capa_record.status or ""
            for lbl, val in self._STATUS_OPTIONS:
                if val == status_val:
                    default_status = lbl
                    break
        self._status_combo = self._add_combo_field(
            "状态",
            items=status_labels,
            default=default_status,
        )

        self._add_separator()

        # PDCA 扩展字段
        self._root_cause_edit = self._add_text_area(
            "根因分析",
            default=(capa_record.root_cause or "") if is_edit else "",
            placeholder="Plan: 分析问题根因",
        )
        self._effectiveness_edit = self._add_text_area(
            "效果验证",
            default=(capa_record.effectiveness or "") if is_edit else "",
            placeholder="Check: 措施效果如何",
        )
        self._follow_up_edit = self._add_text_area(
            "改善追踪",
            default=(capa_record.follow_up or "") if is_edit else "",
            placeholder="Act: 后续改善计划",
        )

    def get_data(self) -> dict:
        status_map = {label: val for label, val in self._STATUS_OPTIONS}
        assignee_name = self._assignee_edit.text().strip()
        data = {
            "action": self._action_edit.toPlainText().strip(),
            "due_date": self._due_date_edit.date().toString("yyyy-MM-dd")
                if self._due_date_edit.date().isValid() and self._due_date_edit.date().year() >= 2020
                else "",
            "assignee_id": None,
            "assignee_name": assignee_name,
            "status": status_map.get(self._status_combo.currentText(), "pending"),
            "root_cause": self._root_cause_edit.toPlainText().strip(),
            "effectiveness": self._effectiveness_edit.toPlainText().strip(),
            "follow_up": self._follow_up_edit.toPlainText().strip(),
        }
        # 编辑模式时附带 id
        if self._capa_record is not None:
            data["id"] = self._capa_record.id
        return data

    def accept(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if not self._action_edit.toPlainText().strip():
            QMessageBox.warning(self, "校验失败", "措施描述为必填项。")
            self._action_edit.setFocus()
            return
        # 职责分离检查：验证人不能是执行人
        status_map = {label: val for label, val in self._STATUS_OPTIONS}
        status = status_map.get(self._status_combo.currentText(), "pending")
        if status == "verified":
            assignee_name = self._assignee_edit.text().strip()
            reply = QMessageBox.question(
                self, "职责分离确认",
                "按质量管理要求，验证人不应与执行人为同一人。\n\n"
                "请确认验证人与负责人不是同一人。\n\n"
                "当前负责人：" + (assignee_name or "（未指定）"),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        super().accept()
