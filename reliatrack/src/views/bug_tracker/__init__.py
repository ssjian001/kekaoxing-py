"""Bug Tracker 主视图容器 — 看板/列表 Tab 切换 + 快捷键 + 信号联动。"""

from __future__ import annotations

from typing import Any

import logging
logger = logging.getLogger("views.bug_tracker.__init__")
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QSizePolicy, QToolButton, QMenu,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, Signal

from src.styles import theme as _t_module
_t = _t_module
from src.styles.constants import *
from src.styles.toast import ToastWidget

from src.views.bug_tracker.kanban_view import BugKanbanView
from src.views.bug_tracker.list_view import BugListView
from src.views.bug_tracker.quick_create import QuickCreateDialog
from src.views.bug_tracker.detail_dialog import IssueDetailDialog
from src.views.bug_tracker.resolve_dialog import ResolveDialog
from src.views.bug_tracker.shortcuts import (
    register_bug_tracker_shortcuts,
    install_shortcut_focus_guard,
    ShortcutHandler,
    QuickSearchDialog,
)
from src.models.issue import Issue
from src.services.issue_service import IssueService


class BugTrackerView(QWidget):
    """Bug Tracker 主视图 — 看板/列表 切换 + 全局快捷键 + 信号联动。

    门面信号 — 转发 BugListView 的信号，供 issue_handlers 在 _build_views 之前连接。
    """

    # ── 门面信号（转发 _list_view）──
    issue_saved = Signal(dict)
    issue_deleted = Signal(int)
    issue_selected = Signal(object)
    fa_record_added = Signal(dict)
    fa_record_edited = Signal(dict)
    fa_record_deleted = Signal(int)
    capa_record_added = Signal(dict)
    capa_record_edited = Signal(dict)
    capa_record_deleted = Signal(int)
    export_8d_requested = Signal(int)

    def __init__(
        self,
        issue_service: IssueService,
        parent: QWidget | None = None,
        undo_manager=None,
    ) -> None:
        super().__init__(parent)
        self._svc = issue_service
        self._undo_manager = undo_manager
        self._project_filter_id: int | None = None  # 项目筛选 ID
        self._technician_map: dict[int, str] = {}   # assignee_id → 人名（detail_dialog 用）

        # 附件 action（门面属性，供 issue_handlers 连接）
        self._act_attachments = QAction("附件")
        self._act_attachments.setToolTip("管理附件")
        self._pending_context: dict = {}

        # 子视图
        self._kanban_view: BugKanbanView | None = None
        self._list_view: BugListView | None = None

        # 当前共享筛选
        self._current_filters: dict[str, Any] = {}

        self._setup_ui()
        self._register_shortcuts()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)
        layout.setSpacing(SPACING_SMALL)

        # ── 顶部 Tab 切换栏 ──
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(2)

        # 看板/列表/更多 统一用 QToolButton + tab 样式
        self._tab_kanban = QToolButton()
        self._tab_kanban.setText("看板")
        self._tab_kanban.setProperty("class", "tab-inactive")
        self._tab_kanban.setFixedHeight(26)
        self._tab_kanban.setCheckable(True)
        self._tab_kanban.clicked.connect(lambda: self._switch_tab(0))
        tab_bar.addWidget(self._tab_kanban)

        self._tab_list = QToolButton()
        self._tab_list.setText("列表")
        self._tab_list.setProperty("class", "tab-active")
        self._tab_list.setFixedHeight(26)
        self._tab_list.setCheckable(True)
        self._tab_list.setChecked(True)
        self._tab_list.clicked.connect(lambda: self._switch_tab(1))
        tab_bar.addWidget(self._tab_list)

        # 更多操作菜单
        self._more_menu = QMenu(self)
        self._act_new_issue = self._more_menu.addAction("新建 Issue")
        self._act_new_issue.setToolTip("新建 Issue (Ctrl+N)")
        self._act_edit_issue = self._more_menu.addAction("编辑 Issue")
        self._act_edit_issue.setToolTip("编辑选中的 Issue")
        self._more_menu.addSeparator()
        self._more_menu.addAction(self._act_attachments)
        self._act_export_8d = self._more_menu.addAction("导出 8D 报告")
        self._act_export_8d.setToolTip("将选中的 Issue 导出为 8D 报告")

        self._btn_more = QToolButton()
        self._btn_more.setText("更多")
        self._btn_more.setMenu(self._more_menu)
        self._btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_more.setProperty("class", "tab-inactive")
        self._btn_more.setFixedHeight(26)
        tab_bar.addWidget(self._btn_more)

        tab_bar.addStretch()

        # 状态信息区
        self._stats_label = QLabel("")
        self._stats_label.setProperty("class", "subtext")
        tab_bar.addWidget(self._stats_label)

        layout.addLayout(tab_bar)

        # ── 内容区 ──
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

    def _connect_signals(self) -> None:
        """连接内部信号（子视图构建后执行，由 _build_views 调用）。"""
        # 实际连接在 _build_views 中完成

    def _build_views(self) -> None:
        """延迟构建子视图（需要在 UI 显示后加载数据）。"""
        if self._kanban_view is not None:
            return

        self._kanban_view = BugKanbanView(self._svc, undo_manager=self._undo_manager)
        self._stack.addWidget(self._kanban_view)

        self._list_view = BugListView(self._svc, undo_manager=self._undo_manager)
        self._stack.addWidget(self._list_view)
        # 默认显示列表视图
        self._stack.setCurrentIndex(1)

        # 注入已缓存的 technician_map（set_technician_map 可能在 _build_views 前调用）
        if self._technician_map:
            self._kanban_view.set_technician_map(self._technician_map)
            self._list_view.set_technician_map(self._technician_map)
        # 注入缓存的上下文数据
        if self._pending_context:
            self._list_view.set_context_data(**self._pending_context)

        # 信号桥接
        self._kanban_view.card_double_clicked.connect(self._on_open_detail)
        self._kanban_view.refresh_requested.connect(self._refresh_all)

        self._list_view.card_double_clicked.connect(self._on_open_detail)
        self._list_view.refresh_requested.connect(self._refresh_all)
        self._list_view.filter_changed.connect(self._on_filter_changed)

        # 门面信号桥接: _list_view → BugTrackerView
        self._list_view.issue_saved.connect(self.issue_saved)
        self._list_view.issue_deleted.connect(self.issue_deleted)
        self._list_view.issue_selected.connect(self.issue_selected)
        self._list_view.fa_record_added.connect(self.fa_record_added)
        self._list_view.fa_record_edited.connect(self.fa_record_edited)
        self._list_view.fa_record_deleted.connect(self.fa_record_deleted)
        self._list_view.capa_record_added.connect(self.capa_record_added)
        self._list_view.capa_record_edited.connect(self.capa_record_edited)
        self._list_view.capa_record_deleted.connect(self.capa_record_deleted)
        self._list_view.export_8d_requested.connect(self.export_8d_requested)

        # 更多操作按钮
        self._act_new_issue.triggered.connect(self._list_view.open_create_issue_dialog)
        self._act_edit_issue.triggered.connect(self._list_view.open_edit_issue_dialog)
        self._act_export_8d.triggered.connect(self._on_export_8d)

        # 首次加载数据（统一走 _refresh_all 注入筛选后数据）
        self._refresh_all()

        self._switch_tab(1)

    def _switch_tab(self, index: int) -> None:
        """切换 0=看板 / 1=列表。"""
        self._tab_kanban.setProperty("class", "tab-active" if index == 0 else "tab-inactive")
        self._tab_list.setProperty("class", "tab-active" if index == 1 else "tab-inactive")
        self._tab_kanban.setChecked(index == 0)
        self._tab_list.setChecked(index == 1)
        # 刷新样式
        for btn in (self._tab_kanban, self._tab_list):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._stack.setCurrentIndex(index)
        self._update_stats()

    def _update_stats(self) -> None:
        """更新统计信息。"""
        try:
            issues = self._get_filtered_issues()
            total = len(issues)
            open_count = sum(1 for i in issues if i.status == "open")
            self._stats_label.setText(
                f"共 {total} 个 Issue · 待处理 {open_count}"
            )
        except Exception:
            logger.exception("_update_stats() failed")
            self._stats_label.setText("")

    def _on_open_detail(self, issue_id: int) -> None:
        """双击打开详情弹窗。"""
        issue = self._svc.get(issue_id)
        if issue is None:
            ToastWidget.show(self, "Issue 不存在", duration=2)
            return
        dlg = IssueDetailDialog(issue, self._svc, self,
                                technician_map=self._technician_map)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def _on_filter_changed(self, filters: dict[str, Any]) -> None:
        """筛选变更时同步到其他视图。"""
        self._current_filters = filters
        # 同步筛选条件到看板视图
        if self._kanban_view:
            self._kanban_view.set_filters(filters)

    def _get_filtered_issues(self) -> list:
        """获取按项目筛选的 Issue 列表（与 Issue 视图逻辑一致）。"""
        pid = self._project_filter_id
        if pid is not None:
            project_issues = self._svc.get_by_project(pid)
            null_issues = self._svc.get_unassigned()
            return project_issues + null_issues
        return self._svc.list_all()

    # ── 门面方法（转发到 _list_view）──

    @property
    def list_view(self):
        """暴露 BugListView（供 refresh_handlers 注入上下文）。"""
        return self._list_view

    def get_selected_issue_id(self):
        if self._list_view:
            return self._list_view.get_selected_issue_id()
        return None

    def refresh_fa(self, records):
        if self._list_view:
            self._list_view.refresh_fa(records)

    def refresh_capa(self, records):
        if self._list_view:
            self._list_view.refresh_capa(records)

    def set_context_data(self, **kwargs):
        """转发上下文数据到 BugListView（_list_view 延迟构建时缓存合并）。"""
        self._pending_context.update(kwargs)
        if self._list_view:
            self._list_view.set_context_data(**kwargs)

    @property
    def btn_attachments(self):
        """附件 action（门面属性）。"""
        return self._act_attachments

    @property
    def btn_export_8d(self):
        """8D 导出 action（门面属性）。"""
        return self._act_export_8d

    def _on_export_8d(self):
        """导出 8D 报告。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            ToastWidget.show(self, "请先选中一个 Issue", duration=2)
            return
        self.export_8d_requested.emit(issue_id)

    def refresh_theme(self):
        """主题切换后刷新。"""
        if self._kanban_view:
            self._kanban_view.refresh_theme()
        if self._list_view and hasattr(self._list_view, "refresh_theme"):
            self._list_view.refresh_theme()

    def set_project_filter(self, pid: int | None) -> None:
        """设置项目筛选 ID（与顶部项目下拉框联动）。"""
        self._project_filter_id = pid

    def _refresh_all(self) -> None:
        """刷新所有视图（统一注入已按项目筛选的数据）。"""
        issues = self._get_filtered_issues()
        if self._kanban_view:
            self._kanban_view.set_issues(issues)
        if self._list_view:
            self._list_view.set_issues(issues)
        self._update_stats()

    # ── 快捷键处理 ──

    def _register_shortcuts(self) -> None:
        handler = ShortcutHandler()
        handler.on_quick_create = self._on_quick_create
        handler.on_quick_search = self._on_quick_search
        handler.on_focus_search = self._on_focus_search
        handler.on_navigate_column = self._on_navigate_column
        shortcuts = register_bug_tracker_shortcuts(self, handler)
        install_shortcut_focus_guard(shortcuts, self)

    def _on_quick_create(self) -> None:
        """C 键 / Ctrl+N — 快速创建。"""
        dlg = QuickCreateDialog(self)
        if dlg.exec() == QuickCreateDialog.DialogCode.Accepted:
            data = dlg.result_data()
            if data:
                try:
                    iid = self._svc.create(**data)
                    ToastWidget.show(
                        self,
                        f"已创建 Issue #{iid}: {data['title'][:30]}{'…' if len(data['title']) > 30 else ''}",
                        duration=3,
                    )
                    self._refresh_all()
                except Exception as exc:
                    logger.exception("_on_quick_create() failed")
                    ToastWidget.show(self, f"创建失败: {exc}", duration=3)

    def _on_quick_search(self) -> None:
        """Ctrl+K — 快捷搜索。"""
        issues = self._get_filtered_issues() if self._svc else []
        dlg = QuickSearchDialog(issues, self)
        dlg.issue_selected.connect(self._on_open_detail)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_focus_search(self) -> None:
        """/ 键 — 聚焦当前视图的搜索框。"""
        view = self._stack.currentWidget()
        if view and hasattr(view, "focus_search"):
            view.focus_search()

    def _on_navigate_column(self, direction: int) -> None:
        """← → 键 — 看板列焦点切换。"""
        view = self._stack.currentWidget()
        if view and hasattr(view, "navigate_column"):
            view.navigate_column(direction)

    # ── 公开接口 ──

    def init_views(self) -> None:
        """首次加载数据（由父视图在 showEvent 后调用）。"""
        self._build_views()

    def refresh(self, issues=None) -> None:
        """外部刷新入口（主题切换后 / 侧栏切换回时）。issues 参数兼容旧接口，内部从 service 加载。"""
        if self._kanban_view is None:
            self._build_views()
        else:
            self._refresh_all()

    def set_technician_map(self, tech_map: dict[int, str]) -> None:
        """转发 technician_map 到看板 + 列表视图。"""
        self._technician_map = tech_map
        if self._kanban_view:
            self._kanban_view.set_technician_map(tech_map)
        if self._list_view:
            self._list_view.set_technician_map(tech_map)

    def showEvent(self, event):
        """首次显示时构建视图。"""
        super().showEvent(event)
        self._build_views()
