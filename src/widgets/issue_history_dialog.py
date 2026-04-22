"""Issue 变更历史对话框 — 展示 issue 字段变更的时间线。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from src.db.database import Database

# 复用 issue_tracker 的常量
from src.widgets.issue_tracker import (
    STATUS_MAP, SEVERITY_MAP, ISSUE_TYPE_MAP, PHASE_MAP,
    BG_EVEN, BG_ODD, BG_PANEL, FG_TEXT, FG_DIM, BORDER, ACCENT,
)

# 字段显示名 & 值映射
_FIELD_LABELS = {
    "status": "状态",
    "severity": "严重程度",
    "issue_type": "类型",
    "phase": "测试阶段",
    "title": "标题",
    "assignee": "负责人",
    "priority": "优先级",
}

_VALUE_MAPS = {
    "status": STATUS_MAP,
    "severity": SEVERITY_MAP,
    "issue_type": ISSUE_TYPE_MAP,
    "phase": PHASE_MAP,
}


def _display_value(field: str, raw: str) -> str:
    """将存储的 raw value 转为可读 label"""
    if field in _VALUE_MAPS and raw:
        label, _ = _VALUE_MAPS[field].get(raw, (raw, FG_DIM))
        return label
    return raw or "—"


class IssueHistoryDialog(QDialog):
    """展示单个 issue 的变更历史"""

    def __init__(self, db: Database, issue_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.issue_id = issue_id
        self.setWindowTitle(f"📜 变更历史 — Issue #{issue_id}")
        self.setMinimumSize(600, 360)
        self.resize(720, 480)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(f"Issue #{self.issue_id} 变更历史")
        title.setStyleSheet(f"color: {FG_TEXT}; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "时间", "字段", "旧值", "新值", "备注"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_EVEN}; color: {FG_TEXT}; }}
            QLabel {{ color: {FG_TEXT}; }}
            QTableWidget {{
                background: {BG_EVEN}; alternate-background-color: {BG_ODD};
                color: {FG_TEXT}; gridline-color: {BORDER};
                border: 1px solid {BORDER}; border-radius: 4px;
            }}
            QTableWidget::item {{
                padding: 3px 6px; border-bottom: 1px solid {BORDER};
            }}
            QHeaderView::section {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: none; border-bottom: 1px solid {BORDER};
                border-right: 1px solid {BORDER};
                padding: 4px 6px; font-size: 12px; font-weight: bold;
            }}
            QPushButton {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 5px 14px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {BORDER}; }}
        """)

    def _load(self):
        records = self.db.get_issue_history(self.issue_id)
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            # 时间
            t = rec.get("changed_at", "")
            t_item = QTableWidgetItem(t)
            t_item.setForeground(QBrush(QColor(FG_DIM)))
            t_item.setFont(QFont("", 11))
            self.table.setItem(row, 0, t_item)

            # 字段
            field = rec.get("field", "")
            label = _FIELD_LABELS.get(field, field)
            f_item = QTableWidgetItem(label)
            f_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, f_item)

            # 旧值
            old_val = _display_value(field, rec.get("old_value", ""))
            old_item = QTableWidgetItem(old_val)
            old_item.setForeground(QBrush(QColor("#f38ba8")))
            self.table.setItem(row, 2, old_item)

            # 新值
            new_val = _display_value(field, rec.get("new_value", ""))
            new_item = QTableWidgetItem(new_val)
            new_item.setForeground(QBrush(QColor("#a6e3a1")))
            self.table.setItem(row, 3, new_item)

            # 备注
            remark = rec.get("remark", "") or ""
            r_item = QTableWidgetItem(remark)
            r_item.setForeground(QBrush(QColor(FG_DIM)))
            self.table.setItem(row, 4, r_item)

        if not records:
            self.table.setRowCount(1)
            empty = QTableWidgetItem("暂无变更记录")
            empty.setForeground(QBrush(QColor(FG_DIM)))
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setSpan(0, 0, 1, 5)
            self.table.setItem(0, 0, empty)
