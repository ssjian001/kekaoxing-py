"""拖拽分配资源视图 — 从左侧资源列表拖拽设备到右侧矩阵给任务分配资源"""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import (
    Qt, Signal, QMimeData, QSize, QPoint,
)
from PySide6.QtGui import (
    QColor, QBrush, QFont, QDragEnterEvent, QDragMoveEvent, QDropEvent,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QSpinBox,
    QDialog, QDialogButtonBox, QProgressBar, QMenu, QApplication,
)

from src.models import Task, Resource, EquipmentRequirement

# ── Catppuccin Mocha 色彩 ─────────────────────────────────
C_BG = "#1e1e2e"
C_PANEL = "#181825"
C_BORDER = "#313244"
C_TEXT = "#cdd6f4"
C_SUBTEXT = "#a6adc8"
C_ACCENT = "#89b4fa"
C_GREEN = "#a6e3a1"
C_YELLOW = "#f9e2af"
C_RED = "#f38ba8"

# 单元格背景
C_CELL_ALLOC = QColor(137, 180, 250, 51)   # rgba(137,180,250,0.2)
C_CELL_OVER = QColor(243, 139, 168, 77)    # rgba(243,139,168,0.3)


# ── 左侧资源项自定义 Widget ─────────────────────────────
class _ResourceItemWidget(QWidget):
    """QListWidget 中每个资源项的自定义显示"""

    def __init__(self, resource: Resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # 第一行: 图标 + 名称 + 数量
        top = QHBoxLayout()
        top.setSpacing(6)
        icon_lbl = QLabel(self.resource.icon)
        icon_lbl.setStyleSheet("font-size: 16px;")
        name_lbl = QLabel(self.resource.name)
        name_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-weight: bold; font-size: 13px;"
        )
        qty_lbl = QLabel(f"{self.resource.available_qty}{self.resource.unit}")
        qty_lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 12px; margin-left: auto;"
        )
        top.addWidget(icon_lbl)
        top.addWidget(name_lbl)
        top.addWidget(qty_lbl)
        layout.addLayout(top)

        # 第二行: 使用率进度条
        bar_container = QHBoxLayout()
        bar_container.setContentsMargins(0, 0, 0, 0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_BORDER};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {C_GREEN};
                border-radius: 3px;
            }}
        """)
        bar_container.addWidget(self.progress_bar)

        self.rate_label = QLabel("0%")
        self.rate_label.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 11px; margin-left: 4px;"
        )
        self.rate_label.setFixedWidth(36)
        self.rate_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bar_container.addWidget(self.rate_label)
        layout.addLayout(bar_container)

    def set_usage_rate(self, rate: float):
        """rate 为 0~1 之间的使用率"""
        pct = min(int(rate * 100), 100)
        self.progress_bar.setValue(pct)
        self.rate_label.setText(f"{pct}%")
        if pct < 60:
            color = C_GREEN
        elif pct < 90:
            color = C_YELLOW
        else:
            color = C_RED
        self.rate_label.setStyleSheet(
            f"color: {color}; font-size: 11px; margin-left: 4px;"
        )
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_BORDER};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 3px;
            }}
        """)


