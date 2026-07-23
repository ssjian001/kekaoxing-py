"""知识库 Tab — 知识条目列表 + 增删改查。"""

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

from src.models.knowledge import KnowledgeEntry
from src.styles.constants import KNOWLEDGE_CATEGORY_COLORS, VIEW_MARGINS, apply_column_specs
import src.styles.theme as _theme
from src.views.widgets.table_delegate import RowHighlightDelegate
from src.views.widgets.search_box import SearchBox
from src.views.widgets.empty_state import EmptyStateWidget

_KNOWLEDGE_SPECS = [
    ("ID", "fixed", 50),
    ("类别", "interactive", 80),
    ("失效模式", "interactive", 200),
    ("原因分析", "interactive", 160),
    ("改进措施", "interactive", 160),
    ("参考标准", "interactive", 120),
]


class KnowledgeView(QWidget):
    """知识库视图 — 顶部搜索栏 + 表格。"""

    knowledge_changed = Signal()  # 增删改后发射

    # 表格列：(显示名, 对应 KnowledgeEntry 属性)
    _COLUMNS = [
        ("ID", "id"),
        ("类别", "category"),
        ("失效模式", "failure_mode"),
        ("原因分析", "cause_analysis"),
        ("改进措施", "improvement"),
        ("参考标准", "reference_standard"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry_list: list[KnowledgeEntry] = []
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
        self._search_edit.setPlaceholderText("搜索类别 / 失效模式 / 原因分析…")
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        self.btn_edit.setToolTip("编辑选中条目 (F2)")
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        self.btn_delete.setToolTip("删除选中条目 (Delete)")
        toolbar.addWidget(self.btn_delete)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setProperty("class", "sep-vline")
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("新增")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        self.btn_add.setToolTip("新增知识条目 (Ctrl+N)")
        toolbar.addWidget(self.btn_add)
        layout.addLayout(toolbar)

        # 表格
        self._table = QTableWidget()
        apply_column_specs(self._table, _KNOWLEDGE_SPECS, "knowledge_table")
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
        self._ctx_act_edit = self._context_menu.addAction("编辑条目")
        self._ctx_act_delete = self._context_menu.addAction("删除条目")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)
        self._ctx_act_delete.triggered.connect(self._on_ctx_delete)

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无知识库条目",
            description="尚未添加知识条目，点击上方「新增」按钮添加",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

    # ── 数据加载 ────────────────────────────────────────────────

    def refresh(self, entry_list: list[KnowledgeEntry]) -> None:
        """刷新知识库表格。"""
        self._entry_list = entry_list
        self._populate_table(entry_list)

    def _populate_table(self, items: list[KnowledgeEntry]) -> None:
        """填充表格。"""
        self._table.setSortingEnabled(False)
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        self._table.setRowCount(len(items))
        for row, entry in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(entry, attr, "")
                # 截断长文本以便表格显示
                text = str(value) if value else ""
                if len(text) > 60:
                    text = text[:57] + "…"
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, entry.id)
                # 居中对齐（ID 列和类别列）
                if col in (0, 1):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 类别列着色
                if col == 1 and text:
                    color = KNOWLEDGE_CATEGORY_COLORS.get(text, _theme.TEXT)
                    item.setForeground(QColor(color))
                # 设置 tooltip 显示完整内容
                if len(str(value) if value else "") > 60:
                    item.setToolTip(str(value))
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

    def get_selected_entry(self) -> KnowledgeEntry | None:
        """获取当前选中的知识条目对象。"""
        row = self._table.currentRow()
        if row < 0:
            return None
        id_item = self._table.item(row, 0)
        if id_item is None:
            return None
        target_id = id_item.data(Qt.ItemDataRole.UserRole)
        for entry in self._entry_list:
            if entry.id == target_id:
                return entry
        return None

    def _on_search(self, text: str) -> None:
        """客户端搜索过滤。"""
        keyword = text.strip().lower()
        if not keyword:
            self._populate_table(self._entry_list)
            return
        filtered = [
            e for e in self._entry_list
            if keyword in (e.category or "").lower()
            or keyword in (e.failure_mode or "").lower()
            or keyword in (e.cause_analysis or "").lower()
            or keyword in (e.improvement or "").lower()
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

    def emit_knowledge_changed(self) -> None:
        """通知外部数据已变更。"""
        self.knowledge_changed.emit()

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
