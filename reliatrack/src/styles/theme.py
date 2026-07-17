"""统一主题系统 — Catppuccin Latte (明亮) / Mocha (暗色) 双色板。

本模块是 QSS 样式表的唯一来源（single source of truth）。
所有 UI 组件通过 `get_stylesheet()` 获取完整的应用样式。

用法:
    from src.styles.theme import get_stylesheet, set_theme, theme_host
    app.setStyleSheet(get_stylesheet())          # 启动时
    set_theme("dark")                             # 切换暗色
    theme_host.theme_changed.connect(my_refresh)  # 订阅刷新
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.styles.constants import FONT_FAMILY, FONT_SIZE_NORMAL

# ═══════════════════════════════════════════════════════════════════
#  Catppuccin 双色板 — Latte (light) / Mocha (dark)
# ═══════════════════════════════════════════════════════════════════

_PALETTES: dict[str, dict[str, str]] = {
    "light": dict(
        # Base neutrals
        CRUST    = "#DCE0E8",
        MANTLE   = "#FFFFFF",      # 卡片/次要背景 → 白底
        BASE     = "#F7F8FC",      # 主背景 → 浅灰
        SURFACE0 = "#F1F5F9",      # 输入框背景
        SURFACE1 = "#E2E8F0",      # hover / 边框
        SURFACE2 = "#CBD5E1",      # 更深灰
        OVERLAY0 = "#94A3B8",      # muted text
        TEXT     = "#1E293B",      # 主文字
        SUBTEXT0 = "#64748B",      # 次要文字
        SUBTEXT1 = "#475569",      # 二级文字
        # Accent
        RED      = "#d20f39",
        PEACH    = "#fe640b",
        YELLOW   = "#df8e1d",
        GREEN    = "#40a02b",
        GREEN_DARK = "#358524",
        BLUE     = "#1e66f5",
        LAVENDER = "#7287fd",
        MAUVE    = "#8839ef",
        PINK     = "#ea76cb",
        TEAL     = "#179299",
        SKY      = "#04a5e5",
        # Semantic aliases
        BG_BASE      = "#F7F8FC",      # 主背景 → BASE 同值
        BG_DARK      = "#F7F8FC",
        BG_CARD      = "#FFFFFF",
        BG_INPUT     = "#F1F5F9",
        BG_HOVER     = "#E2E8F0",
        FG_PRIMARY   = "#1E293B",
        FG_SECONDARY = "#475569",
        FG_MUTED     = "#94A3B8",
        BORDER       = "#F1F5F9",
        ACCENT       = "#1e66f5",
        SUCCESS      = "#40a02b",
        DANGER       = "#d20f39",
        WARNING      = "#df8e1d",
        # rgba helpers (selection, danger button)
        SELECTION_BG  = "rgba(30, 102, 245, 0.12)",
        DANGER_BG     = "rgba(210, 15, 57, 0.08)",
        DANGER_BG_HOV = "rgba(210, 15, 57, 0.14)",
    ),
    "dark": dict(
        # Base neutrals (Catppuccin Mocha)
        CRUST    = "#11111B",
        MANTLE   = "#181825",      # 卡片/次要背景
        BASE     = "#1E1E2E",      # 主背景
        SURFACE0 = "#313244",      # 输入框背景
        SURFACE1 = "#45475A",      # hover / 边框
        SURFACE2 = "#585B70",      # 更深灰
        OVERLAY0 = "#6C7086",      # muted text
        TEXT     = "#CDD6F4",      # 主文字
        SUBTEXT0 = "#A6ADC8",      # 次要文字
        SUBTEXT1 = "#BAC2DE",      # 二级文字
        # Accent (保持 Latte 亮色 — 图表/语义色在暗色下更醒目)
        RED      = "#d20f39",
        PEACH    = "#fe640b",
        YELLOW   = "#df8e1d",
        GREEN    = "#40a02b",
        GREEN_DARK = "#358524",
        BLUE     = "#1e66f5",
        LAVENDER = "#7287fd",
        MAUVE    = "#8839ef",
        PINK     = "#ea76cb",
        TEAL     = "#179299",
        SKY      = "#04a5e5",
        # Semantic aliases
        BG_BASE      = "#1E1E2E",      # 主背景 → BASE 同值
        BG_DARK      = "#1E1E2E",
        BG_CARD      = "#181825",
        BG_INPUT     = "#313244",
        BG_HOVER     = "#45475A",
        FG_PRIMARY   = "#CDD6F4",
        FG_SECONDARY = "#BAC2DE",
        FG_MUTED     = "#6C7086",
        BORDER       = "#313244",
        ACCENT       = "#1e66f5",
        SUCCESS      = "#40a02b",
        DANGER       = "#d20f39",
        WARNING      = "#df8e1d",
        # rgba helpers — 暗色下增大 alpha
        SELECTION_BG  = "rgba(30, 102, 245, 0.25)",
        DANGER_BG     = "rgba(210, 15, 57, 0.18)",
        DANGER_BG_HOV = "rgba(210, 15, 57, 0.28)",
    ),
}

# ═══════════════════════════════════════════════════════════════════
#  初始化：将 light 色板写入模块全局变量
# ═══════════════════════════════════════════════════════════════════

_current_theme: str = "light"

# 将 light 色板的所有 key 注入为模块级常量
globals().update(_PALETTES["light"])


# ═══════════════════════════════════════════════════════════════════
#  主题切换 Signal Host
# ═══════════════════════════════════════════════════════════════════

class _SignalHost(QObject):
    """模块级 Signal 发射器 — theme.py 不是 QObject，需要代理。"""
    theme_changed = Signal(str)   # 参数: "light" | "dark"

theme_host = _SignalHost()


# ═══════════════════════════════════════════════════════════════════
#  QSS 构建块
# ═══════════════════════════════════════════════════════════════════

def _build_qss() -> str:
    """根据当前模块全局常量生成完整 QSS（每次调用都重新求值）。"""
    return f"""
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
    border-radius: 12px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: bold;
    color: {FG_PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

/* ── 输入控件 ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
QDateEdit, QTimeEdit, QDateTimeEdit {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 2px 4px;
    min-height: 24px;
}}
/* ── SpinBox 子控件：双杠(+) / 单杠(-) ── */
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid {BORDER};
    background-color: transparent;
    border-top-right-radius: 7px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: {BG_HOVER};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 8px;
    height: 2px;
    /* + 号：两条横杠 */
    border-top: 2px solid {FG_PRIMARY};
    border-bottom: 2px solid {FG_PRIMARY};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid {BORDER};
    background-color: transparent;
    border-bottom-right-radius: 7px;
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {BG_HOVER};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 8px;
    height: 2px;
    /* - 号：一条横杠 */
    border-top: 2px solid {FG_PRIMARY};
}}

