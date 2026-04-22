"""资源配置视图 - 样品池和设备管理"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QAbstractItemView,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QTextEdit,
    QComboBox, QGroupBox, QMessageBox, QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.db.database import Database
from src.models import Resource, ResourceType, UnavailablePeriod


class ResourceView(QWidget):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # 样品池 Tab
        self.pool_widget = QWidget()
        pool_layout = QVBoxLayout(self.pool_widget)

        # 样品池搜索框
        self.pool_search_edit = QLineEdit()
        self.pool_search_edit.setPlaceholderText("🔍 搜索名称/分类...")
        self.pool_search_edit.textChanged.connect(lambda text: self._filter_resource_table(self.pool_table, text, name_col=1, category_col=2))
        pool_layout.addWidget(self.pool_search_edit)

        self.pool_table = QTableWidget()
        self.pool_table.setColumnCount(6)
        self.pool_table.setHorizontalHeaderLabels(["ID", "名称", "类型", "可用数量", "单位", "描述"])
        self.pool_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pool_table.verticalHeader().setVisible(False)
        self.pool_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pool_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pool_table.setAlternatingRowColors(True)
        self.pool_table.setSortingEnabled(True)
        pool_layout.addWidget(self.pool_table)

        # 样品池空状态提示
        self._pool_empty_hint = QLabel("📦 暂无样品池数据\n点击「➕ 添加样品池」开始")
        self._pool_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pool_empty_hint.setStyleSheet("color: #a6adc8; font-size: 14px;")
        self._pool_empty_hint.setWordWrap(True)
        self._pool_empty_hint.setParent(self.pool_table)
        self._pool_empty_hint.setGeometry(0, 0, 800, 200)
        self._pool_empty_hint.hide()

        pool_btn_layout = QHBoxLayout()
        btn_pool_add = QPushButton("➕ 添加样品池")
        btn_pool_add.setObjectName("primaryBtn")
        btn_pool_add.clicked.connect(lambda: self._show_resource_dialog(ResourceType.SAMPLE_POOL))
        pool_btn_layout.addWidget(btn_pool_add)

        btn_pool_edit = QPushButton("✏️ 编辑样品池")
        btn_pool_edit.clicked.connect(lambda: self._show_resource_dialog(ResourceType.SAMPLE_POOL, edit=True))
        pool_btn_layout.addWidget(btn_pool_edit)

        btn_pool_del = QPushButton("🗑️ 删除样品池")
        btn_pool_del.setObjectName("dangerBtn")
        btn_pool_del.clicked.connect(self._delete_pool)
        pool_btn_layout.addWidget(btn_pool_del)

        pool_layout.addLayout(pool_btn_layout)
        self.tabs.addTab(self.pool_widget, "📦 样品池")

        # 设备 Tab
        self.equip_widget = QWidget()
        equip_layout = QVBoxLayout(self.equip_widget)

        # 设备搜索框
        self.equip_search_edit = QLineEdit()
        self.equip_search_edit.setPlaceholderText("🔍 搜索名称/分类...")
        self.equip_search_edit.textChanged.connect(lambda text: self._filter_resource_table(self.equip_table, text, name_col=1, category_col=2))
        equip_layout.addWidget(self.equip_search_edit)

        self.equip_table = QTableWidget()
        self.equip_table.setColumnCount(7)
        self.equip_table.setHorizontalHeaderLabels(["ID", "名称", "分类", "可用数量", "单位", "图标", "描述"])
        self.equip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.equip_table.verticalHeader().setVisible(False)
        self.equip_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.equip_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.equip_table.setAlternatingRowColors(True)
        self.equip_table.setSortingEnabled(True)
        equip_layout.addWidget(self.equip_table)

        # 设备空状态提示
        self._equip_empty_hint = QLabel("🔧 暂无设备数据\n点击「➕ 添加设备」开始")
        self._equip_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._equip_empty_hint.setStyleSheet("color: #a6adc8; font-size: 14px;")
        self._equip_empty_hint.setWordWrap(True)
        self._equip_empty_hint.setParent(self.equip_table)
        self._equip_empty_hint.setGeometry(0, 0, 800, 200)
        self._equip_empty_hint.hide()

        equip_btn_layout = QHBoxLayout()
        btn_equip_add = QPushButton("➕ 添加设备")
        btn_equip_add.setObjectName("primaryBtn")
        btn_equip_add.clicked.connect(lambda: self._show_resource_dialog(ResourceType.EQUIPMENT))
        equip_btn_layout.addWidget(btn_equip_add)

        btn_equip_edit = QPushButton("✏️ 编辑")
        btn_equip_edit.clicked.connect(lambda: self._show_resource_dialog(ResourceType.EQUIPMENT, edit=True))
        equip_btn_layout.addWidget(btn_equip_edit)

        btn_equip_del = QPushButton("🗑️ 删除")
        btn_equip_del.setObjectName("dangerBtn")
        btn_equip_del.clicked.connect(self._delete_equipment)
        equip_btn_layout.addWidget(btn_equip_del)

        equip_layout.addLayout(equip_btn_layout)
        self.tabs.addTab(self.equip_widget, "🔧 设备")

        layout.addWidget(self.tabs)

    def refresh(self):
        resources = self.db.get_all_resources()

        # 样品池
        pools = [r for r in resources if r.type == ResourceType.SAMPLE_POOL]
        self.pool_table.setSortingEnabled(False)
        self.pool_table.setRowCount(len(pools))
        for i, r in enumerate(pools):
            vals = [str(r.id), r.name, r.category, str(r.available_qty), r.unit, r.description]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                self.pool_table.setItem(i, j, item)
        self.pool_table.setSortingEnabled(True)

        # 样品池空状态提示
        if not pools:
            self._pool_empty_hint.show()
            self._pool_empty_hint.raise_()
        else:
            self._pool_empty_hint.hide()

        # 设备
        equips = [r for r in resources if r.type == ResourceType.EQUIPMENT]
        self.equip_table.setSortingEnabled(False)
        self.equip_table.setRowCount(len(equips))
        for i, r in enumerate(equips):
            vals = [str(r.id), r.name, r.category, str(r.available_qty), r.unit, r.icon, r.description]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                self.equip_table.setItem(i, j, item)
        self.equip_table.setSortingEnabled(True)

        # 设备空状态提示
        if not equips:
            self._equip_empty_hint.show()
            self._equip_empty_hint.raise_()
        else:
            self._equip_empty_hint.hide()

    def _filter_resource_table(self, table: QTableWidget, text: str, name_col: int = 1, category_col: int = 2):
        """根据搜索文本过滤表格行（按名称和分类列匹配）"""
        keyword = text.strip().lower()
        for row in range(table.rowCount()):
            if not keyword:
                table.setRowHidden(row, False)
                continue
            name_item = table.item(row, name_col)
            cat_item = table.item(row, category_col)
            name = name_item.text().lower() if name_item else ""
            cat = cat_item.text().lower() if cat_item else ""
            match = keyword in name or keyword in cat
            table.setRowHidden(row, not match)

    def _show_resource_dialog(self, res_type: ResourceType, edit: bool = False):
        """显示资源编辑对话框"""
        if edit:
            if res_type == ResourceType.EQUIPMENT:
                row = self.equip_table.currentRow()
                if row < 0:
                    QMessageBox.warning(self, "提示", "请先选择一个设备")
                    return
                res_id = int(self.equip_table.item(row, 0).text())
            elif res_type == ResourceType.SAMPLE_POOL:
                row = self.pool_table.currentRow()
                if row < 0:
                    QMessageBox.warning(self, "提示", "请先选择一个样品池")
                    return
                res_id = int(self.pool_table.item(row, 0).text())
            else:
                resource = None
                dialog = ResourceDialog(resource, res_type, self)
                if dialog.exec() == QDialog.Accepted:
                    self.db.insert_resource(dialog.get_resource())
                self.refresh()
                return
            resource = self.db.get_resource(res_id)
            if not resource:
                return
        else:
            resource = None

        dialog = ResourceDialog(resource, res_type, self)
        if dialog.exec() == QDialog.Accepted:
            self.db.update_resource(dialog.get_resource()) if resource else \
                self.db.insert_resource(dialog.get_resource())
            self.refresh()

    def _delete_equipment(self):
        row = self.equip_table.currentRow()
        if row < 0:
            return
        res_id = int(self.equip_table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除该设备吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_resource(res_id)
            self.refresh()

    def _delete_pool(self):
        row = self.pool_table.currentRow()
        if row < 0:
            return
        res_id = int(self.pool_table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除该样品池吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_resource(res_id)
            self.refresh()


class ResourceDialog(QDialog):
    def __init__(self, resource: Resource | None, res_type: ResourceType, parent=None):
        super().__init__(parent)
        self.res_type = res_type
        self.resource = resource
        self.setWindowTitle("编辑资源" if resource else "添加资源")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit(resource.name if resource else "")
        layout.addRow("名称:", self.name_edit)

        self._name_hint = QLabel("")
        self._name_hint.setStyleSheet("color: #f38ba8; font-size: 11px;")
        layout.addRow("", self._name_hint)
        self.name_edit.textChanged.connect(self._validate_name)

        self.category_edit = QLineEdit(resource.category if resource else "")
        layout.addRow("分类:", self.category_edit)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 100)
        self.qty_spin.setValue(resource.available_qty if resource else 1)
        layout.addRow("可用数量:", self.qty_spin)

        self.unit_edit = QLineEdit(resource.unit if resource else "台")
        layout.addRow("单位:", self.unit_edit)

        self.icon_edit = QLineEdit(resource.icon if resource else "📦")
        layout.addRow("图标:", self.icon_edit)

        self.desc_edit = QLineEdit(resource.description if resource else "")
        layout.addRow("描述:", self.desc_edit)

        # 不可用时段
        unavail_group = QGroupBox("不可用时段")
        unavail_layout = QVBoxLayout(unavail_group)

        self.unavail_table = QTableWidget(0, 3)
        self.unavail_table.setHorizontalHeaderLabels(["开始天数", "结束天数", "原因"])
        self.unavail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.unavail_table.verticalHeader().setVisible(False)
        self.unavail_table.setMaximumHeight(120)
        if resource and resource.unavailable_periods:
            self.unavail_table.setRowCount(len(resource.unavailable_periods))
            for i, p in enumerate(resource.unavailable_periods):
                self.unavail_table.setItem(i, 0, QTableWidgetItem(str(p.start_day)))
                self.unavail_table.setItem(i, 1, QTableWidgetItem(str(p.end_day)))
                self.unavail_table.setItem(i, 2, QTableWidgetItem(p.reason))
        unavail_layout.addWidget(self.unavail_table)

        unavail_btn_layout = QHBoxLayout()
        btn_add_period = QPushButton("➕ 添加")
        btn_add_period.clicked.connect(self._add_unavail_row)
        btn_del_period = QPushButton("🗑️ 删除")
        btn_del_period.clicked.connect(self._del_unavail_row)
        unavail_btn_layout.addWidget(btn_add_period)
        unavail_btn_layout.addWidget(btn_del_period)
        unavail_btn_layout.addStretch()
        unavail_layout.addLayout(unavail_btn_layout)

        layout.addRow(unavail_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确认")
        btn_ok.setObjectName("primaryBtn")
        btn_ok.clicked.connect(self._on_accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

    def _add_unavail_row(self):
        row = self.unavail_table.rowCount()
        self.unavail_table.insertRow(row)

    def _del_unavail_row(self):
        rows = set(item.row() for item in self.unavail_table.selectedItems())
        for row in sorted(rows, reverse=True):
            self.unavail_table.removeRow(row)

    def _validate_name(self, text: str):
        """实时验证名称非空"""
        if not text.strip():
            self._name_hint.setText("⚠ 名称不能为空")
            self.name_edit.setStyleSheet("border: 1px solid #f38ba8;")
        else:
            self._name_hint.setText("")
            self.name_edit.setStyleSheet("")

    def _on_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "名称不能为空")
            self.name_edit.setFocus()
            return
        self.accept()

    def get_resource(self) -> Resource:
        # Collect unavailable periods from table
        periods: list[UnavailablePeriod] = []
        for i in range(self.unavail_table.rowCount()):
            start_item = self.unavail_table.item(i, 0)
            end_item = self.unavail_table.item(i, 1)
            reason_item = self.unavail_table.item(i, 2)
            if start_item and end_item:
                periods.append(UnavailablePeriod(
                    start_day=int(start_item.text()),
                    end_day=int(end_item.text()),
                    reason=reason_item.text() if reason_item else "",
                ))

        return Resource(
            id=self.resource.id if self.resource else 0,
            name=self.name_edit.text(),
            type=self.res_type,
            category=self.category_edit.text(),
            unit=self.unit_edit.text(),
            available_qty=self.qty_spin.value(),
            icon=self.icon_edit.text(),
            description=self.desc_edit.text(),
            unavailable_periods=periods,
        )
