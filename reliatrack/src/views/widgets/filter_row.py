"""動態篩選行模式 — FilterRow + FilterPanel。

可動態增刪的條件行（欄位→運算符→值），替代固定 checkbox 篩選面板。

用法：
    panel = DynamicFilterPanel(known_fields={
        "status": ("狀態", "text"),
        "severity": ("嚴重度", "text"),
        "priority": ("優先級", "int"),
        "due_date": ("到期日", "date"),
    })
    panel.filter_changed.connect(self._apply_filters)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.styles.icon import RI_ADD, RI_CLOSE, RI_SEARCH

# ═══════════════════════════════════════════════════════════════════
#  運算符定義
# ═══════════════════════════════════════════════════════════════════

OPERATORS_TEXT = [
    ("contains", "包含"),
    ("not_contains", "不包含"),
    ("eq", "等於"),
    ("ne", "不等於"),
    ("starts_with", "開頭是"),
    ("ends_with", "結尾是"),
]

OPERATORS_NUM = [
    ("eq", "="),
    ("ne", "≠"),
    ("gt", ">"),
    ("gte", "≥"),
    ("lt", "<"),
    ("lte", "≤"),
]

OPERATORS_DATE = [
    ("eq", "等於"),
    ("gt", "之後"),
    ("lt", "之前"),
    ("range", "範圍"),
    ("today", "今天"),
    ("this_week", "本週"),
    ("overdue", "已逾期"),
]

OPERATORS_ENUM = [
    ("eq", "是"),
    ("ne", "不是"),
    ("any", "任意"),
    ("none", "無"),
]


def _operators_for(field_type: str) -> list[tuple[str, str]]:
    if field_type == "int":
        return OPERATORS_NUM
    if field_type == "date":
        return OPERATORS_DATE
    if field_type == "enum":
        return OPERATORS_ENUM
    return OPERATORS_TEXT


# ═══════════════════════════════════════════════════════════════════
#  篩選引擎
# ═══════════════════════════════════════════════════════════════════


def _get_field_value(item: Any, field: str) -> Any:
    """從對象或 dict 中取值。"""
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def match_row(item: Any, conditions: list[dict]) -> bool:
    """檢查一個數據項是否匹配所有篩選條件（AND 合取）。"""
    if not conditions:
        return True
    for cond in conditions:
        field = cond["field"]
        op = cond["op"]
        val = cond["val"]
        field_type = cond.get("field_type", "text")
        actual = _get_field_value(item, field)

        if field_type == "date":
            actual_str = str(actual or "")

            if op == "today":
                today_str = QDate.currentDate().toString("yyyy-MM-dd")
                if actual_str != today_str:
                    return False
            elif op == "overdue":
                if actual_str and actual_str >= QDate.currentDate().toString("yyyy-MM-dd"):
                    return False
            elif op == "this_week":
                from PySide6.QtCore import QDate
                today = QDate.currentDate()
                mon = today.addDays(-(today.dayOfWeek() - 1))
                sun = today.addDays(7 - today.dayOfWeek())
                d = QDate.fromString(actual_str, "yyyy-MM-dd")
                if not d or d < mon or d > sun:
                    return False
            elif val and actual_str != val:
                return False
        elif field_type == "int":
            actual_int = int(actual) if actual else 0
            val_int = int(val) if val else 0
            if op == "eq" and actual_int != val_int:
                return False
            elif op == "ne" and actual_int == val_int:
                return False
            elif op == "gt" and not (actual_int > val_int):
                return False
            elif op == "gte" and not (actual_int >= val_int):
                return False
            elif op == "lt" and not (actual_int < val_int):
                return False
            elif op == "lte" and not (actual_int <= val_int):
                return False
        elif field_type == "enum":
            actual_str = str(actual or "")
            if op == "eq" and actual_str != val:
                return False
            elif op == "ne" and actual_str == val:
                return False
            elif op == "any" and not actual_str:
                return False
            elif op == "none" and actual_str:
                return False
        else:
            # text
            actual_str = str(actual or "")
            val_str = str(val or "")
            if op == "contains" and val_str not in actual_str:
                return False
            elif op == "not_contains" and val_str in actual_str:
                return False
            elif op == "eq" and actual_str != val_str:
                return False
            elif op == "ne" and actual_str == val_str:
                return False
            elif op == "starts_with" and not actual_str.startswith(val_str):
                return False
            elif op == "ends_with" and not actual_str.endswith(val_str):
                return False
    return True


# ═══════════════════════════════════════════════════════════════════
#  FilterRow — 單個篩選條件行
# ═══════════════════════════════════════════════════════════════════


class FilterRow(QFrame):
    """一行篩選條件：欄位 + 運算符 + 值 + 刪除。"""

    changed = Signal()
    removed = Signal(object)  # self

    def __init__(self, known_fields: dict[str, tuple[str, str]],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._known_fields = known_fields
        # field_key → (display_name, field_type)
        self._field_type = "text"
        self.setProperty("class", "row-surface")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # 欄位選擇
        self._field_combo = QComboBox()
        self._field_combo.setProperty("class", "filter-combo")
        self._field_combo.setMinimumWidth(120)
        for key, (chn, _ft) in known_fields.items():
            self._field_combo.addItem(chn, key)
        self._field_combo.currentIndexChanged.connect(self._on_field_change)
        layout.addWidget(self._field_combo)

        # 運算符
        self._op_combo = QComboBox()
        self._op_combo.setProperty("class", "filter-combo")
        self._op_combo.setMinimumWidth(80)
        layout.addWidget(self._op_combo)

        # 值（根據類型切換控件）
        self._value_stack = QStackedWidget()
        self._value_stack.setMinimumWidth(140)

        self._text_edit = QLineEdit()
        self._text_edit.setPlaceholderText("輸入值…")
        self._text_edit.textChanged.connect(lambda: self.changed.emit())
        self._value_stack.addWidget(self._text_edit)  # 0

        self._int_spin = QSpinBox()
        self._int_spin.setRange(0, 9999)
        self._int_spin.valueChanged.connect(lambda: self.changed.emit())
        self._value_stack.addWidget(self._int_spin)  # 1

        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.dateChanged.connect(lambda: self.changed.emit())
        self._value_stack.addWidget(self._date_edit)  # 2

        self._enum_combo = QComboBox()
        self._enum_combo.setProperty("class", "filter-combo")
        self._enum_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        self._value_stack.addWidget(self._enum_combo)  # 3

        self._empty_label = QLabel("")
        self._value_stack.addWidget(self._empty_label)  # 4

        layout.addWidget(self._value_stack, stretch=1)

        # 刪除按鈕
        self._btn_remove = QPushButton()
        self._btn_remove.setIcon(RI_CLOSE.icon())
        self._btn_remove.setIconSize(QSize(14, 14))
        self._btn_remove.setFixedSize(24, 24)
        self._btn_remove.setProperty("class", "action")
        self._btn_remove.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(self._btn_remove)

        # 初始化運算符
        self._refresh_operators()

    def _on_field_change(self, idx: int) -> None:
        self._refresh_operators()
        self.changed.emit()

    def _refresh_operators(self) -> None:
        key = self._field_combo.currentData()
        _, field_type = self._known_fields.get(key, ("", "text"))
        self._field_type = field_type

        # 更新運算符
        self._op_combo.blockSignals(True)
        self._op_combo.clear()
        for op_key, op_label in _operators_for(field_type):
            self._op_combo.addItem(op_label, op_key)
        self._op_combo.blockSignals(False)

        # 切換值控件
        if field_type == "int":
            self._value_stack.setCurrentIndex(1)
            self._int_spin.setValue(0)
        elif field_type == "date":
            op = self._op_combo.currentData()
            if op in ("today", "overdue", "this_week"):
                self._value_stack.setCurrentIndex(4)  # no value needed
            else:
                self._value_stack.setCurrentIndex(2)
        elif field_type == "enum":
            self._value_stack.setCurrentIndex(3)
        else:
            self._value_stack.setCurrentIndex(0)

    def set_enum_options(self, options: list[str]) -> None:
        """設置枚舉類型的可選值。"""
        self._enum_combo.clear()
        self._enum_combo.addItems(options)

    def get_condition(self) -> dict:
        """返回當前行條件 dict。"""
        field = self._field_combo.currentData()
        op = self._op_combo.currentData()
        _, field_type = self._known_fields.get(field, ("", "text"))

        if field_type == "int":
            val = str(self._int_spin.value())
        elif field_type == "date":
            if op in ("today", "overdue", "this_week"):
                val = ""
            else:
                val = self._date_edit.date().toString("yyyy-MM-dd")
        elif field_type == "enum":
            val = self._enum_combo.currentText()
        else:
            val = self._text_edit.text()

        return {
            "field": field,
            "field_type": field_type,
            "op": op,
            "val": val,
        }


# ═══════════════════════════════════════════════════════════════════
#  DynamicFilterPanel — 動態篩選面板容器
# ═══════════════════════════════════════════════════════════════════


class DynamicFilterPanel(QFrame):
    """可動態增刪條件行的篩選面板。"""

    filter_changed = Signal(dict)  # {"conditions": [...]}

    def __init__(self, known_fields: dict[str, tuple[str, str]],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "filter-panel")

        self._known_fields = known_fields
        self._rows: list[FilterRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 頭部說明 + 添加按鈕
        header = QHBoxLayout()
        header.setSpacing(8)
        lbl = QLabel("篩選條件")
        lbl.setProperty("class", "filter-label")
        header.addWidget(lbl)
        header.addStretch()

        self._btn_add = QPushButton("添加條件")
        self._btn_add.setIcon(RI_ADD.icon())
        self._btn_add.setIconSize(QSize(14, 14))
        self._btn_add.clicked.connect(self._add_row)
        header.addWidget(self._btn_add)

        self._btn_clear = QPushButton("清除")
        self._btn_clear.setProperty("class", "action")
        self._btn_clear.clicked.connect(self._clear_all)
        header.addWidget(self._btn_clear)

        layout.addLayout(header)

        # 條件行（滾動區域包裹）
        self._rows_container = QVBoxLayout()
        self._rows_container.setSpacing(4)

        scroll = QScrollArea()
        scroll.setProperty("class", "scroll-base")
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(220)
        content = QWidget()
        content.setLayout(self._rows_container)
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        # 預設添加一行
        self._add_row()

    def _add_row(self) -> None:
        row = FilterRow(self._known_fields, self)
        row.changed.connect(self._emit_filter)
        row.removed.connect(self._remove_row)
        self._rows.append(row)
        self._rows_container.addWidget(row)
        self._emit_filter()

    def _remove_row(self, row: FilterRow) -> None:
        if len(self._rows) <= 1:
            return  # 至少保留一行
        self._rows.remove(row)
        self._rows_container.removeWidget(row)
        row.deleteLater()
        self._emit_filter()

    def _clear_all(self) -> None:
        for row in list(self._rows):
            self._rows.remove(row)
            self._rows_container.removeWidget(row)
            row.deleteLater()
        self._add_row()

    def _emit_filter(self) -> None:
        conditions = [r.get_condition() for r in self._rows]
        self.filter_changed.emit({"conditions": conditions})

    def get_conditions(self) -> list[dict]:
        return [r.get_condition() for r in self._rows]

    def set_enum_options(self, field: str, options: list[str]) -> None:
        """為指定欄位設置枚舉可選值。"""
        for row in self._rows:
            row.set_enum_options(options)
