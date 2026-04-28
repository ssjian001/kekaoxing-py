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
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPixmap

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, PEACH, LAVENDER, OVERLAY0,
)
from src.styles.constants import TABLE_QSS
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
        # 列宽策略：SN / 批次号 ResizeToContents, 状态 Fixed(80), 其余 Stretch
        for col_idx, (header_text, _) in enumerate(columns):
            if header_text == "SN" or header_text == "批次号":
                self.horizontalHeader().setSectionResizeMode(
                    col_idx, QHeaderView.ResizeMode.ResizeToContents,
                )
            elif header_text == "状态":
                self.horizontalHeader().setSectionResizeMode(
                    col_idx, QHeaderView.ResizeMode.Fixed,
                )
                self.setColumnWidth(col_idx, 80)
            else:
                self.horizontalHeader().setSectionResizeMode(
                    col_idx, QHeaderView.ResizeMode.Stretch,
                )
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
        self._search_input.setFixedWidth(280)
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
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)
        toolbar.addStretch()

        self._btn_add = QPushButton("➕ 入库")
        self._btn_add.setProperty("class", "action")
        self._btn_add.setMinimumWidth(70)
        toolbar.addWidget(self._btn_add)

        self._btn_batch_import = QPushButton("📥 批量导入")
        self._btn_batch_import.setProperty("class", "action")
        self._btn_batch_import.setMinimumWidth(70)
        toolbar.addWidget(self._btn_batch_import)

        self._btn_out = QPushButton("📤 出库")
        self._btn_out.setProperty("class", "action")
        self._btn_out.setMinimumWidth(70)
        toolbar.addWidget(self._btn_out)

        self._btn_edit = QPushButton("✏️ 编辑")
        self._btn_edit.setProperty("class", "action")
        self._btn_edit.setMinimumWidth(70)
        toolbar.addWidget(self._btn_edit)

        self._btn_generate_qr = QPushButton("🔲 生成二维码")
        self._btn_generate_qr.setProperty("class", "action")
        self._btn_generate_qr.setMinimumWidth(70)
        toolbar.addWidget(self._btn_generate_qr)

        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS)
        layout.addWidget(self._table)

        # 空状态提示
        self._empty_label = QLabel("暂无样品数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 16px;")
        self._empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_label.setParent(self._table)
        self._empty_label.hide()
        self._table.installEventFilter(self)

        # 全量数据缓存（用于搜索过滤）
        self._all_samples: list[Sample] = []

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
    def btn_generate_qr(self) -> QPushButton:
        """生成二维码按钮。"""
        return self._btn_generate_qr

    def show_qr_dialog(
        self,
        sn: str,
        parent: QWidget | None = None,
        on_save_to_db: object | None = None,
    ) -> None:
        """弹出二维码预览对话框。

        Args:
            sn: 样品序列号，用于生成二维码内容。
            parent: 父窗口。
            on_save_to_db: 保存到数据库的回调 (sn, png_bytes) -> None。
        """
        from src.services.qr_service import generate_qr

        try:
            png_bytes = generate_qr(sn)
        except Exception as e:
            QMessageBox.critical(parent, "生成失败", f"生成二维码失败: {e}")
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(png_bytes):
            QMessageBox.critical(parent, "生成失败", "无法解析二维码图片")
            return

        # 缩放到合适显示尺寸
        scaled = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)

        dlg = _QRCodeDialog(sn, scaled, png_bytes, parent=parent)
        if on_save_to_db is not None:
            dlg._db_callback = on_save_to_db  # type: ignore[attr-defined]
        dlg.exec()

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

    # 操作类型颜色映射
    _TYPE_COLORS: dict[str, str] = {
        "check_in": GREEN,
        "check_out": BLUE,
        "return": GREEN,
        "transfer": YELLOW,
    }

    COLUMNS = [
        "样品SN", "批次号", "操作类型", "操作人",
        "用途", "关联任务", "预计归还", "操作时间",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── 筛选栏 ──
        toolbar = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索 SN...")
        self._search_input.setFixedWidth(280)
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

        self._btn_search = QPushButton("🔍 查询")
        self._btn_search.setProperty("class", "action")
        self._btn_search.setMinimumWidth(70)
        self._btn_search.clicked.connect(self._request_refresh)
        toolbar.addWidget(self._btn_search)

        self._btn_reset = QPushButton("↻ 重置")
        self._btn_reset.setProperty("class", "action")
        self._btn_reset.setMinimumWidth(70)
        self._btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self._btn_reset)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── 表格 ──
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        # 列宽策略：操作类型 ResizeToContents, 操作时间 Fixed(160), 其余 Stretch
        header = self._table.horizontalHeader()
        for col_idx, col_name in enumerate(self.COLUMNS):
            if col_name == "操作类型":
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)
            elif col_name == "操作时间":
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(col_idx, 160)
            else:
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=13,
        ))
        layout.addWidget(self._table)

        # 空状态提示
        self._empty_label = QLabel("暂无出入库记录")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {OVERLAY0}; font-size: 16px;")
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

        self._table.setRowCount(len(filtered))
        for row_idx, record in enumerate(filtered):
            txn_type = record.get("type", "")
            label = self._TYPE_LABELS.get(txn_type, txn_type)
            color = self._TYPE_COLORS.get(txn_type, TEXT)

            values = [
                record.get("sample_sn", ""),
                record.get("batch_no", ""),
                label,
                record.get("operator_name", ""),
                record.get("purpose", ""),
                str(record.get("related_task_id", "")) if record.get("related_task_id") else "",
                record.get("expected_return", ""),
                record.get("created_at", ""),
            ]

            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 操作类型列着色
                if col_idx == 2:
                    item.setForeground(_color_fg(color))
                self._table.setItem(row_idx, col_idx, item)

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
    from PySide6.QtGui import QColor, QBrush
    return QBrush(QColor(hex_color))


