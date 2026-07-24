"""四象限（Eisenhower Matrix）視圖 — 2×2 網格 + 底部未分類行。

QuadrantView 提供 Eisenhower 四象限規劃視圖，支援拖拽卡片切換象限。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from src.models.todo import TodoItem
from src.views.widgets.quadrant_cell import QuadrantCell

# ── 四象限定義 ──────────────────────────────────────────────────

_QUADRANTS: list[tuple[int, str, str, str]] = [
    (1, "① 重要且緊急",  "重要緊急",  "quadrant-cell-q1"),
    (2, "② 重要不緊急",  "重要不緊急", "quadrant-cell-q2"),
    (3, "③ 不重要但緊急", "不重要緊急", "quadrant-cell-q3"),
    (4, "④ 不重要不緊急", "不重要不緊急", "quadrant-cell-q4"),
]


class QuadrantView(QWidget):
    """四象限視圖 — 2×2 網格 + 底部未分類行。"""

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

        # ── 2×2 網格 ──
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        positions = {1: (0, 0), 2: (0, 1), 3: (1, 0), 4: (1, 1)}

        for qid, _label, short_label, cls in _QUADRANTS:
            cell = QuadrantCell(qid, short_label, cls)
            cell.quadrant_changed.connect(self._on_cell_quadrant_changed)
            cell.card_selected.connect(self.card_selected.emit)
            self._cells[qid] = cell
            row, col = positions[qid]
            grid.addWidget(cell, row, col)
            grid.setRowStretch(row, 1)
            grid.setColumnStretch(col, 1)

        layout.addLayout(grid, stretch=1)

        # ── 底部未分類行 ──
        self._unset_cell = QuadrantCell(0, "未分類", "quadrant-cell-unset")
        self._unset_cell.quadrant_changed.connect(
            self._on_cell_quadrant_changed
        )
        self._unset_cell.card_selected.connect(self.card_selected.emit)
        self._unset_cell.setFixedHeight(100)
        layout.addWidget(self._unset_cell)

    # ── 內部转发 ────────────────────────────────────────────────

    def _on_cell_quadrant_changed(
        self, todo_id: int, new_quadrant: int
    ) -> None:
        self.quadrant_changed.emit(todo_id, new_quadrant)

    # ── 公開 API ────────────────────────────────────────────────

    def refresh(self, todos: list[TodoItem]) -> None:
        """按 quadrant 分組填充各單元格。"""
        groups: dict[int, list[TodoItem]] = {
            1: [], 2: [], 3: [], 4: [], 0: []
        }
        for t in todos:
            q = t.quadrant if hasattr(t, 'quadrant') else 0
            groups.setdefault(q, groups[0]).append(t)

        for qid, cell in self._cells.items():
            cell.set_cards(groups.get(qid, []))

        if self._unset_cell is not None:
            self._unset_cell.set_cards(groups.get(0, []))

    def refresh_theme(self) -> None:
        """主題切換後刷新所有卡片選中態。"""
        for cell in self._cells.values():
            cell.refresh_theme()
        if self._unset_cell is not None:
            self._unset_cell.refresh_theme()
