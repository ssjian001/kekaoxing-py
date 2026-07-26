"""全局快捷键帮助指南弹窗 (Keyboard Shortcuts Legend Dialog)。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QPushButton,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY


class KeyboardShortcutsDialog(QDialog):
    """按 ? 键唤出的键盘快捷键地图。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 440)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("shortcuts-container")
        container.setStyleSheet(
            f"QFrame#shortcuts-container {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 12px;"
            f"}}"
        )
        add_shadow(container)

        clay = QVBoxLayout(container)
        clay.setContentsMargins(20, 16, 20, 16)
        clay.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("⌨️ 键盘快捷键地图 (Keyboard Shortcuts)")
        title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 15px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        btn_close = QPushButton("✖ 关闭", self)
        btn_close.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 12px;"
        )
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        clay.addLayout(header)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {_theme.SURFACE0}; max-height: 1px; border: none;")
        clay.addWidget(line)

        # 快捷键 4 列网格布局
        grid = QGridLayout()
        grid.setSpacing(12)

        groups = [
            ("🚀 全局导航", [
                ("Ctrl + K", "打开 Spotlight 极速命令面板"),
                ("?  /  Shift + ?", "显示此快捷键指南地图"),
                ("Esc", "关闭弹窗 / 退出当前视图"),
                ("Ctrl + R", "手动触发数据刷新"),
            ]),
            ("↩️ 撤销与重做", [
                ("Ctrl + Z", "撤销上一步操作 (Undo)"),
                ("Ctrl + Y", "重做撤销的操作 (Redo)"),
                ("Ctrl + Shift + Z", "重做撤销的操作 (Redo)"),
            ]),
            ("🔍 搜索与筛选", [
                ("Ctrl + F", "聚焦项目 / 任务搜索框"),
                ("Tab 1 ~ 9", "按数字键快速切换顶部 Tab"),
            ]),
            ("📋 表格与多选", [
                ("鼠标右键", "唤出任务 / Issue 表格上下文菜单"),
                ("Ctrl + 鼠标左键", "多选独立表格数据行"),
                ("Shift + 鼠标左键", "连续范围勾选表格数据"),
            ]),
        ]

        row = 0
        for cat_title, shortcuts in groups:
            lbl_cat = QLabel(cat_title)
            lbl_cat.setStyleSheet(f"color: {DASH_PRIMARY}; font-size: 13px; font-weight: bold;")
            grid.addWidget(lbl_cat, row, 0, 1, 2)
            row += 1

            for key_str, desc_str in shortcuts:
                lbl_key = QLabel(key_str)
                lbl_key.setStyleSheet(
                    f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
                    f"border: 1px solid {_theme.SURFACE1}; border-radius: 4px; "
                    f"padding: 2px 8px; font-size: 11px; font-weight: bold; font-family: monospace;"
                )
                lbl_desc = QLabel(desc_str)
                lbl_desc.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px;")

                grid.addWidget(lbl_key, row, 0, Qt.AlignmentFlag.AlignLeft)
                grid.addWidget(lbl_desc, row, 1, Qt.AlignmentFlag.AlignLeft)
                row += 1

        clay.addLayout(grid)
        clay.addStretch()

        root.addWidget(container)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self.exec()
