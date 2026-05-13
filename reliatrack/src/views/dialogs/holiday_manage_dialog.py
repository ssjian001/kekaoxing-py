"""节假日管理弹窗 — 查看、添加、删除自定义节假日。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from src.styles.theme import TEXT, SUBTEXT0
from src.views.dialogs.base_dialog import _BaseDialog

if TYPE_CHECKING:
    from src.services.holiday_service import HolidayService


class HolidayManageDialog(_BaseDialog):
    """节假日管理弹窗 — 按年份查看、添加、删除节假日。"""

    def __init__(
        self,
        holiday_service: HolidayService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("节假日管理", parent=parent, width=560)
        self._svc = holiday_service
        self._current_year: int = QDate.currentDate().year()

        # ── 年份选择 ──
        year_row = QHBoxLayout()
        year_label = QLabel("年份：")
        year_label.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        year_row.addWidget(year_label)

        self._year_combo = QComboBox()
        self._year_combo.setMinimumWidth(100)
        for y in range(self._current_year - 1, self._current_year + 3):
            self._year_combo.addItem(str(y), y)
        self._year_combo.setCurrentText(str(self._current_year))
        self._year_combo.currentIndexChanged.connect(self._load_list)
        year_row.addWidget(self._year_combo)
        year_row.addStretch()
        self._form.addRow(year_row)

        # ── 节假日列表 ──
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["日期", "名称", "来源"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().resizeSection(0, 120)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().resizeSection(2, 80)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(250)
        self._form.addRow(self._table)

        # ── 添加区 ──
        add_row = QHBoxLayout()
        add_label = QLabel("添加自定义节假日：")
        add_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 12px;")
        add_row.addWidget(add_label)
        self._form.addRow(add_row)

        input_row = QHBoxLayout()
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setMinimumWidth(130)
        input_row.addWidget(self._date_edit)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("假日名称（如：公司周年庆）")
        self._name_edit.setMinimumWidth(160)
        input_row.addWidget(self._name_edit)

        btn_add = QPushButton("添加")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add)
        input_row.addWidget(btn_add)
        self._form.addRow(input_row)

        # ── 删除按钮 ──
        btn_del_row = QHBoxLayout()
        btn_del_row.addStretch()
        self._btn_delete = QPushButton("删除选中")
        self._btn_delete.setProperty("class", "action")
        self._btn_delete.clicked.connect(self._on_delete)
        btn_del_row.addWidget(self._btn_delete)
        self._form.addRow(btn_del_row)

        # 加载数据
        self._load_list()

    def _load_list(self) -> None:
        """重新加载节假日列表。"""
        idx = self._year_combo.currentData()
        if idx is not None:
            self._current_year = int(idx)
        records = self._svc.get_holidays(year=self._current_year)
        self._table.setRowCount(len(records))
        for row, rec in enumerate(records):
            date_item = QTableWidgetItem(str(rec["date"]))
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            date_item.setData(Qt.ItemDataRole.UserRole, rec["id"])
            self._table.setItem(row, 0, date_item)

            name_item = QTableWidgetItem(str(rec["name"]))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 1, name_item)

            source_item = QTableWidgetItem(str(rec["source"]))
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            source_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, source_item)

    def _on_add(self) -> None:
        """添加自定义节假日。"""
        date_str = self._date_edit.date().toString("yyyy-MM-dd")
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入假日名称。")
            return
        new_id = self._svc.add_holiday(date_str, name, source="custom")
        if new_id == 0:
            QMessageBox.warning(self, "添加失败", f"日期 {date_str} 已存在。")
            return
        self._name_edit.clear()
        # 切换到对应年份
        year = int(date_str[:4])
        idx = self._year_combo.findData(year)
        if idx >= 0:
            self._year_combo.setCurrentIndex(idx)
        self._load_list()

    def _on_delete(self) -> None:
        """删除选中的节假日。"""
        rows = set(item.row() for item in self._table.selectedItems())
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的行。")
            return
        ids = []
        for row in rows:
            item = self._table.item(row, 0)
            if item:
                hid = item.data(Qt.ItemDataRole.UserRole)
                source_item = self._table.item(row, 2)
                source = source_item.text() if source_item else ""
                ids.append((hid, source))

        if not ids:
            return

        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除 {len(ids)} 条节假日记录？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for hid, source in ids:
            self._svc.delete_holiday(hid)
        self._load_list()
