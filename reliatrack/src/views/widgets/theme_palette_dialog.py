"""多主题与品牌强调色切换弹窗 (Theme & Accent Palette Dialog)。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QButtonGroup,
    QApplication,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY, DASH_SUCCESS, DASH_WARNING, DASH_DANGER


class ThemePaletteDialog(QDialog):
    """主题模式与强调色自由切换弹窗。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(460, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("theme-dialog-container")
        container.setStyleSheet(
            f"QFrame#theme-dialog-container {{"
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

        title = QLabel("🎨 界面主题与品牌强调色 (Theme System)")
        title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        btn_close = QPushButton("✖ 关闭", self)
        btn_close.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 11px;"
        )
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        clay.addLayout(header)

        # 主题模式选择 (Dark / Light)
        lbl_mode = QLabel("主题模式 (Theme Mode):")
        lbl_mode.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_mode)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)

        self._btn_dark = QPushButton("🌙 暗黑模式 (Dark)")
        self._btn_light = QPushButton("☀️ 极简明亮 (Light)")

        current_theme = _theme.get_current_theme()
        for btn, name in ((self._btn_dark, "dark"), (self._btn_light, "light")):
            btn.setProperty("class", "pill")
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setChecked(name == current_theme)
            btn.clicked.connect(lambda _, t=name: self._switch_theme(t))
            mode_row.addWidget(btn)

        self._mode_grp = QButtonGroup(self)
        self._mode_grp.addButton(self._btn_dark)
        self._mode_grp.addButton(self._btn_light)

        clay.addLayout(mode_row)

        # 品牌强调色选择
        lbl_accent = QLabel("品牌强调色 (Accent Palette):")
        lbl_accent.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_accent)

        accents_row = QHBoxLayout()
        accents_row.setSpacing(10)

        colors = [
            ("🔵 科技蓝", "#1e66f5"),
            ("🟢 翡翠绿", "#40a02b"),
            ("🟣 优雅紫", "#8839ef"),
            ("🟠 暖金黄", "#fe640b"),
        ]

        for label, hex_color in colors:
            btn_acc = QPushButton(label)
            btn_acc.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_acc.setStyleSheet(
                f"QPushButton {{"
                f"  background: {_theme.SURFACE0};"
                f"  color: {hex_color};"
                f"  border: 1px solid {hex_color};"
                f"  border-radius: 8px;"
                f"  padding: 6px 12px;"
                f"  font-size: 12px;"
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: {hex_color};"
                f"  color: #FFFFFF;"
                f"}}"
            )
            btn_acc.clicked.connect(lambda _, c=hex_color: self._apply_accent(c))
            accents_row.addWidget(btn_acc)

        clay.addLayout(accents_row)

        # 实时效果预览卡片
        preview = QFrame()
        preview.setStyleSheet(f"background: {_theme.SURFACE0}; border-radius: 8px; padding: 12px;")
        play = QVBoxLayout(preview)
        play.setContentsMargins(10, 8, 10, 8)

        lbl_pv = QLabel("✨ 实时预览：ReliaTrack 高品质可靠性追踪管理系统")
        lbl_pv.setStyleSheet(f"color: {_theme.TEXT}; font-size: 12px; font-weight: 500;")
        play.addWidget(lbl_pv)

        clay.addWidget(preview)

        root.addWidget(container)

    def _switch_theme(self, theme_name: str) -> None:
        _theme.set_theme(theme_name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(_theme.get_stylesheet())
        self.accept()

    def _apply_accent(self, color_hex: str) -> None:
        # 修改全局 ACCENT 并应用 QSS
        _theme.BLUE = color_hex
        _theme.ACCENT = color_hex
        app = QApplication.instance()
        if app:
            app.setStyleSheet(_theme.get_stylesheet())
        self.accept()

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self.exec()
