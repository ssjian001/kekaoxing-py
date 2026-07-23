"""看板视图 — BugKanbanView + _KanbanCard + _KanbanColumn。

import logging
logger = logging.getLogger(__name__)
4 列（open / analyzing / verified / closed）布局，支持：
  - 跨列拖拽（QDrag + dropEvent + transition_status）
  - 卡片 aging 色块（<3d 绿 / 3-7d 黄 / >7d 红）
  - closed 列自动折叠超过 30 天的历史记录
  - 双击打开详情、快速创建、刷新
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QEvent, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t

from src.styles.animation import DropShadowAnimation, BackgroundAnimation
from src.models.issue import Issue
from src.services.issue_service import IssueService
from src.styles.constants import (
    PADDING_MEDIUM,
    PADDING_SMALL,
    VIEW_MARGINS,
)
from src.styles.toast import ToastWidget
from src.constants import ISSUE_STATUS_LABELS
from src.views.widgets.search_box import SearchBox

from src.views.widgets.kanban_card import _KanbanCard
from src.views.widgets.kanban_column import _KanbanColumn

# 常量
_CLOSED_FOLD_DAYS = 30  # closed 列折叠阈值（天）

# ═══════════════════════════════════════════════════════════════════
#  BugKanbanView
# ═══════════════════════════════════════════════════════════════════


class BugKanbanView(QWidget):
    """看板主视图 — 4 列水平排列（open / analyzing / verified / closed）。

    信号:
      - card_double_clicked(issue_id): 双击卡片打开详情
      - refresh_requested(): 要求外部刷新
    """

    card_double_clicked = Signal(int)
    refresh_requested = Signal()

    _COLUMN_STATUSES = ["open", "analyzing", "verified", "closed"]

    def __init__(self, service: IssueService,
                 parent: QWidget | None = None,
                 undo_manager=None) -> None:
        super().__init__(parent)
        self._service = service
        self._undo_manager = undo_manager
        self._columns: dict[str, _KanbanColumn] = {}
        self._all_issues: list[Issue] = []
        self._filters: dict[str, Any] = {}
        self._operator: str = ""  # 当前操作人
        self._technician_map: dict[int, str] = {}  # Fix 1: assignee_id → 人名映射
        self._base_issues: list[Issue] = []  # 外部注入的已筛选数据（不再自行 list_all）

        self._setup_ui()

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(*VIEW_MARGINS)
        root_layout.setSpacing(PADDING_MEDIUM)

        # ── 工具栏 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(PADDING_MEDIUM)

        self._btn_refresh = QPushButton("⟳ 刷新")
        self._btn_refresh.setProperty("class", "action")
        self._btn_refresh.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._btn_refresh)

        self._btn_create = QPushButton("＋ 新建")
        self._btn_create.setProperty("class", "primary")
        self._btn_create.clicked.connect(self._on_quick_create)
        toolbar.addWidget(self._btn_create)

        toolbar.addSpacing(16)

        self._search_input = SearchBox()
        self._search_input.setPlaceholderText("搜索 Issue 标题…")
        self._search_input.setFixedWidth(220)
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)

        toolbar.addStretch()

        root_layout.addLayout(toolbar)

        # ── 4 列滚动区域 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setProperty("class", "kanban-scroll")

        columns_widget = QWidget()
        columns_widget.setProperty("class", "columns-container")
        columns_layout = QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(PADDING_SMALL, 0,
                                          PADDING_SMALL, 0)
        columns_layout.setSpacing(PADDING_MEDIUM)

        for status in self._COLUMN_STATUSES:
            label = ISSUE_STATUS_LABELS.get(status, status)
            col = _KanbanColumn(status, label, self._service)
            col.status_changed.connect(self._on_card_dropped)
            self._columns[status] = col
            columns_layout.addWidget(col)
            columns_layout.setStretchFactor(col, 1)  # 4 列等分可用空间

        scroll.setWidget(columns_widget)
        root_layout.addWidget(scroll)

        # ── 空状态提示 ──
        self._empty_label = QLabel("暂无 Issue 数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "empty-label")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(scroll)
        self._empty_label.hide()

    # ── 数据加载 ──────────────────────────────────────────────

    def _load_issues(self) -> None:
        """从 _base_issues（已按项目筛选）分发到各列。"""
        search_text = self._search_input.text().strip().lower()

        issues = list(self._base_issues)

        if search_text:
            issues = [
                i for i in issues
                if search_text in i.title.lower()
            ]

        # 应用外部筛选条件（跳过 status — 看板按列展示）
        if self._filters:
            sev = self._filters.get("severity")
            priority = self._filters.get("priority")
            dri = self._filters.get("dri_name")
            date_from = self._filters.get("date_from")
            date_to = self._filters.get("date_to")

            filtered = []
            for i in issues:
                if sev and i.severity not in sev:
                    continue
                if priority and i.priority not in priority:
                    continue
                if dri and (i.dri_name or "") != dri:
                    continue
                if date_from and (i.created_at or "") < date_from:
                    continue
                if date_to and (i.created_at or "") > date_to:
                    continue
                filtered.append(i)
            issues = filtered

        self._all_issues = issues

        for status in self._COLUMN_STATUSES:
            column_issues = [i for i in issues if i.status == status]
            cards: list[_KanbanCard] = []
            history_cards: list[_KanbanCard] = []

            for issue in column_issues:
                try:
                    aging = self._service.get_aging_days(
                        issue.id if issue.id is not None else 0
                    )
                except Exception:
                    logger.exception("Error in kanban_view")
                    aging = 0

                card = _KanbanCard(
                    issue, aging,
                    assignee_name=issue.dri_name or "",
                )
                card.double_clicked.connect(self._on_card_double_clicked)

                if status == "closed":
                    # Fix 2: 按 updated_at（关闭操作时间）判断是否近 30 天，
                    # 而非 created_at（创建时间），避免刚关闭的老 Issue 被折叠
                    from datetime import datetime, timedelta
                    updated = issue.updated_at or issue.created_at or ""
                    is_recent = False
                    if updated:
                        try:
                            dt = datetime.strptime(updated[:10], "%Y-%m-%d")
                            is_recent = (
                                datetime.now() - dt
                            ) <= timedelta(days=_CLOSED_FOLD_DAYS)
                        except (ValueError, TypeError):
                            is_recent = False
                    if is_recent:
                        cards.append(card)
                    else:
                        history_cards.append(card)
                else:
                    cards.append(card)

            col = self._columns[status]
            col.set_cards(cards, history_cards if status == "closed" else None)

        # 空状态：全部列均无卡片时显示提示
        total = sum(len(col._cards) for col in self._columns.values())
        self._scroll_area_empty_state(total)

    def set_issues(self, issues: list[Issue] | None = None) -> None:
        """外部注入已筛选数据，然后渲染。"""
        if issues is not None:
            self._base_issues = issues
        self._load_issues()

    def set_filters(self, filters: dict[str, Any]) -> None:
        """设置筛选条件并刷新。"""
        self._filters = filters
        self._load_issues()

    # ── 工具栏操作 ────────────────────────────────────────────

    def _on_refresh(self) -> None:
        """刷新所有列。"""
        self._load_issues()
        self.refresh_requested.emit()

    def _on_quick_create(self) -> None:
        """打开快速创建弹窗。"""
        from src.views.bug_tracker.quick_create import QuickCreateDialog
        dlg = QuickCreateDialog(self)
        if dlg.exec() == QuickCreateDialog.DialogCode.Accepted:
            data = dlg.result_data()
            if data:
                try:
                    issue_id = self._service.create(
                        title=data["title"],
                        severity=data["severity"],
                        priority=data["priority"],
                        description=data.get("description", ""),
                    )
                    if issue_id:
                        ToastWidget.show_toast(
                            self, f"Issue #{issue_id} 创建成功",
                            ToastWidget.SUCCESS,
                        )
                        self._load_issues()
                        self.refresh_requested.emit()
                except Exception as exc:
                    logger.exception("Error in kanban_view")
                    ToastWidget.show_toast(
                        self, f"创建失败: {exc}",
                        ToastWidget.ERROR,
                    )

    def _on_search(self, text: str) -> None:
        """搜索输入后过滤列表。"""
        self._load_issues()

    # ── 拖拽处理 ──────────────────────────────────────────────

    def _on_card_dropped(self, issue_id: int, new_status: str) -> None:
        """卡片拖拽放下后执行状态转换（带 Undo 追踪）。"""
        if self._service is None:
            return

        # 获取旧状态
        issue = self._service.get(issue_id)
        if issue is None:
            return
        old_status = issue.status
        if old_status == new_status:
            return

        ok, reason = self._service.transition_status(
            issue_id, new_status, operator=self._operator,
        )
        if ok:
            # 通过 UndoManager 记录（命令已执行，只入栈管理）
            if self._undo_manager is not None:
                from src.services.undo_manager import TransitionIssueStatusCommand
                cmd = TransitionIssueStatusCommand(
                    self._service, issue_id, old_status, new_status,
                    operator=self._operator,
                )
                self._undo_manager.record(cmd)
            ToastWidget.show_toast(
                self, f"Issue #{issue_id} → {ISSUE_STATUS_LABELS.get(new_status, new_status)}",
                ToastWidget.SUCCESS,
            )
            # 刷新各列
            self._load_issues()
            self.refresh_requested.emit()
        else:
            ToastWidget.show_toast(
                self, f"状态变更失败: {reason}",
                ToastWidget.ERROR,
            )
            # 回滚：重新加载恢复原状
            self._load_issues()

    # ── 卡片交互 ──────────────────────────────────────────────

    def _scroll_area_empty_state(self, total_cards: int) -> None:
        """空状态提示的显隐控制。"""
        if total_cards == 0:
            # 获取 scroll 区域作为父容器
            scroll = self.findChild(QScrollArea)
            if scroll and self._empty_label:
                self._empty_label.setGeometry(scroll.viewport().rect())
                self._empty_label.raise_()
                self._empty_label.show()
        else:
            self._empty_label.hide()

    def _on_card_double_clicked(self, issue_id: int) -> None:
        """卡片双击 → 发射信号给父视图打开详情。"""
        self.card_double_clicked.emit(issue_id)

    # ── 公开接口 ──────────────────────────────────────────────

    def set_operator(self, operator: str) -> None:
        """设置当前操作人（用于活动日志）。"""
        self._operator = operator

    def set_technician_map(self, tech_map: dict[int, str]) -> None:
        """Fix 1: 注入 assignee_id → 人名映射，看板卡片显示人名而非数字 ID。"""
        self._technician_map = tech_map

    def refresh(self) -> None:
        """外部刷新入口。"""
        self._load_issues()

    def refresh_theme(self) -> None:
        """主题切换后刷新所有卡片和列的样式。"""
        for col in self._columns.values():
            col.refresh_theme()

    # ── 外部设置 IssueService（用于延迟初始化） ───────────────

    def set_service(self, service: IssueService) -> None:
        """设置或更新 IssueService 引用。"""
        self._service = service
