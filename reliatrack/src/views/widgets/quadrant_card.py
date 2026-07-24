"""四象限視圖專用卡片 — 小尺寸版 TodoCard（54px）。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

import src.styles.theme as _t
from src.models.todo import TodoItem

_MIME_TODO_ID = "application/x-todo-id"


class QuadrantCard(QFrame):
    """四象限視圖卡片 — 54px 高，支援拖拽 + 雙擊編輯。"""

    selected = Signal(int)  # todo_id

    def __init__(self, todo: TodoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo = todo
        self._selected = False
        self._drag_start: QPoint | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("class", "card-container")
        self._build_content()

    def _apply_style(self) -> None:
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
            date_lbl = QLabel(f"{self._todo.due_date}")
            date_lbl.setProperty("class", "hint-label")
            layout.addWidget(date_lbl)

    def todo_id(self) -> int | None:
        return self._todo.id

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = QPoint(
                int(event.position().x()), int(event.position().y())
            )
            if self._todo.id is not None:
                self.selected.emit(self._todo.id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None or self._todo.id is None:
            return super().mouseMoveEvent(event)
        current = QPoint(
            int(event.position().x()), int(event.position().y())
        )
        if (current - self._drag_start).manhattanLength() < 5:
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

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if self._todo.id is not None:
            from src.views.widgets.todo_globals import _global_signals
            _global_signals.edit_requested.emit(self._todo.id)
        super().mouseDoubleClickEvent(event)
