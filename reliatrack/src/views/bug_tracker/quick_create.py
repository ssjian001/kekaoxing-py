"""快速创建 Issue — Ctrl+C / C 键弹窗，极简表单。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QPushButton, QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal
from src.styles.icon import RI_CHECK, RI_CLOSE


class QuickCreateDialog(QDialog):
    """极简 Issue 创建弹窗。Tab 跳转，Enter 提交，Esc 取消。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("快速创建 Issue")
        self.setFixedSize(420, 320)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._result_data: dict | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        lbl_title = QLabel("标题")
        layout.addWidget(lbl_title)
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Issue 标题（必填）")
        layout.addWidget(self._title_edit)

        # 严重度 + 优先级 同行
        row1 = QHBoxLayout()
        lbl_sev = QLabel("严重度")
        row1.addWidget(lbl_sev)
        self._severity_combo = QComboBox()
        self._severity_combo.addItems(["严重 (critical)", "主要 (major)", "次要 (minor)", "外观 (cosmetic)"])
        self._severity_combo.setCurrentIndex(1)  # major 默认
        row1.addWidget(self._severity_combo)

        lbl_pri = QLabel("优先级")
        row1.addWidget(lbl_pri)
        self._priority_combo = QComboBox()
        for i in range(1, 6):
            self._priority_combo.addItem(f"P{i}")
        self._priority_combo.setCurrentIndex(2)  # P3 默认
        row1.addWidget(self._priority_combo)
        layout.addLayout(row1)

        # 描述
        lbl_desc = QLabel("描述")
        layout.addWidget(lbl_desc)
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("问题描述（可选，含复现步骤/截图说明）")
        self._desc_edit.setMaximumHeight(100)
        layout.addWidget(self._desc_edit)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setProperty("class", "action")
        btn_cancel.setIcon(RI_CLOSE.icon())
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        self._btn_create = QPushButton("创建")
        self._btn_create.setProperty("class", "primary")
        self._btn_create.setIcon(RI_CHECK.icon())
        self._btn_create.setDefault(True)
        self._btn_create.clicked.connect(self._on_create)
        btn_row.addWidget(self._btn_create)
        layout.addLayout(btn_row)

        # 自动聚焦标题
        self._title_edit.setFocus()
        # Tab 顺序
        self.setTabOrder(self._title_edit, self._severity_combo)
        self.setTabOrder(self._severity_combo, self._priority_combo)
        self.setTabOrder(self._priority_combo, self._desc_edit)
        self.setTabOrder(self._desc_edit, self._btn_create)

    def _on_create(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            self._title_edit.setFocus()
            self._title_edit.setStyleSheet("border: 1px solid #e64553;")
            QTimer.singleShot(2000, lambda: self._title_edit.setStyleSheet(""))
            return

        severity_map = {
            "严重 (critical)": "critical",
            "主要 (major)": "major",
            "次要 (minor)": "minor",
            "外观 (cosmetic)": "cosmetic",
        }
        severity = severity_map.get(self._severity_combo.currentText(), "major")
        priority = self._priority_combo.currentIndex() + 1

        self._result_data = {
            "title": title,
            "severity": severity,
            "priority": priority,
            "description": self._desc_edit.toPlainText().strip(),
        }
        self.accept()

    def result_data(self) -> dict | None:
        return self._result_data
