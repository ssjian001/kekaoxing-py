"""项目管理 Tab — 项目列表 + 增删改查。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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
from PySide6.QtGui import QColor

from src.models.project import Project
import src.styles.theme as _t
from src.styles.constants import VIEW_MARGINS, PROJECT_STATUS_COLORS, apply_column_specs
from src.constants import PROJECT_STATUS_LABELS
from src.views.widgets.table_delegate import RowHighlightDelegate
from src.views.widgets.search_box import SearchBox
from src.views.widgets.empty_state import EmptyStateWidget

_PROJECT_SPECS = [
    ("ID", "fixed", 50),
    ("名称", "interactive", 200),
    ("产品", "interactive", 120),
    ("客户", "interactive", 120),
    ("状态", "interactive", 80),
    ("创建时间", "interactive", 100),
]


class ProjectView(QWidget):
    """项目管理视图 — 顶部工具栏 + 表格。"""

    # 表格列：(显示名, 对应 Project 属性)
    _COLUMNS = [
        ("ID", "id"),
        ("名称", "name"),
        ("产品", "product"),
        ("客户", "customer"),
        ("状态", "status"),
        ("创建时间", "created_at"),
    ]

    # 状态 → 显示文字
    _STATUS_LABELS: dict[str, str] = PROJECT_STATUS_LABELS

    # 状态 → 颜色（英文 key，与 constants.py PROJECT_STATUS_COLORS 一致）
    _STATUS_COLORS: dict[str, str] = PROJECT_STATUS_COLORS

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_projects: list[Project] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)
        layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = SearchBox()
        self.search_input.setPlaceholderText("搜索项目名称 / 产品 / 客户…")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.setProperty("class", "filter-combo")
        self.status_filter.setFixedHeight(26)
        self.status_filter.setFixedWidth(110)
        self.status_filter.addItem("全部状态", None)
        self.status_filter.addItem("进行中", "active")
        self.status_filter.addItem("已暂停", "paused")
        self.status_filter.addItem("已关闭", "closed")
        self.status_filter.currentIndexChanged.connect(lambda: self._on_search(self.search_input.text()))
        toolbar.addWidget(self.status_filter)



        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        self.btn_edit.setToolTip("编辑选中项目 (F2)")
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        self.btn_delete.setToolTip("删除选中项目 (Delete)")
        toolbar.addWidget(self.btn_delete)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setProperty("class", "sep-vline")
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("新建")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        self.btn_add.setToolTip("新建项目 (Ctrl+N)")
        toolbar.addWidget(self.btn_add)

        layout.addLayout(toolbar)

        # 表格
        self._table = QTableWidget()
        apply_column_specs(self._table, _PROJECT_SPECS, "project_table")
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
        self._ctx_act_edit = self._context_menu.addAction("编辑项目")
        self._ctx_act_delete = self._context_menu.addAction("删除项目")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)
        self._ctx_act_delete.triggered.connect(self._on_ctx_delete)

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无项目数据",
            description="尚未创建任何项目，点击上方「新建」按钮创建项目",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

    # ── 数据加载 ────────────────────────────────────────────────

    def refresh(self, projects: list[Project]) -> None:
        """刷新项目表格。"""
        self._all_projects = projects
        self._on_search(self.search_input.text())

    def _populate_table(self, items: list[Project]) -> None:
        """填充表格。"""
        self._table.setSortingEnabled(False)
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        self._table.setRowCount(len(items))
        for row, proj in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(proj, attr, "")
                # 格式化状态显示
                if attr == "status":
                    value = self._STATUS_LABELS.get(str(value), str(value))
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, proj.id)
                # 居中对齐
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 状态列着色
                if attr == "status":
                    raw_status = str(getattr(proj, attr, ""))
                    color = self._STATUS_COLORS.get(raw_status, _t.OVERLAY0)
                    item.setForeground(QColor(color))
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

    def get_selected_project_id(self) -> int | None:
        """获取当前选中项目的 ID。"""
        row = self._table.currentRow()
        if row < 0:
            return None
        id_item = self._table.item(row, 0)
        if id_item is None:
            return None
        return id_item.data(Qt.ItemDataRole.UserRole)

    def get_selected_project(self) -> Project | None:
        """获取当前选中的项目对象。"""
        pid = self.get_selected_project_id()
        if pid is None:
            return None
        for proj in self._all_projects:
            if proj.id == pid:
                return proj
        return None

    def _on_search(self, text: str) -> None:
        """搜索与状态多重过滤。"""
        keyword = text.strip().lower()
        selected_status = self.status_filter.currentData()

        filtered = self._all_projects

        if keyword:
            filtered = [
                proj for proj in filtered
                if keyword in (proj.name or "").lower()
                or keyword in (proj.product or "").lower()
                or keyword in (proj.customer or "").lower()
            ]

        if selected_status is not None:
            filtered = [
                proj for proj in filtered
                if proj.status == selected_status
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
