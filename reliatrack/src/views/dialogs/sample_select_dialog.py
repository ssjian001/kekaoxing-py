"""样品多选弹窗 — 从当前项目下的样品池中选取关联样品。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models.sample import Sample
from src.styles.constants import install_copy_handler
# 清理死 import（2026-06-01 review 修复）
from src.views.dialogs.base_dialog import _BaseDialog

if TYPE_CHECKING:
    pass


class SampleSelectDialog(_BaseDialog):
    """样品多选弹窗 — 支持搜索过滤、勾选、统计。

    Parameters
    ----------
    samples:
        当前项目下的样品列表。
    selected_ids:
        已选中的样品 ID 列表（编辑时预选）。
    """

    # 状态显示映射
    _STATUS_LABELS: dict[str, str] = {
        "in_stock": "在库",
        "checked_out": "已出库",
        "in_test": "测试中",
        "suspended": "暂停",
        "scrapped": "已报废",
        "returned": "已归还",
    }

    def __init__(
        self,
        samples: list[Sample],
        selected_ids: list[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "选择关联样品",
            parent,
            width=580,
        )
        self._samples = samples
        self._selected_ids = set(selected_ids or [])

        # ── 搜索栏 ──
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 4)
        search_layout.setSpacing(6)

        search_label = QLabel("搜索:")
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入 SN 或批次号过滤…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filter)

        select_all_btn = QPushButton("全选")
        select_all_btn.setProperty("class", "action")
        select_all_btn.setFixedWidth(60)
        select_all_btn.clicked.connect(self._select_all)

        deselect_all_btn = QPushButton("清空")
        deselect_all_btn.setProperty("class", "action")
        deselect_all_btn.setFixedWidth(60)
        deselect_all_btn.clicked.connect(self._deselect_all)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self._search_edit, stretch=1)
        search_layout.addWidget(select_all_btn)
        search_layout.addWidget(deselect_all_btn)

        self._form.addRow(search_container)

        # ── 样品表格 ──
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["☑", "SN", "批次号", "状态"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(0, 40)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        install_copy_handler(self._table)
        self._table.setMinimumHeight(280)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_item_changed)

        self._form.addRow(self._table)

        # ── 底部统计 ──
        self._stats_label = QLabel()
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._form.addRow(self._stats_label)

        # 填充表格
        self._populate_table()
        self._update_stats()

    # ── 表格操作 ───────────────────────────────────────────────

    def _populate_table(self) -> None:
        """填充样品表格数据。"""
        self._table.setRowCount(0)
        self._table.blockSignals(True)
        for sample in self._samples:
            row = self._table.rowCount()
            self._table.insertRow(row)

            # 勾选列
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            if sample.id in self._selected_ids:
                check_item.setCheckState(Qt.CheckState.Checked)
            else:
                check_item.setCheckState(Qt.CheckState.Unchecked)
            check_item.setData(Qt.ItemDataRole.UserRole, sample.id)
            self._table.setItem(row, 0, check_item)

            # SN
            sn_item = QTableWidgetItem(sample.sn)
            sn_item.setData(Qt.ItemDataRole.UserRole, sample.id)
            self._table.setItem(row, 1, sn_item)

            # 批次号
            batch_item = QTableWidgetItem(sample.batch_no)
            self._table.setItem(row, 2, batch_item)

            # 状态
            status_label = self._STATUS_LABELS.get(sample.status, sample.status)
            status_item = QTableWidgetItem(status_label)
            self._table.setItem(row, 3, status_item)

        self._table.blockSignals(False)

    def _apply_filter(self, text: str) -> None:
        """按搜索文本过滤表格行。"""
        keyword = text.strip().lower()
        for row in range(self._table.rowCount()):
            sn_item = self._table.item(row, 1)
            batch_item = self._table.item(row, 2)
            sn = sn_item.text().lower() if sn_item else ""
            batch = batch_item.text().lower() if batch_item else ""
            match = not keyword or keyword in sn or keyword in batch
            self._table.setRowHidden(row, not match)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """勾选状态变更时更新统计。"""
        if item.column() == 0:
            self._update_stats()

    def _select_all(self) -> None:
        """全选可见行。"""
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            if not self._table.isRowHidden(row):
                check_item = self._table.item(row, 0)
                if check_item:
                    check_item.setCheckState(Qt.CheckState.Checked)
        self._table.blockSignals(False)
        self._update_stats()

    def _deselect_all(self) -> None:
        """清空所有勾选。"""
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            check_item = self._table.item(row, 0)
            if check_item:
                check_item.setCheckState(Qt.CheckState.Unchecked)
        self._table.blockSignals(False)
        self._update_stats()

    def _update_stats(self) -> None:
        """更新底部统计标签。"""
        checked = self._get_checked_count()
        total = len(self._samples)
        self._stats_label.setText(f"已选 {checked} / 共 {total} 个")

    def _get_checked_count(self) -> int:
        """获取当前勾选数量。"""
        count = 0
        for row in range(self._table.rowCount()):
            check_item = self._table.item(row, 0)
            if check_item and check_item.checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    # ── 公开 API ───────────────────────────────────────────────

    def get_selected_ids(self) -> list[int]:
        """返回勾选的样品 ID 列表。"""
        selected: list[int] = []
        for row in range(self._table.rowCount()):
            check_item = self._table.item(row, 0)
            if check_item and check_item.checkState() == Qt.CheckState.Checked:
                sample_id = check_item.data(Qt.ItemDataRole.UserRole)
                if sample_id is not None:
                    selected.append(sample_id)
        return selected
