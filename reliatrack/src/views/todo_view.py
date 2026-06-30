"""待办事项 Tab — 轻量级待办列表，按项目筛选。"""

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
    QComboBox,
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QColor

from src.models.todo import TodoItem
from src.models.project import Project
from src.styles.constants import VIEW_MARGINS, apply_column_specs
import src.styles.theme as _theme

_TODO_COLUMN_SPECS = [
    ("状态", "fixed", 50),
    ("标题", "interactive", 280),
    ("优先级", "fixed", 70),
    ("状态文本", "fixed", 80),
    ("截止日期", "fixed", 110),
    ("分类", "fixed", 80),
]

_PRIORITY_COLORS = {
    "high": "#e64553",
    "medium": "#df8e1d",
    "low": "#40a02b",
}

_STATUS_CYCLE = {"pending": "in_progress", "in_progress": "done", "done": "pending"}


class TodoView(QWidget):
    """待办事项视图 — 项目筛选 + 表格列表。"""

    todo_changed = Signal()

    _COLUMNS = [
        ("状态", "status"),       # 0 — checkbox 列
        ("标题", "title"),         # 1
        ("优先级", "priority"),    # 2 — 颜色标记
        ("状态", "status_label"),  # 3
        ("截止日期", "due_date"),  # 4
        ("分类", "category"),      # 5
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo_list: list[TodoItem] = []
        self._all_projects: list[Project] = []
        self._setup_ui()

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)
        layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(180)
        self._project_combo.addItem("全部项目", None)
        self._project_combo.currentIndexChanged.connect(self._on_project_filter_changed)
        toolbar.addWidget(QLabel("项目:"))
        toolbar.addWidget(self._project_combo)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索待办标题…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMinimumWidth(160)
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        self.btn_edit.setToolTip("编辑选中待办 (F2)")
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        self.btn_delete.setToolTip("删除选中待办 (Delete)")
        toolbar.addWidget(self.btn_delete)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setProperty("class", "separator")
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("新增")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        self.btn_add.setToolTip("新增待办事项 (Ctrl+N)")
        toolbar.addWidget(self.btn_add)
        layout.addLayout(toolbar)

        # 表格
        self._table = QTableWidget()
        apply_column_specs(self._table, _TODO_COLUMN_SPECS, "todo_table")
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)

        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # 右键菜单
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu = QMenu(self._table)
        self._ctx_act_toggle = self._context_menu.addAction("切换状态")
        self._ctx_act_edit = self._context_menu.addAction("编辑")
        self._ctx_act_delete = self._context_menu.addAction("删除")
        self._ctx_act_toggle.triggered.connect(self._on_ctx_toggle)
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)
        self._ctx_act_delete.triggered.connect(self._on_ctx_delete)

        # 空状态提示
        self._empty_label = QLabel("暂无待办事项")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "empty-label")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

    # ── 项目筛选 ──────────────────────────────────────────────

    def set_projects(self, projects: list[Project]) -> None:
        """设置项目下拉列表。"""
        self._all_projects = projects
        self._project_combo.blockSignals(True)
        current_id = self._project_combo.currentData()
        self._project_combo.clear()
        self._project_combo.addItem("全部项目", None)
        for p in projects:
            self._project_combo.addItem(p.name, p.id)
        # 恢复选中
        if current_id is not None:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == current_id:
                    self._project_combo.setCurrentIndex(i)
                    break
        self._project_combo.blockSignals(False)

    def get_selected_project_id(self) -> int | None:
        """获取当前选中的项目 ID（None = 全部）。"""
        return self._project_combo.currentData()

    def _on_project_filter_changed(self, _index: int) -> None:
        """项目筛选变化时重新填充表格。"""
        self._populate_table(self._todo_list)

    # ── 数据加载 ──────────────────────────────────────────────

    def refresh(self, todo_list: list[TodoItem], projects: list[Project] | None = None) -> None:
        """刷新待办表格。"""
        if projects is not None:
            self.set_projects(projects)
        self._todo_list = todo_list
        self._populate_table(todo_list)

    def _populate_table(self, items: list[TodoItem]) -> None:
        """填充表格（按项目筛选后）。"""
        project_id = self._project_combo.currentData()
        if project_id is not None:
            items = [t for t in items if t.project_id == project_id]

        self._table.setSortingEnabled(False)
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        self._table.setRowCount(len(items))
        for row, todo in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(todo, attr, "")
                text = str(value) if value else ""
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, todo.id)
                if col == 0:
                    # 状态列 — checkbox 样式
                    item.setText("✓" if todo.is_done else "○")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if todo.is_done:
                        item.setForeground(QColor("#40a02b"))
                    else:
                        item.setForeground(QColor(_theme.SUBTEXT0))
                elif col == 1:
                    # 标题
                    if todo.is_done:
                        item.setForeground(QColor(_theme.SUBTEXT0))
                    if len(text) > 80:
                        item.setToolTip(text)
                elif col == 2:
                    # 优先级 — 颜色标记
                    item.setText(todo.priority_label)
                    color = _PRIORITY_COLORS.get(todo.priority, _theme.TEXT)
                    item.setForeground(QColor(color))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col == 3:
                    # 状态文本
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col == 4:
                    # 截止日期
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col == 5:
                    # 分类
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)
        header.blockSignals(False)
        self._table.setSortingEnabled(True)
        self._update_empty_state()

    # ── 选中 & 搜索 ──────────────────────────────────────────

    def get_selected_todo(self) -> TodoItem | None:
        """获取当前选中的待办对象。"""
        row = self._table.currentRow()
        if row < 0:
            return None
        id_item = self._table.item(row, 0)
        if id_item is None:
            return None
        target_id = id_item.data(Qt.ItemDataRole.UserRole)
        for todo in self._todo_list:
            if todo.id == target_id:
                return todo
        return None

    def _on_search(self, text: str) -> None:
        """客户端搜索过滤。"""
        keyword = text.strip().lower()
        if not keyword:
            self._populate_table(self._todo_list)
            return
        filtered = [
            t for t in self._todo_list
            if keyword in (t.title or "").lower()
        ]
        self._populate_table(filtered)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """点击状态列切换状态。"""
        if col == 0:
            todo = self._find_todo_by_row(row)
            if todo is not None and todo.id is not None:
                from src.services.todo_service import TodoService
                # 通过 handler 切换
                self.toggle_requested.emit(todo.id)

    def _find_todo_by_row(self, row: int) -> TodoItem | None:
        id_item = self._table.item(row, 0)
        if id_item is None:
            return None
        target_id = id_item.data(Qt.ItemDataRole.UserRole)
        for todo in self._todo_list:
            if todo.id == target_id:
                return todo
        return None

    def _on_double_click(self, row: int, _col: int) -> None:
        """双击行触发编辑。"""
        self.btn_edit.click()

    # ── 右键菜单 ──────────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        self._table.selectRow(row)
        self._context_menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_ctx_toggle(self) -> None:
        if todo := self.get_selected_todo():
            if todo.id is not None:
                self.toggle_requested.emit(todo.id)

    def _on_ctx_edit(self) -> None:
        self.btn_edit.click()

    def _on_ctx_delete(self) -> None:
        self.btn_delete.click()

    # ── 信号 ──────────────────────────────────────────────────

    toggle_requested = Signal(int)  # 切换状态信号，携带 todo_id

    def emit_todo_changed(self) -> None:
        self.todo_changed.emit()

    # ── 空状态 ────────────────────────────────────────────────

    def _update_empty_state(self) -> None:
        if self._table.rowCount() == 0:
            self._empty_label.setGeometry(self._table.viewport().rect())
            self._empty_label.show()
        else:
            self._empty_label.hide()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._table and event.type() == QEvent.Type.Resize:
            self._empty_label.setGeometry(self._table.viewport().rect())
        return super().eventFilter(obj, event)
