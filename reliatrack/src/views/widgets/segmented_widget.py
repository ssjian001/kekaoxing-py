"""分頁分段控件 SegmentedWidget — 替代 QTabWidget 的緊湊藥丸樣式。

樣式類似 macOS Segmented Control / Fluent SegmentedWidget。
支持 2~5 項分段切換，無 pane 邊框，高度 26px。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QStackedWidget, QButtonGroup

import src.styles.theme as _t


class SegmentedWidget(QWidget):
    """分段切換控件 — 藥丸形按鈕組，替代 QTabWidget 做子導航。

    用法：
        seg = SegmentedWidget()
        seg.addSegment("看板", widget1)
        seg.addSegment("列表", widget2)
        seg.addSegment("更多", widget3)
        seg.setCurrentIndex(0)
        layout.addWidget(seg)
    """

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)

        self._buttons: list[QPushButton] = []
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._button_group.idClicked.connect(self._on_button_clicked)

    def addSegment(self, text: str, widget: QWidget | None = None):
        """添加一個分段。

        Args:
            text: 顯示文字
            widget: 該分段對應的頁面（可選，後續通過 setStackedWidget 關聯）
        """
        btn = QPushButton(text)
        btn.setProperty("class", "segmented-button")
        btn.setFixedHeight(26)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        idx = len(self._buttons)
        self._button_group.addButton(btn, idx)
        self._layout.addWidget(btn)
        self._buttons.append(btn)

        if widget is not None:
            setattr(self, f"_widget_{idx}", widget)

    def setStackedWidget(self, stacked: QStackedWidget):
        """綁定 QStackedWidget，切換分段時自動更新頁面。"""
        self._stacked = stacked
        self.currentChanged.connect(lambda i: stacked.setCurrentIndex(i))

    def setCurrentIndex(self, index: int):
        """切換到指定分段。"""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self._update_style()
            self.currentChanged.emit(index)

    def _on_button_clicked(self, idx: int):
        """按鈕點擊後更新样式。"""
        self.setCurrentIndex(idx)

    def _update_style(self):
        """更新所有按鈕的屬性样式。"""
        for i, btn in enumerate(self._buttons):
            if btn.isChecked():
                btn.setProperty("class", "segmented-active")
            else:
                btn.setProperty("class", "segmented-button")
            # 強制 Qt 重算样式
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def count(self) -> int:
        return len(self._buttons)
