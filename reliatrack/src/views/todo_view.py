"""待办事项 Tab — 看板（Kanban）视图 + 四象限子 Tab。

包含看板 3 列（待处理 / 进行中 / 已完成）和 Eisenhower 四象限视图，
通过 SegmentedWidget 子导航切换。顶部工具栏含项目筛选 + 搜索框。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMimeData, QDate, QPoint, Qt, Signal, QObject
from PySide6.QtGui import QDrag, QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.views.widgets.segmented_widget import SegmentedWidget

import src.styles.theme as _t
from src.models.todo import TodoItem
from src.models.project import Project
from src.styles.animation import DropShadowAnimation, BackgroundAnimation
from src.styles.constants import VIEW_MARGINS
from src.views.quadrant_view import QuadrantView

# ── 常量 ───────────────────────────────────────────────────────

def _priority_color(priority: str) -> str:
    """优先级色点颜色（运行时读取，跟随主题）。"""
    return {
        "high": _t.RED,
        "medium": _t.WARNING,
        "low": _t.GREEN,
    }.get(priority, _t.FG_MUTED)

# 看板 3 列
_COLUMNS: list[tuple[str, str, str]] = [
    ("pending",     "待处理",   "kanban-col-pending"),
    ("in_progress", "进行中", "kanban-col-progress"),
    ("done",        "已完成",  "kanban-col-done"),
]
_MIME_TODO_ID = "application/x-todo-id"

_TODO_FILTER_FIELDS = {
    "title": ("標題", "text"),
    "priority": ("優先級", "int"),
    "category": ("分類", "text"),
    "due_date": ("到期日", "date"),
}

# ── 字体 ────────────────────────────────────────────────────────

_FONT_CARD_TITLE = QFont()
_FONT_CARD_TITLE.setPixelSize(13)
_FONT_CARD_TITLE.setBold(True)
_FONT_CARD_META = QFont()
_FONT_CARD_META.setPixelSize(11)


# ═══════════════════════════════════════════════════════════════════
#  TodoCard
# ═══════════════════════════════════════════════════════════════════


class TodoCard(QFrame):
    """看板卡片 — 标题 + 优先级色点 + 日期 + tag。"""

    selected = Signal(int)  # card clicked (todo_id)

    def __init__(self, todo: TodoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo = todo
        self._selected = False
        self._drag_start: QPoint | None = None
        self._setup_ui()
        self._bg_anim = BackgroundAnimation(self)
        self._shadow_anim = DropShadowAnimation(self)
        self._shadow_anim.setup(blur=10, offset_y=2, normal_alpha=0, hover_alpha=25)

    def _setup_ui(self) -> None:
        self.setFixedHeight(68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("class", "card-container")
        self._build_content()

    def _apply_style(self) -> None:
        """选中态样式（用 inline 因为状态动态切换）。"""
        if self._selected:
            self.setStyleSheet(
                f"QFrame{{background:{_t.SELECTION_BG};border:2px solid {_t.ACCENT};"
                f"border-radius:8px;}}"
            )
        else:
            self.setStyleSheet("")  # 恢复 QSS 默认

    def set_selected(self, selected: bool) -> None:
        """设置选中状态并更新样式。"""
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_style()

    def refresh_theme(self) -> None:
        """主题切换后刷新内联颜色（选中态）。"""
        self._apply_style()

    def _build_content(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # 第一行：优先级色点 + 标题
        top = QHBoxLayout()
        top.setSpacing(6)
        color = _priority_color(self._todo.priority)

        title = QLabel(self._todo.title)
        title.setFont(_FONT_CARD_TITLE)
        title.setProperty("class", "card-title")
        title.setWordWrap(True)
        title.setMaximumHeight(36)
        top.addWidget(title, stretch=1)
        layout.addLayout(top)

        # 第二行：日期 + tag
        meta = QHBoxLayout()
        meta.setSpacing(6)

        if self._todo.due_date:
            d = QDate.fromString(self._todo.due_date, "yyyy-MM-dd")
            today = QDate.currentDate()
            if self._todo.is_done:
                date_text = "✓ 已完成"
            elif d.isValid() and d < today:
                date_text = f"⚠ 逾期 {today.daysTo(d)} 天" if today.daysTo(d) < 0 else "⚠ 逾期"
            elif d.isValid() and d == today:
                date_text = "今天"
            else:
                date_text = f"{self._todo.due_date}"
            date_lbl = QLabel(date_text)
            date_lbl.setFont(_FONT_CARD_META)
            date_lbl.setProperty("class", "hint-label")
            meta.addWidget(date_lbl)

        if self._todo.category:
            tag = QLabel(self._todo.category)
            tag.setFont(_FONT_CARD_META)
            tag.setProperty("class", "filter-chip")
            meta.addWidget(tag)

        meta.addStretch()
        layout.addLayout(meta)

    def todo_id(self) -> int | None:
        return self._todo.id

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """单击选中卡片，记录拖拽起点。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            if self._todo.id is not None:
                self.selected.emit(self._todo.id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """移动超过阈值才启动拖拽，避免单击即触发 drag。"""
        if self._drag_start is None or self._todo.id is None:
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 5:
            return super().mouseMoveEvent(event)
        self._start_drag()

    def _start_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(_MIME_TODO_ID, str(self._todo.id or "").encode())
        drag.setMimeData(mime)
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event) -> None:
        """双击编辑。"""
        if self._todo.id is not None:
            from src.views.todo_view import _global_edit_request
            _global_edit_request.emit(self._todo.id)
        super().mouseDoubleClickEvent(event)


