"""表格列显示/隐藏自定义菜单控件 (Column Visibility Menu)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QMenu,
    QWidgetAction,
    QCheckBox,
    QTableWidget,
    QPushButton,
    QWidget,
    QVBoxLayout,
)

import src.styles.theme as _theme


class ColumnVisibilityMenu(QMenu):
    """通用的表格列显示/隐藏勾选菜单。"""

    def __init__(self, table: QTableWidget, persistence_key: str, parent: QWidget | None = None):
        super().__init__("👁️ 列显示设置", parent)
        self._table = table
        self._key = f"ReliaTrack/column_visibility_{persistence_key}"
        self._setup_menu()

    def _setup_menu(self) -> None:
        self.setStyleSheet(
            f"QMenu {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 8px;"
            f"  padding: 6px;"
            f"}}"
        )

        header = self._table.horizontalHeader()
        if not header:
            return

        saved_states = QSettings().value(self._key, {})
        if not isinstance(saved_states, dict):
            saved_states = {}

        for col in range(self._table.columnCount()):
            col_name = self._table.model().headerData(col, Qt.Orientation.Horizontal)
            if not col_name:
                col_name = f"第 {col + 1} 列"

            chk = QCheckBox(str(col_name))
            chk.setStyleSheet(
                f"QCheckBox {{ color: {_theme.TEXT}; font-size: 12px; padding: 4px 8px; }}"
                f"QCheckBox:hover {{ background: {_theme.SURFACE0}; border-radius: 4px; }}"
            )

            # 恢复上次保存的隐显状态
            is_hidden = saved_states.get(str(col), self._table.isColumnHidden(col))
            self._table.setColumnHidden(col, bool(is_hidden))
            chk.setChecked(not is_hidden)

            chk.toggled.connect(lambda checked, c=col: self._on_column_toggled(c, checked))

            act = QWidgetAction(self)
            act.setDefaultWidget(chk)
            self.addAction(act)

    def _on_column_toggled(self, col: int, visible: bool) -> None:
        self._table.setColumnHidden(col, not visible)

        # 保存到 QSettings
        states = QSettings().value(self._key, {})
        if not isinstance(states, dict):
            states = {}
        states[str(col)] = not visible
        QSettings().setValue(self._key, states)


def create_column_visibility_button(table: QTableWidget, persistence_key: str, parent: QWidget | None = None) -> QPushButton:
    """快捷创建打开列显示控制菜单的齿轮按钮。"""
    btn = QPushButton("👁️ 列", parent)
    btn.setProperty("class", "action")
    btn.setFixedWidth(54)
    btn.setFixedHeight(26)
    btn.setToolTip("显示/隐藏表格列")

    menu = ColumnVisibilityMenu(table, persistence_key, btn)
    btn.setMenu(menu)
    return btn
