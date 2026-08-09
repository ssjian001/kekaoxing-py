"""样品表格基类 — QTableWidget + RowHighlightDelegate。
提取自 sample_view.py _SampleTable。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QWidget

from src.models.sample import Sample
from src.styles.constants import apply_column_specs
from src.views.widgets.table_delegate import RowHighlightDelegate


class _SampleTable(QTableWidget):
    def __init__(self, columns: list[tuple[str, str]], specs: list[tuple[str, str, int]],
                 table_key: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._columns = columns
        self._data: list[Sample] = []
        apply_column_specs(self, specs, table_key)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setMouseTracking(True)
        from src.constants import SAMPLE_STATUS_LABELS as _LABELS
        self._status_labels = getattr(_LABELS, "status_labels", None) or {}
        self._delegate = RowHighlightDelegate(self)
        self.setItemDelegate(self._delegate)
        self.cellEntered.connect(self._on_cell_entered)
        self.viewportEntered.connect(self._on_viewport_entered)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._init_empty_label()

    def _init_empty_label(self) -> None:
        """空状态提示标签（覆盖在表格上方，数据为空时显示）。"""
        self._empty_label = QLabel("暂无样品数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "empty-label")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self.viewport())
        self._empty_label.hide()

    def _update_empty_label(self) -> None:
        self._empty_label.setVisible(self.rowCount() == 0)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._empty_label.setGeometry(self.viewport().rect())

    def set_samples(self, samples: list[Sample]) -> None:
        from src.constants import SAMPLE_STATUS_LABELS
        self._data = samples
        self.setSortingEnabled(False)
        self.setRowCount(len(samples))
        for row_idx, sample in enumerate(samples):
            for col_idx, (_, field_name) in enumerate(self._columns):
                value = getattr(sample, field_name, "")
                if field_name == "status":
                    value = SAMPLE_STATUS_LABELS.get(value, str(value))
                elif field_name == "test_hours" and isinstance(value, float):
                    value = f"{value:.1f}" if value != int(value) else str(int(value))
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 0 and sample.id is not None:
                    item.setData(Qt.ItemDataRole.UserRole, sample.id)
                self.setItem(row_idx, col_idx, item)
        self.setSortingEnabled(True)
        self._update_empty_label()

    def _on_cell_entered(self, row: int, column: int) -> None:
        self._delegate.hover_row = row
        self.viewport().update()

    def _on_viewport_entered(self) -> None:
        self._delegate.hover_row = -1
        self.viewport().update()

    def _on_selection_changed(self) -> None:
        selected = self.selectedIndexes()
        rows = {idx.row() for idx in selected}
        self._delegate.selected_rows = rows
        self.viewport().update()

    def get_selected_sample_id(self) -> int | None:
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, 0)
        if item is not None:
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid is not None:
                return int(sid)
        return None

    def get_selected_sample_ids(self) -> list[int]:
        ids: list[int] = []
        for row in self.selectionModel().selectedRows():
            item = self.item(row.row(), 0)
            if item is not None:
                sid = item.data(Qt.ItemDataRole.UserRole)
                if sid is not None:
                    ids.append(int(sid))
        return ids
