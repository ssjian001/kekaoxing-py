"""通用弹窗基类 — Catppuccin Mocha 暗色主题。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from src.styles.theme import (
    CRUST,
    MANTLE,
    BASE,
    SURFACE0,
    SURFACE1,
    SURFACE2,
    TEXT,
    SUBTEXT0,
    SUBTEXT1,
    GREEN,
    YELLOW,
    RED,
    BLUE,
    PEACH,
    LAVENDER,
    MAUVE,
    PINK,
)

# ═══════════════════════════════════════════════════════════════════
#  Dialog QSS
# ═══════════════════════════════════════════════════════════════════

_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {MANTLE};
        color: {TEXT};
    }}
    QLabel {{
        color: {TEXT};
        font-size: 13px;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QComboBox {{
        background-color: {SURFACE0};
        color: {TEXT};
        border: 1px solid {SURFACE1};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 13px;
        min-height: 24px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {BLUE};
    }}
    QPushButton {{
        background-color: {BLUE};
        color: {CRUST};
        border: none;
        border-radius: 6px;
        padding: 6px 20px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{
        opacity: 0.85;
    }}
    QComboBox QAbstractItemView {{
        background-color: {SURFACE0};
        color: {TEXT};
        selection-background-color: {SURFACE1};
    }}
    QGroupBox {{
        color: {TEXT};
        border: 1px solid {SURFACE1};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 16px;
        font-size: 14px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
"""


# ═══════════════════════════════════════════════════════════════════
#  Base Dialog
# ═══════════════════════════════════════════════════════════════════

class _BaseDialog(QDialog):
    """通用弹窗基类 — 提供暗色主题、QFormLayout 和 OK/Cancel 按钮。"""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        width: int = 420,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.setStyleSheet(_DIALOG_STYLE)

        # 主布局
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 16, 20, 16)
        self._root.setSpacing(12)

        # 表单布局
        self._form = QFormLayout()
        self._form.setSpacing(10)
        self._form.setLabelAlignment(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignRight
        )
        self._root.addLayout(self._form)

        # 按钮栏
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._btn_box.accepted.connect(self.accept)
        self._btn_box.rejected.connect(self.reject)
        self._root.addWidget(self._btn_box)

    # ── 辅助方法 ──────────────────────────────────────────────────

    def _add_text_field(
        self,
        label: str,
        default: str = "",
        placeholder: str = "",
        readonly: bool = False,
    ) -> QLineEdit:
        """添加一行文本字段并返回控件。"""
        edit = QLineEdit(default)
        if placeholder:
            edit.setPlaceholderText(placeholder)
        if readonly:
            edit.setReadOnly(True)
        self._form.addRow(label, edit)
        return edit

    def _add_combo_field(
        self,
        label: str,
        items: list[str],
        default: str = "",
        editable: bool = False,
    ) -> QComboBox:
        """添加一行下拉框并返回控件。"""
        combo = QComboBox()
        combo.setEditable(editable)
        combo.addItems(items)
        if default:
            idx = combo.findText(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._form.addRow(label, combo)
        return combo

    def _add_date_field(
        self,
        label: str,
    ) -> QDateEdit:
        """添加一行日期选择并返回控件。"""
        from PySide6.QtCore import QDate

        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDate(QDate.currentDate())
        edit.setDisplayFormat("yyyy-MM-dd")
        self._form.addRow(label, edit)
        return edit

    def _add_label_field(
        self,
        label: str,
        text: str,
    ) -> QLabel:
        """添加一行只读标签（用于展示信息）。"""
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        self._form.addRow(label, lbl)
        return lbl

    def _add_separator(self) -> None:
        """在表单中添加水平分隔。"""
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {SURFACE1}; border: none;")
        self._form.addRow(line)

    def _add_text_area(
        self,
        label: str,
        default: str = "",
    ) -> QTextEdit:
        """添加 QTextEdit 多行文本字段并返回控件。"""
        edit = QTextEdit(default)
        edit.setFixedHeight(72)
        self._form.addRow(label, edit)
        return edit

    def _add_spin_field(
        self,
        label: str,
        default: int = 0,
        min_val: int = 0,
        max_val: int = 100,
    ) -> QSpinBox:
        """添加 QSpinBox 数字字段并返回控件。"""
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        self._form.addRow(label, spin)
        return spin
