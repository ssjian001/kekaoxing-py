"""统一主题系统 — Catppuccin Mocha 暗色主题。

本模块是 QSS 样式表的唯一来源（single source of truth）。
所有 UI 组件通过 `get_stylesheet()` 获取完整的应用样式。
"""

from __future__ import annotations

from src.styles.constants import FONT_FAMILY, FONT_SIZE_NORMAL

# ═══════════════════════════════════════════════════════════════════
#  Catppuccin Mocha 色板
# ═══════════════════════════════════════════════════════════════════

# Base
CRUST    = "#11111b"
MANTLE   = "#181825"
BASE     = "#1e1e2e"
SURFACE0 = "#313244"
SURFACE1 = "#45475a"
SURFACE2 = "#585b70"
OVERLAY0 = "#6c7086"
TEXT     = "#cdd6f4"
SUBTEXT0 = "#a6adc8"
SUBTEXT1 = "#bac2de"

# Accent
RED      = "#f38ba8"
PEACH    = "#fab387"
YELLOW   = "#f9e2af"
GREEN    = "#a6e3a1"
BLUE     = "#89b4fa"
LAVENDER = "#b4befe"
MAUVE    = "#cba6f7"
PINK     = "#f5c2e7"
TEAL     = "#94e2d5"
SKY      = "#89dceb"

# Semantic aliases
BG_DARK      = CRUST
BG_CARD      = MANTLE
BG_INPUT     = SURFACE0
BG_HOVER     = SURFACE1
FG_PRIMARY   = TEXT
FG_SECONDARY = SUBTEXT1
FG_MUTED     = OVERLAY0
BORDER       = SURFACE0
ACCENT       = BLUE
SUCCESS      = GREEN
DANGER       = RED
WARNING      = YELLOW


# ═══════════════════════════════════════════════════════════════════
#  QSS 构建块
# ═══════════════════════════════════════════════════════════════════

_BASE_QSS = f"""
/* ── 全局 ── */
QDialog, QMainWindow {{
    background-color: {BG_DARK};
    color: {FG_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_NORMAL}px;
}}

/* ── 分组框 ── */
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: {FG_PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

/* ── 输入控件 ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 24px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background-color: {BG_DARK};
    color: {FG_MUTED};
}}

/* ── 文本编辑框 ── */
QTextEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    font-family: {FONT_FAMILY};
}}

/* ── 按钮 ── */
QPushButton {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
}}
QPushButton:pressed {{
    background-color: {SURFACE2};
}}
QPushButton:disabled {{
    background-color: {BG_DARK};
    color: {FG_MUTED};
}}
QPushButton:checked {{
    background-color: {SURFACE1};
    border-color: {ACCENT};
}}

/* ── 主按钮 ── */
QPushButton[class="primary"] {{
    background-color: #1e6640;
    color: {SUCCESS};
    border-color: #2d9f5f;
}}
QPushButton[class="primary"]:hover {{
    background-color: #2d9f5f;
}}

/* ── 危险按钮 ── */
QPushButton[class="danger"] {{
    background-color: #6e2535;
    color: {DANGER};
    border-color: #a6374d;
}}
QPushButton[class="danger"]:hover {{
    background-color: #a6374d;
}}

/* ── 列表 ── */
QListWidget {{
    background-color: {BG_DARK};
    alternate-background-color: {BG_CARD};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
}}
QListWidget::item {{
    padding: 6px 8px;
}}
QListWidget::item:selected {{
    background-color: {BG_HOVER};
}}
QListWidget::item:alternate {{
    background-color: {BG_CARD};
}}

/* ── 表格 ── */
QTableWidget, QTableView {{
    background-color: {BG_DARK};
    alternate-background-color: {BG_CARD};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    selection-background-color: {BG_HOVER};
    selection-color: {FG_PRIMARY};
}}
QHeaderView::section {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    font-weight: bold;
}}

/* ── Tab ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG_DARK};
}}
QTabBar::tab {{
    background-color: {BG_INPUT};
    color: {FG_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 6px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: {BG_HOVER};
    color: {FG_PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: {SURFACE1};
}}

/* ── 滚动条 ── */
QScrollBar:vertical {{
    background: {BG_DARK};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BG_HOVER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_DARK};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BG_HOVER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── 菜单 ── */
QMenuBar {{
    background-color: {BG_CARD};
    color: {FG_PRIMARY};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item:selected {{
    background-color: {BG_HOVER};
}}
QMenu {{
    background-color: {BG_DARK};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
}}
QMenu::item:selected {{
    background-color: {BG_HOVER};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ── 标签 & 复选框 ── */
QLabel {{
    color: {FG_PRIMARY};
    background: transparent;
}}
QCheckBox {{
    color: {FG_PRIMARY};
    background: transparent;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── 单选按钮 ── */
QRadioButton {{
    color: {FG_PRIMARY};
    background: transparent;
    spacing: 6px;
}}

/* ── 状态栏 ── */
QStatusBar {{
    background-color: {BG_INPUT};
    color: {FG_MUTED};
    border-top: 1px solid {BORDER};
}}

/* ── 工具栏 ── */
QToolBar {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 2px;
}}

/* ── 分割器 ── */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* ── 工具提示 ── */
QToolTip {{
    background-color: {SURFACE2};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
    border-radius: 3px;
}}

/* ── 进度条 ── */
QProgressBar {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {FG_PRIMARY};
    min-height: 18px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ── 日期选择 ── */
QDateEdit, QTimeEdit, QDateTimeEdit {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 24px;
}}

/* ── 下拉列表弹出 ── */
QComboBox QAbstractItemView {{
    background-color: {BG_DARK};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {BG_HOVER};
    selection-color: {FG_PRIMARY};
}}

/* ── 诊断对话框 ── */
QMessageBox {{
    background-color: {BG_CARD};
}}
"""

# ═══════════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════════

# 预编译，避免每次调用 get_stylesheet() 重新拼接
_COMPILED_STYLESHEET: str | None = None


def get_stylesheet() -> str:
    """获取完整的应用 QSS 样式表。

    Returns:
        Catppuccin Mocha 暗色主题的完整 QSS 字符串。
    """
    global _COMPILED_STYLESHEET
    if _COMPILED_STYLESHEET is None:
        _COMPILED_STYLESHEET = _BASE_QSS
    return _COMPILED_STYLESHEET
