"""仪表盘图表组件 — 环形图/进度条/进度环/严重度条。

提取自 dashboard_view.py，纯 QPainter 绘制，无外部依赖。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import QWidget, QSizePolicy

import src.styles.theme as _theme
from src.styles.constants import CHART_COLORS, DASH_SUCCESS, DASH_DANGER, DASH_WARNING, DASH_PRIMARY
from src.constants import SEVERITY_LABELS
from src.styles.constants import ISSUE_SEVERITY_COLORS

# ── 字体 ──
_FAMILY = _theme.FONT_FAMILY.split(",")[0].strip()


def _mk_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(_FAMILY)
    f.setPixelSize(pixel_size)
    if weight != QFont.Weight.Normal:
        f.setWeight(weight)
    return f


_FONT_SM = _mk_font(12)
_FONT_MD = _mk_font(13)
_FONT_XXL = _mk_font(37, QFont.Weight.Bold)


def _alpha(color_hex: str, alpha: int) -> QColor:
    c = QColor(color_hex)
    c.setAlpha(alpha)
    return c


class _DonutChart(QWidget):
    """环形图 + 右侧垂直图例。"""

    _RING_W = 16

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setProperty("class", "card-bg")
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setData(self, data: dict[str, int]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if not self._data:
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(_FONT_MD)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        total = sum(self._data.values())
        if total == 0:
            p.end()
            return

        items = list(self._data.items())
        chart_w = int(w * 0.58)
        legend_x = chart_w + 16

        ring_d = min(chart_w * 0.7, h - 24)
        cx, cy = chart_w / 2, h / 2
        outer_r = ring_d / 2
        inner_r = outer_r - self._RING_W
        rect = QRectF(cx - outer_r, cy - outer_r, ring_d, ring_d)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_alpha(_theme.SUBTEXT0, 34))
        p.drawEllipse(rect)

        start = 0
        for i, (_, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            span = int(val / total * 360 * 16)
            p.setPen(QPen(QColor(_theme.MANTLE), 2))
            p.setBrush(QBrush(color))
            p.drawPie(rect, -start, -span)
            start += span

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_theme.MANTLE))
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        p.setPen(QColor(_theme.TEXT))
        p.setFont(_FONT_XXL)
        p.drawText(QRectF(cx - 36, cy - 16, 72, 32), Qt.AlignmentFlag.AlignCenter, str(total))
        p.setFont(_FONT_SM)
        p.setPen(QColor(_theme.SUBTEXT0))
        p.drawText(QRectF(cx - 30, cy + 16, 60, 16), Qt.AlignmentFlag.AlignCenter, "总任务数")

        p.setFont(_FONT_MD)
        row_h = 28
        legend_start_y = cy - (len(items) * row_h) / 2
        for i, (label, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            ly = legend_start_y + i * row_h
            pct = val / total * 100
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(legend_x, ly + 3, 10, 10), 2, 2)
            p.setPen(QColor(_theme.TEXT))
            p.drawText(QRectF(legend_x + 16, ly - 1, 100, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QColor(_theme.SUBTEXT0))
            p.drawText(QRectF(legend_x + 100, ly - 1, 80, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{val}  ({pct:.0f}%)")
        p.end()


class _StackedBar(QWidget):
    """堆叠进度条: PASS(绿) + FAIL(红) + 进行中(黄) + 待开始(灰)。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._total = 0
        self._pass = 0
        self._fail = 0
        self._progress = 0

    def set_data(self, total: int, pass_count: int, fail_count: int, in_progress: int) -> None:
        self._total = max(total, 1)
        self._pass = pass_count
        self._fail = fail_count
        self._progress = in_progress
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_theme.SURFACE1))
        p.drawRoundedRect(0, 0, w, h, 4, 4)

        if self._total <= 0:
            p.end()
            return

        x = 0
        segments = [(self._pass, DASH_SUCCESS), (self._fail, DASH_DANGER), (self._progress, DASH_WARNING)]
        pending = self._total - self._pass - self._fail - self._progress
        if pending > 0:
            segments.append((pending, _theme.SUBTEXT0))

        for count, color in segments:
            if count <= 0:
                continue
            sw = int(w * count / self._total)
            if sw <= 0:
                continue
            p.setBrush(QColor(color))
            p.drawRect(x, 0, sw, h)
            x += sw

        if segments and segments[0][0] > 0:
            sw0 = int(w * segments[0][0] / self._total)
            if sw0 > 0:
                p.setBrush(QColor(segments[0][1]))
                p.drawRoundedRect(0, 0, sw0, h, 4, 4)
        if len(segments) > 1 and segments[-1][0] > 0:
            sw_last = int(w * segments[-1][0] / self._total)
            x_last = w - sw_last
            if sw_last > 0:
                p.setBrush(QColor(segments[-1][1]))
                p.drawRoundedRect(x_last, 0, sw_last, h, 4, 4)

        p.end()


