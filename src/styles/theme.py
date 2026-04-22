"""深色/浅色主题 QSS 样式表"""

DARK_STYLE = """
/* ── 全局 ── */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    font-size: 13px;
}

/* ── 主窗口 ── */
QMainWindow {
    background-color: #1e1e2e;
}

/* ── 工具栏 ── */
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    padding: 6px;
    spacing: 8px;
}

QToolBar QToolButton {
    background-color: transparent;
    color: #cdd6f4;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
}

QToolBar QToolButton:hover {
    background-color: #313244;
    border-color: #45475a;
}

QToolBar QToolButton:pressed {
    background-color: #585b70;
}

QToolBar QToolButton:checked {
    background-color: #313244;
    border-color: #89b4fa;
    color: #89b4fa;
}

/* ── 按钮 ── */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 16px;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton#primaryBtn {
    background-color: #89b4fa;
    color: #1e1e2e;
    border-color: #89b4fa;
    font-weight: bold;
}

QPushButton#primaryBtn:hover {
    background-color: #74c7ec;
}

QPushButton#dangerBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    border-color: #f38ba8;
}

/* ── 表格 ── */
QTableWidget, QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}

QHeaderView::section {
    background-color: #181825;
    color: #cdd6f4;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #313244;
    border-bottom: 1px solid #313244;
    font-weight: bold;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── 选项卡 ── */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #1e1e2e;
}

QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
}

QTabBar::tab:hover:!selected {
    background-color: #313244;
    color: #cdd6f4;
}

/* ── 输入框 ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #89b4fa;
}

/* ── 复选框 ── */
QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #45475a;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

/* ── 对话框 ── */
QDialog {
    background-color: #1e1e2e;
}

/* ── 分组框 ── */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #cdd6f4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}

/* ── 标签 ── */
QLabel {
    color: #cdd6f4;
}

QLabel#sectionLabel {
    font-weight: bold;
    font-size: 14px;
    padding: 4px 8px;
}

/* ── 下拉菜单 ── */
QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
    border: 1px solid #45475a;
}

/* ── 状态栏 ── */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
}

/* ── 分割器 ── */
QSplitter::handle {
    background-color: #313244;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* ── 工具提示 ── */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── GraphicsView (甘特图) ── */
QGraphicsView {
    background-color: #11111b;
    border: none;
}
"""

LIGHT_STYLE = """
/* ── 全局 ── */
QWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    font-size: 13px;
}

/* ── 主窗口 ── */
QMainWindow {
    background-color: #eff1f5;
}

/* ── 工具栏 ── */
QToolBar {
    background-color: #e6e9ef;
    border-bottom: 1px solid #ccd0da;
    padding: 6px;
    spacing: 8px;
}

QToolBar QToolButton {
    background-color: transparent;
    color: #4c4f69;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
}

QToolBar QToolButton:hover {
    background-color: #ccd0da;
    border-color: #bcc0cc;
}

QToolBar QToolButton:pressed {
    background-color: #bcc0cc;
}

QToolBar QToolButton:checked {
    background-color: #ccd0da;
    border-color: #1e66f5;
    color: #1e66f5;
}

/* ── 按钮 ── */
QPushButton {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 6px 16px;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #ccd0da;
    border-color: #bcc0cc;
}

QPushButton:pressed {
    background-color: #bcc0cc;
}

QPushButton#primaryBtn {
    background-color: #1e66f5;
    color: #ffffff;
    border-color: #1e66f5;
    font-weight: bold;
}

QPushButton#primaryBtn:hover {
    background-color: #2a6ef5;
}

QPushButton#dangerBtn {
    background-color: #d20f39;
    color: #ffffff;
    border-color: #d20f39;
}

/* ── 表格 ── */
QTableWidget, QTableView {
    background-color: #eff1f5;
    alternate-background-color: #e6e9ef;
    gridline-color: #ccd0da;
    border: 1px solid #ccd0da;
    selection-background-color: #ccd0da;
    selection-color: #4c4f69;
}

QHeaderView::section {
    background-color: #e6e9ef;
    color: #4c4f69;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #ccd0da;
    border-bottom: 1px solid #ccd0da;
    font-weight: bold;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    background-color: #e6e9ef;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #ccd0da;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #bcc0cc;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #e6e9ef;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #ccd0da;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── 选项卡 ── */
QTabWidget::pane {
    border: 1px solid #ccd0da;
    border-radius: 6px;
    background-color: #eff1f5;
}

QTabBar::tab {
    background-color: #e6e9ef;
    color: #6c6f85;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #eff1f5;
    color: #1e66f5;
    border-bottom: 2px solid #1e66f5;
}

QTabBar::tab:hover:!selected {
    background-color: #ccd0da;
    color: #4c4f69;
}

/* ── 输入框 ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #1e66f5;
}

/* ── 复选框 ── */
QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #ccd0da;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #1e66f5;
    border-color: #1e66f5;
}

/* ── 对话框 ── */
QDialog {
    background-color: #eff1f5;
}

/* ── 分组框 ── */
QGroupBox {
    border: 1px solid #ccd0da;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #4c4f69;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #1e66f5;
}

/* ── 标签 ── */
QLabel {
    color: #4c4f69;
}

QLabel#sectionLabel {
    font-weight: bold;
    font-size: 14px;
    padding: 4px 8px;
}

/* ── 下拉菜单 ── */
QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #4c4f69;
    selection-background-color: #ccd0da;
    border: 1px solid #ccd0da;
}

/* ── 状态栏 ── */
QStatusBar {
    background-color: #e6e9ef;
    color: #6c6f85;
    border-top: 1px solid #ccd0da;
}

/* ── 分割器 ── */
QSplitter::handle {
    background-color: #ccd0da;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* ── 工具提示 ── */
QToolTip {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── GraphicsView (甘特图) ── */
QGraphicsView {
    background-color: #eff1f5;
    border: none;
}
"""


def apply_theme(app, dark: bool = True):
    """应用主题到 QApplication"""
    from PySide6.QtWidgets import QApplication
    app.setStyleSheet(DARK_STYLE if dark else LIGHT_STYLE)
