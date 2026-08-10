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
from src.views.widgets.search_box import SearchBox

import src.styles.theme as _t
from src.models.todo import TodoItem
from src.models.project import Project
from src.styles.animation import DropShadowAnimation, BackgroundAnimation
from src.styles.constants import VIEW_MARGINS
from src.views.quadrant_view import QuadrantView

from src.views.widgets.todo_card import TodoCard, _priority_color
from src.views.widgets.todo_column import KanbanColumn
from src.views.widgets.todo_globals import _global_signals

# 常量
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


# ═══════════════════════════════════════════════════════════════════
#  TodoView
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
#  TodoView
# ═══════════════════════════════════════════════════════════════════


class TodoView(QWidget):
    """待办视图 — 看板 + 四象限子 Tab + 工具栏搜索。"""

    todo_changed = Signal()
    quadrant_changed = Signal(int, int)  # todo_id, new_quadrant

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
        self._project_combo.setProperty("class", "filter-combo")
        self._project_combo.setMinimumWidth(140)
        self._project_combo.addItem("全部项目", None)
        self._project_combo.currentIndexChanged.connect(self._on_project_filter)
        row.addWidget(self._project_combo)

        # 搜索框
        self._search_edit = SearchBox()
        self._search_edit.setPlaceholderText("搜索待办…")
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

    # ── 主题刷新 ────────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """主题切换后刷新。按鈕樣式由 QSS class 自動更新，只需刷新自定義組件。"""
        # 列卡片
        for col in self._columns.values():
            for card in col._cards:
                card.refresh_theme()
        # 四象限视图
        self._quadrant_view.refresh_theme()
