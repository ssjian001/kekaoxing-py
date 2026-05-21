"""样品管理视图 — 样品池 / 台账 / 出入库。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QBrush
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
    QMenu,
    QAbstractItemView,
)
from PySide6.QtCore import QEvent, Qt

from src.styles.theme import (
    MANTLE, BASE, SURFACE0, SURFACE1,
    TEXT, OVERLAY0,
)
from src.styles.constants import TABLE_QSS, SAMPLE_TYPE_COLORS, VIEW_MARGINS, apply_column_specs
from src.models.sample import Sample

# 样品池列规格
_POOL_SPECS = [
    ("SN", "interactive", 150),
    ("批次号", "interactive", 120),
    ("规格", "interactive", 100),
    ("项目ID", "interactive", 70),
    ("状态", "interactive", 80),
    ("创建时间", "interactive", 100),
]

# 出入库记录列规格
_LOG_SPECS = [
    ("样品SN", "interactive", 120),
    ("批次号", "interactive", 100),
    ("操作类型", "interactive", 80),
    ("操作人", "interactive", 80),
    ("用途", "interactive", 120),
    ("关联任务", "interactive", 120),
    ("预计归还", "interactive", 100),
    ("实际归还", "interactive", 100),
    ("备注", "interactive", 120),
    ("操作时间", "interactive", 140),
]

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


from src.constants import SAMPLE_STATUS_LABELS


class _SampleTable(QTableWidget):
    """样品数据表格基类。"""

    def __init__(self, columns: list[tuple[str, str]], specs: list[tuple[str, str, int]],
                 parent: QWidget | None = None):
        """columns: [(header_text, field_name)], specs: [(header, mode, width)]"""
        super().__init__(parent)
        self._columns = columns
        self._data: list[Sample] = []
        apply_column_specs(self, specs)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=13,
        ))

    def set_samples(self, samples: list[Sample]) -> None:
        self._data = samples
        self.setSortingEnabled(False)
        self.setRowCount(len(samples))
        for row_idx, sample in enumerate(samples):
            for col_idx, (_, field_name) in enumerate(self._columns):
                value = getattr(sample, field_name, "")
                # 状态列显示中文标签
                if field_name == "status":
                    value = SAMPLE_STATUS_LABELS.get(value, str(value))
                # test_hours 去掉多余的 .0
                elif field_name == "test_hours" and isinstance(value, float):
                    value = f"{value:.1f}" if value != int(value) else str(int(value))
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 在第一列存储 sample ID，排序后仍可通过 item 取回
                if col_idx == 0 and sample.id is not None:
                    item.setData(Qt.ItemDataRole.UserRole, sample.id)
                self.setItem(row_idx, col_idx, item)
        self.setSortingEnabled(True)

    def get_selected_sample_id(self) -> int | None:
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, 0)
        if item is not None:
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid is not None:
                return int(sid)
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
        self._search_input.setPlaceholderText("搜索 SN / 批次号...")
        self._search_input.setMinimumWidth(160)
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)
        toolbar.addStretch()

        self._btn_add = QPushButton("入库")
        self._btn_add.setProperty("class", "action")
        self._btn_add.setMinimumWidth(70)
        self._btn_add.setToolTip("样品入库")
        toolbar.addWidget(self._btn_add)

        self._btn_batch_import = QPushButton("批量导入")
        self._btn_batch_import.setProperty("class", "action")
        self._btn_batch_import.setMinimumWidth(70)
        self._btn_batch_import.setToolTip("从 Excel 批量导入样品")
        toolbar.addWidget(self._btn_batch_import)

        self._btn_out = QPushButton("出库")
        self._btn_out.setProperty("class", "action")
        self._btn_out.setMinimumWidth(70)
        self._btn_out.setToolTip("样品出库")
        toolbar.addWidget(self._btn_out)

        self._btn_edit = QPushButton("编辑")
        self._btn_edit.setProperty("class", "action")
        self._btn_edit.setMinimumWidth(70)
        self._btn_edit.setToolTip("编辑选中样品")
        toolbar.addWidget(self._btn_edit)

        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS, _POOL_SPECS)
        layout.addWidget(self._table)

        # 右键菜单
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu = QMenu(self._table)
        self._ctx_act_edit = self._context_menu.addAction("编辑样品")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)

        # 空状态提示
        self._empty_label = QLabel("暂无样品数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 14px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

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
            self._empty_label.setGeometry(self._table.viewport().rect())
            self._empty_label.show()
        else:
            self._empty_label.hide()

    def eventFilter(self, obj, event) -> bool:
        """监听表格缩放以更新空状态标签位置。"""
        if obj is self._table and event.type() == QEvent.Type.Resize:
            self._empty_label.setGeometry(self._table.viewport().rect())
        return super().eventFilter(obj, event)

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
    def btn_batch_import(self) -> QPushButton:
        """批量导入按钮。"""
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
    def search_input(self) -> QLineEdit:
        """搜索输入框。"""
        return self._search_input

    @property
    def table(self) -> _SampleTable:
        """样品池表格。"""
        return self._table


class _SampleUsageTab(QWidget):
    """样品出入库记录 Tab — 完整流水表。"""

    # 操作类型显示映射
    _TYPE_LABELS: dict[str, str] = {
        "check_in": "入库",
        "check_out": "出库",
        "return": "归还",
        "transfer": "转出",
    }

    # 操作类型颜色映射（来自 constants.py）
    _TYPE_COLORS: dict[str, str] = SAMPLE_TYPE_COLORS

    COLUMNS = [
        "样品SN", "批次号", "操作类型", "操作人",
        "用途", "关联任务", "预计归还", "实际归还", "备注", "操作时间",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── 筛选栏 ──
        toolbar = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索 SN...")
        self._search_input.setMinimumWidth(160)
        self._search_input.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search_input)

        self._type_combo = QComboBox()
        self._type_combo.setFixedWidth(140)
        self._type_combo.addItem("全部类型", "")
        self._type_combo.addItem("入库", "check_in")
        self._type_combo.addItem("出库", "check_out")
        self._type_combo.addItem("归还", "return")
        self._type_combo.addItem("转出", "transfer")
        self._type_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._type_combo)

        self._btn_search = QPushButton("查询")
        self._btn_search.setProperty("class", "action")
        self._btn_search.setMinimumWidth(70)
        self._btn_search.clicked.connect(self._request_refresh)
        toolbar.addWidget(self._btn_search)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setProperty("class", "action")
        self._btn_reset.setMinimumWidth(70)
        self._btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self._btn_reset)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── 表格 ──
        self._table = QTableWidget()
        apply_column_specs(self._table, _LOG_SPECS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=13,
        ))
        layout.addWidget(self._table)

        # 空状态提示
        self._empty_label = QLabel("暂无出入库记录")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 14px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

        # 全量数据缓存
        self._all_data: list[dict] = []

        # 外部刷新回调（由 main.py 连接）
        self._refresh_callback: object | None = None

    # ── 公开方法 ──

    def set_refresh_callback(self, callback: object) -> None:
        """设置刷新回调，由外部传入 sample_service.list_transactions 调用。"""
        self._refresh_callback = callback

    def refresh(self, data: list[dict]) -> None:
        """接收数据并应用当前筛选。"""
        self._all_data = data
        self._apply_filter()

    @property
    def table(self) -> QTableWidget:
        return self._table

    # ── 内部方法 ──

    def _request_refresh(self) -> None:
        """触发外部回调重新查询数据。"""
        if self._refresh_callback:
            self._refresh_callback()  # type: ignore[operator]

    def _on_reset(self) -> None:
        """重置筛选条件并刷新。"""
        self._search_input.clear()
        self._type_combo.setCurrentIndex(0)
        self._request_refresh()

    def _apply_filter(self) -> None:
        """根据当前搜索/类型过滤缓存数据并填充表格。"""
        sn_text = self._search_input.text().strip().lower()
        type_val = self._type_combo.currentData()

        filtered = self._all_data
        if sn_text:
            filtered = [
                d for d in filtered
                if sn_text in (d.get("sample_sn") or "").lower()
            ]
        if type_val:
            filtered = [d for d in filtered if d.get("type") == type_val]

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(filtered))
        for row_idx, record in enumerate(filtered):
            txn_type = record.get("type", "")
            label = self._TYPE_LABELS.get(txn_type, txn_type)
            color = self._TYPE_COLORS.get(txn_type, TEXT)

            # 关联任务：显示 #id 任务名
            task_id = record.get("related_task_id")
            task_name = record.get("task_name")
            if task_id and task_name:
                task_display = f"#{task_id} {task_name}"
            elif task_id:
                task_display = f"#{task_id}"
            else:
                task_display = ""

            values = [
                record.get("sample_sn") or "—",
                record.get("batch_no") or "—",
                label,
                record.get("operator_name") or "—",
                record.get("purpose") or "",
                task_display,
                record.get("expected_return") or "—",
                record.get("actual_return") or "—",
                record.get("notes") or "",
                (record.get("created_at") or "")[:16],
            ]

            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 操作类型列着色
                if col_idx == 2:
                    item.setForeground(_color_fg(color))
                self._table.setItem(row_idx, col_idx, item)

        self._table.setSortingEnabled(True)
        self._update_empty_state()

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


def _color_fg(hex_color: str):
    """将 hex 颜色字符串转为 QBrush/ QColor 用于前景色。"""
    return QBrush(QColor(hex_color))


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

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索 SN / 批次号 / 规格...")
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

        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS, _LEDGER_SPECS)
        layout.addWidget(self._table)

        # 右键菜单
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu = QMenu(self._table)
        self._ctx_act_edit = self._context_menu.addAction("编辑样品")
        self._ctx_act_edit.triggered.connect(self._on_ctx_edit)

        # 全量数据缓存（用于搜索过滤）
        self._all_samples: list[Sample] = []

        # 空状态提示
        self._empty_label = QLabel("暂无样品台账数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 14px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.viewport().installEventFilter(self)

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
            self._empty_label.setGeometry(self._table.viewport().rect())
            self._empty_label.show()
        else:
            self._empty_label.hide()

    def eventFilter(self, obj, event):
        """表格 viewport resize 时同步空状态标签位置。"""
        if obj is self._table.viewport() and event.type() == event.Type.Resize:
            if self._empty_label.isVisible():
                self._empty_label.setGeometry(self._table.viewport().rect())
        return super().eventFilter(obj, event)

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
    def table(self) -> _SampleTable:
        """样品台账表格。"""
        return self._table


class SampleView(QWidget):
    """样品管理视图 — 三个子 Tab。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        self._tabs = QTabWidget()

        self._pool_tab = _SamplePoolTab()
        self._ledger_tab = _SampleLedgerTab()
        self._usage_tab = _SampleUsageTab()

        self._tabs.addTab(self._pool_tab, "样品池")
        self._tabs.addTab(self._ledger_tab, "样品台账")
        self._tabs.addTab(self._usage_tab, "出入库记录")

        layout.addWidget(self._tabs)

    def refresh_pool(self, samples: list[Sample]) -> None:
        self._pool_tab.refresh(samples)

    def refresh_ledger(self, samples: list[Sample]) -> None:
        self._ledger_tab.refresh(samples)

    def refresh_usage(self, data: list[dict]) -> None:
        self._usage_tab.refresh(data)

    # 暴露子组件引用
    @property
    def pool_tab(self) -> _SamplePoolTab:
        return self._pool_tab

    @property
    def ledger_tab(self) -> _SampleLedgerTab:
        return self._ledger_tab

    @property
    def usage_tab(self) -> _SampleUsageTab:
        return self._usage_tab
