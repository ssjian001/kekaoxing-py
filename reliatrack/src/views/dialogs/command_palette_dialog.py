"""全局命令面板 / 搜索对话框 (Command Palette Ctrl+K)。"""

from __future__ import annotations

from typing import Any, Callable
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QHBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QKeyEvent

import src.styles.theme as _t
from src.styles.constants import FONT_FAMILY


class CommandPaletteDialog(QDialog):
    """全局 Ctrl+K 快速搜索与功能跳转面板。"""

    # 发射 (category_key, item_id)
    item_selected = Signal(str, object)

    def __init__(
        self,
        fetcher: Callable[[str], list[dict[str, Any]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("全局搜索 (Ctrl+K)")
        self.setFixedWidth(560)
        self.setFixedHeight(380)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._fetcher = fetcher

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题提示
        header = QHBoxLayout()
        title = QLabel("🔍 全局速查 (Ctrl+K)")
        title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {_t.FG_PRIMARY};")
        hint = QLabel("Esc 退出 | ↑↓ 移动 | Enter 打开")
        hint.setStyleSheet(f"font-size: 11px; color: {_t.FG_MUTED};")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(hint)
        layout.addLayout(header)

        # 搜索框
        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText("输入关键字搜索项目、样品、设备、任务、Issue...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {_t.ACCENT};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: {_t.BG_INPUT};
                color: {_t.FG_PRIMARY};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_input)

        # 结果列表
        self._list_widget = QListWidget(self)
        self._list_widget.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {_t.BORDER};
                border-radius: 6px;
                background-color: {_t.BG_CARD};
                color: {_t.FG_PRIMARY};
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {_t.BORDER};
            }}
            QListWidget::item:selected {{
                background-color: {_t.SELECTION_BG};
                color: {_t.ACCENT};
                font-weight: bold;
            }}
        """)
        self._list_widget.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self._list_widget)

        # 聚焦到输入框
        self._search_input.setFocus()
        self._do_search("")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Down:
            idx = self._list_widget.currentRow()
            if idx < self._list_widget.count() - 1:
                self._list_widget.setCurrentRow(idx + 1)
        elif event.key() == Qt.Key.Key_Up:
            idx = self._list_widget.currentRow()
            if idx > 0:
                self._list_widget.setCurrentRow(idx - 1)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self._list_widget.currentItem()
            if item:
                self._on_item_activated(item)
        else:
            super().keyPressEvent(event)

    def _on_search_changed(self, text: str) -> None:
        self._do_search(text.strip())

    def _do_search(self, query: str) -> None:
        self._list_widget.clear()
        results = self._fetcher(query)
        if not results:
            item = QListWidgetItem("未找到相关数据")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list_widget.addItem(item)
            return

        for res in results:
            cat = res.get("category", "数据")
            name = res.get("name", "")
            detail = res.get("detail", "")
            display_text = f"[{cat}]  {name}"
            if detail:
                display_text += f"  ({detail})"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, res)
            self._list_widget.addItem(item)

        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_selected.emit(data.get("category_key", ""), data.get("id"))
            self.accept()