/* DateEdit/TimeEdit/DateTimeEdit — 不覆盖子控件，由 Fusion 默认绘制 */

/* ComboBox 下拉箭头 — 不覆盖，由 Fusion 默认绘制 */

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
    border-radius: 8px;
    padding: 5px 8px;
    font-family: {FONT_FAMILY};
}}

/* ── 按钮 ── */
QPushButton {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
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
    background-color: {GREEN};
    color: {MANTLE};
    border-color: {GREEN_DARK};
    padding: 2px 12px;
}}
QPushButton[class="primary"]:hover {{
    background-color: {GREEN_DARK};
}}

/* ── 危险按钮 ── */
QPushButton[class="danger"] {{
    background-color: {DANGER_BG};
    color: {RED};
    border-color: {RED};
}}
QPushButton[class="danger"]:hover {{
    background-color: {DANGER_BG_HOV};
}}

/* ── 操作按钮 ── */
QPushButton[class="action"],
QToolButton[class="action"] {{
    background-color: {BG_INPUT};
    color: {ACCENT};
    border: 1px solid {ACCENT};
    border-radius: 6px;
    padding: 2px 12px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton[class="action"]:hover,
QToolButton[class="action"]:hover {{
    background-color: {BG_HOVER};
}}
QToolButton[class="action"]::menu-indicator {{
    image: none;
    width: 0;
}}

/* ── Tab 切换按钮 ── */
QToolButton[class="tab-active"] {{
    background-color: {ACCENT}; color: {MANTLE};
    border-radius: 6px; padding: 4px 14px; font-weight: bold;
    border: none;
}}
QToolButton[class="tab-inactive"] {{
    background-color: transparent; color: {FG_SECONDARY};
    border-radius: 6px; padding: 4px 14px; border: none;
}}
QToolButton[class="tab-inactive"]:hover {{
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
    background-color: {BG_CARD};
    alternate-background-color: {BG_DARK};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    selection-background-color: {SELECTION_BG};
    selection-color: {FG_PRIMARY};
}}
QHeaderView::section {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: none;
    border-bottom: 2px solid {SURFACE1};
    padding: 8px 12px;
    font-weight: bold;
    font-size: 13px;
}}

/* ── Tab ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG_DARK};
    padding-top: 4px;
    border-radius: 8px;
}}
QTabBar::tab {{
    background-color: {BG_INPUT};
    color: {FG_SECONDARY};
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG_CARD};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    background-color: {SURFACE1};
    color: {FG_PRIMARY};
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
    spacing: 8px;
}}

/* ── 单选按钮 ── */
QRadioButton {{
    color: {FG_PRIMARY};
    background: transparent;
    spacing: 8px;
}}

/* ── 状态栏 ── */
QStatusBar {{
    background-color: {BG_CARD};
    color: {FG_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 12px;
    padding: 2px 12px;
}}

/* ── 工具栏 ── */
QToolBar {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    spacing: 8px;
    padding: 4px 12px;
}}
QToolBar QToolButton {{
    background-color: transparent;
    color: {FG_PRIMARY};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
}}
QToolBar QToolButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER};
}}
QToolBar QToolButton:pressed {{
    background-color: {SURFACE1};
}}
QToolBar QToolButton:disabled {{
    color: {FG_MUTED};
}}
QToolBar::separator {{
    width: 1px;
    background-color: {BORDER};
    margin: 4px 4px;
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

/* ════════════════════════════════════════════════════════
   业务类选择器 — 替代内联 setStyleSheet(color: ...)
   所有控件通过 setProperty("class", "...") 引用
   ════════════════════════════════════════════════════════ */

/* ── 筛选栏 ── */
QLabel[class="filter-label"] {{
    color: {FG_PRIMARY}; font-size: 12px; font-weight: bold;
}}
QWidget[class="filter-bar"] {{
    background-color: {BG_CARD}; padding: 6px 20px; border-radius: 8px;
}}
QLabel[class="filter-group-label"] {{
    color: {FG_SECONDARY}; font-size: 12px; font-weight: bold; padding-right: 4px;
}}
QComboBox[class="filter-combo"] {{
    background-color: {BG_INPUT}; color: {FG_PRIMARY};
    border: 1px solid {BORDER}; border-radius: 6px;
    padding: 4px 8px; font-size: 12px; min-height: 26px;
}}

/* ── 面板标题（视图/卡片 header）── */
QLabel[class="panel-header"] {{
    color: {FG_PRIMARY}; font-size: 13px; font-weight: bold;
}}

/* ── 正文加粗 ── */
QLabel[class="text-bold"] {{
    color: {FG_PRIMARY}; font-size: 13px; font-weight: bold;
}}

/* ── 次要文字 ── */
QLabel[class="subtext"] {{
    color: {FG_SECONDARY}; font-size: 12px; font-weight: 500;
}}

/* ── 小号提示文字 ── */
QLabel[class="hint-label"] {{
    color: {FG_SECONDARY}; font-size: 11px; border: none; background: transparent;
}}

/* ── 统计数值 ── */
QLabel[class="stat-value"] {{
    color: {FG_PRIMARY}; font-size: 16px; font-weight: bold; border: none;
}}

/* ── 强调色文字 ── */
QLabel[class="accent-label"] {{
    color: {ACCENT}; font-size: 12px; font-weight: bold;
}}

/* ── 计数标签 ── */
QLabel[class="count-label"] {{
    color: {FG_SECONDARY};
}}

/* ── 筛选标签块（chip）── */
QLabel[class="filter-chip"] {{
    color: {FG_SECONDARY}; font-size: 12px; font-weight: 500;
    background-color: {BG_HOVER}; border: 1px solid {BORDER}; border-radius: 4px; padding: 2px 6px;
}}

/* ── 空状态提示文字（最淡）── */
QLabel[class="empty-label"] {{
    color: {OVERLAY0}; font-size: 14px;
}}

/* ── 蓝色强调文字 ── */
QLabel[class="highlight-blue"] {{
    color: {ACCENT}; font-weight: bold;
}}

/* ── 背景容器 ── */
QWidget[class="bg-base"] {{
    background-color: {BG_BASE};
}}
QScrollArea[class="scroll-base"] {{
    background-color: {BG_BASE}; border: none;
}}
QWidget[class="container-base"] {{
    background-color: {BG_BASE};
}}

/* ── 统计卡片容器 ── */
QFrame[class="stat-card"], QWidget[class="stat-card"] {{
    background-color: {MANTLE}; border: 1px solid {SURFACE1}; border-radius: 6px; padding: 8px;
}}

/* ── 卡片背景(圆角16px) / (圆角10px) — 替代 card_qss() ── */
QFrame[class="card-bg"], QWidget[class="card-bg"] {{
    background-color: {MANTLE}; border: 1px solid {SURFACE1};
    border-radius: 16px;
}}
QWidget[class="card-bg-sm"] {{
    background-color: {MANTLE}; border: 1px solid {SURFACE1};
    border-radius: 10px;
}}

/* ── 统计数值(大号) ── */
QLabel[class="stat-value-lg"] {{
    color: {FG_PRIMARY}; font-size: 18px; font-weight: bold;
}}

/* ── 附件列表 ── */
QListWidget[class="attachment-list"] {{
    border-radius: 6px; min-height: 280px; font-size: 13px;
}}
QListWidget[class="attachment-list"]::item {{
    padding: 8px 10px; border-bottom: 1px solid {SURFACE0};
}}

/* ── 结果指示器（色块） ── */
QLabel[class="result-indicator"] {{
    border-radius: 6px; min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;
}}

/* ── 警告注释 ── */
QLabel[class="warning-note"] {{
    color: {YELLOW}; font-size: 12px; padding: 4px 8px;
}}

/* ── 摘要栏 ── */
QLabel[class="summary-bar"] {{
    color: {SUBTEXT1}; font-size: 11px; padding: 2px 8px;
    background: {SURFACE0}; border-radius: 4px;
}}

/* ── 分隔线 ── */
QLabel[class="separator"] {{
    background-color: {BORDER}; border: none;
}}

/* ── 标签页卡片容器 ── */
QWidget[class="card-container"] {{
    background-color: {BG_CARD}; border-radius: 8px;
}}
QWidget[class="card-container"]:hover {{
    background-color: {BG_HOVER};
}}

/* ── 步骤标签 ── */
QLabel[class="step-label"] {{
    color: {BLUE}; font-weight: bold; font-size: 12px;
}}

/* ── 警告文字 ── */
QLabel[class="warning-text"] {{
    color: {PEACH}; font-size: 12px;
}}

/* ── 危险强调标题（红色加粗） ── */
QLabel[class="danger-title"] {{
    color: {RED}; font-size: 13px; font-weight: bold;
}}

/* ── 原因文字 ── */
QLabel[class="cause-text"] {{
    color: {MAUVE}; font-size: 12px;
}}

/* ── 原因文字(小号) ── */
QLabel[class="cause-text-sm"] {{
    color: {MAUVE}; font-size: 11px;
}}

/* ── 成功文字 ── */
QLabel[class="success-text"] {{
    color: {GREEN}; font-size: 11px;
}}

/* ── 斜体提示 ── */
QLabel[class="hint-italic"] {{
    color: {SUBTEXT0}; font-size: 11px; font-style: italic;
}}

/* ── 追踪文字 ── */
QLabel[class="track-text"] {{
    color: {LAVENDER}; font-size: 11px;
}}

/* ── 正文(12px) ── */
QLabel[class="body-text"] {{
    color: {TEXT}; font-size: 12px;
}}

/* ── 看板列 ── */
QFrame[class="kanban-column"] {{
    background-color: {SURFACE0}; border-radius: 10px; border: none;
}}
QFrame[class="kanban-column"]:hover {{
    background-color: {SURFACE1};
}}

/* ── 看板列标题 ── */
QFrame[class="column-header"] {{
    background: transparent; border: none; border-top-left-radius: 10px; border-top-right-radius: 10px;
}}
/* ── 看板列标题文字 ── */
QLabel[class="column-header-label"] {{
    color: {TEXT}; border: none;
}}
/* ── 看板计数标签 ── */
QLabel[class="column-count"] {{
    color: {FG_SECONDARY}; font-size: 11px; font-weight: 600;
    background: {SURFACE1}; border-radius: 8px; padding: 1px 8px; border: none;
}}
/* ── 折叠按钮 ── */
QPushButton[class="fold-btn"] {{
    background: transparent; border: none; border-radius: 4px;
    color: {FG_SECONDARY}; font-size: 13px;
}}
QPushButton[class="fold-btn"]:hover {{
    background: {BG_HOVER}; color: {TEXT};
}}
/* ── 折叠信息栏 ── */
QLabel[class="fold-info"] {{
    color: {FG_SECONDARY}; background: transparent; border: none;
    font-size: 12px;
}}
QLabel[class="fold-info"]:hover {{
    color: {TEXT};
}}
/* ── 滚动区域 ── */
QScrollArea[class="column-scroll"] {{
    background: transparent; border: none;
}}
/* ── 看板外层滚动（旧名兼容） ── */
QScrollArea[class="kanban-scroll"] {{
    background: transparent; border: none;
}}
/* ── 看板列容器（4 列水平布局） ── */
QWidget[class="columns-container"] {{
    background: transparent; border: none;
}}
/* ── 看板列标题（旧名兼容：todo_view） ── */
QLabel[class="kanban-col-header"] {{
    color: {TEXT}; border: none;
}}
/* ── 看板计数标签（旧名兼容：todo_view, quadrant_view） ── */
QLabel[class="kanban-count"] {{
    color: {FG_SECONDARY}; font-size: 11px; font-weight: 600;
    background: {SURFACE1}; border-radius: 8px; padding: 1px 8px; border: none;
}}
/* ── 搜索输入框 ── */
QLineEdit[class="search-input"] {{
    background: {BG_INPUT}; border: 1px solid {SURFACE1}; border-radius: 6px;
    padding: 2px 8px; color: {TEXT};
}}
/* ── 筛选面板 ── */
QFrame[class="filter-panel"] {{
    background: {SURFACE0}; border-radius: 8px; border: none;
}}
/* ── 筛选复选框组 ── */
QWidget[class="filter-checkbox"] {{
    background: transparent; border: none;
}}
/* ── Issue 详情 Tab ── */
QTabWidget[class="detail-tabs"] {{
    background: transparent; border: none;
}}
/* ── 卡片元信息 ── */
QLabel[class="card-meta"] {{
    color: {FG_SECONDARY}; font-size: 11px; border: none;
}}
/* ── 看板卡片标题 ── */
QLabel[class="card-title"] {{
    color: {TEXT}; border: none;
}}
/* ── 垂直线分隔符 ── */
QFrame[class="sep-vline"] {{
    color: {SURFACE1}; max-width: 1px; min-width: 1px; min-height: 16px; border: none;
}}

/* ── 四象限单元格 ── */
QFrame[class="quadrant-cell-q1"]  {{ background: rgba(210,15,57,0.12); border-radius: 8px; }}
QFrame[class="quadrant-cell-q2"]  {{ background: rgba(30,102,245,0.12); border-radius: 8px; }}
QFrame[class="quadrant-cell-q3"]  {{ background: rgba(254,100,11,0.12); border-radius: 8px; }}
QFrame[class="quadrant-cell-q4"]  {{ background: {SURFACE0}; border-radius: 8px; }}
QFrame[class="quadrant-cell-unset"] {{ background: {BG_INPUT}; border-radius: 8px; border: 1px dashed {BORDER}; }}

/* ── 四象限标题 ── */
QLabel[class="quadrant-title"] {{
    color: {TEXT}; font-size: 13px; font-weight: 700; border: none;
}}

/* ── Issue 面板滚动区 ── */
QScrollArea[class="issue-scroll"] {{
    background-color: {BASE}; border: 1px solid {SURFACE1};
    border-radius: 8px;
}}

/* ── Issue 卡片 ── */
QFrame[class="issue-card"] {{
    background-color: {SURFACE0}; border-radius: 8px;
    border: 1px solid {SURFACE1};
}}

/* ── 参考信息块 ── */
QLabel[class="ref-info"] {{
    color: {SUBTEXT0}; font-size: 11px; padding: 4px 6px;
    background: {SURFACE0}; border-radius: 4px;
}}

/* ── 小节标题 ── */
QLabel[class="section-label"] {{
    color: {TEXT}; font-size: 12px; font-weight: bold;
}}

/* ── 分类标签 ── */
QLabel[class="cat-label"] {{
    color: {TEXT}; font-size: 12px;
}}

/* ── 模式标签 ── */
QLabel[class="mode-label"] {{
    color: {SUBTEXT0}; font-size: 12px;
}}

/* ── 输入框文字 ── */
QLineEdit[class="field-text"] {{
    color: {TEXT}; font-size: 12px;
}}
QLineEdit[class="field-text-sm"] {{
    color: {TEXT}; font-size: 11px;
}}
/* ── 详情文字 ── */
QLabel[class="detail-text"] {{
    color: {SUBTEXT0}; font-size: 12px; padding: 4px 0;
}}
/* ── 行背景 ── */
QWidget[class="row-surface"] {{
    background-color: {SURFACE0}; border-radius: 4px;
}}

/* ── 通过率颜色(动态 rate-class 属性) ── */
QLabel[rate-class="good"] {{
    color: {GREEN}; font-size: 11px; display: block; font-weight: bold;
}}
QLabel[rate-class="warn"]  {{
    color: {YELLOW}; font-size: 11px; display: block; font-weight: bold;
}}
QLabel[rate-class="bad"]   {{
    color: {RED}; font-size: 11px; display: block; font-weight: bold;
}}

/* ── 结果行状态(动态 row-state 属性) ── */
QFrame[row-state="normal"]   {{
    background-color: {SURFACE0}; border: 1px solid {SURFACE1}; border-radius: 6px; padding: 4px;
}}
QFrame[row-state="attention"] {{
    background-color: {SELECTION_BG}; border: 1px solid {BLUE}; border-radius: 6px; padding: 4px;
}}
QFrame[row-state="deleted"]   {{
    background-color: {SURFACE2}; border: 1px solid {RED}; border-radius: 6px; padding: 4px;
}}

/* ── 全部通过按钮 ── */
QPushButton[class="btn-pass-all"] {{
    color: {MANTLE}; background-color: {GREEN};
    border: none; border-radius: 4px; padding: 2px 8px;
}}

/* ── 导入结果标签 ── */
QLabel[class="import-result-ok"] {{
    color: {SUBTEXT0}; font-size: 12px; padding: 8px;
    background-color: {SURFACE0}; border-radius: 6px;
}}
QLabel[class="import-result-warn"] {{
    color: {YELLOW}; font-size: 12px; padding: 8px;
    background-color: {SURFACE0}; border-radius: 6px;
}}

/* ── 必填标签 ── */
QLabel[class="req-field"] {{
    color: {PEACH}; font-size: 13px;
}}
"""


# ═══════════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════════

# 预编译缓存
_COMPILED_STYLESHEET: str | None = None


def get_stylesheet() -> str:
    """获取完整的应用 QSS 样式表。

    Returns:
        当前主题（Latte / Mocha）的完整 QSS 字符串。
    """
    global _COMPILED_STYLESHEET
    if _COMPILED_STYLESHEET is None:
        _COMPILED_STYLESHEET = _build_qss()
    return _COMPILED_STYLESHEET


def set_theme(name: str) -> None:
    """切换主题（light / dark）。

    1. 用 globals().update() 重绑定所有颜色常量
    2. 清空 QSS 缓存
    3. 发射 theme_changed 信号
    """
    global _current_theme, _COMPILED_STYLESHEET
    if name not in _PALETTES:
        raise ValueError(f"Unknown theme: {name!r}, expected 'light' or 'dark'")
    if name == _current_theme:
        return

    _current_theme = name
    globals().update(_PALETTES[name])
    _COMPILED_STYLESHEET = None
    theme_host.theme_changed.emit(name)


def current_theme() -> str:
    """返回当前主题名称。"""
    return _current_theme

def apply_palette() -> None:
    """同步 QPalette 到当前主题色板。

    QSS 只覆盖匹配选择器的控件；QPalette 是 fallback 机制，
    控制 QSS 未覆盖的子控件（QCalendarWidget、QComboBox popup、
    QScrollArea viewport 等原生弹出窗口的背景和文字色）。
    必须在 set_theme() 之后、setStyleSheet() 之前调用。
    """
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return

    pal = QPalette()
    # 背景色（Window / Base / AlternateBase / Button）
    pal.setColor(QPalette.ColorRole.Window, QColor(BG_DARK))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(FG_PRIMARY))
    pal.setColor(QPalette.ColorRole.Base, QColor(BG_INPUT))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_CARD))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE2))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(FG_PRIMARY))
    pal.setColor(QPalette.ColorRole.Text, QColor(FG_PRIMARY))
    pal.setColor(QPalette.ColorRole.Button, QColor(BG_INPUT))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(FG_PRIMARY))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(RED))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(FG_MUTED))
    # 高亮
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(MANTLE))

    app.setPalette(pal)


def get_palette() -> dict[str, str]:
    """返回当前色板（只读副本）。"""
    return dict(_PALETTES[_current_theme])


