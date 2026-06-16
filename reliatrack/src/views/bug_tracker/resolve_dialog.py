"""关闭 Issue 弹窗 — 强制选择 Resolution 和关闭评论。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTextEdit, QPushButton, QWidget,
)
from PySide6.QtCore import Qt, QTimer


_RESOLUTIONS = [
    ("fixed", "已修复"),
    ("wont_fix", "不予修复"),
    ("duplicate", "重复问题"),
    ("cannot_reproduce", "无法复现"),
    ("not_an_issue", "非问题"),
]


class ResolveDialog(QDialog):
    """关闭 Issue 弹窗 — 强制选 resolution + 关闭评论。"""

    def __init__(self, issue_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关闭 Issue")
        self.setFixedSize(400, 280)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._result: dict | None = None
        self._issue_title = issue_title
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Issue 标题
        lbl_info = QLabel(f"关闭 Issue: {self._issue_title}")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        # Resolution 选择
        lbl_res = QLabel("处理结果（必选）")
        layout.addWidget(lbl_res)
        self._resolution_combo = QComboBox()
        for eng, chn in _RESOLUTIONS:
            self._resolution_combo.addItem(f"{chn} ({eng})", eng)
        layout.addWidget(self._resolution_combo)

        # 关闭评论
        lbl_comment = QLabel("关闭说明（可选）")
        layout.addWidget(lbl_comment)
        self._comment_edit = QTextEdit()
        self._comment_edit.setPlaceholderText("记录关闭原因、验证结论等…")
        self._comment_edit.setMaximumHeight(80)
        layout.addWidget(self._comment_edit)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setProperty("class", "action")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        self._btn_confirm = QPushButton("关闭 Issue")
        self._btn_confirm.setProperty("class", "primary")
        self._btn_confirm.setDefault(True)
        self._btn_confirm.clicked.connect(self._on_confirm)
        btn_row.addWidget(self._btn_confirm)
        layout.addLayout(btn_row)

        self._resolution_combo.setFocus()

    def _on_confirm(self) -> None:
        self._result = {
            "resolution": self._resolution_combo.currentData(),
            "resolution_label": self._resolution_combo.currentText(),
            "closing_comment": self._comment_edit.toPlainText().strip(),
        }
        self.accept()

    def result_data(self) -> dict | None:
        return self._result
