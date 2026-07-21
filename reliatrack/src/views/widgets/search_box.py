"""搜索框 — 內置清除按鈕 + 可選搜索圖標。

移植自 qfluentwidgets LineEdit。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QToolButton, QSizePolicy

import src.styles.theme as _t


class SearchBox(QLineEdit):
    """搜索輸入框，帶清除按鈕和可選左側搜索圖標按鈕。"""

    # textChanged 繼承自 QLineEdit，直接使用

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "search-box")
        self.setFixedHeight(26)
        self.setPlaceholderText("搜索…")
        self.setMinimumWidth(160)
        self.setMaximumWidth(260)
        self.setClearButtonEnabled(True)

        # 右側清除按鈕（QLineEdit 自帶，但我們自定義樣式）
        # QLineEdit 的 clearButton 已夠用，不再額外添加

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # 可選：聚焦時高亮邊框
        self.setProperty("focused", True)
        self.style().unpolish(self)
        self.style().polish(self)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.setProperty("focused", False)
        self.style().unpolish(self)
        self.style().polish(self)
