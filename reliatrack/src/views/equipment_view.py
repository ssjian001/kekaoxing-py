"""设备管理 Tab — 设备列表 + 增删改查。"""

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
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import QEvent, Signal, Qt
from PySide6.QtGui import QColor

from src.models.common import Equipment
from src.styles.theme import (
    CRUST,
    OVERLAY0,
    SURFACE0,
    SURFACE1,
    TEXT,
    SUBTEXT0,
    GREEN,
    RED,
    BLUE,
    YELLOW,
)
from src.styles.constants import EQUIPMENT_STATUS_COLORS, VIEW_MARGINS


class EquipmentView(QWidget):
    """设备管理视图 — 顶部工具栏 + 表格。"""

    equipment_changed = Signal()  # 增删改后发射

    # 表格列：(显示名, 对应 Equipment 属性)
    _COLUMNS = [
        ("ID", "id"),
        ("型号", "model"),
        ("名称", "name"),
        ("类型", "type"),
        ("校准日期", "calibration_date"),
        ("下次校准", "next_calibration_date"),
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

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索设备名称 / 型号 / 类型…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMinimumWidth(160)
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setProperty("class", "action")
        self.btn_edit.setMinimumWidth(70)
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setMinimumWidth(70)
        toolbar.addWidget(self.btn_delete)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {SURFACE1};")
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("新增")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.setMinimumWidth(70)
        toolbar.addWidget(self.btn_add)
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
        self._table.setSortingEnabled(True)

        # 列宽
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 型号
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)            # 名称
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 类型
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 校准日期
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # 下次校准
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # 状态

        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # 空状态提示
        self._empty_label = QLabel("暂无设备数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 14px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

    # ── 数据加载 ────────────────────────────────────────────────

    def refresh(self, equipment_list: list[Equipment]) -> None:
        """刷新设备表格。"""
        self._equip_list = equipment_list
        self._populate_table(equipment_list)

    def _populate_table(self, items: list[Equipment]) -> None:
        """填充表格。"""
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        self._table.setRowCount(len(items))
        for row, eq in enumerate(items):
            for col, (_, attr) in enumerate(self._COLUMNS):
                value = getattr(eq, attr, "")
                # 格式化状态显示
                if attr == "status":
                    status_map = {
                        "available": "正常",
                        "maintenance": "维修中",
                        "offline": "停用",
                    }
                    value = status_map.get(str(value), str(value))
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, eq.id)
                # 居中对齐
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 状态列着色
                if attr == "status":
                    color = EQUIPMENT_STATUS_COLORS.get(str(value) if value else "", TEXT)
                    item.setForeground(QColor(color))
                self._table.setItem(row, col, item)
        header.blockSignals(False)

        self._update_empty_state()

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
        ]
        self._populate_table(filtered)

    def _on_double_click(self, row: int, _col: int) -> None:
        """双击行触发编辑。"""
        self.btn_edit.click()

    # ── 公开方法 ────────────────────────────────────────────────

    def emit_equipment_changed(self) -> None:
        """通知外部数据已变更。"""
        self.equipment_changed.emit()

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
