"""四象限單元格 — drop target + scroll area + 卡片列表。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.todo import TodoItem
from src.views.widgets.quadrant_card import QuadrantCard, _MIME_TODO_ID


class QuadrantCell(QFrame):
    """四象限單元格 — drop target + scroll area + 卡片列表。"""

    quadrant_changed = Signal(int, int)  # todo_id, new_quadrant
    card_selected = Signal(int)          # todo_id

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
        self._cards: list[QuadrantCard] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setProperty("class", self._col_class)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── 標題 + 計數 ──
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
        for card in self._cards:
            self._card_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        self._count.setText(str(len(todos)))
        for todo in todos:
            card = QuadrantCard(todo)
            card.selected.connect(self.card_selected.emit)
            self._cards.append(card)
            self._card_layout.insertWidget(
                self._card_layout.count() - 1, card
            )

    def refresh_theme(self) -> None:
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
