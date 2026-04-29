"""样式常量 — 颜色、字体、间距、状态映射。

所有 UI 组件共享的常量定义，避免硬编码分散在各处。
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
PADDING_LARGE: int = 16
VIEW_MARGINS: tuple[int, int, int, int] = (16, 10, 16, 10)
SPACING_SMALL: int = 4
SPACING_MEDIUM: int = 8
SPACING_LARGE: int = 16

# ═══════════════════════════════════════════════════════════════════
#  字体
# ═══════════════════════════════════════════════════════════════════

FONT_FAMILY: str = "Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif"
FONT_SIZE_SMALL: int = 12
FONT_SIZE_NORMAL: int = 14
FONT_SIZE_LARGE: int = 17
FONT_SIZE_TITLE: int = 22

# ═══════════════════════════════════════════════════════════════════
#  状态 → 颜色映射
# ═══════════════════════════════════════════════════════════════════

# 项目状态
PROJECT_STATUS_COLORS: dict[str, str] = {
    "active": "#a6e3a1",   # Green
    "paused": "#f9e2af",   # Yellow
    "closed": "#6c7086",   # Overlay0
}

# 样品状态
SAMPLE_STATUS_COLORS: dict[str, str] = {
    "in_stock": "#89b4fa",     # Blue
    "checked_out": "#fab387",  # Peach
    "in_test": "#cba6f7",      # Mauve
    "suspended": "#f9e2af",    # Yellow
    "scrapped": "#f38ba8",     # Red
    "returned": "#a6e3a1",     # Green
}

# 测试计划状态
TEST_PLAN_STATUS_COLORS: dict[str, str] = {
    "draft": "#6c7086",        # Overlay0
    "in_progress": "#89b4fa",  # Blue
    "completed": "#a6e3a1",    # Green
    "paused": "#f9e2af",       # Yellow
}

# 测试任务状态
TASK_STATUS_COLORS: dict[str, str] = {
    "pending": "#6c7086",        # Overlay0
    "in_progress": "#89b4fa",    # Blue
    "completed": "#a6e3a1",      # Green
    "skipped": "#585b70",        # Surface2
}

# 测试结果
RESULT_STATUS_COLORS: dict[str, str] = {
    "pass": "#a6e3a1",       # Green
    "fail": "#f38ba8",       # Red
    "conditional": "#f9e2af", # Yellow
    "pending": "#6c7086",    # Overlay0
    "skip": "#585b70",       # Surface2
}

# Issue 状态
ISSUE_STATUS_COLORS: dict[str, str] = {
    "open": "#f38ba8",      # Red
    "analyzing": "#89b4fa", # Blue
    "verified": "#f9e2af",  # Yellow
    "closed": "#a6e3a1",    # Green
}

# Issue 严重度
ISSUE_SEVERITY_COLORS: dict[str, str] = {
    "critical": "#f38ba8",  # Red
    "major": "#fab387",     # Peach
    "minor": "#f9e2af",     # Yellow
    "cosmetic": "#6c7086",  # Overlay0
}

# 设备状态
EQUIPMENT_STATUS_COLORS: dict[str, str] = {
    "available": "#a6e3a1",    # Green
    "maintenance": "#f9e2af",  # Yellow
    "offline": "#585b70",      # Surface2
}

# 优先级
PRIORITY_COLORS: dict[int, str] = {
    1: "#f38ba8",  # Red - 最高
    2: "#fab387",  # Peach
    3: "#f9e2af",  # Yellow - 默认
    4: "#6c7086",  # Overlay0 - 低
    5: "#585b70",  # Surface2 - 最低
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
    "元器件": "#89b4fa",  # Blue
    "结构": "#a6e3a1",    # Green
    "软件": "#cba6f7",    # Mauve
    "工艺": "#fab387",    # Peach
    "材料": "#f9e2af",    # Yellow
    "环境": "#94e2d5",    # Teal
    "其他": "#6c7086",    # Overlay0
}
