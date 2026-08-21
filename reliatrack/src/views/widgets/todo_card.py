"""待办看板卡片 — 标题/优先级色点/日期/tag/选中态。

提取自 todo_view.py TodoCard + 全局信号。
"""
from __future__ import annotations

from PySide6.QtCore import QDate, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPixmap, QDrag
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.todo import TodoItem
from src.styles.animation import DropShadowAnimation, BackgroundAnimation
from src.views.widgets.todo_globals import _global_signals

_MIME_TODO_ID = "application/x-todo-id"


def _priority_color(priority: int) -> str:
    if priority >= 4:
        return _t.RED
    if priority >= 2:
        return _t.YELLOW
    return _t.GREEN


_FONT_CARD_TITLE = QFont()
_FONT_CARD_META = QFont()
_FONT_CARD_TITLE.setPixelSize(13)
_FONT_CARD_TITLE.setBold(True)
_FONT_CARD_META.setPixelSize(11)


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
        if self._selected:
            self.setStyleSheet(
                f"QFrame{{background:{_t.SELECTION_BG};border:2px solid {_t.ACCENT};"
                f"border-radius:8px;}}"
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(6)
        title = QLabel(self._todo.title)
        title.setFont(_FONT_CARD_TITLE)
        title.setProperty("class", "card-title")
        title.setWordWrap(True)
        title.setMaximumHeight(36)
        top.addWidget(title, stretch=1)
        layout.addLayout(top)

        meta = QHBoxLayout()
        meta.setSpacing(6)

        if self._todo.due_date:
            d = QDate.fromString(self._todo.due_date, "yyyy-MM-dd")
            today = QDate.currentDate()
            if self._todo.is_done:
                date_text = "✓ 已完成"
            elif d.isValid() and d < today:
                # 审计 #25：today.daysTo(d) 对过去日期恒为负，原代码渲染
                # "逾期 -3 天"。取绝对值显示真实逾期天数。
                overdue_days = abs(today.daysTo(d))
                date_text = f"⚠ 逾期 {overdue_days} 天"
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
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            if self._todo.id is not None:
                self.selected.emit(self._todo.id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
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
        if self._todo.id is not None:
            _global_signals.edit_requested.emit(self._todo.id)
        super().mouseDoubleClickEvent(event)
