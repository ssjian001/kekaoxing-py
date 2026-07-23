"""待办看板列 — 带标题头和大片拖放区域。

提取自 todo_view.py KanbanColumn。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.todo import TodoItem
from src.views.widgets.todo_card import TodoCard

_MIME_TODO_ID = "application/x-todo-id"


class KanbanColumn(QFrame):
    """看板列 — 带标题头和大片拖放区域。"""

    todo_dropped = Signal(int, str)  # todo_id, new_status
    card_selected = Signal(int)

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
