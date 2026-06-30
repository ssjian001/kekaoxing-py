"""四象限（Eisenhower Matrix）视图 — 2×2 网格 + 底部未分类行。

QuadrantView 提供 Eisenhower 四象限规划视图，支持拖拽卡片切换象限。
每个象限是一个 QuadrantCell(QFrame)，支持 dropEvent 接收 _MIME_TODO_ID。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.todo import TodoItem
from src.views.todo_view import _MIME_TODO_ID

# ── 四象限定义 ──────────────────────────────────────────────────

_QUADRANTS: list[tuple[int, str, str, str]] = [
    (1, "① 重要且紧急",  "重要紧急",  "quadrant-cell-q1"),
    (2, "② 重要不紧急",  "重要不紧急", "quadrant-cell-q2"),
    (3, "③ 不重要但紧急", "不重要紧急", "quadrant-cell-q3"),
    (4, "④ 不重要不紧急", "不重要不紧急","quadrant-cell-q4"),
]

_QUADRANT_LABELS: dict[int, str] = {q[0]: q[1] for q in _QUADRANTS}


# ═══════════════════════════════════════════════════════════════════
#  QuadrantCell
# ═══════════════════════════════════════════════════════════════════


class QuadrantCell(QFrame):
    """四象限单元格 — drop target + scroll area + card 列表。"""

    quadrant_changed = Signal(int, int)   # todo_id, new_quadrant
    card_selected = Signal(int)           # todo_id

    def __init__(
        self,
        quadrant: int,
        label: str,
        col_class: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._quadrant = quadrant
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

        # ── 标题 + 计数 ──
        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel(self._label)
        title.setProperty("class", "quadrant-title")
        head.addWidget(title)
        self._count = QLabel("0")
        self._count.setProperty("class", "kanban-count")
        head.addWidget(self._count)
        head.addStretch()
        layout.addLayout(head)

        # ── ScrollArea ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
        )

        self._card_container = QWidget()
        self._card_container.setStyleSheet(
            "background:transparent;border:none;"
        )
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, stretch=1)

    # ── 卡片管理 ────────────────────────────────────────────────

    def set_cards(self, todos: list[TodoItem]) -> None:
        """替换单元格内所有卡片。"""
        for card in self._cards:
            self._card_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        self._count.setText(str(len(todos)))
        for todo in todos:
            card = TodoCard(todo)
            card.selected.connect(self.card_selected.emit)
            self._cards.append(card)
            self._card_layout.insertWidget(
                self._card_layout.count() - 1, card
            )

    def refresh_theme(self) -> None:
        """主题切换后刷新所有卡片的选中态。"""
        for card in self._cards:
            card.refresh_theme()

    # ── 拖拽事件 ────────────────────────────────────────────────

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasFormat(_MIME_TODO_ID):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: Any) -> None:
        if event.mimeData().hasFormat(_MIME_TODO_ID):
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:
        data = event.mimeData().data(_MIME_TODO_ID)
        try:
            todo_id = int(data.data().decode())
        except (ValueError, TypeError):
            return
        self.quadrant_changed.emit(todo_id, self._quadrant)
        event.acceptProposedAction()

    def count(self) -> int:
        return len(self._cards)


# ═══════════════════════════════════════════════════════════════════
#  TodoCard (smaller variant for quadrant view)
# ═══════════════════════════════════════════════════════════════════


class TodoCard(QFrame):
    """四象限视图中的卡片 — 复用 todo_view.py 的拖拽逻辑。"""

    selected = Signal(int)  # todo_id

    def __init__(self, todo: TodoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo = todo
        self._selected = False
        self._drag_start: QPoint | None = None  # type: ignore[assignment]
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("class", "card-container")
        self._build_content()

    def _apply_style(self) -> None:
        """选中态样式（用 inline 因为状态动态切换）。"""
        if self._selected:
            self.setStyleSheet(
                f"QFrame{{background:{_t.SELECTION_BG};"
                f"border:2px solid {_t.ACCENT};border-radius:8px;}}"
            )
        else:
            self.setStyleSheet("")

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_style()

    def refresh_theme(self) -> None:
        """主题切换后刷新内联颜色（选中态）。"""
        self._apply_style()

    def _build_content(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        title = QLabel(self._todo.title)
        title.setProperty("class", "card-title")
        title.setWordWrap(True)
        title.setMaximumHeight(32)
        layout.addWidget(title, stretch=1)

        if self._todo.due_date:
            date_lbl = QLabel(f"📅 {self._todo.due_date}")
            date_lbl.setProperty("class", "hint-label")
            layout.addWidget(date_lbl)

    def todo_id(self) -> int | None:
        return self._todo.id

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = QPoint(int(event.position().x()),
                                       int(event.position().y()))
            if self._todo.id is not None:
                self.selected.emit(self._todo.id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None or self._todo.id is None:
            return super().mouseMoveEvent(event)
        current = QPoint(int(event.position().x()), int(event.position().y()))
        if (current - self._drag_start).manhattanLength() < 5:
            return super().mouseMoveEvent(event)
        self._start_drag()

    def _start_drag(self) -> None:
        from PySide6.QtCore import QMimeData
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(_MIME_TODO_ID, str(self._todo.id or "").encode())
        drag.setMimeData(mime)
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if self._todo.id is not None:
            from src.views.todo_view import _global_edit_request
            _global_edit_request.emit(self._todo.id)
        super().mouseDoubleClickEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  QuadrantView
# ═══════════════════════════════════════════════════════════════════


class QuadrantView(QWidget):
    """四象限视图 — 2×2 网格 + 底部未分类行。"""

    quadrant_changed = Signal(int, int)  # todo_id, new_quadrant
    card_selected = Signal(int)          # todo_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cells: dict[int, QuadrantCell] = {}
        self._unset_cell: QuadrantCell | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── 2×2 网格 ──
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        # 行0（重要）：Q1 重要紧急(左) / Q2 重要不紧急(右)
        # 行1（不重要）：Q3 不重要紧急(左) / Q4 不重要不紧急(右)
        positions = {
            1: (0, 0),
            2: (0, 1),
            3: (1, 0),
            4: (1, 1),
        }

        for qid, label, short_label, cls in _QUADRANTS:
            cell = QuadrantCell(qid, short_label, cls)
            cell.quadrant_changed.connect(self._on_cell_quadrant_changed)
            cell.card_selected.connect(self.card_selected.emit)
            self._cells[qid] = cell
            row, col = positions[qid]
            grid.addWidget(cell, row, col)
            grid.setRowStretch(row, 1)
            grid.setColumnStretch(col, 1)

        layout.addLayout(grid, stretch=1)

        # ── 底部未分类行 ──
        self._unset_cell = QuadrantCell(0, "未分类", "quadrant-cell-unset")
        self._unset_cell.quadrant_changed.connect(
            self._on_cell_quadrant_changed
        )
        self._unset_cell.card_selected.connect(self.card_selected.emit)
        self._unset_cell.setFixedHeight(100)
        layout.addWidget(self._unset_cell)

    # ── 内部 ────────────────────────────────────────────────────

    def _on_cell_quadrant_changed(
        self, todo_id: int, new_quadrant: int
    ) -> None:
        """子 cell 转发上来的象限变更信号。"""
        self.quadrant_changed.emit(todo_id, new_quadrant)

    # ── 公开 API ────────────────────────────────────────────────

    def refresh(self, todos: list[TodoItem]) -> None:
        """按 quadrant 分组填充各单元格。"""
        groups: dict[int, list[TodoItem]] = {1: [], 2: [], 3: [], 4: [], 0: []}
        for t in todos:
            q = t.quadrant if hasattr(t, 'quadrant') else 0
            groups.setdefault(q, groups[0]).append(t)

        for qid, cell in self._cells.items():
            cell.set_cards(groups.get(qid, []))

        if self._unset_cell is not None:
            self._unset_cell.set_cards(groups.get(0, []))

    def refresh_theme(self) -> None:
        """主题切换后刷新所有卡片的选中态。"""
        for cell in self._cells.values():
            cell.refresh_theme()
        if self._unset_cell is not None:
            self._unset_cell.refresh_theme()
