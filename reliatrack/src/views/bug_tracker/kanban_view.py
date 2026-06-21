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

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, Signal, QTimer
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPalette,
)
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
from src.models.issue import Issue
from src.services.issue_service import IssueService
from src.styles.constants import (
    STATUS_GREEN,
    STATUS_BLUE,
    STATUS_RED,
    STATUS_YELLOW,
    STATUS_PEACH,
    STATUS_OVERLAY,
    ISSUE_STATUS_COLORS,
    ISSUE_SEVERITY_COLORS,
    PRIORITY_COLORS,
    PADDING_SMALL,
    PADDING_MEDIUM,
    PADDING_LARGE,
    VIEW_MARGINS,
)
from src.styles.toast import ToastWidget
from src.constants import ISSUE_STATUS_LABELS, PRIORITY_LABELS, SEVERITY_LABELS

# ── Aging 色块阈值 ──────────────────────────────────────────────
_AGING_THRESHOLD_LOW = 3      # <3 天 → 绿色
_AGING_THRESHOLD_MID = 7      # 3-7 天 → 黄色, >7 天 → 红色
_CLOSED_FOLD_DAYS = 30        # closed 列折叠阈值（天）


def _aging_color(days: int) -> str:
    """根据停留天数返回色块颜色。"""
    if days < _AGING_THRESHOLD_LOW:
        return STATUS_GREEN
    if days <= _AGING_THRESHOLD_MID:
        return STATUS_YELLOW
    return STATUS_RED


