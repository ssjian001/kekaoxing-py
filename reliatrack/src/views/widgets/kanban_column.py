"""看板列容器 — 垂直排列卡片，支持拖拽放下。

提取自 kanban_view.py _KanbanColumn。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.issue import Issue
from src.services.issue_service import IssueService
from src.styles.constants import (
    ISSUE_STATUS_COLORS,
    PADDING_MEDIUM,
    PADDING_SMALL,
    STATUS_OVERLAY,
)
from src.views.widgets.kanban_card import _KanbanCard

# ── 字体 ──
_FONT_COLUMN_HEADER = QFont()
_FONT_COLUMN_HEADER.setPixelSize(14)
_FONT_COLUMN_HEADER.setWeight(QFont.Weight.Bold)

_FONT_CARD_META = QFont()
_FONT_CARD_META.setPixelSize(11)

_FONT_COLLAPSED = QFont()
_FONT_COLLAPSED.setPixelSize(11)

_ColumnStatus = tuple[int, int]


class _KanbanColumn(QFrame):
    """看板列 — 垂直排列卡片的容器，支持拖拽放下。"""

    status_changed = Signal(int, str)

    COLUMN_WIDTH = 210

    def __init__(self, status: str, label: str,
                 service: IssueService | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._label = label
        self._service = service
        self._cards: list[_KanbanCard] = []
        self._folded: bool = True
        self._is_closed_col = (status == "closed")

        self.setProperty("class", "kanban-column")
        self.setMinimumWidth(self.COLUMN_WIDTH)
        self.setAcceptDrops(True)
        self._setup_ui()

    @property
    def column_status(self) -> str:
        return self._status

    def _setup_ui(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        header = QFrame()
        header.setProperty("class", "column-header")
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(PADDING_MEDIUM, PADDING_SMALL,
                                         PADDING_MEDIUM, PADDING_SMALL)

        color = ISSUE_STATUS_COLORS.get(self._status, STATUS_OVERLAY)
        color_dot = QLabel("●")
        color_dot.setFont(_FONT_COLUMN_HEADER)
        color_dot.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )
        header_layout.addWidget(color_dot)

        self._title_label = QLabel(self._label)
        self._title_label.setFont(_FONT_COLUMN_HEADER)
        self._title_label.setProperty("class", "column-header-label")
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel("0")
        self._count_label.setFont(_FONT_CARD_META)
        self._count_label.setProperty("class", "column-count")
        header_layout.addWidget(self._count_label)

        header_layout.addStretch()

        self._fold_btn = QPushButton("▾" if self._is_closed_col else "")
        self._fold_btn.setFont(_FONT_COLLAPSED)
        self._fold_btn.setFixedSize(24, 24)
        self._fold_btn.setProperty("class", "fold-btn")
        self._fold_btn.setVisible(self._is_closed_col)
        self._fold_btn.clicked.connect(self._toggle_fold)
        header_layout.addWidget(self._fold_btn)

        self._root_layout.addWidget(header)

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

        self._fold_info = QLabel("")
        self._fold_info.setProperty("class", "fold-info")
        self._fold_info.setFont(_FONT_COLLAPSED)
        self._fold_info.setFixedHeight(26)
        self._fold_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fold_info.setVisible(False)
        self._fold_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fold_info.mousePressEvent = lambda _: self._toggle_fold()
        self._root_layout.addWidget(self._fold_info)

    def set_cards(self, cards: list[_KanbanCard],
                  history_cards: list[_KanbanCard] | None = None) -> None:
        self._clear_cards()
        self._cards = []

        if self._is_closed_col:
            recent = cards
            history = history_cards or []
            visible = recent if self._folded else recent + history
            self._cards = recent + history

            total_current = len(recent)
            total_history = len(history)

            if total_history > 0:
                self._title_label.setText(
                    f"{self._label} (30天内 {total_current}条"
                )
                if self._folded:
                    self._fold_info.setText(f"还有 {total_history} 条历史记录 ▾")
                else:
                    self._fold_info.setText("收起历史记录 ▴")
                self._fold_info.setVisible(True)
            else:
                self._title_label.setText(self._label)
                self._fold_info.setVisible(False)
        else:
            self._cards = cards

        for card in visible if self._is_closed_col else cards:
            self._card_layout.insertWidget(
                self._card_layout.count() - 1, card
            )

        self._update_count()

    def _clear_cards(self) -> None:
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

    def _update_count(self) -> None:
        self._count_label.setText(str(len(self._cards)))

    def _toggle_fold(self) -> None:
        if not self._is_closed_col:
            return
        self._folded = not self._folded
        self._fold_btn.setText("▴" if not self._folded else "▾")
        parent = self.parent()
        while parent and not hasattr(parent, "_load_issues"):
            parent = parent.parent()
        if parent and hasattr(parent, "_load_issues"):
            parent._load_issues()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("issue:"):
                parts = text.split(":")
                if len(parts) >= 3 and parts[2] != self._status:
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
        current_status = parts[2]
        if current_status == self._status:
            event.ignore()
            return
        event.acceptProposedAction()
        self.status_changed.emit(issue_id, self._status)

    def refresh_theme(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        for child in self.findChildren(QFrame):
            child.style().unpolish(child)
            child.style().polish(child)
        for card in self._cards:
            card.refresh_theme()
