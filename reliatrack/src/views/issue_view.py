"""Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor, QAction
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QEvent, Qt, Signal

import src.styles.theme as _t
from src.models.issue import Issue, FARecord, CAPARecord
from src.views.dialogs.issue_dialog import IssueEditDialog
from src.views.dialogs.fa_record_dialog import FARecordDialog
from src.styles.constants import VIEW_MARGINS, ISSUE_STATUS_COLORS, ISSUE_SEVERITY_COLORS, apply_column_specs
from src.constants import SEVERITY_LABELS, ISSUE_STATUS_LABELS, RESOLUTION_LABELS, ISSUE_CATEGORY_OPTIONS
from src.views.dialogs.base_dialog import _BaseDialog

# Issue 表列规格: (表头, 模式, 默认宽度)
#   fixed=固定 / content=按内容 / stretch=填满 / interactive=可拖拽
_ISSUE_SPECS = [
    ("ID", "fixed", 50),
    ("Issue描述", "interactive", 200),
    ("严重度", "interactive", 70),
    ("状态", "interactive", 80),
    ("类别", "interactive", 70),
    ("优先级", "interactive", 70),
    ("DRI", "interactive", 80),
    ("解决结果", "interactive", 80),
    ("根因", "interactive", 120),
    ("改善对策", "interactive", 120),
    ("创建时间", "interactive", 100),
]


class _IssueTable(QTableWidget):
    """Issue 列表表格。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_column_specs(self, _ISSUE_SPECS, "issue_table")
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self._issues: list[Issue] = []
        self._context_menu: QMenu | None = None

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
        category_labels = {v: k for k, v in ISSUE_CATEGORY_OPTIONS}
        for row, issue in enumerate(issues):
            for col, val in enumerate([
                issue.id,
                issue.title,
                severity_labels.get(issue.severity, issue.severity),
                status_labels.get(issue.status, issue.status),
                category_labels.get(issue.category, issue.category or ""),
                issue.priority,
                getattr(issue, "dri_name", "") or "",
                RESOLUTION_LABELS.get(getattr(issue, "resolution", ""), getattr(issue, "resolution", "") or ""),
                (issue.root_cause or "")[:15],
                (issue.improvement_measures or "")[:40],
                (issue.created_at or "")[:10],
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, issue.id)
                elif col == 2:  # severity
                    item.setForeground(QColor(ISSUE_SEVERITY_COLORS.get(issue.severity, _t.TEXT)))
                elif col == 3:  # status
                    item.setForeground(QColor(ISSUE_STATUS_COLORS.get(issue.status, _t.TEXT)))
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
            # 跳转到关联任务/样品
            self._context_menu.addSeparator()
            self._act_goto_task = self._context_menu.addAction("跳转到关联任务")
            self._act_goto_sample = self._context_menu.addAction("跳转到关联样品")
            self._act_goto_task.triggered.connect(self._on_goto_task)
            self._act_goto_sample.triggered.connect(self._on_goto_sample)

        issue_id = self.get_selected_issue_id()
        self._act_edit.setEnabled(issue_id is not None)
        self._act_delete.setEnabled(issue_id is not None)
        # 仅当 issue 有关联 task_id / sample_id 时启用跳转
        issue = self.get_selected_issue()
        self._act_goto_task.setEnabled(issue is not None and issue.task_id is not None)
        self._act_goto_sample.setEnabled(issue is not None and issue.sample_id is not None)
        self._context_menu.exec(self.viewport().mapToGlobal(pos))

    def _on_goto_task(self) -> None:
        """跳转到关联任务（Tab 3: 测试计划）。"""
        issue = self.get_selected_issue()
        if not issue or issue.task_id is None:
            return
        view = self.parent_issue_view()
        if view:
            win = view.parent()
            if win and hasattr(win, "_tab_widget"):
                win._tab_widget.setCurrentIndex(3)

    def _on_goto_sample(self) -> None:
        """跳转到关联样品（Tab 2: 样品管理）。"""
        issue = self.get_selected_issue()
        if not issue or issue.sample_id is None:
            return
        view = self.parent_issue_view()
        if view:
            win = view.parent()
            if win and hasattr(win, "_tab_widget"):
                win._tab_widget.setCurrentIndex(2)

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

    fa_edit_requested = Signal(int)     # fa_record.id
    fa_delete_requested = Signal(int)   # fa_record.id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._records: list[FARecord] = []
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)
        self.setProperty("class", "issue-scroll")

    def refresh_theme(self) -> None:
        """主题切换回调 — 用当前数据重建卡片以刷新内联颜色。"""
        self.set_fa_records(self._records)

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
            label.setProperty("class", "subtext")
            self._layout.addWidget(label)
            return

        for i, rec in enumerate(records):
            card = QFrame()
            card.setProperty("class", "issue-card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # 标题行
            header = QHBoxLayout()
            step_label = QLabel(f"Step {rec.step_no}")
            step_label.setProperty("class", "step-label")
            header.addWidget(step_label)

            method_label = QLabel(rec.method or "")
            method_label.setProperty("class", "subtext")
            header.addWidget(method_label)
            header.addStretch()

            # 编辑/删除按钮（参考 CAPA 纯文字样式）
            btn_edit = QPushButton("编辑")
            btn_edit.setFixedHeight(24)
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            rec_id = rec.id
            btn_edit.clicked.connect(lambda checked, rid=rec_id: self.fa_edit_requested.emit(rid))
            header.addWidget(btn_edit)

            btn_del = QPushButton("删除")
            btn_del.setFixedHeight(24)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, rid=rec_id: self.fa_delete_requested.emit(rid))
            header.addWidget(btn_del)

            card_layout.addLayout(header)

            # 步骤标题
            title = QLabel(rec.step_title or "")
            title.setProperty("class", "text-bold")
            card_layout.addWidget(title)

            # 描述
            desc = QLabel(rec.description or "")
            desc.setWordWrap(True)
            desc.setProperty("class", "body-text")
            card_layout.addWidget(desc)

            # 发现
            if rec.findings:
                findings = QLabel(f"发现: {rec.findings}")
                findings.setWordWrap(True)
                findings.setProperty("class", "warning-text")
                card_layout.addWidget(findings)

            # 可能原因（鱼骨图分类）
            if rec.possible_cause:
                cause = QLabel(f"可能原因: {rec.possible_cause}")
                cause.setWordWrap(True)
                cause.setProperty("class", "cause-text")
                card_layout.addWidget(cause)

            # 原因分类 + 确认状态
            meta_parts = []
            if rec.cause_category:
                meta_parts.append(f"分类: {rec.cause_category}")
            confirmed_labels = {0: "待定", 1: "确认", 2: "排除"}
            confirmed_colors = {0: _t.SUBTEXT0, 1: _t.GREEN, 2: _t.RED}
            confirmed_label = confirmed_labels.get(rec.confirmed, "待定")
            confirmed_color = confirmed_colors.get(rec.confirmed, _t.SUBTEXT0)
            meta_parts.append(f"状态: {confirmed_label}")
            meta_text = "  |  ".join(meta_parts)
            meta = QLabel(meta_text)
            # 动态颜色（confirmed_color 取决于运行时状态），保留内联
            meta.setStyleSheet(f"color: {confirmed_color};")
            card_layout.addWidget(meta)

            self._layout.addWidget(card)