class _HProgressBar(QWidget):
    """水平进度条（用于通过率显示）。"""

    def __init__(self, color: str = DASH_SUCCESS, height: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._bar_h = height
        self._pct: float = 0.0
        self.setFixedHeight(height + 4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setPercent(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bar_y = (h - self._bar_h) / 2
        bg_rect = QRectF(0, bar_y, w, self._bar_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_alpha(_theme.SUBTEXT0, 51))
        p.drawRoundedRect(bg_rect, self._bar_h / 2, self._bar_h / 2)
        if self._pct > 0:
            fill_w = w * self._pct / 100
            fill_rect = QRectF(0, bar_y, fill_w, self._bar_h)
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0, QColor(self._color))
            grad.setColorAt(1, QColor(self._color).lighter(115))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, self._bar_h / 2, self._bar_h / 2)
        p.end()


class _ProgressRing(QWidget):
    """圆弧进度指示器。"""

    _ARC_W = 12

    def __init__(self, label: str, color: str = DASH_PRIMARY, parent: QWidget | None = None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._pct: float = 0.0
        self.setMinimumSize(100, 100)
        self.setMaximumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setPercent(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, (h - 16) / 2
        r = min(cx, cy) - 4
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        p.setPen(QPen(_alpha(_theme.SUBTEXT0, 51), self._ARC_W,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)
        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), self._ARC_W,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(self._pct / 100 * 360 * 16))
        p.setPen(QColor(_theme.TEXT))
        p.setFont(QFont(_FAMILY, 16, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 30, cy - 10, 60, 20), Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")
        p.setPen(QColor(_theme.SUBTEXT0))
        p.setFont(QFont(_FAMILY, 9))
        p.drawText(QRectF(0, h - 16, w, 14), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


class _SeverityBar(QWidget):
    """水平分段严重度条（Critical / Major / Minor / Cosmetic）。"""

    _SEVERITY_ORDER: list[str] = list(SEVERITY_LABELS.keys())

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setData(self, data: dict[str, int]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        total = sum(self._data.get(s, 0) for s in self._SEVERITY_ORDER)
        bar_h, bar_y, gap = 14, 6, 2
        if total == 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(_theme.SUBTEXT0, 34))
            p.drawRoundedRect(QRectF(bar_x := 0, bar_y, w, bar_h), bar_h / 2, bar_h / 2)
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(_FONT_SM)
            p.drawText(QRectF(0, bar_y + bar_h + 4, w, 16), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        usable_w = w - gap * (len([s for s in self._SEVERITY_ORDER if self._data.get(s, 0) > 0]) - 1)
        x = 0.0
        for sev in self._SEVERITY_ORDER:
            val = self._data.get(sev, 0)
            if val <= 0:
                continue
            seg_w = usable_w * val / total
            color_str = ISSUE_SEVERITY_COLORS.get(sev, _theme.SUBTEXT0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color_str))
            p.drawRoundedRect(QRectF(x, bar_y, seg_w, bar_h), bar_h / 2, bar_h / 2)
            x += seg_w + gap

        p.setFont(_FONT_SM)
        legend_y = bar_y + bar_h + 6
        lx = 0.0
        for sev in self._SEVERITY_ORDER:
            val = self._data.get(sev, 0)
            label = SEVERITY_LABELS.get(sev, sev)
            color_str = ISSUE_SEVERITY_COLORS.get(sev, _theme.SUBTEXT0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color_str))
            p.drawRoundedRect(QRectF(lx, legend_y + 2, 8, 8), 2, 2)
            p.setPen(QColor(_theme.TEXT))
            text = f"{label} {val}"
            p.drawText(QRectF(lx + 12, legend_y - 1, 70, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            fm = QFontMetrics(_FONT_SM)
            lx += 12 + fm.horizontalAdvance(text) + 16
        p.end()
