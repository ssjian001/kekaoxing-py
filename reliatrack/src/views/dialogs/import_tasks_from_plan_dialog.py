"""从其他计划导入任务弹窗。"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from src.models.test_plan import TestTask
from src.styles.theme import SUBTEXT0, LAVENDER
from src.styles.constants import install_copy_handler
from src.views.dialogs.base_dialog import _BaseDialog

if TYPE_CHECKING:
    pass

class ImportTasksFromPlanDialog(_BaseDialog):
    """从其他计划导入任务弹窗。"""
    def __init__(
        self,
        tasks: list[TestTask],
        source_plan_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("从其他计划导入任务", parent, width=700)
        self._tasks = tasks
        self._source_plan_name = source_plan_name
        
        # ── 来源提示 ──
        hint = QLabel(f"来源计划: {source_plan_name}  |  共 {len(tasks)} 个任务")
        hint.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px; padding: 2px 0;")
        self._form.addRow(hint)
        
        # ── 搜索 + 全选/清空 ──
        search_bar = QWidget()
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(0, 0, 0, 4)
        search_layout.setSpacing(6)
        
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索任务名…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        
        sel_all = QPushButton("全选")
        sel_all.setProperty("class", "action")
        sel_all.setFixedWidth(60)
        sel_all.clicked.connect(self._select_all)
        
        desel_all = QPushButton("清空")
        desel_all.setProperty("class", "action")
        desel_all.setFixedWidth(60)
        desel_all.clicked.connect(self._deselect_all)
        
        self._count_label = QLabel("已选 0 项")
        self._count_label.setStyleSheet(f"color: {LAVENDER}; font-weight: bold;")
        
        search_layout.addWidget(self._search, stretch=1)
        search_layout.addWidget(sel_all)
        search_layout.addWidget(desel_all)
        search_layout.addWidget(self._count_label)
        self._form.addRow(search_bar)
        
        # ── 任务表格 ──
        self._table = QTableWidget(len(tasks), 7)
        self._table.setHorizontalHeaderLabels(
            ["", "任务名", "测试类别", "测试标准", "工期", "优先级", "温度"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 30)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        install_copy_handler(self._table)
        for row, task in enumerate(tasks):
            # checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self._table.setItem(row, 0, chk)
            self._table.setItem(row, 1, QTableWidgetItem(task.name))
            self._table.setItem(row, 2, QTableWidgetItem(task.category))
            self._table.setItem(row, 3, QTableWidgetItem(task.test_standard))
            self._table.setItem(row, 4, QTableWidgetItem(str(task.duration)))
            self._table.setItem(row, 5, QTableWidgetItem(str(task.priority)))
            self._table.setItem(row, 6, QTableWidgetItem(
                f"{task.temperature} {task.humidity}".strip()
            ))
        
        self._table.itemChanged.connect(self._on_item_changed)
        self._form.addRow(self._table)
    
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._update_count()
    
    def _update_count(self) -> None:
        n = sum(
            1 for r in range(self._table.rowCount())
            if self._table.item(r, 0)
            and self._table.item(r, 0).checkState() == Qt.CheckState.Checked
        )
        self._count_label.setText(f"已选 {n} 项")
    
    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for r in range(self._table.rowCount()):
            name_item = self._table.item(r, 1)
            match = not keyword or keyword in (name_item.text().lower() if name_item else "")
            self._table.setRowHidden(r, not match)
    
    def _select_all(self) -> None:
        self._table.blockSignals(True)
        for r in range(self._table.rowCount()):
            if not self._table.isRowHidden(r):
                item = self._table.item(r, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)
        self._table.blockSignals(False)
        self._update_count()
    
    def _deselect_all(self) -> None:
        self._table.blockSignals(True)
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._table.blockSignals(False)
        self._update_count()
    
    def get_selected_tasks(self) -> list[TestTask]:
        """返回用户勾选的任务列表。"""
        result = []
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(self._tasks[r])
        return result