# 全局信号，避免循环 import
class _GlobalSignals(QObject):
    edit_requested = Signal(int)
_global_signals = _GlobalSignals()
_global_edit_request = _global_signals.edit_requested


# ═══════════════════════════════════════════════════════════════════
#  KanbanColumn
# ═══════════════════════════════════════════════════════════════════


class KanbanColumn(QFrame):
    """看板列 — 带标题头和大片拖放区域。"""

    todo_dropped = Signal(int, str)  # todo_id, new_status
    card_selected = Signal(int)     # card clicked (todo_id)

    def __init__(self, status: str, label: str, col_class: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._label = label
        self._col_class = col_class
        self._cards: list[TodoCard] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setProperty("class", self._col_class)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 列标题
        head = QHBoxLayout()
        head.setSpacing(6)
        lbl = QLabel(self._label)
        lbl.setProperty("class", "kanban-col-header")
        hdr_font = QFont()
        hdr_font.setPixelSize(14)
        hdr_font.setBold(True)
        lbl.setFont(hdr_font)
        head.addWidget(lbl)
        self._count = QLabel("0")
        self._count.setProperty("class", "kanban-count")
        head.addWidget(self._count)
        head.addStretch()
        layout.addLayout(head)

        # 滚动卡片列表
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._card_container = QWidget()
        self._card_container.setStyleSheet("background:transparent;border:none;")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, stretch=1)

    def set_cards(self, todos: list[TodoItem]) -> None:
        """替换列内所有卡片。"""
        # 清除旧卡片
        for card in self._cards:
            self._card_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        self._count.setText(str(len(todos)))
        for todo in todos:
            card = TodoCard(todo)
            card.selected.connect(self.card_selected.emit)
            self._cards.append(card)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(_MIME_TODO_ID):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(_MIME_TODO_ID):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        data = event.mimeData().data(_MIME_TODO_ID)
        try:
            todo_id = int(data.data().decode())
        except (ValueError, TypeError):
            return
        self.todo_dropped.emit(todo_id, self._status)
        event.acceptProposedAction()

    def count(self) -> int:
        return len(self._cards)


# ═══════════════════════════════════════════════════════════════════
#  TodoView
# ═══════════════════════════════════════════════════════════════════


