"""看板卡片小部件 — 显示 Issue 关键信息，支持拖拽。

提取自 kanban_view.py _KanbanCard。
"""
from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.issue import Issue
from src.styles.animation import DropShadowAnimation, BackgroundAnimation
from src.styles.constants import (
    AGING_THRESHOLD_LOW,
    AGING_THRESHOLD_MID,
    ISSUE_SEVERITY_COLORS,
    PRIORITY_COLORS,
    PADDING_MEDIUM,
    PADDING_SMALL,
    STATUS_GREEN,
    STATUS_OVERLAY,
    STATUS_RED,
    STATUS_YELLOW,
)
from src.constants import PRIORITY_LABELS, SEVERITY_LABELS


def _aging_color(days: int) -> str:
    if days < AGING_THRESHOLD_LOW:
        return STATUS_GREEN
    if days <= AGING_THRESHOLD_MID:
        return STATUS_YELLOW
    return STATUS_RED


# ── 字体 ──
_FONT_CARD_TITLE = QFont()
_FONT_CARD_TITLE.setPixelSize(13)
_FONT_CARD_TITLE.setWeight(QFont.Weight.Bold)

_FONT_CARD_META = QFont()
_FONT_CARD_META.setPixelSize(11)

_FONT_BADGE = QFont()
_FONT_BADGE.setPixelSize(10)
_FONT_BADGE.setWeight(QFont.Weight.Bold)


class _KanbanCard(QFrame):
    """看板卡片 — Issue 关键信息 + 拖拽。"""

    clicked = Signal(int)
    double_clicked = Signal(int)
    drag_started = Signal(int)

    CARD_WIDTH = 180
    CARD_HEIGHT = 68

    def __init__(self, issue: Issue, aging_days: int = 0,
                 assignee_name: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._issue = issue
        self._aging_days = aging_days
        self._assignee_name = assignee_name
        self._drag_start_pos: QPoint | None = None
        self._drag_started = False

        self.setProperty("class", "kanban-card")
        self._bg_anim = BackgroundAnimation(self)
        self._shadow_anim = DropShadowAnimation(self)
        self._shadow_anim.setup(blur=12, offset_y=3, normal_alpha=0, hover_alpha=30)
        self.setMinimumHeight(self.CARD_HEIGHT)
        self.setMaximumHeight(self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAcceptDrops(False)
        self._setup_ui()
        self._apply_card_style()

    @property
    def issue_id(self) -> int:
        return self._issue.id if self._issue.id is not None else 0

    @property
    def issue_status(self) -> str:
        return self._issue.status

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_MEDIUM, PADDING_SMALL,
                                  PADDING_MEDIUM, PADDING_SMALL)
        layout.setSpacing(4)

        self._title_label = QLabel(self._issue.title)
        self._title_label.setFont(_FONT_CARD_TITLE)
        self._title_label.setWordWrap(False)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._title_label.setFixedHeight(18)
        layout.addWidget(self._title_label)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

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

        priority = self._issue.priority
        pri_color = PRIORITY_COLORS.get(priority, STATUS_OVERLAY)
        pri_label = QLabel(PRIORITY_LABELS.get(priority, f"P{priority}"))
        pri_label.setFont(_FONT_BADGE)
        pri_label.setStyleSheet(
            f"color: {pri_color}; background: transparent; border: none;"
        )
        meta_row.addWidget(pri_label)

        meta_row.addStretch()

        display_name = self._assignee_name or getattr(self._issue, "dri_name", "") or ""
        assignee_label = QLabel(display_name) if display_name else QLabel("—")
        assignee_label.setFont(_FONT_CARD_META)
        assignee_label.setProperty("class", "card-meta")
        meta_row.addWidget(assignee_label)

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
        border_color = _t.SURFACE1
        self.setStyleSheet(
            f"background-color: {_t.BG_CARD};"
            f"border: 1px solid {border_color};"
            f"border-radius: 8px;"
        )

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

        delta = event.position().toPoint() - self._drag_start_pos
        if delta.manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        self._drag_started = True
        self.drag_started.emit(self.issue_id)

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"issue:{self.issue_id}:{self._issue.status}")
        drag.setMimeData(mime)

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
        drag.setHotSpot(QPoint(self.CARD_WIDTH // 4, self.CARD_HEIGHT // 4))
        self.setGraphicsEffect(None)
        result = drag.exec(Qt.DropAction.MoveAction)
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

    def refresh_theme(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
