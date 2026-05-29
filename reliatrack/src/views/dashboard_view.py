"""仪表盘视图 — 现代企业 SaaS 风格，浅灰背景 + 白底圆角卡片。

布局结构:
    Header（项目名 + 最后更新时间）
    整体健康度卡片（健康评分 + 进度条 + 3 辅助指标）
    左右两栏:
        左栏: 测试执行概览（4 KPI + 环形图）
        右栏: 质量与问题概览（3 KPI + 2 独立进度环卡片）
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QBrush, QLinearGradient

import src.styles.theme as _theme

from src.styles.constants import (
    FONT_FAMILY,
    VIEW_MARGINS,
    CHART_COLORS,
    ISSUE_SEVERITY_COLORS,
    DASH_PRIMARY,
    DASH_SUCCESS,
    DASH_WARNING,
    DASH_DANGER,
    DASH_NEUTRAL,
    STATUS_RED,
    STATUS_PEACH,
    card_qss,
    add_shadow,
)

# ── 通用字体 ──
_FAMILY = FONT_FAMILY.split(",")[0].strip()


def _mk_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """用 pixel size 创建 QFont，避免 pt/px 混用。"""
    f = QFont(_FAMILY)
    f.setPixelSize(pixel_size)
    if weight != QFont.Weight.Normal:
        f.setWeight(weight)
    return f


_FONT_SM = _mk_font(12)
_FONT_MD = _mk_font(13)
_FONT_LG = _mk_font(17, QFont.Weight.Bold)
_FONT_XL = _mk_font(21, QFont.Weight.Bold)
_FONT_XXL = _mk_font(37, QFont.Weight.Bold)
_FONT_SCORE = _mk_font(48, QFont.Weight.Bold)


def _alpha(color_hex: str, alpha: int) -> QColor:
    """从 hex 色值创建带 alpha 的 QColor（替代字符串拼接 8 位 hex）。"""
    c = QColor(color_hex)
    c.setAlpha(alpha)
    return c

# ═══════════════════════════════════════════════════════════════════
#  KPI 卡片 — 替代旧 _KPICard
# ═══════════════════════════════════════════════════════════════════

class _StatCard(QFrame):
    """现代 KPI 卡片: label / 大数字 / 百分比, 16px 圆角 + 柔阴影。"""

    def __init__(self, title: str, value: str = "0", color: str = DASH_PRIMARY,
                 tab_index: int = -1, parent: QWidget | None = None):
        super().__init__(parent)
        self._tab_index = tab_index
        self._color = color
        self.setObjectName("stat-card")
        self.setStyleSheet(card_qss(16))
        self.setMinimumHeight(64)
        self.setMaximumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        add_shadow(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)

        # 标签
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;"
            f"border: none; background: transparent;"
        )
        lay.addWidget(self._title_label)

        # 大数字
        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        lay.addWidget(self._val)

        _theme.theme_host.theme_changed.connect(self._refresh_theme_styles)

    def set_value(self, text: str) -> None:
        self._val.setText(text)

    def _refresh_theme_styles(self) -> None:
        self.setStyleSheet(card_qss(16))
        self._title_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;"
            f"border: none; background: transparent;"
        )
        self._val.setStyleSheet(
            f"color: {self._color}; font-size: 22px; font-weight: bold;"
            f"border: none; background: transparent;"
        )

    def enterEvent(self, event):  # noqa: N802
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setBlurRadius(20)
            shadow.setOffset(0, 4)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 2)
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        w = self.parent()
        while w is not None:
            if hasattr(w, "card_clicked"):
                w.card_clicked.emit(self._tab_index)
                break
            w = w.parent()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  辅助指标卡片 — 健康度卡片的右侧小卡片
# ═══════════════════════════════════════════════════════════════════

class _AuxCard(QFrame):
    """紧凑辅助指标: 标题 + 值。"""

    def __init__(self, title: str, value: str, parent: QWidget | None = None):
        super().__init__(parent)
        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 6, 12, 6)
        vl.setSpacing(0)
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 11px; border: none; background: transparent;"
        )
        vl.addWidget(self._title_label)
        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(
            f"color: {DASH_PRIMARY}; font-size: 16px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        vl.addWidget(self._value_label)
        _theme.theme_host.theme_changed.connect(self._refresh_theme_styles)

    def set_value(self, text: str) -> None:
        self._value_label.setText(text)

    def _refresh_theme_styles(self) -> None:
        self.setStyleSheet(card_qss(10))
        self._title_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 11px; border: none; background: transparent;"
        )
        self._value_label.setStyleSheet(
            f"color: {DASH_PRIMARY}; font-size: 16px; font-weight: bold;"
            f"border: none; background: transparent;"
        )


# ═══════════════════════════════════════════════════════════════════
#  健康度卡片 — 顶部大摘要
# ═══════════════════════════════════════════════════════════════════

class _TestProgressCard(QFrame):
    """测试进度摘要: 堆叠进度条 (PASS/FAIL/进行中/待开始) + 辅助指标。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(card_qss(16))
        self.setFixedHeight(88)
        add_shadow(self, blur=16, offset=3, opacity=20)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12)
        lay.setSpacing(24)

        # ── 左侧: 堆叠进度条 + 图例 ──
        left = QVBoxLayout()
        left.setSpacing(4)

        self._title_label = QLabel("测试进度")
        self._title_label.setStyleSheet(
            f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        left.addWidget(self._title_label)

        self._stacked = _StackedBar()
        left.addWidget(self._stacked)

        # 图例行
        legend = QHBoxLayout()
        legend.setSpacing(12)
        self._legend_labels: list[QLabel] = []
        for label, color in [("PASS", DASH_SUCCESS), ("FAIL", DASH_DANGER),
                             ("进行中", DASH_WARNING), ("待开始", DASH_NEUTRAL)]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; border: none; background: transparent;")
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 10px; border: none; background: transparent;")
            self._legend_labels.append(lbl)
            legend.addWidget(dot)
            legend.addWidget(lbl)
        legend.addStretch()
        left.addLayout(legend)
        lay.addLayout(left, 3)

        # ── 右侧: 2 个辅助指标 ──
        right = QHBoxLayout()
        right.setSpacing(16)
        self._aux1 = self._mk_aux("测试通过率", "—%")
        self._aux2 = self._mk_aux("最后更新", "—")
        right.addWidget(self._aux1)
        right.addWidget(self._aux2)
        lay.addLayout(right, 2)

        _theme.theme_host.theme_changed.connect(self._refresh_theme_styles)

    @staticmethod
    def _mk_aux(title: str, value: str) -> _AuxCard:
        """创建紧凑辅助指标。"""
        card = _AuxCard(title, value)
        card.setStyleSheet(card_qss(10))
        card.setFixedHeight(56)
        return card

    def refresh(self, total: int, completed: int, pass_count: int, fail_count: int,
                in_progress: int, pass_rate: float | None,
                last_update: str | None) -> None:
        self._stacked.set_data(total, pass_count, fail_count, in_progress)
        self._aux1.set_value(f"{pass_rate:.1f}%" if pass_rate is not None else "—%")
        self._aux2.set_value(last_update or "—")

    def _refresh_theme_styles(self) -> None:
        self.setStyleSheet(card_qss(16))
        self._title_label.setStyleSheet(
            f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        for lbl in self._legend_labels:
            lbl.setStyleSheet(
                f"color: {_theme.SUBTEXT0}; font-size: 10px; border: none; background: transparent;"
            )
        self._aux1._refresh_theme_styles()
        self._aux2._refresh_theme_styles()


# ═══════════════════════════════════════════════════════════════════
#  环形图（Donut）— QPainter, 图例右侧垂直
# ═══════════════════════════════════════════════════════════════════

class _DonutChart(QFrame):
    """环形图 + 右侧垂直图例。"""

    _RING_W = 16

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setStyleSheet(card_qss(16))
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        add_shadow(self)
        _theme.theme_host.theme_changed.connect(self.update)

    def setData(self, data: dict[str, int]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if not self._data:
            # 空态提示
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(_FONT_MD)
            p.drawText(QRectF(0, 0, w, h),
                       Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        total = sum(self._data.values())
        if total == 0:
            p.end()
            return

        items = list(self._data.items())

        # ── 布局: 左侧环形图(60%) + 右侧图例(40%) ──
        chart_w = int(w * 0.58)
        legend_x = chart_w + 16

        # 环形图
        ring_d = min(chart_w * 0.7, h - 24)
        cx, cy = chart_w / 2, h / 2
        outer_r = ring_d / 2
        inner_r = outer_r - self._RING_W
        rect = QRectF(cx - outer_r, cy - outer_r, ring_d, ring_d)

        # 底环
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_alpha(_theme.SUBTEXT0, 34))
        p.drawEllipse(rect)

        # 扇形（白色间隔线模拟圆角感）
        start = 0
        for i, (_, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            span = int(val / total * 360 * 16)
            p.setPen(QPen(QColor(_theme.MANTLE), 2))
            p.setBrush(QBrush(color))
            p.drawPie(rect, -start, -span)
            start += span

        # 挖空中心
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_theme.MANTLE))
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        # 中心总数
        p.setPen(QColor(_theme.TEXT))
        p.setFont(_FONT_XXL)
        p.drawText(QRectF(cx - 36, cy - 16, 72, 32),
                   Qt.AlignmentFlag.AlignCenter, str(total))
        p.setFont(_FONT_SM)
        p.setPen(QColor(_theme.SUBTEXT0))
        p.drawText(QRectF(cx - 30, cy + 16, 60, 16),
                   Qt.AlignmentFlag.AlignCenter, "总任务数")

        # ── 右侧图例（垂直排列）──
        p.setFont(_FONT_MD)
        row_h = 28
        legend_start_y = cy - (len(items) * row_h) / 2
        for i, (label, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            ly = legend_start_y + i * row_h
            pct = val / total * 100

            # 色点
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(legend_x, ly + 3, 10, 10), 2, 2)

            # 文字
            p.setPen(QColor(_theme.TEXT))
            p.drawText(QRectF(legend_x + 16, ly - 1, 100, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)

            # 数值 + 百分比
            p.setPen(QColor(_theme.SUBTEXT0))
            val_w = 80
            p.drawText(QRectF(legend_x + 100, ly - 1, val_w, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{val}  ({pct:.0f}%)")
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  水平进度条 — QPainter
# ═══════════════════════════════════════════════════════════════════

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
        _theme.theme_host.theme_changed.connect(self.update)

    def set_data(self, total: int, pass_count: int, fail_count: int,
                 in_progress: int) -> None:
        self._total = max(total, 1)
        self._pass = pass_count
        self._fail = fail_count
        self._progress = in_progress
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_theme.SURFACE1))
        p.drawRoundedRect(0, 0, w, h, 4, 4)

        if self._total <= 0:
            p.end()
            return

        x = 0
        segments = [
            (self._pass, DASH_SUCCESS),
            (self._fail, DASH_DANGER),
            (self._progress, DASH_WARNING),
        ]
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
            # 首尾段带圆角，中间段矩形
            p.drawRect(x, 0, sw, h)
            x += sw

        # 首段和尾段圆角覆盖
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

    def __init__(self, color: str = DASH_SUCCESS, height: int = 8,
                 parent: QWidget | None = None):
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

        # 背景条
        bar_y = (h - self._bar_h) / 2
        bg_rect = QRectF(0, bar_y, w, self._bar_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_alpha(_theme.SUBTEXT0, 51))
        p.drawRoundedRect(bg_rect, self._bar_h / 2, self._bar_h / 2)

        # 进度条（渐变）
        if self._pct > 0:
            fill_w = w * self._pct / 100
            fill_rect = QRectF(0, bar_y, fill_w, self._bar_h)
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0, QColor(self._color))
            grad.setColorAt(1, QColor(self._color).lighter(115))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, self._bar_h / 2, self._bar_h / 2)

        p.end()


# ═══════════════════════════════════════════════════════════════════
#  进度环（Progress Ring）— QPainter, 100px
# ═══════════════════════════════════════════════════════════════════

class _ProgressRing(QWidget):
    """圆弧进度指示器。"""

    _ARC_W = 12

    def __init__(self, label: str, color: str = DASH_PRIMARY,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._pct: float = 0.0
        self.setMinimumSize(100, 100)
        self.setMaximumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _theme.theme_host.theme_changed.connect(self.update)

    def setPercent(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, (h - 16) / 2  # 底部留标签
        r = min(cx, cy) - 4
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # 背景弧
        p.setPen(QPen(_alpha(_theme.SUBTEXT0, 51), self._ARC_W,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)

        # 进度弧
        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), self._ARC_W,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(self._pct / 100 * 360 * 16))

        # 中心数字
        p.setPen(QColor(_theme.TEXT))
        p.setFont(QFont(_FAMILY, 16, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 30, cy - 10, 60, 20),
                   Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")

        # 底部标签
        p.setPen(QColor(_theme.SUBTEXT0))
        p.setFont(QFont(_FAMILY, 9))
        p.drawText(QRectF(0, h - 16, w, 14),
                   Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  严重度分布条 — QPainter
# ═══════════════════════════════════════════════════════════════════

class _SeverityBar(QWidget):
    """水平分段严重度条（Critical / Major / Minor / Cosmetic）。"""

    _SEVERITY_ORDER: list[str] = ["critical", "major", "minor", "cosmetic"]
    _SEVERITY_LABELS: dict[str, str] = {
        "critical": "严重", "major": "主要", "minor": "次要", "cosmetic": "外观",
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _theme.theme_host.theme_changed.connect(self.update)

    def setData(self, data: dict[str, int]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        total = sum(self._data.get(s, 0) for s in self._SEVERITY_ORDER)
        bar_h = 14
        bar_y = 6
        bar_x = 0
        gap = 2

        if total == 0:
            # 空态
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(_theme.SUBTEXT0, 34))
            p.drawRoundedRect(QRectF(bar_x, bar_y, w, bar_h), bar_h / 2, bar_h / 2)
            p.setPen(QColor(_theme.SUBTEXT0))
            p.setFont(_FONT_SM)
            p.drawText(QRectF(0, bar_y + bar_h + 4, w, 16),
                       Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        # 画分段条
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

        # 图例
        p.setFont(_FONT_SM)
        legend_y = bar_y + bar_h + 6
        lx = 0.0
        for sev in self._SEVERITY_ORDER:
            val = self._data.get(sev, 0)
            label = self._SEVERITY_LABELS.get(sev, sev)
            color_str = ISSUE_SEVERITY_COLORS.get(sev, _theme.SUBTEXT0)

            # 色点
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color_str))
            p.drawRoundedRect(QRectF(lx, legend_y + 2, 8, 8), 2, 2)

            # 文字
            p.setPen(QColor(_theme.TEXT))
            text = f"{label} {val}"
            p.drawText(QRectF(lx + 12, legend_y - 1, 70, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       text)
            # 测量宽度推进
            fm = QFontMetrics(_FONT_SM)
            lx += 12 + fm.horizontalAdvance(text) + 16
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  数据封装
# ═══════════════════════════════════════════════════════════════════

class DashboardData:
    """Dashboard 刷新数据封装。"""

    __slots__ = (
        # 测试状态
        "task_total", "task_completed", "task_in_progress", "task_pending",
        "pass_rate", "failure_rate", "task_status_data",
        # 质量与问题
        "issue_count", "issue_closed_count",
        "capa_completion_rate", "failed_task_count",
        "issue_severity_data",
        # 筛选
        "project_name", "plan_name",
        # 新增
        "health_score", "plan_count", "technician_count",
        "pass_count", "fail_count",
        "last_update", "pass_rate_trend", "capa_trend",
    )

    def __init__(self, **kwargs: object) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(
                slot,
                0 if "count" in slot or "total" in slot
                else {} if "data" in slot
                else None
            ))


# ═══════════════════════════════════════════════════════════════════
#  仪表盘主视图
# ═══════════════════════════════════════════════════════════════════

class DashboardView(QWidget):
    """仪表盘 — 现代企业 SaaS 风格。

    Header + 健康度卡片 + 左右两栏
    """

    card_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
        _theme.theme_host.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self) -> None:
        """Refresh QSS for all widgets on theme change."""
        # Scroll area & container
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {_theme.BASE}; border: none; }}"
            f"QScrollBar:vertical {{ width: 8px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {_theme.SURFACE1}; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self._container.setStyleSheet(f"background-color: {_theme.BASE};")

        # Header labels
        self._filter_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;"
            f"background-color: {_theme.MANTLE}; border: 1px solid {_theme.SURFACE1};"
            f"border-radius: 8px; padding: 4px 12px;"
        )
        self._time_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 11px;"
            f"background: transparent; border: none;"
        )

        # Section titles
        for lbl in self._section_titles:
            lbl.setStyleSheet(
                f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;"
                f"background: transparent; border: none;"
            )

        # Ring card frames
        for card in self._ring_cards:
            card.setStyleSheet(card_qss(16))

    def _setup_ui(self) -> None:
        # 外层 QScrollArea 包裹，兜底小窗口
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {_theme.BASE}; border: none; }}"
            f"QScrollBar:vertical {{ width: 8px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {_theme.SURFACE1}; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        self._container = QWidget()
        self._container.setStyleSheet(f"background-color: {_theme.BASE};")
        root = QVBoxLayout(self._container)
        root.setContentsMargins(*VIEW_MARGINS)
        root.setSpacing(16)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(8)
        self._filter_label = QLabel("全部项目")
        self._filter_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;"
            f"background-color: {_theme.MANTLE}; border: 1px solid {_theme.SURFACE1};"
            f"border-radius: 8px; padding: 4px 12px;"
        )
        header.addWidget(self._filter_label)
        header.addStretch()

        self._time_label = QLabel("")
        self._time_label.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 11px;"
            f"background: transparent; border: none;"
        )
        header.addWidget(self._time_label)
        root.addLayout(header)

        # ── 测试进度卡片 ──
        self._health = _TestProgressCard()
        root.addWidget(self._health)

        # ── 左右两栏 ──
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ═══ 左栏: 测试执行概览 ═══
        left = QVBoxLayout()
        left.setSpacing(12)
        self._section_titles: list[QLabel] = []
        sec1 = self._mk_section_title("测试执行概览")
        self._section_titles.append(sec1)
        left.addWidget(sec1)

        # KPI 4 卡（已完成 / 进行中 / 待开始 / Fail）
        ga = QHBoxLayout()
        ga.setSpacing(10)
        self._card_done   = _StatCard("已完成", "0", DASH_SUCCESS, 3)
        self._card_active = _StatCard("进行中", "0", DASH_WARNING, 3)
        self._card_wait   = _StatCard("待开始", "0", DASH_NEUTRAL, 3)
        self._card_fail   = _StatCard("Fail", "0", DASH_DANGER, 3)
        ga.addWidget(self._card_done)
        ga.addWidget(self._card_active)
        ga.addWidget(self._card_wait)
        ga.addWidget(self._card_fail)
        left.addLayout(ga)

        # 环形图
        self._donut = _DonutChart()
        left.addWidget(self._donut, 1)

        cols.addLayout(left, 1)

        # ═══ 右栏: 质量与问题概览 ═══
        right = QVBoxLayout()
        right.setSpacing(12)
        sec2 = self._mk_section_title("质量与问题概览")
        self._section_titles.append(sec2)
        right.addWidget(sec2)

        # KPI 3 卡
        gb = QHBoxLayout()
        gb.setSpacing(10)
        self._card_issues      = _StatCard("Issue 数", "0", DASH_WARNING, 4)
        self._card_issue_close = _StatCard("Issue 闭环", "0", DASH_PRIMARY, 4)
        self._card_capa        = _StatCard("CAPA 率", "—%", DASH_PRIMARY, 4)
        gb.addWidget(self._card_issues)
        gb.addWidget(self._card_issue_close)
        gb.addWidget(self._card_capa)
        right.addLayout(gb)

        # 进度环（两个独立卡片）
        ring_row = QHBoxLayout()
        ring_row.setSpacing(10)

        self._ring_issue = _ProgressRing("Issue 闭环率", DASH_PRIMARY)
        self._ring_capa  = _ProgressRing("CAPA 完成率", DASH_SUCCESS)

        self._ring_cards: list[QFrame] = []
        for ring_widget in (self._ring_issue, self._ring_capa):
            card = QFrame()
            card.setStyleSheet(card_qss(16))
            card.setFixedHeight(170)
            add_shadow(card)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.addWidget(ring_widget)
            ring_row.addWidget(card, 1)
            self._ring_cards.append(card)
        right.addLayout(ring_row)

        right.addStretch()
        cols.addLayout(right, 1)

        root.addLayout(cols)
        root.addStretch()

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

    @staticmethod
    def _mk_section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;"
            f"background: transparent; border: none;"
        )
        return lbl

    # ── 刷新 ──────────────────────────────────────────────────

    def refresh(self, data: DashboardData | None = None, **kwargs: object) -> None:
        if data is None:
            data = DashboardData(**kwargs)

        # Header
        self._update_filter(data.project_name, data.plan_name)
        self._time_label.setText(
            f"最后更新：{data.last_update}" if data.last_update else ""
        )

        # 测试进度卡片
        self._health.refresh(
            total=data.task_total or 0,
            completed=data.task_completed or 0,
            pass_count=data.pass_count or 0,
            fail_count=data.fail_count or 0,
            in_progress=data.task_in_progress or 0,
            pass_rate=data.pass_rate,
            last_update=data.last_update,
        )

        # 左栏 KPI
        self._card_done.set_value(str(data.task_completed))
        self._card_active.set_value(str(data.task_in_progress))
        self._card_wait.set_value(str(data.task_pending))
        self._card_fail.set_value(str(data.fail_count or 0))

        # 环形图
        task_map = {
            "pending": "待开始", "in_progress": "进行中",
            "completed": "已完成", "skipped": "已跳过", "failed": "失败",
        }
        self._donut.setData(
            {task_map.get(k, k): v for k, v in (data.task_status_data or {}).items() if v > 0}
        )

        # 右栏 KPI
        self._card_issues.set_value(str(data.issue_count))
        self._card_issue_close.set_value(str(data.issue_closed_count))
        cr = data.capa_completion_rate
        self._card_capa.set_value(f"{cr:.0f}%" if cr is not None else "—%")

        # 进度环
        ic = data.issue_count or 0
        icc = data.issue_closed_count or 0
        self._ring_issue.setPercent(icc / ic * 100 if ic else 0)
        self._ring_capa.setPercent(cr if cr is not None else 0)

    def _update_filter(self, project_name: str | None, plan_name: str | None) -> None:
        if project_name and plan_name:
            text = f"{project_name} / {plan_name}"
            ss = (
                f"color: {DASH_PRIMARY}; font-size: 12px; font-weight: bold;"
                f"background-color: {_theme.MANTLE}; border: 1px solid {DASH_PRIMARY};"
                f"border-radius: 8px; padding: 4px 12px;"
            )
        elif project_name:
            text = project_name
            ss = (
                f"color: {DASH_PRIMARY}; font-size: 12px; font-weight: bold;"
                f"background-color: {_theme.MANTLE}; border: 1px solid {DASH_PRIMARY};"
                f"border-radius: 8px; padding: 4px 12px;"
            )
        else:
            text = "全部项目"
            ss = (
                f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;"
                f"background-color: {_theme.MANTLE}; border: 1px solid {_theme.SURFACE1};"
                f"border-radius: 8px; padding: 4px 12px;"
            )
        self._filter_label.setText(text)
        self._filter_label.setStyleSheet(ss)
