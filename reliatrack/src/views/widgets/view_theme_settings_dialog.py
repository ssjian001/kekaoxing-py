"""视图与主题融合设置中心 (Unified View & Theme Settings Dialog)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
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
    QTabWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY, DASH_SUCCESS


class ViewThemeSettingsDialog(QDialog):
    """视图与主题统一设置中心弹窗。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(520, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("settings-dialog-container")
        container.setStyleSheet(
            f"QFrame#settings-dialog-container {{"
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

        title = QLabel("⚙️ 视图偏好与主题个性化设置中心")
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

        # Tab 面板分类
        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {_theme.SURFACE1}; border-radius: 8px; background: {_theme.BASE}; }}"
            f"QTabBar::tab {{ padding: 6px 14px; margin-right: 4px; border-radius: 6px; font-size: 12px; font-weight: 500; }}"
            f"QTabBar::tab:selected {{ background: {_theme.SURFACE0}; color: {_theme.TEXT}; font-weight: bold; }}"
        )

        # ───── Tab 1: 主题色彩 ─────
        tab_theme = QWidget()
        th_lay = QVBoxLayout(tab_theme)
        th_lay.setContentsMargins(14, 14, 14, 14)
        th_lay.setSpacing(12)

        lbl_mode = QLabel("主题模式 (Theme Mode):")
        lbl_mode.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        th_lay.addWidget(lbl_mode)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)

        btn_dark = QPushButton("🌙 暗黑模式 (Dark)")
        btn_light = QPushButton("☀️ 极简明亮 (Light)")

        cur_theme = _theme.get_current_theme()
        btn_dark.setChecked(cur_theme == "dark")
        btn_light.setChecked(cur_theme == "light")

        btn_dark.clicked.connect(lambda: self._switch_theme("dark"))
        btn_light.clicked.connect(lambda: self._switch_theme("light"))

        mode_row.addWidget(btn_dark)
        mode_row.addWidget(btn_light)
        th_lay.addLayout(mode_row)

        # 品牌强调色
        lbl_acc = QLabel("品牌强调色 (Accent Palette):")
        lbl_acc.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        th_lay.addWidget(lbl_acc)

        acc_row = QHBoxLayout()
        acc_row.setSpacing(8)

        colors = [
            ("🔵 科技蓝", "#1e66f5"),
            ("🟢 翡翠绿", "#40a02b"),
            ("🟣 优雅紫", "#8839ef"),
            ("🟠 暖金黄", "#fe640b"),
        ]

        for label, hex_col in colors:
            btn_acc = QPushButton(label)
            btn_acc.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_acc.setStyleSheet(
                f"background: {_theme.SURFACE0}; color: {hex_col}; "
                f"border: 1px solid {hex_col}; border-radius: 6px; padding: 6px 10px; font-weight: 600; font-size: 11px;"
            )
            btn_acc.clicked.connect(lambda _, c=hex_col: self._apply_accent(c))
            acc_row.addWidget(btn_acc)

        th_lay.addLayout(acc_row)
        th_lay.addStretch()

        tabs.addTab(tab_theme, "🎨 主题色彩")

        # ───── Tab 2: 视图与列偏好 ─────
        tab_view = QWidget()
        v_lay = QVBoxLayout(tab_view)
        v_lay.setContentsMargins(14, 14, 14, 14)
        v_lay.setSpacing(12)

        lbl_col_reset = QLabel("表格自定义列控制重置 (Table Visibility):")
        lbl_col_reset.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        v_lay.addWidget(lbl_col_reset)

        btn_reset_cols = QPushButton("🔄 一键恢复所有表格列默认显示")
        btn_reset_cols.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; border: 1px solid {_theme.SURFACE1}; "
            f"border-radius: 6px; padding: 6px 12px; font-size: 12px;"
        )
        btn_reset_cols.clicked.connect(self._reset_all_column_visibility)
        v_lay.addWidget(btn_reset_cols)

        v_lay.addStretch()
        tabs.addTab(tab_view, "👁️ 视图偏好")

        clay.addWidget(tabs)
        root.addWidget(container)

    def _switch_theme(self, theme_name: str) -> None:
        try:
            if theme_name != _theme.get_current_theme():
                _theme.set_theme(theme_name)
                _theme.apply_palette()
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(_theme.get_stylesheet())
                mw = self.parent()
                if hasattr(mw, "refresh_theme"):
                    mw.refresh_theme()
        except Exception:
            pass

    def _apply_accent(self, color_hex: str) -> None:
        try:
            cur = _theme.get_current_theme()
            _theme._PALETTES[cur]["ACCENT"] = color_hex
            _theme._PALETTES[cur]["BLUE"] = color_hex
            globals()["ACCENT"] = color_hex
            globals()["BLUE"] = color_hex
            _theme.apply_palette()
            app = QApplication.instance()
            if app:
                app.setStyleSheet(_theme.get_stylesheet())
        except Exception:
            pass

    def _reset_all_column_visibility(self) -> None:
        settings = QSettings()
        for key in ["task_table", "project_table", "equipment_table", "sample_ledger", "bug_table"]:
            settings.remove(key)
        mw = self.parent()
        if hasattr(mw, "toast"):
            mw.toast("已成功恢复所有表格列默认显示状态！", "success")

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self.exec()
