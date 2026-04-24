"""样品管理视图 — 样品池 / 台账 / 出入库。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLineEdit,
    QLabel,
    QComboBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, PEACH, LAVENDER,
)
from src.models.sample import Sample


class _SampleTable(QTableWidget):
    """样品数据表格基类。"""

    def __init__(self, columns: list[tuple[str, str]], parent: QWidget | None = None):
        """columns: [(header_text, field_name), ...]"""
        super().__init__(parent)
        self._columns = columns
        self._data: list[Sample] = []
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels([c[0] for c in columns])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {BASE};
                color: {TEXT};
                gridline-color: {SURFACE1};
                border: 1px solid {SURFACE1};
                border-radius: 8px;
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QTableWidget::item:alternate {{
                background-color: {MANTLE};
            }}
            QHeaderView::section {{
                background-color: {SURFACE0};
                color: {SUBTEXT0};
                padding: 8px;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }}
        """)

    def set_samples(self, samples: list[Sample]) -> None:
        self._data = samples
        self.setRowCount(len(samples))
        for row_idx, sample in enumerate(samples):
            for col_idx, (_, field_name) in enumerate(self._columns):
                value = getattr(sample, field_name, "")
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row_idx, col_idx, item)

    def get_selected_sample_id(self) -> int | None:
        row = self.currentRow()
        if 0 <= row < len(self._data):
            return self._data[row].id
        return None


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
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索 SN / 批次号...")
        self._search_input.setFixedWidth(260)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE0};
                color: {TEXT};
                border: 1px solid {SURFACE1};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }}
        """)
        toolbar.addWidget(self._search_input)
        toolbar.addStretch()

        self._btn_add = QPushButton("➕ 入库")
        self._btn_add.setStyleSheet(self._btn_style(GREEN))
        self._btn_add.setFixedWidth(100)
        toolbar.addWidget(self._btn_add)

        self._btn_out = QPushButton("📤 出库")
        self._btn_out.setStyleSheet(self._btn_style(PEACH))
        self._btn_out.setFixedWidth(100)
        toolbar.addWidget(self._btn_out)

        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS)
        layout.addWidget(self._table)

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: {CRUST};
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
        """

    def refresh(self, samples: list[Sample]) -> None:
        self._table.set_samples(samples)

    # 暴露按钮引用
    @property
    def btn_add(self) -> QPushButton:
        """入库按钮。"""
        return self._btn_add

    @property
    def btn_out(self) -> QPushButton:
        """出库按钮。"""
        return self._btn_out

    @property
    def search_input(self) -> QLineEdit:
        """搜索输入框。"""
        return self._search_input

    @property
    def table(self) -> _SampleTable:
        """样品池表格。"""
        return self._table


class _SampleLedgerTab(QWidget):
    """样品台账 Tab — 所有样品记录。"""

    COLUMNS = [
        ("ID", "id"),
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
        self._table = _SampleTable(self.COLUMNS)
        layout.addWidget(self._table)

    def refresh(self, samples: list[Sample]) -> None:
        self._table.set_samples(samples)


class SampleView(QWidget):
    """样品管理视图 — 三个子 Tab。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        title = QLabel("📦 样品管理")
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {SURFACE1};
                border-radius: 8px;
                background-color: {BASE};
            }}
            QTabBar::tab {{
                background-color: {SURFACE0};
                color: {SUBTEXT0};
                padding: 8px 20px;
                border: none;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background-color: {SURFACE1};
                color: {TEXT};
            }}
        """)

        self._pool_tab = _SamplePoolTab()
        self._ledger_tab = _SampleLedgerTab()

        self._tabs.addTab(self._pool_tab, "样品池")
        self._tabs.addTab(self._ledger_tab, "样品台账")
        # 第三个 Tab（样品占用）暂时用占位
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_label = QLabel("样品占用 — 开发中")
        ph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 16px;")
        ph_layout.addWidget(ph_label)
        self._tabs.addTab(placeholder, "样品占用")

        layout.addWidget(self._tabs)

    def refresh_pool(self, samples: list[Sample]) -> None:
        self._pool_tab.refresh(samples)

    def refresh_ledger(self, samples: list[Sample]) -> None:
        self._ledger_tab.refresh(samples)

    # 暴露子组件引用
    @property
    def pool_tab(self) -> _SamplePoolTab:
        return self._pool_tab

    @property
    def ledger_tab(self) -> _SampleLedgerTab:
        return self._ledger_tab
