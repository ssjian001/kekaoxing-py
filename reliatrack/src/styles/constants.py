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

import sys as _sys

if _sys.platform == "linux":
    FONT_FAMILY: str = "Noto Sans CJK SC, WenQuanYi Micro Hei, Microsoft YaHei, sans-serif"
elif _sys.platform == "darwin":
    FONT_FAMILY: str = "PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif"
else:
    FONT_FAMILY: str = "Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif"

del _sys
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

# 暗色替身 — Latte 原值在深底上对比度不足 (WCAG AA 文字≥4.5), 切暗色时由
# theme.set_theme() 调 resolve_status_color() 替换; 亮色值保持原样
_DARK_ALIASES: dict[str, str] = {
    "#d20f39": "#ea5a52",  # RED    3.0→4.75
    "#179299": "#23b5bd",  # TEAL   4.4→6.6
}


def resolve_status_color(hex_color: str, theme_name: str) -> str:
    """按主题解析语义色。亮色返回原值, 暗色返回提亮替身(如有)。"""
    if theme_name == "dark":
        return _DARK_ALIASES.get(hex_color.lower(), hex_color)
    # 亮色: 把替身映射回原值 (主题来回切换时幂等)
    for _orig, _dark in _DARK_ALIASES.items():
        if hex_color.lower() == _dark:
            return _orig
    return hex_color


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
    "archived": STATUS_SURFACE,
}