def _make_font(pixel_size: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(pixel_size)
    f.setBold(bold)
    return f


_FONT_CARD_TITLE = _make_font(13, bold=True)
_FONT_CARD_META = _make_font(11)
_FONT_COLUMN_HEADER = _make_font(14, bold=True)
_FONT_BADGE = _make_font(11, bold=True)
_FONT_COLLAPSED = _make_font(12)


# ═══════════════════════════════════════════════════════════════════
#  _KanbanCard
# ═══════════════════════════════════════════════════════════════════


class _KanbanCard(QFrame):
    """看板卡片小部件 — 显示 Issue 关键信息，支持拖拽。

    布局（横向压缩）:
      ┌──────────────────────────────────┐
      │ 标题文本（单行省略）              │
      │ [●严重度] [P1-P5]  指派人  [aging]│
      └──────────────────────────────────┘
    """

    clicked = Signal(int)       # 单击（同位置释放）
    double_clicked = Signal(int)  # 双击
    drag_started = Signal(int)   # 拖拽开始

    # 卡片固定尺寸
    CARD_WIDTH = 180
    CARD_HEIGHT = 68

    def __init__(self, issue: Issue, aging_days: int = 0,
                 assignee_name: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._issue = issue
        self._aging_days = aging_days
        self._assignee_name = assignee_name  # Fix 1: 解析后的人名（非 ID）
        self._drag_start_pos: QPoint | None = None
        self._drag_started = False

        self.setProperty("class", "kanban-card")
        # 宽度跟随列伸缩，高度固定
        self.setMinimumHeight(self.CARD_HEIGHT)
        self.setMaximumHeight(self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAcceptDrops(False)
        self._setup_ui()
        self._apply_card_style()

    # ── 属性 ───────────────────────────────────────────────────

    @property
    def issue_id(self) -> int:
        return self._issue.id if self._issue.id is not None else 0

    @property
    def issue_status(self) -> str:
        return self._issue.status

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_MEDIUM, PADDING_SMALL,
                                  PADDING_MEDIUM, PADDING_SMALL)
        layout.setSpacing(4)

        # 第 1 行: 标题（单行省略）
        self._title_label = QLabel(self._issue.title)
        self._title_label.setFont(_FONT_CARD_TITLE)
        self._title_label.setWordWrap(False)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._title_label.setFixedHeight(18)
        layout.addWidget(self._title_label)

        # 第 2 行: 严重徽标 + 优先级 + 指派人 + aging
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        # 严重度徽标（彩色圆点 + 标签）
        severity_color = ISSUE_SEVERITY_COLORS.get(
            self._issue.severity, STATUS_OVERLAY
        )
        severity_badge = QLabel(
            f"● {SEVERITY_LABELS.get(self._issue.severity, self._issue.severity)}"
        )
        severity_badge.setFont(_FONT_CARD_META)
        severity_badge.setStyleSheet(
            f"color: {severity_color}; background: transparent; border: none;"
        )
        meta_row.addWidget(severity_badge)

        # 优先级标记
        priority = self._issue.priority
        pri_color = PRIORITY_COLORS.get(priority, STATUS_OVERLAY)
        pri_label = QLabel(PRIORITY_LABELS.get(priority, f"P{priority}"))
        pri_label.setFont(_FONT_BADGE)
        pri_label.setStyleSheet(
            f"color: {pri_color}; background: transparent; border: none;"
        )
        meta_row.addWidget(pri_label)

        meta_row.addStretch()

        # 指派人（Fix 1: 显示人名，不再显示数字 ID）
        display_name = self._assignee_name or getattr(self._issue, "dri_name", "") or ""
        if display_name:
            assignee_label = QLabel(display_name)
        else:
            assignee_label = QLabel("—")
        assignee_label.setFont(_FONT_CARD_META)
        assignee_label.setProperty("class", "card-meta")
        meta_row.addWidget(assignee_label)

        # Aging 色块
        aging_label = QLabel(f"  {self._aging_days}d  ")
        aging_label.setFont(_FONT_CARD_META)
        aging_color = _aging_color(self._aging_days)
        aging_label.setStyleSheet(
            f"background-color: {aging_color}; color: #ffffff; "
            f"border-radius: 3px; padding: 1px 4px; border: none;"
        )
        meta_row.addWidget(aging_label)

        layout.addLayout(meta_row)

    def _apply_card_style(self) -> None:
        """更新卡片的背景边框样式（主题切换时调用）。"""
        border_color = _t.SURFACE1
        self.setStyleSheet(
            f"background-color: {_t.BG_CARD};"
            f"border: 1px solid {border_color};"
            f"border-radius: 8px;"
        )

    # ── 拖拽事件 ──────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._drag_started = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            super().mouseMoveEvent(event)
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self._drag_start_pos = None
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return

        # 检查是否超过拖拽启动距离
        delta = event.position().toPoint() - self._drag_start_pos
        drag_distance = QApplication.startDragDistance()
        if delta.manhattanLength() < drag_distance:
            super().mouseMoveEvent(event)
            return

        self._drag_started = True
        self.drag_started.emit(self.issue_id)

        # 启动 QDrag
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"issue:{self.issue_id}:{self._issue.status}")
        drag.setMimeData(mime)

        # 拖拽时的半透明缩略图
        pixmap = self.grab()
        painter = QPainter(pixmap)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_DestinationIn
        )
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 160))
        painter.end()
        drag.setPixmap(pixmap.scaled(
            self.CARD_WIDTH // 2, self.CARD_HEIGHT // 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        drag.setHotSpot(
            QPoint(self.CARD_WIDTH // 4, self.CARD_HEIGHT // 4)
        )

        self.setGraphicsEffect(None)
        result = drag.exec(Qt.DropAction.MoveAction)

        # 拖拽结束后恢复光标
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            super().mouseReleaseEvent(event)
            return
        if (event.button() == Qt.MouseButton.LeftButton
                and not self._drag_started):
            self.clicked.emit(self.issue_id)
        self._drag_start_pos = None
        self._drag_started = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        self.double_clicked.emit(self.issue_id)
        super().mouseDoubleClickEvent(event)

    # ── 主题刷新 ──────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """主题切换后重绘卡片样式。"""
        self._apply_card_style()


# ═══════════════════════════════════════════════════════════════════
#  _KanbanColumn
# ═══════════════════════════════════════════════════════════════════

_ColumnStatus = tuple[int, int]  # (current_count, history_count)


class _KanbanColumn(QFrame):
    """看板列 — 垂直排列卡片的容器，支持拖拽放下。

    closed 列自动折叠超过 30 天的历史卡片，显示:
      "已关闭(30天内 N条 · 历史 M条)"
    """

    status_changed = Signal(int, str)  # issue_id, new_status

    COLUMN_WIDTH = 210

    def __init__(self, status: str, label: str,
                 service: IssueService | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._label = label
        self._service = service
        self._cards: list[_KanbanCard] = []
        self._folded: bool = True           # closed 列折叠状态
        self._is_closed_col = (status == "closed")

        self.setProperty("class", "kanban-column")
        self.setMinimumWidth(self.COLUMN_WIDTH)  # 最小宽，允许拉伸填满空间
        self.setAcceptDrops(True)
        self._setup_ui()

    # ── 属性 ───────────────────────────────────────────────────

    @property
    def column_status(self) -> str:
        return self._status

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # --- 列头: 状态名称 + 计数 + 折叠按钮 ---
        header = QFrame()
        header.setProperty("class", "column-header")
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(PADDING_MEDIUM, PADDING_SMALL,
                                         PADDING_MEDIUM, PADDING_SMALL)

        # 状态颜色指示条
        color = ISSUE_STATUS_COLORS.get(self._status, STATUS_OVERLAY)
        color_dot = QLabel("●")
        color_dot.setFont(_FONT_COLUMN_HEADER)
        color_dot.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )
        header_layout.addWidget(color_dot)

        self._title_label = QLabel(self._label)
        self._title_label.setFont(_FONT_COLUMN_HEADER)
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel("0")
        self._count_label.setFont(_FONT_CARD_META)
        self._count_label.setProperty("class", "column-count")
        header_layout.addWidget(self._count_label)

        header_layout.addStretch()

        # 折叠/展开按钮（仅 closed 列显示）
        self._fold_btn = QPushButton("▾" if self._is_closed_col else "")
        self._fold_btn.setFont(_FONT_COLLAPSED)
        self._fold_btn.setFixedSize(24, 24)
        self._fold_btn.setProperty("class", "fold-btn")
        self._fold_btn.setVisible(self._is_closed_col)
        self._fold_btn.clicked.connect(self._toggle_fold)
        header_layout.addWidget(self._fold_btn)

        self._root_layout.addWidget(header)

        # --- 可滚动的卡片容器 ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setProperty("class", "column-scroll")

        self._card_container = QWidget()
        self._card_container.setProperty("class", "card-container")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(
            PADDING_SMALL, PADDING_SMALL,
            PADDING_SMALL, PADDING_SMALL,
        )
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()

        scroll.setWidget(self._card_container)
        self._root_layout.addWidget(scroll)

        # 折叠信息栏（closed 历史记录提示）
        self._fold_info = QLabel("")
        self._fold_info.setProperty("class", "fold-info")
        self._fold_info.setFont(_FONT_COLLAPSED)
        self._fold_info.setFixedHeight(28)
        self._fold_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fold_info.setVisible(False)
        self._fold_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fold_info.mousePressEvent = lambda _: self._toggle_fold()
        self._root_layout.addWidget(self._fold_info)

    # ── 卡片管理 ──────────────────────────────────────────────

    def set_cards(self, cards: list[_KanbanCard],
                  history_cards: list[_KanbanCard] | None = None) -> None:
        """设置列中的卡片。history_cards 仅在 closed 列使用。"""
        # 清空现有卡片（保留 stretch）
        self._clear_cards()
        self._cards = []

        if self._is_closed_col:
            # closed 列: 当前 30 天内 + 历史折叠
            recent = cards
            history = history_cards or []
            visible = recent if self._folded else recent + history
            self._cards = recent + history

            total_current = len(recent)
            total_history = len(history)

            # 更新标题
            if total_history > 0:
                self._title_label.setText(
                    f"{self._label} (30天内 {total_current}条"
                )
                # 折叠信息栏
                if self._folded:
                    self._fold_info.setText(
                        f"还有 {total_history} 条历史记录 ▾"
                    )
                else:
                    self._fold_info.setText(f"收起历史记录 ▴")
                self._fold_info.setVisible(True)
            else:
                self._title_label.setText(self._label)
                self._fold_info.setVisible(False)
        else:
            self._cards = cards

        # 插入可见卡片
        for card in visible if self._is_closed_col else cards:
            self._card_layout.insertWidget(
                self._card_layout.count() - 1, card  # 在 stretch 前
            )

        self._update_count()

    def _clear_cards(self) -> None:
        """移除所有卡片到临时列表但不删除。"""
        while self._card_layout.count() > 1:  # 保留 stretch
            item = self._card_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

    def _update_count(self) -> None:
        count = len(self._cards)
        self._count_label.setText(str(count))

    def _toggle_fold(self) -> None:
        """切换 closed 列的折叠/展开状态。"""
        if not self._is_closed_col:
            return
        self._folded = not self._folded
        self._fold_btn.setText("▴" if not self._folded else "▾")
        # 触发父视图重新加载（通过状态变更信号间接）
        # 实际刷新由 BugKanbanView._load_issues 处理
        parent = self.parent()
        while parent and not isinstance(parent, BugKanbanView):
            parent = parent.parent()
        if parent and hasattr(parent, "_load_issues"):
            parent._load_issues()

    # ── 拖拽放下 ──────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("issue:"):
                parts = text.split(":")
                if len(parts) >= 3:
                    current_status = parts[2]
                    if current_status != self._status:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("issue:"):
                parts = text.split(":")
                if len(parts) >= 3 and parts[2] != self._status:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasText():
            event.ignore()
            return

        text = event.mimeData().text()
        if not text.startswith("issue:"):
            event.ignore()
            return

        parts = text.split(":")
        if len(parts) < 3:
            event.ignore()
            return

        try:
            issue_id = int(parts[1])
        except (ValueError, IndexError):
            event.ignore()
            return

        # 验证目标状态不同
        current_status = parts[2]
        if current_status == self._status:
            event.ignore()
            return

        event.acceptProposedAction()
        self.status_changed.emit(issue_id, self._status)

    # ── 主题刷新 ──────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """主题切换后重绘列样式。"""
        border = _t.SURFACE1
        self.setStyleSheet(
            f"background-color: {_t.MANTLE};"
            f"border: 1px solid {border};"
            f"border-radius: 10px;"
        )
        header_style = (
            f"background-color: {_t.MANTLE};"
            f"border-top-left-radius: 10px;"
            f"border-top-right-radius: 10px;"
            f"border-bottom: 1px solid {border};"
        )
        # 由于 header 是 QFrame child，通过 class 间接设置
        self.findChild(QFrame, "", Qt.FindChildOption.FindChildrenRecursively)
        for child in self.findChildren(QFrame):
            if child.property("class") == "column-header":
                child.setStyleSheet(header_style)

        for card in self._cards:
            card.refresh_theme()


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

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索 Issue 标题...")
        self._search_input.setFixedWidth(220)
        self._search_input.setClearButtonEnabled(True)
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
        """卡片拖拽放下后执行状态转换。"""
        if self._service is None:
            return

        ok, reason = self._service.transition_status(
            issue_id, new_status, operator=self._operator,
        )
        if ok:
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
