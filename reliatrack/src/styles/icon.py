"""SVG 图标系统 — 主题自适应的图标引擎。

替代 emoji 按钮，图标颜色随 Catppuccin 主题自动变化。

用法：
    from src.styles.icon import Icon, RI_ADD
    btn.setIcon(RI_ADD.icon())
    btn.setIconSize(QSize(16, 16))
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

import src.styles.theme as _t


# ═══════════════════════════════════════════════════════════════════
#  SVG 图标定义 — 使用 currentColor 占位符
# ═══════════════════════════════════════════════════════════════════

_SVG_CACHE: dict[str, str] = {}

_ICONS: dict[str, str] = {
    "add":
        '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M12 8v8M8 12h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "edit":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M15.232 5.232l3.536 3.536M9 11l-3 3V8.5L12.5 3 16 6.5 11 11.5 9 11z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 20h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "delete":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2M10 11v6M14 11v6M5 6l1 14a2 2 0 002 2h8a2 2 0 002-2l1-14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "search":
        '<svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="M16.5 16.5L21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "check":
        '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M8 12l3 3 5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "close":
        '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M9 9l6 6M15 9l-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "filter":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M4 4h16L14 12v7l-4-3v-4L4 4z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "export":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4M8 8l4-4 4 4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "import":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M12 4v12M8 12l4 4 4-4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "folder":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M4 5a1 1 0 011-1h5l2 2h7a1 1 0 011 1v11a1 1 0 01-1 1H5a1 1 0 01-1-1V5z" stroke="currentColor" stroke-width="2"/></svg>',
    "calendar":
        '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M8 2v4M16 2v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "settings":
        '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "refresh":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M1 4v6h6M23 20v-6h-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "backup":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" stroke="currentColor" stroke-width="2"/><path d="M17 21v-4H7v4M7 3v2h10V3" stroke="currentColor" stroke-width="2"/><path d="M9 15h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "dashboard":
        '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="8" height="8" rx="1" stroke="currentColor" stroke-width="2"/><rect x="13" y="3" width="8" height="4" rx="1" stroke="currentColor" stroke-width="2"/><rect x="13" y="9" width="8" height="12" rx="1" stroke="currentColor" stroke-width="2"/><rect x="3" y="13" width="8" height="8" rx="1" stroke="currentColor" stroke-width="2"/></svg>',
    "pin":
        '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2v10l-4 3v3h8v-3l-4-3V2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "more":
        '<svg viewBox="0 0 24 24" fill="none"><circle cx="5" cy="12" r="1.5" stroke="currentColor" stroke-width="2" fill="currentColor"/><circle cx="12" cy="12" r="1.5" stroke="currentColor" stroke-width="2" fill="currentColor"/><circle cx="19" cy="12" r="1.5" stroke="currentColor" stroke-width="2" fill="currentColor"/></svg>',
}


# ═══════════════════════════════════════════════════════════════════
#  主题色 SVG 着色
# ═══════════════════════════════════════════════════════════════════


def _color_svg(svg: str, color: QColor | str) -> str:
    """将 SVG 中的 currentColor 替换为指定颜色。"""
    if isinstance(color, QColor):
        color = color.name()
    return svg.replace("currentColor", color)


# ═══════════════════════════════════════════════════════════════════
#  图标引擎
# ═══════════════════════════════════════════════════════════════════


class ThemeIconEngine(QIconEngine):
    """主题自适应 SVG 图标引擎。

    使用当前主题的 FG_PRIMARY 颜色渲染图标（取代 emoji）。
    disabled 模式下透明度降至 50%，selected 模式降至 70%。
    """

    def __init__(self, svg: str):
        super().__init__()
        self._svg = svg

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode,
              state: QIcon.State) -> None:
        painter.save()

        # 禁用/选中 透明度
        if mode == QIcon.Mode.Disabled:
            painter.setOpacity(0.5)
        elif mode == QIcon.Mode.Selected:
            painter.setOpacity(0.7)

        # 用当前主题色渲染
        color = _t.FG_PRIMARY
        colored_svg = _color_svg(self._svg, color)

        renderer = QSvgRenderer(bytes(colored_svg, "utf-8"))
        renderer.render(painter, QRectF(rect))

        painter.restore()

    def pixmap(self, size, mode, state) -> QPixmap:
        pix = QPixmap(size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        self.paint(p, QRect(0, 0, size.width(), size.height()), mode, state)
        p.end()
        return pix

    def clone(self) -> ThemeIconEngine:
        return ThemeIconEngine(self._svg)


# ═══════════════════════════════════════════════════════════════════
#  图标定义（可枚举）
# ═══════════════════════════════════════════════════════════════════


class Icon:
    """声明式图标定义。

    Usage:
        RI_ADD = Icon("add")
        btn.setIcon(RI_ADD.icon())

    icon() 返回 QIcon，颜色跟随主题自动切换。
    """

    def __init__(self, name: str):
        if name not in _ICONS:
            raise KeyError(f"Unknown icon: {name!r}, available: {list(_ICONS.keys())}")
        self._name = name

    def svg(self) -> str:
        return _ICONS[self._name]

    def icon(self, size: int = 16) -> QIcon:
        """返回主题自适应的 QIcon。"""
        return QIcon(ThemeIconEngine(self._svg()))

    def _svg(self) -> str:
        return _ICONS[self._name]


_SVG_CACHE: dict[str, str] = {}

RI_ADD = Icon("add")
RI_EDIT = Icon("edit")
RI_DELETE = Icon("delete")
RI_SEARCH = Icon("search")
RI_CHECK = Icon("check")
RI_CLOSE = Icon("close")
RI_FILTER = Icon("filter")
RI_EXPORT = Icon("export")
RI_IMPORT = Icon("import")
RI_FOLDER = Icon("folder")
RI_CALENDAR = Icon("calendar")
RI_SETTINGS = Icon("settings")
RI_REFRESH = Icon("refresh")
RI_BACKUP = Icon("backup")
RI_DASHBOARD = Icon("dashboard")
RI_PIN = Icon("pin")
RI_MORE = Icon("more")


# ═══════════════════════════════════════════════════════════════════
#  便利函数：直接给 QPushButton/QToolButton 设置图标
# ═══════════════════════════════════════════════════════════════════


def set_icon(btn, icon: Icon, size: int = 16) -> None:
    """给按钮设置 SVG 图标 + 大小。"""
    from PySide6.QtCore import QSize as _QS
    btn.setIcon(icon.icon())
    btn.setIconSize(_QS(size, size))
