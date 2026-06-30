"""待办事项 Tab — 看板（Kanban）视图。

3 列（待处理 / 进行中 / 已完成），卡片拖拽切换状态。
轻量实现，复用 Bug Tracker 看板的拖拽模式。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QMimeData, QDate, Qt, Signal, QObject
from PySide6.QtGui import QColor, QDrag, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLineEdit,
)

import src.styles.theme as _t
from src.models.todo import TodoItem
from src.models.project import Project
from src.styles.constants import VIEW_MARGINS

# ── 常量 ───────────────────────────────────────────────────────

_PRIORITY_COLORS = {"high": "#e64553", "medium": "#df8e1d", "low": "#40a02b"}
# 看板 3 列
_COLUMNS: list[tuple[str, str]] = [
    ("pending", "待处理"),
    ("in_progress", "进行中"),
    ("done", "已完成"),
]
_COLORS = {"pending": _t.BG_INPUT, "in_progress": "#e8f4fd", "done": "#e5f5e5"}
_COLUMN_HEADS = {"pending": _t.TEXT, "in_progress": _t.BLUE, "done": _t.GREEN}
_MIME_TODO_ID = "application/x-todo-id"

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

    def __init__(self, todo: TodoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo = todo
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedHeight(68)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            f"TodoCard{{background:{_t.BG_CARD};border:1px solid {_t.BORDER};"
            f"border-radius:8px;padding:8px 10px;}}"
            f"TodoCard:hover{{border-color:{_t.ACCENT};}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # 第一行：优先级色点 + 标题
        top = QHBoxLayout()
        top.setSpacing(6)
        color = _PRIORITY_COLORS.get(self._todo.priority, _t.FG_MUTED)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{color};border-radius:4px;")
        top.addWidget(dot)

        title = QLabel(self._todo.title)
        title.setFont(_FONT_CARD_TITLE)
        title.setStyleSheet(f"color:{_t.TEXT};border:none;")
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
                dc = _t.GREEN
            elif d.isValid() and d < today:
                date_text = f"⚠ 逾期 {today.daysTo(d)} 天" if today.daysTo(d) < 0 else "⚠ 逾期"
                dc = "#e64553"
            elif d.isValid() and d == today:
                date_text = "📌 今天"
                dc = "#df8e1d"
            else:
                date_text = f"📅 {self._todo.due_date}"
                dc = _t.SUBTEXT0
            date_lbl = QLabel(date_text)
            date_lbl.setFont(_FONT_CARD_META)
            date_lbl.setStyleSheet(f"color:{dc};border:none;")
            meta.addWidget(date_lbl)

        if self._todo.category:
            tag = QLabel(self._todo.category)
            tag.setFont(_FONT_CARD_META)
            tag.setStyleSheet(
                f"color:{_t.SUBTEXT0};background:{_t.SURFACE1};"
                f"border-radius:4px;padding:1px 6px;border:none;"
            )
            meta.addWidget(tag)

        meta.addStretch()
        layout.addLayout(meta)

    def todo_id(self) -> int | None:
        return self._todo.id

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_MIME_TODO_ID, str(self._todo.id or "").encode())
            drag.setMimeData(mime)

            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.exec(Qt.DropAction.MoveAction)
        super().mousePressEvent(event)

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

    def __init__(self, status: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._label = label
        self._cards: list[TodoCard] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        bg = _COLORS.get(self._status, _t.BG_BASE)
        self.setStyleSheet(
            f"KanbanColumn{{background:{bg};border-radius:10px;}}"
        )
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 列标题
        head = QHBoxLayout()
        head.setSpacing(6)
        lbl = QLabel(self._label)
        lbl.setFont(QFont())
        lbl.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{_COLUMN_HEADS.get(self._status, _t.TEXT)};"
            f"border:none;"
        )
        head.addWidget(lbl)
        self._count = QLabel("0")
        self._count.setStyleSheet(
            f"font-size:11px;font-weight:600;color:{_t.FG_MUTED};"
            f"background:{_t.SURFACE1};border-radius:8px;padding:1px 8px;border:none;"
        )
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
#  TodoKanbanView
# ═══════════════════════════════════════════════════════════════════


class TodoView(QWidget):
    """待办看板视图 — 3 列 + 顶部工具栏 + 快速添加。"""

    todo_changed = Signal()
    toggle_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo_list: list[TodoItem] = []
        self._all_projects: list[Project] = []
        self._setup_ui()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        self._build_toolbar(layout)

        # 快速添加
        self._build_quick_add(layout)

        # 看板 3 列
        board = QHBoxLayout()
        board.setContentsMargins(8, 4, 8, 8)
        board.setSpacing(8)

        self._columns: dict[str, KanbanColumn] = {}
        for status, label in _COLUMNS:
            col = KanbanColumn(status, label)
            col.todo_dropped.connect(self._on_todo_dropped)
            self._columns[status] = col
            board.addWidget(col, stretch=1)

        layout.addLayout(board, stretch=1)

        # 双击编辑信号路由
        _global_signals.edit_requested.connect(self._on_card_edit)

    def _build_toolbar(self, parent_layout: QVBoxLayout) -> None:
        tb = QHBoxLayout()
        tb.setContentsMargins(*VIEW_MARGINS)
        tb.setSpacing(6)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(160)
        self._project_combo.addItem("全部项目", None)
        self._project_combo.currentIndexChanged.connect(self._on_project_filter)
        proj_lbl = QLabel("项目")
        proj_lbl.setStyleSheet(f"color:{_t.SUBTEXT0};font-size:12px;")
        tb.addWidget(proj_lbl)
        tb.addWidget(self._project_combo)
        tb.addStretch()

        self.btn_edit = QPushButton("编辑")
        self._style_tool_btn(self.btn_edit, f"color:{_t.ACCENT};border:1px solid {_t.BORDER};background:{_t.BG_INPUT};")

        self.btn_delete = QPushButton("删除")
        self._style_tool_btn(self.btn_delete, f"color:{_t.RED};border:1px solid transparent;")

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet(f"color:{_t.SURFACE1};")

        self.btn_add = QPushButton("＋ 新增")
        self._style_tool_btn(self.btn_add, f"background:{_t.ACCENT};color:white;font-weight:600;border:none;")

        tb.addWidget(self.btn_edit)
        tb.addWidget(self.btn_delete)
        tb.addWidget(sep)
        tb.addWidget(self.btn_add)
        parent_layout.addLayout(tb)

    def _style_tool_btn(self, btn: QPushButton, base: str) -> None:
        btn.setFixedHeight(28)
        btn.setStyleSheet(
            f"QPushButton{{{base}border-radius:14px;padding:2px 14px;font-size:12px;}}"
            f"QPushButton:hover{{opacity:0.8;}}"
        )

    def _build_quick_add(self, parent_layout: QVBoxLayout) -> None:
        qb = QHBoxLayout()
        qb.setContentsMargins(12, 4, 12, 8)
        qb.setSpacing(0)

        container = QWidget()
        container.setStyleSheet(
            f"background:{_t.BG_INPUT};border:1px solid {_t.BORDER};border-radius:15px;"
        )
        container.setFixedHeight(30)
        cl = QHBoxLayout(container)
        cl.setContentsMargins(12, 0, 4, 0)
        cl.setSpacing(0)

        self._quick_add = QLineEdit()
        self._quick_add.setPlaceholderText("添加待办，回车快速创建…")
        self._quick_add.setClearButtonEnabled(True)
        self._quick_add.setFixedHeight(28)
        self._quick_add.setStyleSheet(
            "QLineEdit{background:transparent;border:none;font-size:13px;color:%s;}" % _t.TEXT
        )
        self._quick_add.returnPressed.connect(self._on_quick_add)
        cl.addWidget(self._quick_add, stretch=1)

        self._btn_quick_add = QPushButton("添加")
        self._btn_quick_add.setFixedSize(48, 22)
        self._btn_quick_add.setStyleSheet(
            f"QPushButton{{background:{_t.ACCENT};color:white;border:none;border-radius:11px;font-size:11px;}}"
            f"QPushButton:hover{{background:{_t.BLUE};}}"
        )
        self._btn_quick_add.clicked.connect(self._on_quick_add)
        cl.addWidget(self._btn_quick_add)

        qb.addWidget(container)
        parent_layout.addLayout(qb)

    # ── Public API ─────────────────────────────────────────────

    def refresh(self, todo_list: list[TodoItem], projects: list[Project] | None = None) -> None:
        if projects is not None:
            self.set_projects(projects)
        self._todo_list = todo_list
        self._populate()

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
        return None  # 看板模式无单行选中，通过双击卡片编辑

    # ── 内部 ────────────────────────────────────────────────────

    def _populate(self) -> None:
        """按项目 filter 分配卡片到各列。"""
        pid = self._project_combo.currentData()
        filtered = self._todo_list
        if pid is not None:
            filtered = [t for t in filtered if t.project_id == pid]

        groups: dict[str, list[TodoItem]] = {"pending": [], "in_progress": [], "done": []}
        for t in filtered:
            groups.setdefault(t.status, groups["pending"]).append(t)

        for status, col in self._columns.items():
            col.set_cards(groups.get(status, []))

    def _on_project_filter(self, _idx: int) -> None:
        self._populate()

    def _on_quick_add(self) -> None:
        text = self._quick_add.text().strip()
        if not text:
            return
        self._quick_add.clear()
        self.quick_add_created.emit(text, self._project_combo.currentData())

    quick_add_created = Signal(str, object)

    def _on_todo_dropped(self, todo_id: int, new_status: str) -> None:
        """卡片拖拽到新列 → 触发状态变更。"""
        if new_status == "done":
            # 需要 toggle 状态到 done（走 toggle 循环）
            self.toggle_requested.emit(todo_id)
        else:
            # 直接设置状态
            self._direct_status_change.emit(todo_id, new_status)

    _direct_status_change = Signal(int, str)  # todo_id, new_status

    def _on_card_edit(self, todo_id: int) -> None:
        """卡片双击编辑。"""
        self.btn_edit.click()

    # ── 兼容旧 handler ─────────────────────────────────────────

    def emit_todo_changed(self) -> None:
        self.todo_changed.emit()