# ── 左侧资源列表 (支持拖拽) ─────────────────────────────
class _ResourceListWidget(QListWidget):
    """左侧设备资源列表，可拖拽"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(f"""
            QListWidget {{
                background: {C_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                border: none;
                padding: 2px;
                margin: 2px 0;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background: {C_ACCENT}33;
            }}
            QListWidget::item:hover {{
                background: {C_BORDER};
            }}
        """)
        self.setSpacing(2)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return
        resource_id = item.data(Qt.ItemDataRole.UserRole)
        if resource_id is None:
            return
        mime = QMimeData()
        mime.setText(str(resource_id))
        drag = QApplication.dragObject(self)
        if drag is None:
            return
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)


# ── 右侧矩阵表格 (接受拖拽) ────────────────────────────
class _MatrixTable(QTableWidget):
    """任务 × 资源 矩阵，接受拖拽放置、双击编辑、右键清除"""

    cell_changed = Signal(int, int, int)  # task_idx, resource_idx, new_qty

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTableWidget.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.cellDoubleClicked.connect(self._on_double_click)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setHighlightSections(False)
        self.setStyleSheet(f"""
            QTableWidget {{
                background: {C_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                gridline-color: {C_BORDER};
                color: {C_TEXT};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background: {C_ACCENT}55;
            }}
            QHeaderView::section {{
                background: {C_BG};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                padding: 6px 4px;
                font-weight: bold;
                font-size: 12px;
            }}
            QScrollBar:vertical {{
                background: {C_BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar:horizontal {{
                background: {C_BG};
                height: 8px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {C_BORDER};
                border-radius: 4px;
                min-width: 20px;
            }}
        """)

    # ── 拖拽事件 ────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if not event.mimeData().hasText():
            event.ignore()
            return
        try:
            resource_id = int(event.mimeData().text())
        except ValueError:
            event.ignore()
            return

        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        item = self.itemAt(pos)
        if item is None:
            event.ignore()
            return

        row = item.row()
        col = item.column()
        # 仅处理数据行/数据列（非汇总行/列）
        if row < 0 or col < 1:
            event.ignore()
            return

        # 检查该列是否对应被拖拽的 resource_id
        res_id_at_col = self.horizontalHeaderItem(col)
        if res_id_at_col is None:
            event.ignore()
            return
        col_res_id = res_id_at_col.data(Qt.ItemDataRole.UserRole)
        if col_res_id is None or col_res_id != resource_id:
            event.ignore()
            return

        # +1
        current = item.data(Qt.ItemDataRole.UserRole) or 0
        new_qty = current + 1
        item.setData(Qt.ItemDataRole.UserRole, new_qty)
        self.cell_changed.emit(row, col, new_qty)
        self._update_cell_display(item, new_qty)
        self._update_row_total(row)
        self._update_col_total(col)

        event.acceptProposedAction()

    # ── 双击编辑 ────────────────────────────────────────

    def _on_double_click(self, row: int, col: int):
        """弹出 QSpinBox 对话框精确编辑数量"""
        # 跳过汇总行/列
        total_col = self.columnCount() - 1
        total_row = self.rowCount() - 1  # 总需求行
        if col == 0 or col == total_col or row >= total_row:
            return

        item = self.item(row, col)
        current = item.data(Qt.ItemDataRole.UserRole) or 0

        dialog = QDialog(self)
        dialog.setWindowTitle("编辑分配数量")
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {C_BG};
                color: {C_TEXT};
            }}
            QLabel {{
                color: {C_TEXT};
                font-size: 13px;
            }}
            QSpinBox {{
                background: {C_PANEL};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
                min-width: 100px;
            }}
            QPushButton {{
                background: {C_ACCENT};
                color: {C_BG};
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {C_ACCENT}cc;
            }}
        """)
        layout = QHBoxLayout(dialog)
        lbl = QLabel("数量:")
        spin = QSpinBox()
        spin.setRange(0, 999)
        spin.setValue(current)
        layout.addWidget(lbl)
        layout.addWidget(spin)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_qty = spin.value()
            item.setData(Qt.ItemDataRole.UserRole, new_qty)
            self.cell_changed.emit(row, col, new_qty)
            self._update_cell_display(item, new_qty)
            self._update_row_total(row)
            self._update_col_total(col)

    # ── 右键菜单 ────────────────────────────────────────

    def _on_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        if item is None:
            return
        row = item.row()
        col = item.column()
        total_col = self.columnCount() - 1
        total_row = self.rowCount() - 1
        if col == 0 or col == total_col or row >= total_row:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {C_PANEL};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {C_ACCENT}55;
            }}
        """)
        action = menu.addAction("清除分配")
        if menu.exec(self.viewport().mapToGlobal(pos)) == action:
            item.setData(Qt.ItemDataRole.UserRole, 0)
            self.cell_changed.emit(row, col, 0)
            self._update_cell_display(item, 0)
            self._update_row_total(row)
            self._update_col_total(col)

    # ── 单元格显示 ──────────────────────────────────────

    def _update_cell_display(self, item: QTableWidgetItem, qty: int):
        """更新单元格的文字和背景"""
        if qty == 0:
            item.setText("-")
            item.setForeground(QBrush(QColor(C_SUBTEXT)))
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
        else:
            item.setText(str(qty))
            item.setForeground(QBrush(QColor(C_TEXT)))
            item.setBackground(QBrush(C_CELL_ALLOC))
        item.setTextAlignment(Qt.AlignCenter)
        font = item.font()
        font.setBold(qty > 0)
        item.setFont(font)

    def _update_cell_overload(self, item: QTableWidgetItem, overload: bool):
        """如果是超载状态，设置红色背景"""
        if overload:
            item.setBackground(QBrush(C_CELL_OVER))
            item.setForeground(QBrush(QColor(C_RED)))
        elif item.data(Qt.ItemDataRole.UserRole) and item.data(Qt.ItemDataRole.UserRole) > 0:
            item.setBackground(QBrush(C_CELL_ALLOC))
            item.setForeground(QBrush(QColor(C_TEXT)))

    def _update_row_total(self, row: int):
        """更新某一行的总计列"""
        total_col = self.columnCount() - 1
        total = 0
        for c in range(1, total_col):
            it = self.item(row, c)
            if it:
                v = it.data(Qt.ItemDataRole.UserRole) or 0
                total += v
        total_item = self.item(row, total_col)
        if total_item:
            total_item.setText(str(total) if total > 0 else "-")
            total_item.setForeground(
                QBrush(QColor(C_TEXT) if total > 0 else QColor(C_SUBTEXT))
            )
            total_item.setTextAlignment(Qt.AlignCenter)

    def _update_col_total(self, col: int):
        """更新某一列的总需求行"""
        total_row = self.rowCount() - 3  # 总需求行
        available_row = total_row + 1
        status_row = total_row + 2
        total = 0
        task_count = total_row  # 任务行数
        for r in range(task_count):
            it = self.item(r, col)
            if it:
                v = it.data(Qt.ItemDataRole.UserRole) or 0
                total += v
        # 更新总需求
        demand_item = self.item(total_row, col)
        if demand_item:
            demand_item.setText(str(total) if total > 0 else "-")
            demand_item.setForeground(
                QBrush(QColor(C_TEXT) if total > 0 else QColor(C_SUBTEXT))
            )
            demand_item.setTextAlignment(Qt.AlignCenter)

        # 更新状态行
        avail_item = self.item(available_row, col)
        available = avail_item.data(Qt.ItemDataRole.UserRole) if avail_item else 0
        if available is None:
            available = 0
        status_item = self.item(status_row, col)
        if status_item:
            if total == 0:
                status_item.setText("✅ OK")
                status_item.setForeground(QBrush(QColor(C_GREEN)))
            elif total <= available:
                status_item.setText("✅ OK")
                status_item.setForeground(QBrush(QColor(C_GREEN)))
            elif total <= available * 1.2:
                status_item.setText("⚠️ 满载")
                status_item.setForeground(QBrush(QColor(C_YELLOW)))
            else:
                status_item.setText("🔴 超载")
                status_item.setForeground(QBrush(QColor(C_RED)))
            status_item.setTextAlignment(Qt.AlignCenter)

            # 更新各单元格超载状态
            overload = total > available
            for r in range(task_count):
                it = self.item(r, col)
                if it:
                    self._update_cell_overload(it, overload)

    def update_all_totals(self):
        """刷新所有汇总行/列"""
        total_col = self.columnCount() - 1
        total_row = self.rowCount() - 3
        task_count = total_row
        # 行总计
        for r in range(task_count):
            self._update_row_total(r)
        # 列总计 + 状态
        for c in range(1, self.columnCount()):
            self._update_col_total(c)


# ════════════════════════════════════════════════════════════
# 主视图
# ════════════════════════════════════════════════════════════
class ResourceDragView(QWidget):
    """拖拽分配资源视图 — 左侧资源列表 + 右侧任务×资源矩阵"""

    data_changed = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._tasks: list[Task] = []
        self._resources: list[Resource] = []

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C_BORDER};
                width: 2px;
            }}
        """)

        # ── 左侧面板 ────────────────────────────────────
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        title = QLabel("设备资源")
        title.setStyleSheet(
            f"color: {C_TEXT}; font-weight: bold; font-size: 14px; "
            f"padding: 8px;"
        )
        left_layout.addWidget(title)

        self.resource_list = _ResourceListWidget()
        left_layout.addWidget(self.resource_list)
        left_panel.setMinimumWidth(220)
        left_panel.setMaximumWidth(320)

        splitter.addWidget(left_panel)

        # ── 右侧矩阵 ────────────────────────────────────
        self.matrix_table = _MatrixTable()
        self.matrix_table.cell_changed.connect(self._on_cell_changed)
        splitter.addWidget(self.matrix_table)

        # 空状态提示
        self._empty_hint = QLabel("🎯 暂无任务或设备数据\n请先在甘特图添加任务，在资源配置添加设备")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setStyleSheet("color: #a6adc8; font-size: 14px;")
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setParent(self.matrix_table)
        self._empty_hint.setGeometry(0, 0, 800, 200)
        self._empty_hint.hide()

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 700])

        main_layout.addWidget(splitter)

    # ── 数据加载 ──────────────────────────────────────────

    def refresh(self):
        """重新加载数据并刷新矩阵"""
        self._load_data()

    def _load_data(self):
        """从 DB 加载 tasks/resources 并重建 UI"""
        self._tasks = self.db.get_all_tasks()
        self._resources = self.db.get_all_resources()
        self._build_resource_list()
        self._build_matrix()
        # 空状态提示
        if not self._tasks or not self._resources:
            self._empty_hint.show()
            self._empty_hint.raise_()
        else:
            self._empty_hint.hide()

    def _build_resource_list(self):
        """构建左侧资源列表"""
        self.resource_list.clear()
        for res in self._resources:
            if res.type.value != "equipment":
                continue
            item = QListWidgetItem(self.resource_list)
            item.setSizeHint(QSize(0, 52))
            item.setData(Qt.ItemDataRole.UserRole, res.id)
            widget = _ResourceItemWidget(res)
            self.resource_list.addItem(item)
            self.resource_list.setItemWidget(item, widget)
        self._update_usage_rates()

    def _build_matrix(self):
        """构建/更新右侧任务×资源表格"""
        tasks = self._tasks
        resources = [r for r in self._resources if r.type.value == "equipment"]
        num_tasks = len(tasks)
        num_resources = len(resources)
        # 列: 0=任务名称, 1..N=各资源, N+1=总计
        num_cols = 1 + num_resources + 1
        # 行: 0..N-1=任务, N=总需求, N+1=可用, N+2=状态
        num_rows = num_tasks + 3

        self.matrix_table.blockSignals(True)
        self.matrix_table.setRowCount(num_rows)
        self.matrix_table.setColumnCount(num_cols)

        # ── 表头 ──
        header_item = QTableWidgetItem("任务")
        header_item.setTextAlignment(Qt.AlignCenter)
        self.matrix_table.setHorizontalHeaderItem(0, header_item)

        res_id_map: dict[int, int] = {}  # resource_id -> col_index
        for ci, res in enumerate(resources, start=1):
            col_item = QTableWidgetItem(f"{res.icon} {res.name}")
            col_item.setTextAlignment(Qt.AlignCenter)
            col_item.setData(Qt.ItemDataRole.UserRole, res.id)
            self.matrix_table.setHorizontalHeaderItem(ci, col_item)
            res_id_map[res.id] = ci

        total_header = QTableWidgetItem("总计")
        total_header.setTextAlignment(Qt.AlignCenter)
        self.matrix_table.setHorizontalHeaderItem(
            num_cols - 1, total_header
        )

        # ── 任务行 ──
        for ri, task in enumerate(tasks):
            # 任务名列
            name_item = QTableWidgetItem(f"{task.num} {task.name_cn}")
            name_item.setFlags(
                name_item.flags() & ~Qt.ItemFlag.ItemIsSelectable
            )
            name_item.setForeground(QBrush(QColor(C_TEXT)))
            name_item.setData(
                Qt.ItemDataRole.UserRole, task.id
            )
            self.matrix_table.setItem(ri, 0, name_item)

            # 各资源列
            for res in resources:
                ci = res_id_map.get(res.id)
                if ci is None:
                    continue
                qty = 0
                for req in task.requirements:
                    if req.resource_id == res.id:
                        qty = req.quantity
                        break
                cell = QTableWidgetItem()
                cell.setData(Qt.ItemDataRole.UserRole, qty)
                cell.setFlags(
                    cell.flags() | Qt.ItemFlag.ItemIsDragEnabled
                )
                self.matrix_table._update_cell_display(cell, qty)
                self.matrix_table.setItem(ri, ci, cell)

            # 总计列
            total_cell = QTableWidgetItem("-")
            total_cell.setFlags(
                total_cell.flags()
                & ~Qt.ItemFlag.ItemIsSelectable
                & ~Qt.ItemFlag.ItemIsEnabled
            )
            total_cell.setForeground(QBrush(QColor(C_SUBTEXT)))
            total_cell.setTextAlignment(Qt.AlignCenter)
            self.matrix_table.setItem(ri, num_cols - 1, total_cell)

        # ── 汇总行 ──
        summary_labels = ["总需求", "可用", "状态"]
        summary_rows = [num_tasks, num_tasks + 1, num_tasks + 2]
        for label, sri in zip(summary_labels, summary_rows):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(
                label_item.flags()
                & ~Qt.ItemFlag.ItemIsSelectable
                & ~Qt.ItemFlag.ItemIsEnabled
            )
            label_item.setForeground(QBrush(QColor(C_SUBTEXT)))
            label_item.setFont(
                QFont(label_item.font().family(), -1, QFont.Weight.Bold)
            )
            self.matrix_table.setRowHeight(sri, 32)
            self.matrix_table.setItem(sri, 0, label_item)

            for ci in range(1, num_cols):
                cell = QTableWidgetItem("-")
                cell.setFlags(
                    cell.flags()
                    & ~Qt.ItemFlag.ItemIsSelectable
                    & ~Qt.ItemFlag.ItemIsEnabled
                )
                cell.setForeground(QBrush(QColor(C_SUBTEXT)))
                cell.setTextAlignment(Qt.AlignCenter)
                self.matrix_table.setItem(sri, ci, cell)

        # 填充可用行
        for ci, res in enumerate(resources, start=1):
            avail_cell = self.matrix_table.item(num_tasks + 1, ci)
            if avail_cell:
                avail_cell.setText(str(res.available_qty))
                avail_cell.setForeground(QBrush(QColor(C_GREEN)))
                avail_cell.setData(Qt.ItemDataRole.UserRole, res.available_qty)

        # 列宽
        self.matrix_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for ci in range(1, num_cols):
            self.matrix_table.horizontalHeader().setSectionResizeMode(
                ci, QHeaderView.ResizeMode.ResizeToContents
            )

        # 刷新汇总
        self.matrix_table.update_all_totals()

        self.matrix_table.blockSignals(False)

    # ── 数据变更 ──────────────────────────────────────────

    def _on_cell_changed(self, row: int, col: int, new_qty: int):
        """单元格修改后保存到 DB"""
        if row >= len(self._tasks):
            return
        task = self._tasks[row]
        task_id = task.id

        # 获取 resource_id
        header_item = self.matrix_table.horizontalHeaderItem(col)
        if header_item is None:
            return
        resource_id = header_item.data(Qt.ItemDataRole.UserRole)
        if resource_id is None:
            return

        # 重建 requirements 列表
        requirements = list(task.requirements)
        found = False
        for req in requirements:
            if req.resource_id == resource_id:
                req.quantity = new_qty
                found = True
                break
        if not found and new_qty > 0:
            requirements.append(
                EquipmentRequirement(resource_id=resource_id, quantity=new_qty)
            )
        # 过滤掉 quantity 为 0 的
        requirements = [r for r in requirements if r.quantity > 0]

        self._save_requirements(task_id, requirements)
        # 更新本地缓存
        task.requirements = requirements
        self._update_usage_rates()
        self.data_changed.emit()

    def _save_requirements(self, task_id: int, requirements):
        """保存 requirements 到 DB"""
        reqs_json = json.dumps([
            {"resource_id": r.resource_id, "quantity": r.quantity}
            for r in requirements
        ])
        self.db.conn.execute(
            "UPDATE tasks SET requirements=?, updated_at=datetime('now') WHERE id=?",
            (reqs_json, task_id),
        )
        self.db.conn.commit()

    # ── 使用率更新 ────────────────────────────────────────

    def _update_usage_rates(self):
        """更新左侧资源使用率"""
        resources = self._resources
        # 计算每种设备总分配量
        allocation: dict[int, int] = {}
        for res in resources:
            allocation[res.id] = 0
        for task in self._tasks:
            for req in task.requirements:
                allocation[req.resource_id] = (
                    allocation.get(req.resource_id, 0) + req.quantity
                )

        for i in range(self.resource_list.count()):
            item = self.resource_list.item(i)
            widget = self.resource_list.itemWidget(item)
            if isinstance(widget, _ResourceItemWidget):
                res_id = widget.resource.id
                total = allocation.get(res_id, 0)
                avail = widget.resource.available_qty
                rate = total / avail if avail > 0 else (1.0 if total > 0 else 0.0)
                widget.set_usage_rate(rate)
