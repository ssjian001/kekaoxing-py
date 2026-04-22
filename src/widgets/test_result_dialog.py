"""测试结果记录对话框"""

from __future__ import annotations

import json
from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QDateEdit, QTextEdit,
    QLineEdit, QListWidget, QTabWidget, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QFileDialog, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QColor, QFont

from src.db.database import Database


# ── 结果状态定义 ──────────────────────────────────
RESULT_META = {
    "pass":         {"label": "✅ 通过",       "color": "#a6e3a1", "dot": "🟢"},
    "fail":         {"label": "❌ 失败",       "color": "#f38ba8", "dot": "🔴"},
    "pending":      {"label": "⏳ 待定",       "color": "#6c7086", "dot": "⚪"},
    "skip":         {"label": "⏭️ 跳过",      "color": "#f9e2af", "dot": "🟡"},
    "conditional":  {"label": "⚠️ 有条件通过", "color": "#89b4fa", "dot": "🔵"},
}

SEVERITY_META = {
    "critical":   "严重",
    "major":      "主要",
    "minor":      "次要",
    "cosmetic":   "外观",
    "suggestion": "建议",
}


class _ResultButton(QPushButton):
    """单个结果选择按钮"""

    def __init__(self, key: str, parent=None):
        meta = RESULT_META[key]
        super().__init__(meta["label"], parent)
        self.result_key = key
        self.color = meta["color"]
        self.setFixedSize(90, 40)
        self.setCheckable(True)
        self._apply_style(False)

    def _apply_style(self, checked: bool):
        border = f"2px solid {self.color}" if checked else "1px solid #45475a"
        bg = self.color if checked else "#1e1e2e"
        opacity = "200" if checked else "100"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #1e1e2e;
                border: {border};
                border-radius: 8px;
                font-size: 13px;
                font-weight: {"bold" if checked else "normal"};
            }}
            QPushButton:hover {{
                background-color: {self.color};
            }}
        """)

    def set_checked_with_style(self, checked: bool):
        self.setChecked(checked)
        self._apply_style(checked)


class _DetailDialog(QDialog):
    """只读详情弹窗"""

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 测试结果详情")
        self.setMinimumSize(500, 400)
        self._record = record
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)

        r = self._record
        meta = RESULT_META.get(r.get("result", ""), {})
        result_label = meta.get("label", r.get("result", ""))

        date_val = r.get("test_date", "")
        if isinstance(date_val, str) and date_val:
            date_val = date_val[:10]

        fields = [
            ("测试日期", date_val or "-"),
            ("测试结果", result_label),
            ("测试人员", r.get("tester", "") or "-"),
            ("测试数据", r.get("test_data", "") or "-"),
            ("备注", r.get("notes", "") or "-"),
            ("创建时间", (r.get("created_at", "") or "-")[:19]),
        ]

        for label, value in fields:
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #a6adc8; font-weight: bold;")
            val = QLabel(str(value))
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if label == "测试结果:" and meta:
                val.setStyleSheet(f"color: {meta['color']}; font-size: 14px; font-weight: bold;")
            layout.addRow(lbl, val)

        # 附件
        attachments = r.get("attachments")
        if attachments:
            if isinstance(attachments, str):
                try:
                    attachments = json.loads(attachments)
                except (json.JSONDecodeError, TypeError):
                    attachments = None
            if attachments and isinstance(attachments, (list, tuple)):
                att_lbl = QLabel("附件:")
                att_lbl.setStyleSheet("color: #a6adc8; font-weight: bold;")
                att_list = QListWidget()
                att_list.setMaximumHeight(80)
                att_list.addItems(str(a) for a in attachments)
                layout.addRow(att_lbl, att_list)

        # 关闭按钮
        btn = QPushButton("关闭")
        btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        layout.addRow(btn_layout)


class TestResultDialog(QDialog):
    """测试结果记录对话框"""

    def __init__(
        self,
        db: Database,
        task_id: int,
        task_num: str = "",
        task_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.task_id = task_id
        self.task_num = task_num
        self.task_name = task_name
        self._attachments: list[str] = []

        self.setWindowTitle(f"🧪 测试结果 — {task_num} {task_name}")
        self.setMinimumSize(700, 500)

        self._build_ui()
        self._load_latest_status()
        self.refresh()

    # ── UI 构建 ──────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── 顶部任务信息栏 ──
        info_bar = QFrame()
        info_bar.setObjectName("infoBar")
        info_bar.setStyleSheet("""
            #infoBar {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(12, 8, 12, 8)

        self.lbl_task_info = QLabel(
            f"<b>{self.task_num}</b>  {self.task_name}"
        )
        self.lbl_task_info.setStyleSheet("color: #cdd6f4; font-size: 14px;")
        info_layout.addWidget(self.lbl_task_info)

        self.lbl_latest_result = QLabel("")
        self.lbl_latest_result.setStyleSheet("font-size: 13px; font-weight: bold;")
        info_layout.addStretch()
        info_layout.addWidget(self.lbl_latest_result)

        root.addWidget(info_bar)

        # ── Tab Widget ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 6px;
                background: #1e1e2e;
                top: -1px;
            }
            QTabBar::tab {
                background: #181825;
                color: #a6adc8;
                padding: 8px 20px;
                border: 1px solid #313244;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #1e1e2e;
                color: #cdd6f4;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #313244;
            }
        """)
        self._build_new_result_tab()
        self._build_history_tab()
        root.addWidget(self.tabs)

        # ── Issue 快速创建区 ──
        self.issue_widget = QWidget()
        self.issue_widget.setVisible(False)
        self._build_issue_section()
        root.addWidget(self.issue_widget)

    def _build_new_result_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # 测试日期
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setFixedWidth(200)
        self.date_edit.setStyleSheet("""
            QDateEdit {
                background: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QDateEdit::drop-down { border: none; }
            QCalendarWidget {
                background: #1e1e2e;
                color: #cdd6f4;
            }
        """)
        form.addRow("测试日期:", self.date_edit)

        # 测试结果 — 大按钮组
        result_label = QLabel("测试结果:")
        result_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        btn_group = QWidget()
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        self.result_buttons: list[_ResultButton] = []
        for key in RESULT_META:
            btn = _ResultButton(key)
            btn.clicked.connect(lambda checked, k=key: self._select_result(k))
            btn_layout.addWidget(btn)
            self.result_buttons.append(btn)

        btn_layout.addStretch()
        form.addRow(result_label, btn_group)

        # 测试人员
        self.tester_edit = QLineEdit()
        self.tester_edit.setPlaceholderText("输入测试人员姓名")
        self._apply_input_style(self.tester_edit)
        form.addRow("测试人员:", self.tester_edit)

        # 测试数据
        self.test_data_edit = QTextEdit()
        self.test_data_edit.setFixedHeight(56)
        self.test_data_edit.setPlaceholderText("输入关键数据摘要…")
        self._apply_textedit_style(self.test_data_edit)
        form.addRow("测试数据:", self.test_data_edit)

        # 备注
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(84)
        self.notes_edit.setPlaceholderText("输入备注信息…")
        self._apply_textedit_style(self.notes_edit)
        form.addRow("备注:", self.notes_edit)

        # 附件
        att_container = QWidget()
        att_layout = QVBoxLayout(att_container)
        att_layout.setContentsMargins(0, 0, 0, 0)
        att_layout.setSpacing(4)

        self.attachment_list = QListWidget()
        self.attachment_list.setFixedHeight(60)
        self.attachment_list.setStyleSheet("""
            QListWidget {
                background: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-size: 12px;
            }
            QListWidget::item { padding: 2px; }
        """)
        att_layout.addWidget(self.attachment_list)

        att_btn_row = QHBoxLayout()
        att_btn_row.setSpacing(6)
        btn_add_att = QPushButton("📎 添加")
        btn_add_att.setFixedWidth(80)
        btn_add_att.clicked.connect(self._add_attachment)
        btn_del_att = QPushButton("🗑️ 删除")
        btn_del_att.setFixedWidth(80)
        btn_del_att.clicked.connect(self._remove_attachment)
        att_btn_row.addWidget(btn_add_att)
        att_btn_row.addWidget(btn_del_att)
        att_btn_row.addStretch()
        att_layout.addLayout(att_btn_row)

        form.addRow("附件:", att_container)

        layout.addLayout(form)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_reset = QPushButton("🔄 重置")
        self.btn_reset.setFixedWidth(100)
        self.btn_reset.clicked.connect(self._reset_form)
        btn_row.addWidget(self.btn_reset)

        self.btn_save = QPushButton("💾 保存结果")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.setFixedWidth(120)
        self.btn_save.clicked.connect(self._save_result)
        self.btn_save.setStyleSheet("""
            QPushButton#primaryBtn {
                background: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#primaryBtn:hover {
                background: #b4d0fb;
            }
        """)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

        self.tabs.addTab(page, "📝 新增结果")

    def _build_history_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["日期", "结果", "测试人员", "测试数据", "备注", "操作"]
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Fixed
        )
        self.history_table.setColumnWidth(0, 100)
        self.history_table.setColumnWidth(5, 160)
        self.history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                gridline-color: #313244;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #313244;
            }
            QTableWidget::item:alternate {
                background: #181825;
            }
            QHeaderView::section {
                background: #181825;
                color: #a6adc8;
                border: none;
                border-bottom: 1px solid #313244;
                border-right: 1px solid #313244;
                padding: 6px 4px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self.history_table.cellDoubleClicked.connect(self._show_detail)

        layout.addWidget(self.history_table)
        self.tabs.addTab(page, "📋 历史记录")

    def _build_issue_section(self):
        self.issue_widget.setStyleSheet("""
            QWidget#issueSection {
                background: #181825;
                border: 1px solid #f38ba8;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        self.issue_widget.setObjectName("issueSection")

        layout = QVBoxLayout(self.issue_widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        title = QLabel("🐛 快速创建 Issue")
        title.setStyleSheet(
            "color: #f38ba8; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self.issue_title_edit = QLineEdit()
        self.issue_title_edit.setText(
            f"任务 {self.task_num} - {self.task_name} 测试失败"
        )
        self._apply_input_style(self.issue_title_edit)
        form.addRow("标题:", self.issue_title_edit)

        self.severity_combo = QComboBox()
        self.severity_combo.setFixedWidth(160)
        for key, label in SEVERITY_META.items():
            self.severity_combo.addItem(label, key)
        self.severity_combo.setStyleSheet("""
            QComboBox {
                background: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1e1e2e;
                color: #cdd6f4;
                selection-background-color: #313244;
            }
        """)
        form.addRow("严重程度:", self.severity_combo)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_create = QPushButton("🐛 创建 Issue")
        btn_create.setFixedWidth(130)
        btn_create.setStyleSheet("""
            QPushButton {
                background: #f38ba8;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #f5a3b8; }
        """)
        btn_create.clicked.connect(self._create_issue)
        btn_row.addWidget(btn_create)
        layout.addLayout(btn_row)

    # ── 样式辅助 ──────────────────────────────────

    @staticmethod
    def _apply_input_style(widget: QLineEdit):
        widget.setStyleSheet("""
            QLineEdit {
                background: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
            }
        """)

    @staticmethod
    def _apply_textedit_style(widget: QTextEdit):
        widget.setStyleSheet("""
            QTextEdit {
                background: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #89b4fa;
            }
        """)

    # ── 逻辑 ──────────────────────────────────

    def _load_latest_status(self):
        latest = self.db.get_latest_test_result(self.task_id)
        if latest:
            meta = RESULT_META.get(latest.get("result", ""), {})
            color = meta.get("color", "#a6adc8")
            label = meta.get("label", latest["result"])
            self.lbl_latest_result.setText(f"最新结果: {label}")
            self.lbl_latest_result.setStyleSheet(
                f"color: {color}; font-size: 13px; font-weight: bold;"
            )
        else:
            self.lbl_latest_result.setText("最新结果: 暂无")
            self.lbl_latest_result.setStyleSheet(
                "color: #6c7086; font-size: 13px; font-weight: bold;"
            )

    def _select_result(self, key: str):
        for btn in self.result_buttons:
            btn.set_checked_with_style(btn.result_key == key)
        # 显示/隐藏 Issue 区域
        self.issue_widget.setVisible(key == "fail")

    def _current_result(self) -> str | None:
        for btn in self.result_buttons:
            if btn.isChecked():
                return btn.result_key
        return None

    def _add_attachment(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择附件", "", "All Files (*)"
        )
        for f in files:
            self._attachments.append(f)
            self.attachment_list.addItem(f)

    def _remove_attachment(self):
        row = self.attachment_list.currentRow()
        if row >= 0:
            self._attachments.pop(row)
            self.attachment_list.takeItem(row)

    def _save_result(self):
        result = self._current_result()
        if not result:
            QMessageBox.warning(self, "提示", "请选择测试结果！")
            return

        test_date = self.date_edit.date().toString("yyyy-MM-dd")
        tester = self.tester_edit.text().strip()
        test_data = self.test_data_edit.toPlainText().strip()
        notes = self.notes_edit.toPlainText().strip()
        attachments = self._attachments if self._attachments else None

        self.db.insert_test_result(
            self.task_id,
            result,
            test_data=test_data,
            notes=notes,
            tester=tester,
            attachments=attachments,
        )
        QMessageBox.information(self, "成功", "测试结果已保存！")
        self._load_latest_status()
        self.refresh()
        self._reset_form()

    def _reset_form(self):
        self.date_edit.setDate(QDate.currentDate())
        for btn in self.result_buttons:
            btn.set_checked_with_style(False)
        self.tester_edit.clear()
        self.test_data_edit.clear()
        self.notes_edit.clear()
        self._attachments.clear()
        self.attachment_list.clear()
        self.issue_widget.setVisible(False)

    def refresh(self):
        """刷新历史记录表格"""
        results = self.db.get_test_results(self.task_id)
        self.history_table.setRowCount(len(results))

        for row_idx, r in enumerate(results):
            # 日期
            d = r.get("test_date", "")
            if isinstance(d, str):
                d = d[:10]
            date_item = QTableWidgetItem(str(d))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row_idx, 0, date_item)

            # 结果 — 彩色标签
            meta = RESULT_META.get(r.get("result", ""), {})
            color = meta.get("color", "#cdd6f4")
            label = meta.get("label", r.get("result", ""))
            result_item = QTableWidgetItem(f" {label} ")
            result_item.setForeground(QColor(color))
            result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = result_item.font()
            font.setBold(True)
            result_item.setFont(font)
            self.history_table.setItem(row_idx, 1, result_item)

            # 测试人员
            self.history_table.setItem(
                row_idx, 2, QTableWidgetItem(r.get("tester", "") or "-")
            )

            # 测试数据（截断显示）
            td = r.get("test_data", "") or "-"
            if len(td) > 40:
                td = td[:40] + "…"
            self.history_table.setItem(row_idx, 3, QTableWidgetItem(td))

            # 备注（截断显示）
            nt = r.get("notes", "") or "-"
            if len(nt) > 40:
                nt = nt[:40] + "…"
            self.history_table.setItem(row_idx, 4, QTableWidgetItem(nt))

            # 操作列 — 嵌入按钮
            ops_widget = QWidget()
            ops_layout = QHBoxLayout(ops_widget)
            ops_layout.setContentsMargins(4, 2, 4, 2)
            ops_layout.setSpacing(4)

            btn_detail = QPushButton("详情")
            btn_detail.setFixedSize(60, 26)
            btn_detail.setStyleSheet("""
                QPushButton {
                    background: #313244;
                    color: #cdd6f4;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover { background: #45475a; }
            """)
            btn_detail.clicked.connect(
                lambda checked, rid=r["id"]: self._show_detail_by_id(rid)
            )
            ops_layout.addWidget(btn_detail)

            btn_del = QPushButton("删除")
            btn_del.setFixedSize(60, 26)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: #45273a;
                    color: #f38ba8;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover { background: #58374c; }
            """)
            btn_del.clicked.connect(
                lambda checked, rid=r["id"]: self._delete_result(rid)
            )
            ops_layout.addWidget(btn_del)

            self.history_table.setCellWidget(row_idx, 5, ops_widget)

        # 设置行高
        self.history_table.resizeRowsToContents()

    def _show_detail(self, row: int, _col: int):
        """双击表格行 → 弹出详情"""
        results = self.db.get_test_results(self.task_id)
        if 0 <= row < len(results):
            dlg = _DetailDialog(results[row], self)
            dlg.exec()

    def _show_detail_by_id(self, result_id: int):
        results = self.db.get_test_results(self.task_id)
        for r in results:
            if r["id"] == result_id:
                dlg = _DetailDialog(r, self)
                dlg.exec()
                return

    def _delete_result(self, result_id: int):
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条测试记录吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_test_result(result_id)
            self._load_latest_status()
            self.refresh()

    def _create_issue(self):
        title = self.issue_title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入 Issue 标题！")
            return

        severity = self.severity_combo.currentData()
        notes = self.notes_edit.toPlainText().strip()
        tester = self.tester_edit.text().strip()

        description_parts = []
        if tester:
            description_parts.append(f"测试人员: {tester}")
        if notes:
            description_parts.append(f"备注: {notes}")
        test_data = self.test_data_edit.toPlainText().strip()
        if test_data:
            description_parts.append(f"测试数据: {test_data}")
        description = "\n".join(description_parts)

        self.db.insert_issue(
            self.task_id,
            title,
            description=description,
            severity=severity,
        )
        QMessageBox.information(self, "成功", f"Issue 已创建：\n{title}")
        self.issue_title_edit.clear()