class _QRCodeDialog(QDialog):
    """二维码预览对话框 — 展示 QR 码并提供保存到文件 / 数据库选项。"""

    def __init__(
        self,
        sn: str,
        pixmap: QPixmap,
        png_bytes: bytes,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sn = sn
        self._png_bytes = png_bytes
        self.setWindowTitle(f"二维码 — {sn}")
        self.setMinimumSize(380, 440)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {MANTLE};
                color: {TEXT};
            }}
            QLabel {{
                color: {TEXT};
            }}
            QPushButton {{
                background-color: {SURFACE0};
                color: {TEXT};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {SURFACE1};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel(f"🔲 样品二维码：{sn}")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        layout.addWidget(title)

        # 图片
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        layout.addStretch()

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_save_file = QPushButton("💾 保存到文件")
        btn_save_file.setStyleSheet(f"""
            QPushButton {{
                background-color: {BLUE};
                color: {CRUST};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {SURFACE1};
            }}
        """)
        btn_save_file.clicked.connect(self._save_to_file)
        btn_layout.addWidget(btn_save_file)

        btn_save_db = QPushButton("💾 保存到数据库")
        btn_save_db.setStyleSheet(f"""
            QPushButton {{
                background-color: {BLUE};
                color: {CRUST};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {SURFACE1};
            }}
        """)
        btn_save_db.clicked.connect(self._save_to_db)
        btn_layout.addWidget(btn_save_db)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _save_to_file(self) -> None:
        """保存二维码 PNG 到本地文件。"""
        default_name = f"QR_{self._sn}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存二维码", default_name,
            "PNG 图片 (*.png);;所有文件 (*)",
        )
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._png_bytes)
            QMessageBox.information(self, "保存成功", f"二维码已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件失败: {e}")

    def _save_to_db(self) -> None:
        """保存 base64 编码的二维码到数据库（通过回调）。

        由 main.py 中连接的回调处理实际存储逻辑。
        """
        if hasattr(self, "_db_callback") and callable(self._db_callback):
            self._db_callback(self._sn, self._png_bytes)


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

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addStretch()

        self._btn_edit = QPushButton("✏️ 编辑")
        self._btn_edit.setProperty("class", "action")
        self._btn_edit.setMinimumWidth(70)
        toolbar.addWidget(self._btn_edit)

        self._btn_generate_qr = QPushButton("🔲 生成二维码")
        self._btn_generate_qr.setProperty("class", "action")
        self._btn_generate_qr.setMinimumWidth(70)
        toolbar.addWidget(self._btn_generate_qr)

        layout.addLayout(toolbar)

        self._table = _SampleTable(self.COLUMNS)
        layout.addWidget(self._table)

    def refresh(self, samples: list[Sample]) -> None:
        self._table.set_samples(samples)

    # 暴露按钮和表格引用
    @property
    def btn_generate_qr(self) -> QPushButton:
        """生成二维码按钮。"""
        return self._btn_generate_qr

    @property
    def btn_edit(self) -> QPushButton:
        """编辑按钮。"""
        return self._btn_edit

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
        layout.setContentsMargins(24, 16, 24, 16)

        title = QLabel("📦 样品管理")
        title.setStyleSheet(f"color: {TEXT}; font-size: 24px; font-weight: bold;")
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
                color: {TEXT};
                padding: 8px 20px;
                border: none;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 14px;
            }}
            QTabBar::tab:selected {{
                background-color: {SURFACE1};
                color: {TEXT};
            }}
        """)

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
