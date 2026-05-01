"""统一主题系统 — Catppuccin Latte 明亮主题。

本模块是 QSS 样式表的唯一来源（single source of truth）。
所有 UI 组件通过 `get_stylesheet()` 获取完整的应用样式。
"""

from __future__ import annotations

from src.styles.constants import FONT_FAMILY, FONT_SIZE_NORMAL

# ═══════════════════════════════════════════════════════════════════
#  Catppuccin Latte 色板
# ═══════════════════════════════════════════════════════════════════

# Base
CRUST    = "#dc8a78"
MANTLE   = "#e6e9ef"
BASE     = "#eff1f5"
SURFACE0 = "#ccd0da"
SURFACE1 = "#bcc0cc"
SURFACE2 = "#acb0be"
OVERLAY0 = "#9ca0b0"
TEXT     = "#4c4f69"
SUBTEXT0 = "#6c6f85"
SUBTEXT1 = "#5c5f77"

# Accent
RED      = "#d20f39"
PEACH    = "#fe640b"
YELLOW   = "#df8e1d"
GREEN    = "#40a02b"
BLUE     = "#1e66f5"
LAVENDER = "#7287fd"
MAUVE    = "#8839ef"
PINK     = "#ea76cb"
TEAL     = "#179299"
SKY      = "#04a5e5"

# Semantic aliases
BG_DARK      = BASE       # main background (lightest)
BG_CARD      = MANTLE     # card/secondary background
BG_INPUT     = SURFACE0   # input fields
BG_HOVER     = SURFACE1   # hover states
FG_PRIMARY   = TEXT       # primary text (dark)
FG_SECONDARY = SUBTEXT1   # secondary text
FG_MUTED     = OVERLAY0   # muted/disabled text
BORDER       = SURFACE0   # borders
ACCENT       = BLUE       # accent color
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
QLineEdit, QDoubleSpinBox, QComboBox {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 24px;
}}
QSpinBox {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 4px;
    min-height: 24px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px;
    border: none;
    background-color: {BORDER};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {ACCENT};
}}
QSpinBox::up-arrow {{
    width: 8px;
    height: 8px;
}}
QSpinBox::down-arrow {{
    width: 8px;
    height: 8px;
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
    background-color: #40a02b;
    color: #ffffff;
    border-color: #358524;
}}
QPushButton[class="primary"]:hover {{
    background-color: #358524;
}}

/* ── 危险按钮 ── */
QPushButton[class="danger"] {{
    background-color: #fdf2f4;
    color: #d20f39;
    border-color: #d20f39;
}}
QPushButton[class="danger"]:hover {{
    background-color: #fce4e8;
}}

/* ── 操作按钮 ── */
QPushButton[class="action"] {{
    background-color: {BG_INPUT};
    color: {ACCENT};
    border: 1px solid {ACCENT};
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton[class="action"]:hover {{
    background-color: {BG_HOVER};
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
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 10px;
    font-weight: bold;
    font-size: 13px;
}}

/* ── Tab ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG_DARK};
    padding-top: 4px;
}}
QTabBar::tab {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 6px 14px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 13px;
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
    color: {FG_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 13px;
}}

/* ── 工具栏 ── */
QToolBar {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 3px 8px;
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
        Catppuccin Latte 明亮主题的完整 QSS 字符串。
    """
    global _COMPILED_STYLESHEET
    if _COMPILED_STYLESHEET is None:
        _COMPILED_STYLESHEET = _BASE_QSS
    return _COMPILED_STYLESHEET
