"""样品出入库记录 Tab — 完整流水表。"""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

import src.styles.theme as _t
from src.styles.constants import SAMPLE_TYPE_COLORS, apply_column_specs
from src.views.widgets.empty_state import EmptyStateWidget
from src.views.widgets.search_box import SearchBox

# 出入库记录列规格
_LOG_SPECS = [
    ("样品SN", "interactive", 120),
    ("批次号", "interactive", 100),
    ("操作类型", "interactive", 80),
    ("操作人", "interactive", 80),
    ("用途", "interactive", 120),
    ("关联任务", "interactive", 120),
    ("预计归还", "interactive", 100),
    ("实际归还", "interactive", 100),
    ("备注", "interactive", 120),
    ("操作时间", "interactive", 140),
]


def _color_fg(hex_color: str):
    """将 hex 颜色字符串转为 QBrush 用于前景色。"""
    return QBrush(QColor(hex_color))


class _SampleUsageTab(QWidget):
    """样品出入库记录 Tab — 完整流水表。"""

    # 操作类型显示映射
    _TYPE_LABELS: dict[str, str] = {
        "check_in": "入库",
        "check_out": "出库",
        "return": "归还",
        "transfer": "转出",
    }

    # 操作类型颜色映射（来自 constants.py）
    _TYPE_COLORS: dict[str, str] = SAMPLE_TYPE_COLORS

    COLUMNS = [
        "样品SN", "批次号", "操作类型", "操作人",
        "用途", "关联任务", "预计归还", "实际归还", "备注", "操作时间",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── 筛选栏 ──
        toolbar = QHBoxLayout()

        self._search_input = SearchBox()
        self._search_input.setPlaceholderText("搜索 SN…")
        self._search_input.setMinimumWidth(160)
        self._search_input.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search_input)

        self._type_combo = QComboBox()
        self._type_combo.setProperty("class", "filter-combo")
        self._type_combo.setFixedWidth(140)
        self._type_combo.addItem("全部类型", "")
        self._type_combo.addItem("入库", "check_in")
        self._type_combo.addItem("出库", "check_out")
        self._type_combo.addItem("归还", "return")
        self._type_combo.addItem("转出", "transfer")
        self._type_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._type_combo)

        self._btn_search = QPushButton("查询")
        self._btn_search.setProperty("class", "action")
        self._btn_search.setMinimumWidth(70)
        self._btn_search.clicked.connect(self._request_refresh)
        toolbar.addWidget(self._btn_search)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setProperty("class", "action")
        self._btn_reset.setMinimumWidth(70)
        self._btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self._btn_reset)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── 表格 ──
        self._table = QTableWidget()
        apply_column_specs(self._table, _LOG_SPECS, "sample_log")
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)

        # RowHighlightDelegate — 行 hover/选中高亮
        self._table.setMouseTracking(True)
        from src.views.widgets.table_delegate import RowHighlightDelegate
        self._log_delegate = RowHighlightDelegate(self._table)
        self._table.setItemDelegate(self._log_delegate)
        self._table.cellEntered.connect(self._on_log_cell_entered)
        self._table.viewportEntered.connect(self._on_log_viewport_entered)
        self._table.selectionModel().selectionChanged.connect(self._on_log_selection_changed)

        layout.addWidget(self._table)

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无出入库记录",
            description="该样品尚无出入库操作记录",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

        # 全量数据缓存
        self._all_data: list[dict] = []

        # 外部刷新回调（由 main.py 连接）
        self._refresh_callback: object | None = None

    def set_refresh_callback(self, callback: object) -> None:
        """设置刷新回调，由外部传入 sample_service.list_transactions 调用。"""
        self._refresh_callback = callback

    def refresh(self, data: list[dict]) -> None:
        """接收数据并应用当前筛选。"""
        self._all_data = data
        self._apply_filter()

    @property
    def table(self) -> QTableWidget:
        return self._table

    # ── 内部方法 ──

    def _request_refresh(self) -> None:
        """触发外部回调重新查询数据。"""
        if self._refresh_callback:
            self._refresh_callback()  # type: ignore[operator]

    def _on_log_cell_entered(self, row: int, column: int) -> None:
        self._log_delegate.hover_row = row
        self._table.viewport().update()

    def _on_log_viewport_entered(self) -> None:
        self._log_delegate.hover_row = -1
        self._table.viewport().update()

    def _on_log_selection_changed(self) -> None:
        self._log_delegate.selected_rows = {idx.row() for idx in self._table.selectedIndexes()}
        self._table.viewport().update()

    def _on_reset(self) -> None:
        """重置筛选条件并刷新。"""
        self._search_input.clear()
        self._type_combo.setCurrentIndex(0)
        self._request_refresh()

    def _apply_filter(self) -> None:
        """根据当前搜索/类型过滤缓存数据并填充表格。"""
        sn_text = self._search_input.text().strip().lower()
        type_val = self._type_combo.currentData()

        filtered = self._all_data
        if sn_text:
            filtered = [
                d for d in filtered
                if sn_text in (d.get("sample_sn") or "").lower()
            ]
        if type_val:
            filtered = [d for d in filtered if d.get("type") == type_val]

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(filtered))
        for row_idx, record in enumerate(filtered):
            txn_type = record.get("type", "")
            label = self._TYPE_LABELS.get(txn_type, txn_type)
            color = self._TYPE_COLORS.get(txn_type, _t.TEXT)

            # 关联任务：显示 #id 任务名
            task_id = record.get("related_task_id")
            task_name = record.get("task_name")
            if task_id and task_name:
                task_display = f"#{task_id} {task_name}"
            elif task_id:
                task_display = f"#{task_id}"
            else:
                task_display = ""

            values = [
                record.get("sample_sn") or "—",
                record.get("batch_no") or "—",
                label,
                record.get("operator_name") or "—",
                record.get("purpose") or "",
                task_display,
                record.get("expected_return") or "—",
                record.get("actual_return") or "—",
                record.get("notes") or "",
                (record.get("created_at") or "")[:16],
            ]

            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 操作类型列着色
                if col_idx == 2:
                    item.setForeground(_color_fg(color))
                self._table.setItem(row_idx, col_idx, item)

        self._table.setSortingEnabled(True)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        """根据表格行数显示/隐藏空状态提示。"""
        if self._table.rowCount() == 0:
            self._empty_widget.setGeometry(self._table.viewport().rect())
            self._empty_widget.show()
        else:
            self._empty_widget.hide()

    def resizeEvent(self, event) -> None:
        """窗口缩放时调整空状态位置。"""
        super().resizeEvent(event)
        if hasattr(self, "_empty_widget") and self._empty_widget.isVisible():
            self._empty_widget.setGeometry(self._table.viewport().rect())
