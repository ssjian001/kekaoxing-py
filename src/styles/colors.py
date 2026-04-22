"""统一的 Catppuccin Mocha 色板常量 — 全局唯一来源。"""

# ── Base ──
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

# ── Accent ──
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

# ── Semantic ──
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

# ── QSS building blocks ──
BASE_QSS = f"""
QDialog, QMainWindow {{
    background-color: {BG_DARK};
    color: {FG_PRIMARY};
}}
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
QTableWidget {{
    background-color: {BG_DARK};
    alternate-background-color: {BG_CARD};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
}}
QHeaderView::section {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
}}
QTabBar::tab {{
    background-color: {BG_INPUT};
    color: {FG_SECONDARY};
    border: 1px solid {BORDER};
    padding: 6px 16px;
}}
QTabBar::tab:selected {{
    background-color: {BG_HOVER};
    color: {FG_PRIMARY};
}}
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
QLabel {{
    color: {FG_PRIMARY};
}}
QCheckBox {{
    color: {FG_PRIMARY};
}}
QStatusBar {{
    background-color: {BG_INPUT};
    color: {FG_MUTED};
}}
QToolTip {{
    background-color: {SURFACE2};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""

PRIMARY_BTN_QSS = f"""
QPushButton {{
    background-color: #1e6640;
    color: {SUCCESS};
    border-color: #2d9f5f;
}}
QPushButton:hover {{
    background-color: #2d9f5f;
}}
"""

DANGER_BTN_QSS = f"""
QPushButton {{
    background-color: #6e2535;
    color: {DANGER};
    border-color: #a6374d;
}}
QPushButton:hover {{
    background-color: #a6374d;
}}
"""
