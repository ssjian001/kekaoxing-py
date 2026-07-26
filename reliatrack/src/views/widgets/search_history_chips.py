"""搜索历史气泡芯片组件 (Search History Chips)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY


class SearchHistoryChips(QFrame):
    """搜索历史气泡标签行。"""

    chip_clicked = Signal(str)

    def __init__(self, key: str = "default", parent: QWidget | None = None):
        super().__init__(parent)
        self._key = f"ReliaTrack/search_history_{key}"
        self._setup_ui()
        self.reload_chips()

    def _setup_ui(self) -> None:
        self.setFixedHeight(30)
        self.setStyleSheet("background: transparent; border: none;")

        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)

    def reload_chips(self) -> None:
        """从 QSettings 重新加载最近 5 条搜索历史。"""
        # 清理已有子控件
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        raw = QSettings().value(self._key, [])
        history = list(raw) if isinstance(raw, list) else []

        if not history:
            self.hide()
            return

        self.show()

        lbl_hint = QLabel("最近搜索:")
        lbl_hint.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
        self._lay.addWidget(lbl_hint)

        for kw in history[:5]:  # 保留前 5 条
            if not isinstance(kw, str) or not kw.strip():
                continue
            btn = QPushButton(kw.strip())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {_theme.SURFACE0};"
                f"  color: {_theme.TEXT};"
                f"  border: 1px solid {_theme.SURFACE1};"
                f"  border-radius: 10px;"
                f"  padding: 2px 8px;"
                f"  font-size: 11px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: {_theme.SURFACE1};"
                f"  color: {DASH_PRIMARY};"
                f"}}"
            )
            btn.clicked.connect(lambda _, text=kw.strip(): self.chip_clicked.emit(text))
            self._lay.addWidget(btn)

        # 清空按钮
        btn_clear = QPushButton("✖")
        btn_clear.setToolTip("清空搜索历史")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_theme.SUBTEXT0}; border: none; font-size: 10px; }}"
            f"QPushButton:hover {{ color: {_theme.DANGER}; }}"
        )
        btn_clear.clicked.connect(self.clear_history)
        self._lay.addWidget(btn_clear)

        self._lay.addStretch()

    def save_keyword(self, keyword: str) -> None:
        """保存新关键词到历史。"""
        kw = keyword.strip()
        if not kw or len(kw) < 2:
            return

        raw = QSettings().value(self._key, [])
        history = list(raw) if isinstance(raw, list) else []

        if kw in history:
            history.remove(kw)
        history.insert(0, kw)
        history = history[:10]  # 最多存 10 条

        QSettings().setValue(self._key, history)
        self.reload_chips()

    def clear_history(self) -> None:
        """清空保存的搜索历史。"""
        QSettings().setValue(self._key, [])
        self.reload_chips()
