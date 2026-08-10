"""设备管理 Tab — 设备列表 + 增删改查。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from src.models.common import Equipment
import src.styles.theme as _theme
from src.styles.constants import EQUIPMENT_STATUS_COLORS, VIEW_MARGINS, apply_column_specs
from src.constants import EQUIPMENT_STATUS_LABELS
from src.views.widgets.table_delegate import RowHighlightDelegate
from src.views.widgets.search_box import SearchBox
from src.views.widgets.empty_state import EmptyStateWidget

_EQUIPMENT_SPECS = [
    ("ID", "fixed", 50),
    ("资产编号", "interactive", 120),
    ("型号", "interactive", 120),
    ("名称", "stretch", 200),
    ("类型", "interactive", 80),
    ("制造商", "interactive", 120),
    ("精度/不确定度", "interactive", 110),
    ("校准日期", "interactive", 100),
    ("下次校准", "interactive", 100),
    ("间隔(月)", "interactive", 70),
    ("状态", "interactive", 80),
]


class EquipmentView(QWidget):
    """设备管理视图 — 顶部工具栏 + 表格。"""

    equipment_changed = Signal()  # 增删改后发射

    # 表格列：(显示名, 对应 Equipment 属性)
    _COLUMNS = [
        ("ID", "id"),
        ("资产编号", "asset_no"),
        ("型号", "model"),
        ("名称", "name"),
        ("类型", "type"),
        ("制造商", "manufacturer"),
        ("精度/不确定度", "accuracy"),
        ("校准日期", "calibration_date"),
        ("下次校准", "next_calibration_date"),
        ("间隔(月)", "calibration_interval_months"),
        ("状态", "status"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._equip_list: list[Equipment] = []
        self._setup_ui()

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)
        layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search_edit = SearchBox()
        self._search_edit.setPlaceholderText("搜索设备名称 / 型号 / 类型…")
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        self.btn_edit.setToolTip("编辑选中设备 (F2)")
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        self.btn_delete.setToolTip("删除选中设备 (Delete)")
        toolbar.addWidget(self.btn_delete)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setProperty("class", "sep-vline")
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("新增")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        self.btn_add.setToolTip("新增设备 (Ctrl+N)")
        toolbar.addWidget(self.btn_add)

        self.btn_import = QPushButton("导入")
        self.btn_import.setProperty("class", "action")
        self.btn_import.setMinimumWidth(70)
        self.btn_import.setToolTip("从 Excel 批量导入设备")
        toolbar.addWidget(self.btn_import)

        layout.addLayout(toolbar)

        # 设备容量与负荷热力图
        from src.views.widgets.equipment_heatmap_widget import EquipmentLoadHeatmapWidget
        self._heatmap = EquipmentLoadHeatmapWidget(self)
        layout.addWidget(self._heatmap)

        # 表格
        self._table = QTableWidget()
        apply_column_specs(self._table, _EQUIPMENT_SPECS, "equipment_table")

        from src.views.widgets.column_visibility_menu import create_column_visibility_button
        btn_col_vis = create_column_visibility_button(self._table, "equipment_table", self)
        toolbar.insertWidget(toolbar.indexOf(self.btn_edit), btn_col_vis)



        # 默认隐藏低频列，减少 800px 窗口水平溢出
        # 列索引对应 _EQUIPMENT_SPECS: 5=制造商, 6=精度/不确定度, 9=间隔(月)
        for _col_idx in (5, 6, 9):
            self._table.setColumnHidden(_col_idx, True)

        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)

        # RowHighlightDelegate
        self._table.setMouseTracking(True)
        self._delegate = RowHighlightDelegate(self._table)
        self._table.setItemDelegate(self._delegate)
        self._table.cellEntered.connect(self._on_cell_entered)
        self._table.viewportEntered.connect(self._on_viewport_entered)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # 右键菜单
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu = QMenu(self._table)
        self._ctx_act_edit = self._context_menu.addAction("编辑设备")
        self._ctx_act_delete = self._context_menu.addAction("删除设备")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)
        self._ctx_act_delete.triggered.connect(self._on_ctx_delete)

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无设备数据",
            description="尚未添加任何设备，点击上方「新增」按钮添加设备",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

    # ── 数据加载 ────────────────────────────────────────────────

    def refresh(self, equipment_list: list[Equipment], task_ref_counts: dict[int, int] | None = None) -> None:
        """刷新设备表格 + 热力图。

        Args:
            equipment_list: 设备列表。
            task_ref_counts: 设备 id → 被测试任务引用数（真实负载数据源）。
        """
        self._equip_list = equipment_list
        if hasattr(self, '_heatmap'):
            self._heatmap.refresh(equipment_list, task_ref_counts)
        self._populate_table(equipment_list)


    def _populate_table(self, items: list[Equipment]) -> None:
        """填充表格。"""
        self._table.setSortingEnabled(False)
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        self._table.setRowCount(len(items))
        for row, eq in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(eq, attr, "")
                # 格式化状态显示
                if attr == "status":
                    raw_status = str(value)
                    value = EQUIPMENT_STATUS_LABELS.get(raw_status, raw_status)
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, eq.id)
                # 居中对齐
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 状态列着色（用原始英文值匹配）
                if attr == "status":
                    color = EQUIPMENT_STATUS_COLORS.get(raw_status, _theme.TEXT)
                    item.setForeground(QColor(color))
                # 下次校准列：30天内到期黄色预警，已过期红色
                if attr == "next_calibration_date" and value:
                    from datetime import date, timedelta
                    try:
                        next_cal = date.fromisoformat(str(value))
                        today = date.today()
                        if next_cal < today:
                            item.setForeground(QColor(_theme.RED))
                            item.setText(f"{value} (过期)")
                        elif next_cal <= today + timedelta(days=30):
                            item.setForeground(QColor(_theme.YELLOW))
                    except ValueError:
                        pass
                self._table.setItem(row, col, item)
        header.blockSignals(False)
        self._table.setSortingEnabled(True)

        self._update_empty_state()

    # ── RowHighlightDelegate ──

    def _on_cell_entered(self, row: int, column: int) -> None:
        self._delegate.hover_row = row
        self._table.viewport().update()

    def _on_viewport_entered(self) -> None:
        self._delegate.hover_row = -1
        self._table.viewport().update()

    def _on_selection_changed(self) -> None:
        selected = self._table.selectedIndexes()
        rows = {idx.row() for idx in selected}
        self._delegate.selected_rows = rows
        self._table.viewport().update()

    # ── 选中 & 搜索 ────────────────────────────────────────────

    def get_selected_equipment(self) -> Equipment | None:
        """获取当前选中的设备对象。"""
        row = self._table.currentRow()
        if row < 0:
            return None
        eq_id = self._table.item(row, 0)
        if eq_id is None:
            return None
        target_id = eq_id.data(Qt.ItemDataRole.UserRole)
        for eq in self._equip_list:
            if eq.id == target_id:
                return eq
        return None

    def _on_search(self, text: str) -> None:
        """搜索过滤。"""
        keyword = text.strip().lower()
        if not keyword:
            self._populate_table(self._equip_list)
            return
        filtered = [
            eq for eq in self._equip_list
            if keyword in (eq.name or "").lower()
            or keyword in (eq.model or "").lower()
            or keyword in (eq.type or "").lower()
            or keyword in (eq.asset_no or "").lower()
            or keyword in (eq.manufacturer or "").lower()
        ]
        self._populate_table(filtered)

    def _on_double_click(self, row: int, _col: int) -> None:
        """双击行触发编辑。"""
        self.btn_edit.click()

    # ── 右键菜单 ──────────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        """在表格行上显示右键菜单。"""
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        self._table.selectRow(row)
        self._context_menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_ctx_edit(self) -> None:
        """右键编辑 → 触发工具栏编辑按钮。"""
        self.btn_edit.click()

    def _on_ctx_delete(self) -> None:
        """右键删除 → 触发工具栏删除按钮。"""
        self.btn_delete.click()

    # ── 公开方法 ────────────────────────────────────────────────

    def emit_equipment_changed(self) -> None:
        """通知外部数据已变更。"""
        self.equipment_changed.emit()

    # ── 空状态 ────────────────────────────────────────────────

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
