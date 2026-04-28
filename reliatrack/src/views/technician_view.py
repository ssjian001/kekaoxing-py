"""技术员管理 Tab — 技术员列表 + 增删改查。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import QEvent, Signal, Qt

from src.models.common import Technician
from src.styles.theme import (
    OVERLAY0,
    SURFACE0,
    SURFACE1,
    TEXT,
)
from src.styles.constants import VIEW_MARGINS


class TechnicianView(QWidget):
    """技术员管理视图 — 顶部工具栏 + 表格。"""

    technician_changed = Signal()  # 增删改后发射

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

        # 页面标题
        title = QLabel("👷 技术员管理")
        title.setStyleSheet(f"color: {TEXT}; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍 搜索姓名 / 工号 / 部门…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setFixedWidth(280)
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        self.btn_add = QPushButton("➕ 新增")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        toolbar.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏️ 编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑 删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in self._COLUMNS])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)

        # 列宽
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 工号
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)            # 姓名
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 部门
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 职位
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # 联系方式
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)            # 邮箱

        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # 空状态提示
        self._empty_label = QLabel("暂无技术员数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 16px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

    # ── 数据加载 ────────────────────────────────────────────────

    def refresh(self, technician_list: list[Technician]) -> None:
        """刷新技术员表格。"""
        self._tech_list = technician_list
        self._populate_table(technician_list)

    def _populate_table(self, items: list[Technician]) -> None:
        """填充表格。"""
        self._table.setRowCount(len(items))
        for row, tech in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(tech, attr, "")
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, tech.id)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)

        self._update_empty_state()

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

    # ── 公开方法 ────────────────────────────────────────────────

    def emit_technician_changed(self) -> None:
        """通知外部数据已变更。"""
        self.technician_changed.emit()

    # ── 空状态 ────────────────────────────────────────────────

    def _update_empty_state(self) -> None:
        """根据表格行数显示/隐藏空状态提示。"""
        if self._table.rowCount() == 0:
            self._empty_label.setGeometry(self._table.viewport().rect())
            self._empty_label.show()
        else:
            self._empty_label.hide()

    def eventFilter(self, obj, event) -> bool:
        """监听表格缩放以更新空状态标签位置。"""
        if obj is self._table and event.type() == QEvent.Type.Resize:
            self._empty_label.setGeometry(self._table.viewport().rect())
        return super().eventFilter(obj, event)
