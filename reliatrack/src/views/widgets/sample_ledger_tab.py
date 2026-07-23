"""样品台账 Tab — 所有样品记录。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.sample import Sample
from src.styles.icon import RI_EDIT, set_icon
from src.views.widgets.empty_state import EmptyStateWidget
from src.views.widgets.sample_table import _SampleTable
from src.views.widgets.search_box import SearchBox

# 样品台账列规格
_LEDGER_SPECS = [
    ("ID", "fixed", 50),
    ("SN", "interactive", 150),
    ("批次号", "interactive", 120),
    ("规格", "interactive", 100),
    ("项目ID", "interactive", 70),
    ("状态", "interactive", 80),
    ("供应商", "interactive", 100),
    ("累计测试(h)", "interactive", 80),
    ("创建时间", "interactive", 100),
]


class _SampleLedgerTab(QWidget):
    """样品台账 Tab — 所有样品记录。"""

    COLUMNS = [
        ("ID", "id"),
        ("SN", "sn"),
        ("批次号", "batch_no"),
        ("规格", "spec"),
        ("项目ID", "project_id"),
        ("状态", "status"),
        ("供应商", "supplier"),
        ("累计测试(h)", "test_hours"),
        ("创建时间", "created_at"),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()

        self._search_input = SearchBox()
        self._search_input.setPlaceholderText("搜索 SN / 批次号 / 规格…")
        self._search_input.setMinimumWidth(160)
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)

        toolbar.addStretch()

        self._btn_edit = QPushButton("编辑")
        self._btn_edit.setProperty("class", "action")
        self._btn_edit.setMinimumWidth(70)
        self._btn_edit.setToolTip("编辑选中样品")
        toolbar.addWidget(self._btn_edit)

        self._btn_return = QPushButton("归还")
        self._btn_return.setProperty("class", "action")
        self._btn_return.setMinimumWidth(70)
        self._btn_return.setToolTip("归还选中已出库样品")
        toolbar.addWidget(self._btn_return)

        self._btn_batch_edit = QPushButton("批量编辑")
        self._btn_batch_edit.setProperty("class", "action")
        self._btn_batch_edit.setMinimumWidth(70)
        self._btn_batch_edit.setToolTip("批量编辑选中的多个样品")
        toolbar.addWidget(self._btn_batch_edit)

        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS, _LEDGER_SPECS, "sample_ledger")
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

        # 全量数据缓存（用于搜索过滤）
        self._all_samples: list[Sample] = []

        # 空状态
        self._empty_widget = EmptyStateWidget(
            title="暂无样品台账数据",
            description="所有样品的历史记录将在此显示",
            parent=self._table,
        )
        self._empty_widget.hide()
        self._empty_widget.raise_()

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

    def _update_empty_state(self) -> None:
        """更新空状态提示。"""
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
                or text in (s.spec or "").lower()
            ]
        self._table.set_samples(filtered)
        self._update_empty_state()

    def refresh(self, samples: list[Sample]) -> None:
        """刷新台账数据并应用当前搜索过滤。"""
        self._all_samples = samples
        self._on_search(self._search_input.text())

    @property
    def btn_edit(self) -> QPushButton:
        """编辑按钮。"""
        return self._btn_edit

    @property
    def btn_return(self) -> QPushButton:
        """归还按钮。"""
        return self._btn_return

    @property
    def btn_batch_edit(self) -> QPushButton:
        """批量编辑按钮。"""
        return self._btn_batch_edit

    @property
    def table(self) -> _SampleTable:
        """样品台账表格。"""
        return self._table
