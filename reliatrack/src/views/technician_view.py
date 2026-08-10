"""技术员管理 Tab — 技术员列表 + 增删改查。"""

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
from PySide6.QtCore import Qt

from src.models.common import Technician
import src.styles.theme as _theme
from src.styles.constants import VIEW_MARGINS, apply_column_specs
from src.views.widgets.table_delegate import RowHighlightDelegate
from src.views.widgets.search_box import SearchBox
from src.views.widgets.empty_state import EmptyStateWidget

_TECHNICIAN_SPECS = [
    ("ID", "fixed", 50),
    ("工号", "interactive", 90),
    ("姓名", "interactive", 100),
    ("部门", "stretch", 100),
    ("职位", "interactive", 100),
    ("联系方式", "interactive", 120),
    ("邮箱", "interactive", 200),
]


class TechnicianView(QWidget):
    """技术员管理视图 — 顶部工具栏 + 表格。"""

    # 表格列：(显示名, 对应 Technician 属性)
    _COLUMNS = [
        ("ID", "id"),
        ("工号", "employee_id"),
        ("姓名", "name"),
        ("部门", "department"),
        ("职位", "role"),
        ("联系方式", "phone"),
        ("邮箱", "email"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tech_list: list[Technician] = []
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
        self._search_edit.setPlaceholderText("搜索姓名 / 工号 / 部门…")
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        self.btn_edit.setToolTip("编辑选中技术员 (F2)")
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        self.btn_delete.setToolTip("删除选中技术员 (Delete)")
        toolbar.addWidget(self.btn_delete)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setProperty("class", "sep-vline")
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("新增")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        self.btn_add.setToolTip("新增技术员 (Ctrl+N)")
        toolbar.addWidget(self.btn_add)

        self.btn_import = QPushButton("导入")
        self.btn_import.setProperty("class", "action")
        self.btn_import.setMinimumWidth(70)
        self.btn_import.setToolTip("从 Excel 批量导入技术员")
        toolbar.addWidget(self.btn_import)

        layout.addLayout(toolbar)

        # 表格
        self._table = QTableWidget()
        apply_column_specs(self._table, _TECHNICIAN_SPECS, "technician_table")
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
        self._ctx_act_edit = self._context_menu.addAction("编辑技术员")
        self._ctx_act_delete = self._context_menu.addAction("删除技术员")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)
        self._ctx_act_delete.triggered.connect(self._on_ctx_delete)

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无技术员数据",
            description="尚未添加任何技术员，点击上方「新增」按钮添加技术员",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

    # ── 数据加载 ────────────────────────────────────────────────

    def refresh(self, technician_list: list[Technician]) -> None:
        """刷新技术员表格。"""
        self._tech_list = technician_list
        self._populate_table(technician_list)

    def _populate_table(self, items: list[Technician]) -> None:
        """填充表格。"""
        self._table.setSortingEnabled(False)
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        self._table.setRowCount(len(items))
        for row, tech in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(tech, attr, "")
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, tech.id)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def get_selected_technician(self) -> Technician | None:
        """获取当前选中的技术员对象。"""
        row = self._table.currentRow()
        if row < 0:
            return None
        id_item = self._table.item(row, 0)
        if id_item is None:
            return None
        target_id = id_item.data(Qt.ItemDataRole.UserRole)
        for tech in self._tech_list:
            if tech.id == target_id:
                return tech
        return None

    def _on_search(self, text: str) -> None:
        """搜索过滤。"""
        keyword = text.strip().lower()
        if not keyword:
            self._populate_table(self._tech_list)
            return
        filtered = [
            tech for tech in self._tech_list
            if keyword in (tech.name or "").lower()
            or keyword in (tech.employee_id or "").lower()
            or keyword in (tech.department or "").lower()
            or keyword in (tech.role or "").lower()
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
