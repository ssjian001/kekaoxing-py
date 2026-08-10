"""Bug 列表表格 — 排序/列宽持久化/Aging 色块/行高亮。

提取自 list_view.py _BugTable。
"""
from __future__ import annotations

from typing import Optional

import logging
logger = logging.getLogger("widgets.bug_table")

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

import src.styles.theme as _t
from src.models.issue import Issue
from src.services.issue_service import IssueService
from src.styles.constants import (
    ISSUE_SEVERITY_COLORS,
    ISSUE_STATUS_COLORS,
    PRIORITY_COLORS,
    apply_column_specs,
)
from src.constants import ISSUE_STATUS_LABELS, SEVERITY_LABELS, PRIORITY_LABELS
from src.views.widgets.table_delegate import RowHighlightDelegate
from src.styles.column_persistence import save_column_widths_debounced


def _aging_color(days: int, GREEN: str, YELLOW: str, RED: str,
                 threshold_low: int, threshold_mid: int) -> str:
    if days < threshold_low:
        return GREEN
    elif days <= threshold_mid:
        return YELLOW
    return RED


_BUG_TABLE_SPECS = [
    ("", "fixed", 32),
    ("ID", "fixed", 50),
    ("标题", "interactive", 200),
    ("严重度", "interactive", 70),
    ("状态", "interactive", 80),
    ("优先级", "interactive", 60),
    ("DRI", "interactive", 80),
    ("Aging", "interactive", 70),
    ("创建时间", "interactive", 100),
    ("任务", "interactive", 80),
    ("样品", "interactive", 80),
]


class _BugTable(QTableWidget):
    """Bug 列表表格 — checkbox 列 + 排序 + 列宽持久化 + Aging 色块。"""

    card_double_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_column_specs(self, _BUG_TABLE_SPECS, "bug_list_table")
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self._issues: list[Issue] = []
        self._issue_service: IssueService | None = None
        self._technician_map: dict[int, str] = {}
        self.horizontalHeader().setSortIndicatorShown(True)

        self.setMouseTracking(True)
        self._delegate = RowHighlightDelegate(self)
        self.setItemDelegate(self._delegate)
        self.cellEntered.connect(self._on_cell_entered)
        self.viewportEntered.connect(self._on_viewport_entered)

        self.doubleClicked.connect(self._on_double_click)
        self.horizontalHeader().sectionResized.connect(self._on_section_resized)

    def set_issue_service(self, service: IssueService) -> None:
        self._issue_service = service

    def set_technician_map(self, tech_map: dict[int, str]) -> None:
        self._technician_map = tech_map

    def set_issues(self, issues: list[Issue]) -> None:
        saved_selected = self.get_selected_issue_id()
        saved_checks: set = set(self.get_checked_ids())

        self._issues = issues
        self.setSortingEnabled(False)
        self.setRowCount(len(issues))

        # 批量预取 aging 天数（一次 DB 查询替代逐行 get_aging_days）
        aging_cache: dict[int, int] = {}
        if self._issue_service is not None:
            ids = [i.id for i in issues if i.id is not None]
            if ids:
                try:
                    aging_cache = self._issue_service.get_aging_days_map(ids)
                except Exception:
                    logger.exception("set_issues: batch aging fetch failed")
                    aging_cache = {}

        for row, issue in enumerate(issues):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            chk_item.setCheckState(
                Qt.CheckState.Checked if issue.id in saved_checks
                else Qt.CheckState.Unchecked
            )
            chk_item.setData(Qt.ItemDataRole.UserRole, issue.id)
            chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 0, chk_item)

            for col, val in enumerate([
                issue.id,
                issue.title,
                SEVERITY_LABELS.get(issue.severity, issue.severity),
                ISSUE_STATUS_LABELS.get(issue.status, issue.status),
                PRIORITY_LABELS.get(issue.priority, f"P{issue.priority}"),
                issue.dri_name or "",
                "",
                (issue.created_at or "")[:10],
                str(issue.task_id or ""),
                str(issue.sample_id or ""),
            ], start=1):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, issue.id)
                if col == 3:
                    item.setForeground(QColor(ISSUE_SEVERITY_COLORS.get(issue.severity, _t.TEXT)))
                elif col == 4:
                    item.setForeground(QColor(ISSUE_STATUS_COLORS.get(issue.status, _t.TEXT)))
                elif col == 5:
                    item.setForeground(QColor(PRIORITY_COLORS.get(issue.priority, _t.TEXT)))
                self.setItem(row, col, item)

            aging_days = aging_cache.get(issue.id, 0) if issue.id is not None else 0
            aging_text = f"{aging_days}天" if aging_days >= 0 else "-"
            aging_item = QTableWidgetItem(aging_text)
            aging_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            aging_item.setData(Qt.ItemDataRole.UserRole, issue.id)
            color = _aging_color(aging_days, _t.GREEN, _t.YELLOW, _t.RED, 3, 7)
            aging_item.setForeground(QColor(color))
            aging_item.setToolTip(f"当前状态停留 {aging_days} 天")
            self.setItem(row, 7, aging_item)

        self.setSortingEnabled(True)

        if saved_selected is not None:
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == saved_selected:
                    self.setCurrentCell(row, 0)
                    break

    def _get_issue_id_at_row(self, row: int) -> Optional[int]:
        if 0 <= row < self.rowCount():
            item = self.item(row, 0)
            if item is not None:
                uid = item.data(Qt.ItemDataRole.UserRole)
                if uid is not None:
                    return int(uid)
        return None

    def get_selected_issue_id(self) -> Optional[int]:
        return self._get_issue_id_at_row(self.currentRow())

    def get_checked_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                uid = item.data(Qt.ItemDataRole.UserRole)
                if uid is not None:
                    ids.append(int(uid))
        return ids

    def select_all(self, checked: bool = True) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item:
                item.setCheckState(state)

    def get_issue_by_id(self, issue_id: int) -> Optional[Issue]:
        for issue in self._issues:
            if issue.id == issue_id:
                return issue
        return None

    def _on_double_click(self) -> None:
        issue_id = self.get_selected_issue_id()
        if issue_id is not None:
            self.card_double_clicked.emit(issue_id)

    def _on_section_resized(self, index: int, old_size: int, new_size: int) -> None:
        save_column_widths_debounced(self, "bug_list_table")

    def _on_cell_entered(self, row: int, column: int) -> None:
        self._delegate.hover_row = row
        self.viewport().update()

    def _on_viewport_entered(self) -> None:
        self._delegate.hover_row = -1
        self.viewport().update()