# 测试任务状态
TASK_STATUS_COLORS: dict[str, str] = {
    "pending": STATUS_OVERLAY,
    "in_progress": STATUS_BLUE,
    "completed": STATUS_GREEN,
    "skipped": STATUS_SURFACE,
    "failed": STATUS_RED,
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

# Issue 严重度 — 收敛色系: 红=致命 橙=主要 灰蓝阶=次要/外观 (原 4 色过载, 降为 2 主色+2 中性)
ISSUE_SEVERITY_COLORS: dict[str, str] = {
    "critical": STATUS_RED,
    "major": STATUS_PEACH,
    "minor": STATUS_OVERLAY,
    "cosmetic": STATUS_SURFACE,
}

# Issue 优先级 — 与严重度共用红橙轴, 低优降中性灰 (原 5 色全谱 → 3 色)
PRIORITY_COLORS: dict[int, str] = {
    1: STATUS_RED,       # 最高
    2: STATUS_PEACH,
    3: STATUS_YELLOW,    # 默认
    4: STATUS_OVERLAY,
    5: STATUS_SURFACE,   # 最低
}

ISSUE_RESOLUTION_COLORS: dict[str, str] = {
    "": "",          # 动态填充，见 resolve_issue_resolution_color()
    "fixed": STATUS_GREEN,
    "wont_fix": STATUS_OVERLAY,
    "duplicate": STATUS_OVERLAY,
    "cannot_reproduce": STATUS_YELLOW,
    "not_an_issue": STATUS_OVERLAY,
}

# 设备状态
EQUIPMENT_STATUS_COLORS: dict[str, str] = {
    "available": STATUS_GREEN,
    "maintenance": STATUS_YELLOW,
    "offline": STATUS_SURFACE,
}

# 优先级
# ═══════════════════════════════════════════════════════════════════
#  Issue Aging 阈值
# ═══════════════════════════════════════════════════════════════════

AGING_THRESHOLD_LOW: int = 3   # <3 天 → 绿色
AGING_THRESHOLD_MID: int = 7   # 3-7 天 → 黄色, >7 天 → 红色

# ═══════════════════════════════════════════════════════════════════
#  QSS 片段
# ═══════════════════════════════════════════════════════════════════

# QTableWidget 统一样式片段（使用 BG_DARK 背景与全局主题一致）
# 占位符: {bg}, {text}, {gridline}, {alt_row}, {header_bg}, {header_text},
#         {font_size}, {selection_bg}
TABLE_QSS: str = (
    "QTableWidget {{"
    "background-color: {bg}; color: {text};"
    "gridline-color: {gridline}; border: 1px solid {gridline};"
    "border-radius: 8px; font-size: {font_size}px;"
    "}}"
    "QTableWidget::item {{ padding: 6px; }}"
    "QTableWidget::item:selected,"
    "QTableWidget::item:selected:!focus {{"
    "background-color: {selection_bg}; color: {text};"
    "}}"
    "QTableWidget::item:alternate:!selected {{ background-color: {alt_row}; }}"
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
# 注意: 模块级 list 在 import 时冻结 Latte 值; 暗色下由 theme.set_theme() 调
# resolve_status_color() 就地刷新各元素
CHART_COLORS: list[str] = [
    STATUS_BLUE,    # 蓝
    STATUS_GREEN,   # 绿
    STATUS_RED,     # 红
    STATUS_YELLOW,  # 黄
    STATUS_MAUVE,   # 紫
    STATUS_PEACH,   # 橙
    STATUS_TEAL,    # 青
]

DASH_PRIMARY = STATUS_BLUE       # #1e66f5
DASH_SUCCESS = STATUS_GREEN      # #40a02b
DASH_WARNING = STATUS_YELLOW     # #df8e1d
DASH_DANGER  = STATUS_RED        # 模块级默认; 图表 paint 时经 resolve_status_color() 按主题刷新

# 以下值通过延迟导入从 theme.py 动态读取，确保主题切换后同步
def _dash_colors() -> dict[str, str]:
    """返回当前主题下的 Dashboard 背景色常量。"""
    import src.styles.theme as _t
    return dict(
        DASH_NEUTRAL     = _t.SUBTEXT0,
        DASH_BG          = _t.BASE,
        DASH_CARD_BG     = _t.MANTLE,
        DASH_CARD_BORDER = _t.SURFACE1,
    )

# 模块级属性代理：dashboard_view.py 等 import 后使用 DASH_BG 等名
# 通过模块 __getattr__ 实现延迟求值
import sys as _sys

_THIS = _sys.modules[__name__]
_DASH_KEYS = ("DASH_NEUTRAL", "DASH_BG", "DASH_CARD_BG", "DASH_CARD_BORDER")

def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name in _DASH_KEYS:
        return _dash_colors()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ═══════════════════════════════════════════════════════════════════
#  全局卡片样式工具（提升自 dashboard_view）
# ═══════════════════════════════════════════════════════════════════

def card_qss(radius: int = 12) -> str:
    """返回白底圆角卡片 QSS，供所有 Tab/Dialog 复用。"""
    import src.styles.theme as _t
    return (
        f"background-color: {_t.MANTLE};"
        f"border: 1px solid {_t.SURFACE1};"
        f"border-radius: {radius}px;"
    )


def add_shadow(widget, blur: int = 12, offset: int = 2,
               opacity: int = 25) -> None:
    """给 widget 添加柔和阴影效果。暗色主题下自动调整阴影色。"""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    from PySide6.QtGui import QColor
    import src.styles.theme as _t
    shadow = QGraphicsDropShadowEffect()
    shadow.setOffset(0, offset)
    shadow.setBlurRadius(blur)
    # 暗色主题下用浅色阴影，亮色下用黑色阴影
    if _t.current_theme() == "dark":
        shadow.setColor(QColor(255, 255, 255, min(opacity + 15, 50)))
    else:
        shadow.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(shadow)


# ═══════════════════════════════════════════════════════════════════
#  自适应列宽工具（三档混合策略）
# ═══════════════════════════════════════════════════════════════════
#
# 列规格格式: (表头, 模式, 默认宽度)
#   模式:
#     'content'    — ResizeToContents，短文本/日期/状态自动贴合
#     'stretch'    — Stretch，充满剩余空间（每表仅 1 列）
#     'interactive' — Interactive，用户可拖拽，给默认宽度
#     'fixed'      — Fixed，不可调整（如 ID 列）
#
# 用法:
#   SPECS = [("ID", "fixed", 50), ("名称", "stretch", 0), ...]
#   apply_column_specs(table, SPECS)
#

# ═══════════════════════════════════════════════════════════════════
#  Ctrl+C 复制支持（事件过滤器方案）
# ═══════════════════════════════════════════════════════════════════

def install_copy_handler(table) -> None:
    """为 QTableWidget 安装 Ctrl+C 复制事件过滤器。

    选中单元格后按 Ctrl+C 将内容以 TSV 格式复制到剪贴板，
    可直接粘贴到 Excel / WPS 等电子表格。
    """
    from PySide6.QtCore import QObject, QEvent
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QApplication

    class _CopyFilter(QObject):
        def eventFilter(self, obj, event):
            if (event.type() == QEvent.Type.KeyPress
                    and event.matches(QKeySequence.StandardKey.Copy)):
                self._copy_selection(obj)
                return True
            return super().eventFilter(obj, event)

        @staticmethod
        def _copy_selection(table):
            selected = table.selectedRanges()
            if not selected:
                return
            rows: set[int] = set()
            cols: set[int] = set()
            for r in selected:
                rows.update(range(r.topRow(), r.bottomRow() + 1))
                cols.update(range(r.leftColumn(), r.rightColumn() + 1))
            lines: list[str] = []
            for row in sorted(rows):
                cells: list[str] = []
                for col in sorted(cols):
                    item = table.item(row, col)
                    cells.append(item.text() if item else "")
                lines.append("\t".join(cells))
            QApplication.clipboard().setText("\n".join(lines))

    table.installEventFilter(_CopyFilter(table))


def apply_column_specs(table, specs: list[tuple[str, str, int]],
                       table_key: str = "") -> None:
    """根据列规格自动设置表头模式和宽度。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView

    table.setColumnCount(len(specs))
    table.setHorizontalHeaderLabels([s[0] for s in specs])

    header = table.horizontalHeader()
    header.setMinimumSectionSize(40)  # 空表时防止列塌缩

    for col, (_, mode, width) in enumerate(specs):
        if mode == "fixed":
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, width)
        elif mode == "content":
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            # 设最小宽度防止空表时太窄
            if width > 0:
                header.setMinimumSectionSize(max(header.minimumSectionSize(), width))
        elif mode == "stretch":
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        elif mode == "interactive":
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(col, width)

    # 文字截断时显示省略号
    from PySide6.QtWidgets import QAbstractItemView
    table.setTextElideMode(Qt.TextElideMode.ElideRight)

    # 表头排序箭头显示
    header.setSortIndicatorShown(True)

    # 双击列头自适应宽度（仅 interactive 列有效）
    def _auto_resize(col: int) -> None:
        if col >= 0 and col < len(specs) and specs[col][1] == "interactive":
            table.resizeColumnToContents(col)
            # 留点 padding，防止文字贴边
            cur = table.columnWidth(col)
            table.setColumnWidth(col, cur + 16)
    header.sectionDoubleClicked.connect(_auto_resize)

    # 列宽持久化（仅 interactive 列有意义）
    if table_key:
        from src.styles.column_persistence import (
            restore_column_widths, save_column_widths_debounced,
        )
        restore_column_widths(table, table_key)
        header.sectionResized.connect(
            lambda *_: save_column_widths_debounced(table, table_key)
        )

    # Ctrl+C 复制支持
    install_copy_handler(table)
