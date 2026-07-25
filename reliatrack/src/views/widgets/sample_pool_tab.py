"""样品池 Tab — 在库样品列表。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.sample import Sample
from src.styles.icon import RI_ADD, RI_DELETE, RI_EDIT, RI_EXPORT, RI_IMPORT, RI_MORE, set_icon
from src.views.widgets.command_bar import CommandBar
from src.views.widgets.empty_state import EmptyStateWidget
from src.views.widgets.sample_table import _SampleTable
from src.views.widgets.search_box import SearchBox

# 样品池列规格
_POOL_SPECS = [
    ("SN", "interactive", 150),
    ("批次号", "interactive", 120),
    ("规格", "interactive", 100),
    ("项目ID", "interactive", 70),
    ("状态", "interactive", 80),
    ("创建时间", "interactive", 100),
]


class _SamplePoolTab(QWidget):
    """样品池 Tab — 在库样品列表。"""

    COLUMNS = [
        ("SN", "sn"),
        ("批次号", "batch_no"),
        ("规格", "spec"),
        ("项目ID", "project_id"),
        ("状态", "status"),
        ("创建时间", "created_at"),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self._search_input = SearchBox()
        self._search_input.setPlaceholderText("搜索 SN / 批次号…")
        self._search_input.setMinimumWidth(160)
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)
        # ── CommandBar（自動溢出）──
        action_bar = CommandBar()
        toolbar.addWidget(action_bar, 1)
        action_bar.setButtonTight(True)

        self._btn_add = QPushButton("入库")
        self._btn_add.setProperty("class", "action")
        self._btn_add.setMinimumWidth(70)
        self._btn_add.setToolTip("样品入库")
        set_icon(self._btn_add, RI_ADD)
        action_bar.addWidget(self._btn_add)

        self._btn_batch_import = QPushButton("批量导入")
        self._btn_batch_import.setProperty("class", "action")
        self._btn_batch_import.setMinimumWidth(70)
        self._btn_batch_import.setToolTip("从 Excel 批量导入样品")
        set_icon(self._btn_batch_import, RI_IMPORT)
        action_bar.addWidget(self._btn_batch_import)

        self._btn_out = QPushButton("出库")
        self._btn_out.setProperty("class", "action")
        self._btn_out.setMinimumWidth(70)
        self._btn_out.setToolTip("样品出库")
        set_icon(self._btn_out, RI_EXPORT)
        action_bar.addWidget(self._btn_out)

        # 分隔線
        action_bar.addSeparator()

        self._btn_edit = QPushButton("编辑")
        self._btn_edit.setProperty("class", "action")
        self._btn_edit.setMinimumWidth(70)
        self._btn_edit.setToolTip("编辑选中样品")
        set_icon(self._btn_edit, RI_EDIT)
        action_bar.addWidget(self._btn_edit)

        self._btn_tag = QPushButton("标签")
        self._btn_tag.setProperty("class", "action")
        self._btn_tag.setMinimumWidth(70)
        self._btn_tag.setToolTip("生成样品条形码/二维码标签")
        action_bar.addWidget(self._btn_tag)

        self._btn_delete = QPushButton("删除")
        self._btn_delete.setProperty("class", "action")
        self._btn_delete.setMinimumWidth(70)
        self._btn_delete.setToolTip("彻底删除选中样品")
        set_icon(self._btn_delete, RI_DELETE)
        action_bar.addWidget(self._btn_delete)

        # 更多操作（批量编辑）
        self._more_menu = QMenu(self)
        self._act_batch_edit = self._more_menu.addAction("批量编辑")
        self._act_batch_edit.setToolTip("批量编辑选中的多个样品")
        self._btn_more = QToolButton()
        self._btn_more.setText("更多")
        self._btn_more.setMenu(self._more_menu)
        self._btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_more.setProperty("class", "action")
        self._btn_more.setMinimumWidth(70)
        set_icon(self._btn_more, RI_MORE)
        action_bar.addWidget(self._btn_more)

        toolbar.addWidget(action_bar)
        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS, _POOL_SPECS, "sample_pool")
        # 启用多选
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        layout.addWidget(self._table)

        # 右键菜单
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu = QMenu(self._table)
        self._ctx_act_edit = self._context_menu.addAction("编辑样品")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)
        self._context_menu.addSeparator()
        self._ctx_act_delete = self._context_menu.addAction("删除样品")
        self._ctx_act_delete.triggered.connect(self._on_ctx_delete)

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无样品数据",
            description="尚未录入任何样品，点击上方「入库」按钮添加样品",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

        # 全量数据缓存（用于搜索过滤）
        self._all_samples: list[Sample] = []

    def _show_context_menu(self, pos) -> None:
        """在表格行上显示右键菜单。"""
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        self._table.selectRow(row)
        self._context_menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_ctx_edit(self) -> None:
        """右键编辑 → 触发工具栏编辑按钮。"""
        self._btn_edit.click()

    def _on_ctx_delete(self) -> None:
        """右键删除 → 触发工具栏删除按钮。"""
        self._btn_delete.click()

    def _on_search(self, text: str) -> None:
        """根据搜索关键词过滤样品列表。"""
        text = text.strip().lower()
        if not text:
            filtered = self._all_samples
        else:
            filtered = [
                s for s in self._all_samples
                if text in (s.sn or "").lower()
                or text in (s.batch_no or "").lower()
            ]
        self._table.set_samples(filtered)
        self._update_empty_state()

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

    def refresh(self, samples: list[Sample]) -> None:
        """刷新样品池数据并应用当前搜索过滤。"""
        self._all_samples = samples
        self._on_search(self._search_input.text())

    # 暴露按钮引用
    @property
    def btn_add(self) -> QPushButton:
        """入库按钮。"""
        return self._btn_add

    @property
    def btn_batch_import(self) -> object:
        """批量导入按钮（工具栏）。"""
        return self._btn_batch_import

    @property
    def btn_out(self) -> QPushButton:
        """出库按钮。"""
        return self._btn_out

    @property
    def btn_edit(self) -> QPushButton:
        """编辑按钮。"""
        return self._btn_edit

    @property
    def btn_tag(self) -> QPushButton:
        """标签按钮。"""
        return self._btn_tag

    @property
    def btn_batch_edit(self) -> object:
        """批量编辑（在更多菜单中）。"""
        return self._act_batch_edit

    @property
    def btn_delete(self) -> QPushButton:
        """删除按钮。"""
        return self._btn_delete

    @property
    def search_input(self) -> QLineEdit:
        """搜索输入框。"""
        return self._search_input

    @property
    def table(self) -> _SampleTable:
        """样品池表格。"""
        return self._table