class TodoView(QWidget):
    """待办视图 — 看板 + 四象限子 Tab + 工具栏搜索。"""

    todo_changed = Signal()
    toggle_requested = Signal(int)
    quadrant_changed = Signal(int, int)  # todo_id, new_quadrant
    archive_requested = Signal(int)  # todo_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo_list: list[TodoItem] = []
        self._all_projects: list[Project] = []
        self._selected_todo_id: int | None = None
        self._selected_card: TodoCard | None = None
        self._setup_ui()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 1. 筛选行：项目 + 搜索 + 显示归档
        self._build_filter_row(layout)

        # 2. 操作行：快速添加 + 操作按钮靠右
        self._build_action_row(layout)

        # 子 Tab 切换
        self._sub_tabs = SegmentedWidget()
        self._stack = QStackedWidget()

        # 看板视图
        self._kanban_widget = self._build_kanban_view()
        self._stack.addWidget(self._kanban_widget)

        # 四象限视图
        self._quadrant_view = QuadrantView()
        self._quadrant_view.quadrant_changed.connect(self._on_quadrant_changed)
        self._stack.addWidget(self._quadrant_view)

        self._sub_tabs.addSegment("看板")
        self._sub_tabs.addSegment("四象限")
        self._sub_tabs.setStackedWidget(self._stack)

        layout.addWidget(self._sub_tabs)
        layout.addWidget(self._stack, stretch=1)

        # 双击编辑信号路由
        _global_signals.edit_requested.connect(self._on_card_edit)

    def _build_kanban_view(self) -> QWidget:
        """构建看板 3 列内容，返回 QWidget。"""
        widget = QWidget()
        self._kanban_board = QHBoxLayout(widget)
        self._kanban_board.setContentsMargins(8, 4, 8, 8)
        self._kanban_board.setSpacing(8)

        self._columns: dict[str, KanbanColumn] = {}
        for status, label, cls in _COLUMNS:
            col = KanbanColumn(status, label, cls)
            col.todo_dropped.connect(self._on_todo_dropped)
            col.card_selected.connect(self._on_card_selected)
            self._columns[status] = col
            self._kanban_board.addWidget(col, stretch=1)

        return widget

    def _toggle_empty_state(self, count: int) -> None:
        """空状态提示显隐。"""
        # 由子类 call 暂不实现，后续可加 UI 提示

    def _build_filter_row(self, parent_layout: QVBoxLayout) -> None:
        """筛选行：项目选择 + 搜索 + 显示归档。"""
        row = QHBoxLayout()
        row.setContentsMargins(*VIEW_MARGINS)
        row.setSpacing(6)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(140)
        self._project_combo.addItem("全部项目", None)
        self._project_combo.currentIndexChanged.connect(self._on_project_filter)
        row.addWidget(self._project_combo)

        # 搜索框
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索待办…")
        self._search_edit.setFixedHeight(26)
        self._search_edit.setMaximumWidth(160)
        self._search_edit.textChanged.connect(self._on_search)
        row.addWidget(self._search_edit)

        from src.views.widgets.switch_button import SwitchButton
        self._show_archived_cb = SwitchButton("显示已归档")
        self._show_archived_cb.toggled.connect(self._refresh_current_view)
        row.addWidget(self._show_archived_cb)

        row.addStretch()
        parent_layout.addLayout(row)

    def _build_action_row(self, parent_layout: QVBoxLayout) -> None:
        """操作行：快速添加靠左 · 编辑/删除/归档靠右。"""
        row = QHBoxLayout()
        row.setContentsMargins(*VIEW_MARGINS)
        row.setSpacing(6)

        # 快速添加輸入框
        self._quick_add = QLineEdit()
        self._quick_add.setPlaceholderText("快速添加待办，回车即创建…")
        self._quick_add.setClearButtonEnabled(True)
        self._quick_add.setFixedHeight(26)
        self._quick_add.setMinimumWidth(200)
        self._quick_add.setProperty("class", "quick-add-input")
        self._quick_add.returnPressed.connect(self._on_quick_add)
        row.addWidget(self._quick_add)

        self._btn_quick_add = QPushButton("添加")
        self._btn_quick_add.setProperty("class", "pill-primary")
        self._btn_quick_add.setFixedHeight(26)
        self._btn_quick_add.clicked.connect(self._on_quick_add)
        row.addWidget(self._btn_quick_add)

        row.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "pill-outline")
        self.btn_edit.setFixedHeight(26)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "pill-danger")
        self.btn_delete.setFixedHeight(26)

        self.btn_archive = QPushButton("归档")
        self.btn_archive.setProperty("class", "pill-outline")
        self.btn_archive.setFixedHeight(26)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(18)
        sep.setProperty("class", "sep-vline")

        row.addWidget(self.btn_edit)
        row.addWidget(self.btn_delete)
        row.addWidget(self.btn_archive)
        row.addWidget(sep)

        parent_layout.addLayout(row)

    def _build_quick_add(self, parent_layout: QVBoxLayout) -> None:
        pass  # 快速添加已合併到 _build_toolbar

    # ── Public API ─────────────────────────────────────────────

    def refresh(self, todo_list: list[TodoItem], projects: list[Project] | None = None) -> None:
        if projects is not None:
            self.set_projects(projects)
        self._todo_list = todo_list
        filtered = self._filter_todos(todo_list)
        self._populate_kanban(filtered)
        self._quadrant_view.refresh(filtered)

    def set_projects(self, projects: list[Project]) -> None:
        self._all_projects = projects
        self._project_combo.blockSignals(True)
        cur = self._project_combo.currentData()
        self._project_combo.clear()
        self._project_combo.addItem("全部项目", None)
        for p in projects:
            self._project_combo.addItem(p.name, p.id)
        if cur is not None:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == cur:
                    self._project_combo.setCurrentIndex(i)
                    break
        self._project_combo.blockSignals(False)

    def get_selected_project_id(self) -> int | None:
        return self._project_combo.currentData()

    def get_selected_todo(self) -> TodoItem | None:
        """获取当前选中的待办。"""
        tid = self._selected_todo_id
        if tid is None:
            return None
        for t in self._todo_list:
            if t.id == tid:
                return t
        return None

    # ── 过滤 ────────────────────────────────────────────────────

    def _filter_todos(self, todo_list: list[TodoItem]) -> list[TodoItem]:
        """按项目 + 搜索 + 动态筛选条件过滤。"""
        pid = self._project_combo.currentData()
        search = self._search_edit.text().strip().lower() if hasattr(self, '_search_edit') else ""

        filtered = todo_list
        if pid is not None:
            filtered = [t for t in filtered if t.project_id == pid]
        if search:
            filtered = [
                t for t in filtered
                if search in t.title.lower()
                or (t.description and search in t.description.lower())
            ]
        # 归档过滤（除非勾选显示已归档）
        show_archived = hasattr(self, '_show_archived_cb') and self._show_archived_cb.isChecked()
        if not show_archived:
            filtered = [t for t in filtered if not t.archived]
        return filtered

    def _on_project_filter(self, _idx: int) -> None:
        self._refresh_current_view()

    def _on_search(self, _text: str) -> None:
        self._refresh_current_view()


    def _refresh_current_view(self) -> None:
        """刷新当前子 Tab 显示内容。"""
        filtered = self._filter_todos(self._todo_list)
        self._populate_kanban(filtered)
        if hasattr(self, '_quadrant_view'):
            self._quadrant_view.refresh(filtered)

    # ── 看板填充 ────────────────────────────────────────────────

    def _populate_kanban(self, filtered: list[TodoItem]) -> None:
        """按项目 filter 分配卡片到各列。"""
        self._selected_todo_id = None  # 清除选中（刷新后重建）
        self._selected_card = None

        groups: dict[str, list[TodoItem]] = {"pending": [], "in_progress": [], "done": []}
        for t in filtered:
            groups.setdefault(t.status, groups["pending"]).append(t)

        for status, col in self._columns.items():
            col.set_cards(groups.get(status, []))

        # 空状态：检查全部列
        in_view = sum(len(col._cards) for col in self._columns.values())
        self._toggle_empty_state(in_view)

    def _on_card_selected(self, todo_id: int) -> None:
        """卡片单击选中 — 取消旧选中，标记新选中。"""
        # 取消旧的选中高亮
        if self._selected_card is not None:
            self._selected_card.set_selected(False)
        self._selected_todo_id = todo_id
        self._selected_card = None
        # 找到新选中的卡片并高亮
        for col in self._columns.values():
            for card in col._cards:
                if card.todo_id() == todo_id:
                    card.set_selected(True)
                    self._selected_card = card
                    return

    def _on_quick_add(self) -> None:
        text = self._quick_add.text().strip()
        if not text:
            return
        self._quick_add.clear()
        self.quick_add_created.emit(text, self._project_combo.currentData())

    quick_add_created = Signal(str, object)

    def _on_todo_dropped(self, todo_id: int, new_status: str) -> None:
        """卡片拖拽到新列 → 触发状态变更。"""
        self._direct_status_change.emit(todo_id, new_status)

    _direct_status_change = Signal(int, str)  # todo_id, new_status

    def _on_card_edit(self, todo_id: int) -> None:
        """卡片双击编辑。"""
        self.btn_edit.click()

    def _on_quadrant_changed(self, todo_id: int, new_quadrant: int) -> None:
        """四象限拖拽变更 → 转发信号给 handler。"""
        self.quadrant_changed.emit(todo_id, new_quadrant)

    # ── 兼容旧 handler ─────────────────────────────────────────

    def emit_todo_changed(self) -> None:
        self.todo_changed.emit()

    # ── 主题刷新 ────────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """主题切换后刷新。按鈕樣式由 QSS class 自動更新，只需刷新自定義組件。"""
        # 列卡片
        for col in self._columns.values():
            for card in col._cards:
                card.refresh_theme()
        # 四象限视图
        self._quadrant_view.refresh_theme()
