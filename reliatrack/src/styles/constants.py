"""样式常量 — 颜色、字体、间距、状态映射。

所有 UI 组件共享的常量定义，避免硬编码分散在各处。
颜色统一使用 Catppuccin Latte 色板（与 theme.py 一致）。
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════
#  布局常量
# ═══════════════════════════════════════════════════════════════════

ROW_HEIGHT: int = 32
DAY_WIDTH: int = 40
HEADER_HEIGHT: int = 36
PADDING_SMALL: int = 4
PADDING_MEDIUM: int = 8
PADDING_LARGE: int = 12
VIEW_MARGINS: tuple[int, int, int, int] = (16, 10, 16, 10)
SPACING_SMALL: int = 4
SPACING_MEDIUM: int = 8
SPACING_LARGE: int = 12

# ═══════════════════════════════════════════════════════════════════
#  字体
# ═══════════════════════════════════════════════════════════════════

FONT_FAMILY: str = "Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif"
FONT_SIZE_SMALL: int = 12
FONT_SIZE_NORMAL: int = 14
FONT_SIZE_LARGE: int = 17
FONT_SIZE_TITLE: int = 22

# ═══════════════════════════════════════════════════════════════════
#  Catppuccin Latte 色板（与 theme.py 一致）
#  用于前景着色/状态标识，需在亮色背景上可读
# ═══════════════════════════════════════════════════════════════════

STATUS_GREEN   = "#40a02b"  # 成功/完成/正常
STATUS_BLUE    = "#1e66f5"  # 进行中/处理中
STATUS_RED     = "#d20f39"  # 失败/严重/阻塞
STATUS_YELLOW  = "#df8e1d"  # 警告/暂停/已验证
STATUS_PEACH   = "#fe640b"  # 次要/出库中
STATUS_MAUVE   = "#8839ef"  # 测试中
STATUS_TEAL    = "#179299"  # 环境/特殊
STATUS_OVERLAY = "#9ca0b0"  # 停用/草稿/关闭/外观
STATUS_SURFACE = "#acb0be"  # 跳过/离线/最低

# ═══════════════════════════════════════════════════════════════════
#  状态 → 颜色映射
# ═══════════════════════════════════════════════════════════════════

# 项目状态
PROJECT_STATUS_COLORS: dict[str, str] = {
    "active": STATUS_GREEN,
    "paused": STATUS_YELLOW,
    "closed": STATUS_OVERLAY,
}

# 样品状态
SAMPLE_STATUS_COLORS: dict[str, str] = {
    "in_stock": STATUS_BLUE,
    "checked_out": STATUS_PEACH,
    "in_test": STATUS_MAUVE,
    "suspended": STATUS_YELLOW,
    "scrapped": STATUS_RED,
    "returned": STATUS_GREEN,
}

# 测试计划状态
TEST_PLAN_STATUS_COLORS: dict[str, str] = {
    "draft": STATUS_OVERLAY,
    "in_progress": STATUS_BLUE,
    "completed": STATUS_GREEN,
    "paused": STATUS_YELLOW,
}

# 测试任务状态
TASK_STATUS_COLORS: dict[str, str] = {
    "pending": STATUS_OVERLAY,
    "in_progress": STATUS_BLUE,
    "completed": STATUS_GREEN,
    "skipped": STATUS_SURFACE,
}

# 测试结果
RESULT_STATUS_COLORS: dict[str, str] = {
    "pass": STATUS_GREEN,
    "fail": STATUS_RED,
    "conditional": STATUS_YELLOW,
    "pending": STATUS_OVERLAY,
    "skip": STATUS_SURFACE,
}

# Issue 状态
ISSUE_STATUS_COLORS: dict[str, str] = {
    "open": STATUS_RED,
    "analyzing": STATUS_BLUE,
    "verified": STATUS_YELLOW,
    "closed": STATUS_GREEN,
}

# Issue 严重度
ISSUE_SEVERITY_COLORS: dict[str, str] = {
    "critical": STATUS_RED,
    "major": STATUS_PEACH,
    "minor": STATUS_YELLOW,
    "cosmetic": STATUS_OVERLAY,
}

# 设备状态
EQUIPMENT_STATUS_COLORS: dict[str, str] = {
    "available": STATUS_GREEN,
    "maintenance": STATUS_YELLOW,
    "offline": STATUS_SURFACE,
}

# 优先级
PRIORITY_COLORS: dict[int, str] = {
    1: STATUS_RED,       # 最高
    2: STATUS_PEACH,
    3: STATUS_YELLOW,    # 默认
    4: STATUS_OVERLAY,
    5: STATUS_SURFACE,   # 最低
}

# ═══════════════════════════════════════════════════════════════════
#  QSS 片段
# ═══════════════════════════════════════════════════════════════════

# QTableWidget 统一样式片段（使用 BG_DARK 背景与全局主题一致）
# 占位符: {bg}, {text}, {gridline}, {alt_row}, {header_bg}, {header_text}, {font_size}
TABLE_QSS: str = (
    "QTableWidget {{"
    "background-color: {bg}; color: {text};"
    "gridline-color: {gridline}; border: 1px solid {gridline};"
    "border-radius: 8px; font-size: {font_size}px;"
    "}}"
    "QTableWidget::item {{ padding: 6px; }}"
    "QTableWidget::item:alternate {{ background-color: {alt_row}; }}"
    "QHeaderView::section {{"
    "background-color: {header_bg}; color: {header_text};"
    "padding: 8px; border: none;"
    "font-weight: bold; font-size: {font_size}px;"
    "}}"
)

# 知识库类别颜色
KNOWLEDGE_CATEGORY_COLORS: dict[str, str] = {
    "元器件": STATUS_BLUE,
    "结构": STATUS_GREEN,
    "软件": STATUS_MAUVE,
    "工艺": STATUS_PEACH,
    "材料": STATUS_YELLOW,
    "环境": STATUS_TEAL,
    "其他": STATUS_OVERLAY,
}

# 样品操作类型颜色
SAMPLE_TYPE_COLORS: dict[str, str] = {
    "check_in": STATUS_GREEN,
    "check_out": STATUS_BLUE,
    "return": STATUS_GREEN,
    "transfer": STATUS_YELLOW,
}

# Dashboard 图表配色（Latte 亮色调色板）
CHART_COLORS: list[str] = [
    STATUS_BLUE,    # 蓝
    STATUS_GREEN,   # 绿
    STATUS_RED,     # 红
    STATUS_YELLOW,  # 黄
    STATUS_MAUVE,   # 紫
    STATUS_PEACH,   # 橙
    STATUS_TEAL,    # 青
]