_UNSET = object()


class IssueView(QWidget):
    """Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

    # ── 信号（替代旧钩子方法）──
    issue_saved = Signal(dict)          # Issue 保存/更新时发射 data: dict
    issue_deleted = Signal(int)         # Issue 删除时发射 issue_id
    issue_selected = Signal(object)     # Issue 选中时发射 issue_id (int | None)
    fa_record_added = Signal(dict)      # FA 记录添加时发射 data: dict
    fa_record_edited = Signal(dict)     # FA 记录编辑时发射 data: dict (含 id)
    fa_record_deleted = Signal(int)     # FA 记录删除时发射 fa_id
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

    def refresh_theme(self) -> None:
        """主题切换回调 — 刷新 FA/CAPA 面板中的内联颜色。"""
        if hasattr(self, "_fa_panel") and hasattr(self._fa_panel, "refresh_theme"):
            self._fa_panel.refresh_theme()
        if hasattr(self, "_capa_panel") and hasattr(self._capa_panel, "refresh_theme"):
            self._capa_panel.refresh_theme()

    def set_context_data(
        self,
        *,
        projects: list | None = None,
        default_project_id: int | None = _UNSET,
        samples: list | None = None,
        knowledge: list | None = None,
        tasks: list | None = None,
        technicians: list | None = None,
    ) -> None:
        """批量设置 Issue 弹窗所需的上下文数据（替代直接写入私有属性）。

        仅传入非 None 的参数会被更新。default_project_id 使用哨兵对象，
        允许显式传入 None 来清除默认项目。
        """
        if projects is not None:
            self._project_list = projects
        if default_project_id is not _UNSET:
            self._default_project_id = default_project_id
        if samples is not None:
            self._sample_list = samples
        if knowledge is not None:
            self._knowledge_list = knowledge
        if tasks is not None:
            self._task_list = tasks
        if technicians is not None:
            self._technician_list = technicians

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        # 工具栏
        toolbar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索 Issue 描述 / 根因…")
        self._search_input.setMinimumWidth(160)
        toolbar.addWidget(self._search_input)

        # 状态筛选（多选）
        self._status_filter_btn = QPushButton("状态筛选")
        self._status_filter_btn.setProperty("class", "action")
        self._status_filter_btn.setFixedWidth(100)
        self._status_filter_btn.setToolTip("按状态筛选（可多选）")
        self._status_filter_menu = QMenu(self._status_filter_btn)
        self._status_filter_actions: dict[str, QAction] = {}
        for chn, eng in [("待处理", "open"), ("分析中", "analyzing"), ("已验证", "verified"), ("已关闭", "closed")]:
            act = self._status_filter_menu.addAction(chn)
            act.setCheckable(True)
            act.setChecked(True)
            act.setData(eng)
            act.toggled.connect(self._apply_filters)
            self._status_filter_actions[eng] = act
        self._status_filter_btn.setMenu(self._status_filter_menu)
        toolbar.addWidget(self._status_filter_btn)

        # 严重度筛选
        self._severity_filter = QComboBox()
        self._severity_filter.setProperty("class", "filter-combo")
        self._severity_filter.addItems(["全部严重度", "严重", "主要", "次要", "外观"])
        self._severity_filter.setFixedWidth(110)
        self._severity_filter.setToolTip("按严重度筛选")
        toolbar.addWidget(self._severity_filter)

        self._btn_add = QPushButton("新建 Issue")
        self._btn_add.setProperty("class", "primary")
        self._btn_add.setToolTip("新建 Issue (Ctrl+N)")
        toolbar.addWidget(self._btn_add)

        # ── 更多操作（收起低频按钮，防止 800px 溢出） ──
        self._more_menu = QMenu(self)
        self._act_add_fa = self._more_menu.addAction("新建 FA 步骤")
        self._act_add_fa.setToolTip("添加 FA 分析步骤")
        self._act_add_capa = self._more_menu.addAction("新建 CAPA")
        self._act_add_capa.setToolTip("添加纠正预防措施")
        self._more_menu.addSeparator()
        self._act_export_8d = self._more_menu.addAction("导出 8D 报告")
        self._act_export_8d.setToolTip("将选中的 Issue 导出为 8D 报告 (PDF)")
        self._act_attachments = self._more_menu.addAction("附件")
        self._act_attachments.setToolTip("管理附件")

        self._btn_more = QToolButton()
        self._btn_more.setText("更多")
        self._btn_more.setMenu(self._more_menu)
        self._btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_more.setProperty("class", "action")
        self._btn_more.setFixedHeight(28)
        self._btn_more.setToolTip("FA/CAPA/导出/附件等更多操作")
        toolbar.addWidget(self._btn_more)

        toolbar.addStretch()

        # 统计标签
        self._stats_label = QLabel("0 个 Issue")
        self._stats_label.setProperty("class", "subtext")
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
        self._fa_label.setProperty("class", "panel-header")
        fa_col.addWidget(self._fa_label)
        self._fa_panel = _FAPanel()
        self._fa_panel.fa_edit_requested.connect(self._open_edit_fa_dialog)
        self._fa_panel.fa_delete_requested.connect(self._delete_fa_record)
        fa_col.addWidget(self._fa_panel, stretch=1)

        # 右: CAPA 面板
        capa_col = QVBoxLayout()
        capa_col.setSpacing(4)
        self._capa_label = QLabel("CAPA 纠正预防措施")
        self._capa_label.setProperty("class", "panel-header")
        capa_col.addWidget(self._capa_label)
        self._capa_panel = _CAPAPanel()
        capa_col.addWidget(self._capa_panel, stretch=1)

        bottom_row.addLayout(fa_col, stretch=1)
        bottom_row.addLayout(capa_col, stretch=1)
        layout.addLayout(bottom_row, stretch=2)

        # 空状态提示
        self._empty_label = QLabel("暂无 Issue 数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "empty-label")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._issue_table)
        self._empty_label.hide()
        self._issue_table.installEventFilter(self)

        # ── 信号连接 ──
        self._btn_add.clicked.connect(self._open_create_dialog)
        self._act_add_fa.triggered.connect(self._open_fa_dialog)
        self._act_add_capa.triggered.connect(self._open_capa_dialog)
        self._act_export_8d.triggered.connect(self._on_export_8d)
        # 选中 Issue 时自动加载 FA 记录
        self._issue_table.itemSelectionChanged.connect(self._on_issue_selection_changed)
        # 筛选联动
        self._search_input.textChanged.connect(self._apply_filters)
        self._severity_filter.currentIndexChanged.connect(self._apply_filters)

    # ── 数据刷新 ──────────────────────────────────────────────

    def refresh(self, issues: list[Issue]) -> None:
        self._all_issues = issues
        self._apply_filters()

    def _apply_filters(self) -> None:
        """根据搜索文本 + 状态（多选）+ 严重度筛选 Issue 列表。"""
        # 状态多选：收集所有勾选的状态
        selected_statuses = {
            eng for eng, act in self._status_filter_actions.items() if act.isChecked()
        }
        # 严重度
        _SEVERITY_MAP = {"严重": "critical", "主要": "major", "次要": "minor", "外观": "cosmetic"}
        severity_val = _SEVERITY_MAP.get(self._severity_filter.currentText())
        search_text = self._search_input.text().strip().lower()

        filtered = self._all_issues
        if selected_statuses and len(selected_statuses) < 4:
            filtered = [i for i in filtered if i.status in selected_statuses]
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
        resolved = sum(1 for i in filtered if getattr(i, "resolution", ""))
        total = len(self._all_issues)
        shown = len(filtered)
        if total == shown:
            self._stats_label.setText(f"{total} 个 Issue（{open_count} 待处理，{analyzing} 分析中，{resolved} 已解决）")
        else:
            self._stats_label.setText(f"{shown}/{total} 个 Issue（{open_count} 待处理，{analyzing} 分析中，{resolved} 已解决）")
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
    def btn_add_fa(self) -> QAction:
        return self._act_add_fa

    @property
    def btn_add_capa(self) -> QAction:
        return self._act_add_capa

    @property
    def btn_export_8d(self) -> QAction:
        """8D 报告导出按钮。"""
        return self._act_export_8d

    @property
    def btn_attachments(self) -> QAction:
        """附件管理按钮。"""
        return self._act_attachments

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
        dlg.deleteLater()

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
        dlg.deleteLater()

    def _delete_issue(self, issue: Issue) -> None:
        """删除 Issue（带确认）。"""
        reply = QMessageBox.warning(
            self,
            "确认删除",
            f"确定要删除 Issue #{issue.id} 「{issue.title}」吗？\n可通过 Ctrl+Z 撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if issue.id is None:
                QMessageBox.warning(self, "错误", "无法删除：Issue 缺少 ID")
                return
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
        dlg.deleteLater()

    def _open_edit_fa_dialog(self, fa_id: int) -> None:
        """打开编辑 FA 步骤弹窗。"""
        # 找到对应的 FARecord
        record = None
        for rec in self._fa_panel._records:
            if rec.id == fa_id:
                record = rec
                break
        if record is None:
            return
        existing_nos = [rec.step_no for rec in self._fa_panel._records]
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
        """删除 FA 记录，需确认。"""
        ret = QMessageBox.question(
            self, "确认删除",
            "确定要删除这条 FA 分析记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.fa_record_deleted.emit(fa_id)

    def _open_capa_dialog(self) -> None:
        """打开新建 CAPA 弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在左侧列表中选中一个 Issue。")
            return
        issue = self._issue_table.get_selected_issue()
        dlg = _CAPADialog(
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
        """打开编辑 CAPA 弹窗。"""
        dlg = _CAPADialog(
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

    @classmethod
    def _status_labels(cls) -> dict[str, tuple[str, str]]:
        """动态读取主题色，主题切换后自动生效。"""
        return {
            "pending": ("待执行", _t.SUBTEXT0),
            "in_progress": ("进行中", _t.YELLOW),
            "completed": ("已完成", _t.GREEN),
            "verified": ("已验证", _t.BLUE),
        }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)
        self.setProperty("class", "issue-scroll")
        self._records: list = []
        # 初始占位
        label = QLabel("选择一个 Issue 查看 CAPA 记录")
        label.setProperty("class", "subtext")
        self._layout.addWidget(label)

    def refresh_theme(self) -> None:
        """主题切换回调 — 用当前数据重建卡片以刷新内联颜色。"""
        self.set_capa_records(self._records)

    def set_capa_records(self, records: list) -> None:
        """刷新 CAPA 记录卡片。"""
        self._records = records
        # 清空
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        if not records:
            label = QLabel("暂无 CAPA 记录")
            label.setProperty("class", "subtext")
            self._layout.addWidget(label)
            return

        for rec in records:
            card = QFrame()
            card.setProperty("class", "issue-card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # 状态行
            status_label_text, status_color = self._status_labels().get(
                rec.status, ("未知", _t.SUBTEXT0)
            )
            header = QHBoxLayout()
            status_lbl = QLabel(status_label_text)
            # 动态颜色（status_color 取决于运行时状态），保留内联
            status_lbl.setStyleSheet(f"color: {status_color}; font-weight: bold;")
            header.addWidget(status_lbl)
            if rec.due_date:
                due_lbl = QLabel(f"截止: {rec.due_date}")
                due_lbl.setProperty("class", "hint-label")
                header.addWidget(due_lbl)
            header.addStretch()

            # 编辑/删除按钮
            btn_edit = QPushButton("编辑")
            btn_edit.setFixedHeight(24)
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.clicked.connect(lambda checked, r=rec: self._on_edit_capa(r))
            header.addWidget(btn_edit)

            btn_del = QPushButton("删除")
            btn_del.setFixedHeight(24)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, r=rec: self._on_delete_capa(r))
            header.addWidget(btn_del)

            card_layout.addLayout(header)

            # 措施内容
            action_lbl = QLabel(rec.action or "")
            action_lbl.setWordWrap(True)
            action_lbl.setProperty("class", "body-text")
            card_layout.addWidget(action_lbl)

            # 负责人
            assignee_name = getattr(rec, 'assignee_name', '') or ''
            if assignee_name:
                assignee_lbl = QLabel(f"负责人: {assignee_name}")
                assignee_lbl.setProperty("class", "hint-label")
                card_layout.addWidget(assignee_lbl)

            # PDCA 字段：根因分析
            root_cause = getattr(rec, 'root_cause', '') or ''
            if root_cause:
                rc_lbl = QLabel(f"根因分析: {root_cause}")
                rc_lbl.setWordWrap(True)
                rc_lbl.setProperty("class", "cause-text-sm")
            else:
                rc_lbl = QLabel("根因分析: 待填写")
                rc_lbl.setProperty("class", "hint-italic")
            card_layout.addWidget(rc_lbl)

            # PDCA 字段：效果验证
            effectiveness = getattr(rec, 'effectiveness', '') or ''
            if effectiveness:
                eff_lbl = QLabel(f"效果验证: {effectiveness}")
                eff_lbl.setWordWrap(True)
                eff_lbl.setProperty("class", "success-text")
            else:
                eff_lbl = QLabel("效果验证: 待填写")
                eff_lbl.setProperty("class", "hint-italic")
            card_layout.addWidget(eff_lbl)

            # PDCA 字段：改善追踪
            follow_up = getattr(rec, 'follow_up', '') or ''
            if follow_up:
                fu_lbl = QLabel(f"改善追踪: {follow_up}")
                fu_lbl.setWordWrap(True)
                fu_lbl.setProperty("class", "track-text")
            else:
                fu_lbl = QLabel("改善追踪: 待填写")
                fu_lbl.setProperty("class", "hint-italic")
            card_layout.addWidget(fu_lbl)

            # 验证结果
            if rec.verification_result:
                v_lbl = QLabel(f"验证: {rec.verification_result}")
                v_lbl.setWordWrap(True)
                v_lbl.setProperty("class", "success-text")
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
                 issue: Issue | None = None,
                 parent: QWidget | None = None):
        is_edit = capa_record is not None
        title = "编辑 CAPA 措施" if is_edit else "新建 CAPA 措施"
        super().__init__(title, parent, width=520)

        self._capa_record = capa_record
        self._technician_list = technician_list or []

        # 新建模式：显示关联 Issue 参考信息
        if not is_edit and issue:
            parts = [issue.title]
            if getattr(issue, "failure_mode", ""):
                parts.append(f"失效模式: {issue.failure_mode}")
            desc = getattr(issue, "description", "")
            if desc:
                parts.append(desc[:120])
            ref_text = "\n".join(parts)
            ref_label = QLabel(ref_text)
            ref_label.setWordWrap(True)
            ref_label.setProperty("class", "ref-info")
            self._form.addRow("关联 Issue", ref_label)

        self._action_edit = self._add_text_area(
            "措施描述",
            default=(capa_record.action or "") if is_edit else "",
            placeholder="描述纠正或预防措施",
        )
        self._due_date_edit = self._add_date_field("截止日期")
        # 编辑模式：恢复已保存的截止日期
        if is_edit and capa_record.due_date:
            from PySide6.QtCore import QDate
            d = QDate.fromString(capa_record.due_date, "yyyy-MM-dd")
            if d.isValid():
                self._due_date_edit.setDate(d)

        # 负责人（自由输入）
        self._assignee_edit = self._add_text_field(
            "负责人",
            default=(capa_record.assignee_name or "") if is_edit else (
                getattr(issue, "dri_name", "") or "" if issue else ""
            ),
            placeholder="输入负责人姓名",
        )

        # 验证人（自由输入，一直显示）
        self._verifier_edit = self._add_text_field(
            "验证人",
            default=(capa_record.verifier_name or "") if is_edit and hasattr(capa_record, "verifier_name") else "",
            placeholder="输入验证人姓名",
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
            default=(capa_record.root_cause or "") if is_edit else (
                getattr(issue, "root_cause", "") or "" if issue else ""
            ),
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
        verifier_name = self._verifier_edit.text().strip()
        data = {
            "action": self._action_edit.toPlainText().strip(),
            "due_date": self._due_date_edit.date().toString("yyyy-MM-dd")
                if self._due_date_edit.date().isValid()
                else "",
            "assignee_id": None,
            "assignee_name": assignee_name,
            "verifier_name": verifier_name,
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
        # 职责分离检查：验证人不能是负责人
        status_map = {label: val for label, val in self._STATUS_OPTIONS}
        status = status_map.get(self._status_combo.currentText(), "pending")
        if status == "verified":
            assignee_name = self._assignee_edit.text().strip()
            verifier_name = self._verifier_edit.text().strip()
            if verifier_name and assignee_name and verifier_name == assignee_name:
                QMessageBox.warning(
                    self, "职责分离冲突",
                    f"按质量管理要求，验证人不应与负责人为同一人。\n\n"
                    f"当前负责人：{assignee_name}\n"
                    f"当前验证人：{verifier_name}\n\n"
                    f"请修改后再保存。",
                )
                return
            if not verifier_name:
                reply = QMessageBox.question(
                    self, "验证人未指定",
                    "状态为「已验证」但未指定验证人。\n\n"
                    "建议填写验证人以确保职责分离。仍要继续吗？",
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
        super().accept()
