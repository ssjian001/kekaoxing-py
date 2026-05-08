"""仪表盘视图 — 现代企业 SaaS 风格，浅灰背景 + 白底圆角卡片。

布局结构:
    Header（项目名 + 最后更新时间）
    整体健康度卡片（健康评分 + 进度条 + 3 辅助指标）
    左右两栏:
        左栏: 测试执行概览（4 KPI + 环形图 + 通过率进度条）
        右栏: 质量与问题概览（4 KPI + 2 进度环 + 严重度分布条）
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
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient

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
    DASH_BG,
    DASH_CARD_BG,
    DASH_CARD_BORDER,
    STATUS_RED,
    STATUS_PEACH,
)

# ── 通用字体 ──
_FAMILY = FONT_FAMILY.split(",")[0].strip()
_FONT_SM = QFont(_FAMILY, 9)
_FONT_MD = QFont(_FAMILY, 10)
_FONT_LG = QFont(_FAMILY, 13, QFont.Weight.Bold)
_FONT_XL = QFont(_FAMILY, 16, QFont.Weight.Bold)
_FONT_XXL = QFont(_FAMILY, 28, QFont.Weight.Bold)
_FONT_SCORE = QFont(_FAMILY, 36, QFont.Weight.Bold)


# ═══════════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════════

def _add_shadow(widget: QWidget, blur: int = 12, offset: int = 2,
                opacity: int = 25) -> None:
    """给 widget 添加柔和阴影效果。"""
    shadow = QGraphicsDropShadowEffect()
    shadow.setOffset(0, offset)
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(shadow)


def _card_qss(radius: int = 16) -> str:
    """返回白底圆角卡片 QSS。"""
    return (
        f"background-color: {DASH_CARD_BG};"
        f"border: 1px solid {DASH_CARD_BORDER};"
        f"border-radius: {radius}px;"
    )


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
        self.setStyleSheet(_card_qss(16))
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _add_shadow(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)

        # 标签
        t = QLabel(title)
        t.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 12px; font-weight: 500;"
            f"border: none; background: transparent;"
        )
        lay.addWidget(t)

        # 大数字
        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        lay.addWidget(self._val)

    def set_value(self, text: str) -> None:
        self._val.setText(text)

    def mousePressEvent(self, event):  # noqa: N802
        w = self.parent()
        while w is not None:
            if hasattr(w, "card_clicked"):
                w.card_clicked.emit(self._tab_index)
                break
            w = w.parent()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  健康度卡片 — 顶部大摘要
# ═══════════════════════════════════════════════════════════════════

class _HealthCard(QFrame):
    """整体健康度摘要: 左侧健康评分 + 进度条, 右侧 3 个辅助指标。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(_card_qss(16))
        self.setFixedHeight(88)
        _add_shadow(self, blur=16, offset=3, opacity=20)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12)
        lay.setSpacing(32)

        # ── 左侧: 评分 + 状态 + 进度条 ──
        left = QVBoxLayout()
        left.setSpacing(4)

        score_row = QHBoxLayout()
        score_row.setSpacing(8)
        self._score_label = QLabel("—")
        self._score_label.setStyleSheet(
            f"color: {DASH_PRIMARY}; font-size: 36px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        score_row.addWidget(self._score_label)

        score_unit = QLabel("/ 100")
        score_unit.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 14px;"
            f"border: none; background: transparent;"
        )
        score_row.addWidget(score_unit)
        score_row.addStretch()
        left.addLayout(score_row)

        self._status_label = QLabel("状态：—")
        self._status_label.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 12px;"
            f"border: none; background: transparent;"
        )
        left.addWidget(self._status_label)

        # 进度条（QPainter 自绘容器）
        self._progress = _HProgressBar(color=DASH_SUCCESS, height=8)
        left.addWidget(self._progress)
        lay.addLayout(left, 3)

        # ── 右侧: 3 个辅助指标 ──
        right = QHBoxLayout()
        right.setSpacing(16)
        self._aux1 = self._mk_aux("测试计划数", "0")
        self._aux2 = self._mk_aux("人员参与", "0")
        self._aux3 = self._mk_aux("最后更新", "—")
        right.addWidget(self._aux1)
        right.addWidget(self._aux2)
        right.addWidget(self._aux3)
        lay.addLayout(right, 2)

    @staticmethod
    def _mk_aux(title: str, value: str) -> QFrame:
        """创建紧凑辅助指标。"""
        f = QFrame()
        f.setStyleSheet(_card_qss(10))
        f.setFixedHeight(56)
        vl = QVBoxLayout(f)
        vl.setContentsMargins(12, 6, 12, 6)
        vl.setSpacing(0)
        t = QLabel(title)
        t.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 11px; border: none; background: transparent;"
        )
        vl.addWidget(t)
        v = QLabel(value)
        v.setStyleSheet(
            f"color: {DASH_PRIMARY}; font-size: 16px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        vl.addWidget(v)
        f._value_label = v  # type: ignore[attr-defined]
        return f

    def refresh(self, score: float | None, plan_count: int,
                technician_count: int, last_update: str | None) -> None:
        # 评分
        if score is not None:
            self._score_label.setText(f"{score:.0f}")
            if score >= 80:
                color, status = DASH_SUCCESS, "良好"
            elif score >= 60:
                color, status = DASH_WARNING, "一般"
            else:
                color, status = DASH_DANGER, "需关注"
            self._score_label.setStyleSheet(
                f"color: {color}; font-size: 36px; font-weight: bold;"
                f"border: none; background: transparent;"
            )
            self._status_label.setText(f"状态：{status}")
            self._status_label.setStyleSheet(
                f"color: {color}; font-size: 12px;"
                f"border: none; background: transparent;"
            )
            self._progress.setPercent(score)
        else:
            self._score_label.setText("—")
            self._status_label.setText("状态：无数据")
            self._progress.setPercent(0)

        # 辅助指标
        self._aux1._value_label.setText(str(plan_count))  # type: ignore[attr-defined]
        self._aux2._value_label.setText(str(technician_count))  # type: ignore[attr-defined]
        self._aux3._value_label.setText(last_update or "—")  # type: ignore[attr-defined]


# ═══════════════════════════════════════════════════════════════════
#  环形图（Donut）— QPainter, 图例右侧垂直
# ═══════════════════════════════════════════════════════════════════

class _DonutChart(QFrame):
    """环形图 + 右侧垂直图例。"""

    _RING_W = 16

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setStyleSheet(_card_qss(16))
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _add_shadow(self)

    def setData(self, data: dict[str, int]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
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
        p.setBrush(QColor(DASH_NEUTRAL + "22"))
        p.drawEllipse(rect)

        # 扇形（白色间隔线模拟圆角感）
        start = 0
        for i, (_, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            span = int(val / total * 360 * 16)
            p.setPen(QPen(QColor(DASH_CARD_BG), 2))
            p.setBrush(QBrush(color))
            p.drawPie(rect, -start, -span)
            start += span

        # 挖空中心
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(DASH_CARD_BG))
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        # 中心总数
        p.setPen(QColor("#1E293B"))
        p.setFont(_FONT_XXL)
        p.drawText(QRectF(cx - 36, cy - 16, 72, 32),
                   Qt.AlignmentFlag.AlignCenter, str(total))
        p.setFont(_FONT_SM)
        p.setPen(QColor(DASH_NEUTRAL))
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
            p.setPen(QColor("#1E293B"))
            p.drawText(QRectF(legend_x + 16, ly - 1, 100, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)

            # 数值 + 百分比
            p.setPen(QColor(DASH_NEUTRAL))
            val_w = 80
            p.drawText(QRectF(legend_x + 100, ly - 1, val_w, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{val}  ({pct:.0f}%)")
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  水平进度条 — QPainter
# ═══════════════════════════════════════════════════════════════════

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
        p.setBrush(QColor(DASH_NEUTRAL + "33"))
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

    _ARC_W = 10

    def __init__(self, label: str, color: str = DASH_PRIMARY,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._pct: float = 0.0
        self.setFixedSize(100, 100)

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
        p.setPen(QPen(QColor(DASH_NEUTRAL + "33"), self._ARC_W,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)

        # 进度弧
        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), self._ARC_W,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(self._pct / 100 * 360 * 16))

        # 中心数字
        p.setPen(QColor("#1E293B"))
        p.setFont(QFont(_FAMILY, 14, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 30, cy - 10, 60, 20),
                   Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")

        # 底部标签
        p.setPen(QColor(DASH_NEUTRAL))
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
            p.setBrush(QColor(DASH_NEUTRAL + "22"))
            p.drawRoundedRect(QRectF(bar_x, bar_y, w, bar_h), bar_h / 2, bar_h / 2)
            p.setPen(QColor(DASH_NEUTRAL))
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
            color_str = ISSUE_SEVERITY_COLORS.get(sev, DASH_NEUTRAL)
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
            color_str = ISSUE_SEVERITY_COLORS.get(sev, DASH_NEUTRAL)

            # 色点
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color_str))
            p.drawRoundedRect(QRectF(lx, legend_y + 2, 8, 8), 2, 2)

            # 文字
            p.setPen(QColor("#1E293B"))
            text = f"{label} {val}"
            p.drawText(QRectF(lx + 12, legend_y - 1, 70, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       text)
            # 测量宽度推进
            from PySide6.QtGui import QFontMetrics
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

    def _setup_ui(self) -> None:
        # 外层 QScrollArea 包裹，兜底小窗口
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {DASH_BG}; border: none; }}"
            f"QScrollBar:vertical {{ width: 8px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {DASH_CARD_BORDER}; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        container = QWidget()
        container.setStyleSheet(f"background-color: {DASH_BG};")
        root = QVBoxLayout(container)
        root.setContentsMargins(*VIEW_MARGINS)
        root.setSpacing(16)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(8)
        self._filter_label = QLabel("全部项目")
        self._filter_label.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 12px; font-weight: 500;"
            f"background-color: {DASH_CARD_BG}; border: 1px solid {DASH_CARD_BORDER};"
            f"border-radius: 8px; padding: 4px 12px;"
        )
        header.addWidget(self._filter_label)
        header.addStretch()

        self._time_label = QLabel("")
        self._time_label.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 11px;"
            f"background: transparent; border: none;"
        )
        header.addWidget(self._time_label)
        root.addLayout(header)

        # ── 健康度卡片 ──
        self._health = _HealthCard()
        root.addWidget(self._health)

        # ── 左右两栏 ──
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ═══ 左栏: 测试执行概览 ═══
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._mk_section_title("测试执行概览"))

        # KPI 4 卡
        ga = QGridLayout()
        ga.setSpacing(10)
        self._card_total  = _StatCard("任务数", "0", DASH_PRIMARY, 3)
        self._card_done   = _StatCard("已完成", "0", DASH_SUCCESS, 3)
        self._card_active = _StatCard("进行中", "0", DASH_WARNING, 3)
        self._card_wait   = _StatCard("待开始", "0", DASH_NEUTRAL, 3)
        ga.addWidget(self._card_total, 0, 0)
        ga.addWidget(self._card_done, 0, 1)
        ga.addWidget(self._card_active, 1, 0)
        ga.addWidget(self._card_wait, 1, 1)
        left.addLayout(ga)

        # 环形图
        self._donut = _DonutChart()
        left.addWidget(self._donut, 1)

        # 通过率进度条
        pass_card = QFrame()
        pass_card.setStyleSheet(_card_qss(16))
        pass_card.setFixedHeight(60)
        _add_shadow(pass_card)
        pass_lay = QVBoxLayout(pass_card)
        pass_lay.setContentsMargins(16, 8, 16, 8)
        pass_lay.setSpacing(4)
        pass_header = QHBoxLayout()
        pass_title = QLabel("通过率")
        pass_title.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 12px; font-weight: 500;"
            f"border: none; background: transparent;"
        )
        pass_header.addWidget(pass_title)
        pass_header.addStretch()
        self._pass_pct_label = QLabel("—%")
        self._pass_pct_label.setStyleSheet(
            f"color: {DASH_SUCCESS}; font-size: 16px; font-weight: bold;"
            f"border: none; background: transparent;"
        )
        pass_header.addWidget(self._pass_pct_label)
        pass_lay.addLayout(pass_header)
        self._pass_bar = _HProgressBar(color=DASH_SUCCESS, height=8)
        pass_lay.addWidget(self._pass_bar)
        left.addWidget(pass_card)

        cols.addLayout(left, 1)

        # ═══ 右栏: 质量与问题概览 ═══
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._mk_section_title("质量与问题概览"))

        # KPI 4 卡
        gb = QGridLayout()
        gb.setSpacing(10)
        self._card_fail_task   = _StatCard("Fail 项", "0", DASH_DANGER, 3)
        self._card_issues      = _StatCard("Issue 数", "0", DASH_WARNING, 4)
        self._card_issue_close = _StatCard("Issue 闭环", "0", DASH_PRIMARY, 4)
        self._card_capa        = _StatCard("CAPA 率", "—%", DASH_PRIMARY, 4)
        gb.addWidget(self._card_fail_task, 0, 0)
        gb.addWidget(self._card_issues, 0, 1)
        gb.addWidget(self._card_issue_close, 1, 0)
        gb.addWidget(self._card_capa, 1, 1)
        right.addLayout(gb)

        # 进度环（居中）
        rings_card = QFrame()
        rings_card.setStyleSheet(_card_qss(16))
        rings_card.setFixedHeight(130)
        _add_shadow(rings_card)
        rings_lay = QHBoxLayout(rings_card)
        rings_lay.setContentsMargins(16, 12, 16, 12)
        rings_lay.setSpacing(24)
        rings_lay.addStretch()
        self._ring_issue = _ProgressRing("Issue 闭环率", DASH_PRIMARY)
        self._ring_capa  = _ProgressRing("CAPA 完成率", DASH_SUCCESS)
        rings_lay.addWidget(self._ring_issue)
        rings_lay.addWidget(self._ring_capa)
        rings_lay.addStretch()
        right.addWidget(rings_card)

        # 严重度分布条
        sev_card = QFrame()
        sev_card.setStyleSheet(_card_qss(16))
        sev_card.setFixedHeight(68)
        _add_shadow(sev_card)
        sev_lay = QVBoxLayout(sev_card)
        sev_lay.setContentsMargins(16, 8, 16, 6)
        sev_lay.setSpacing(2)
        sev_title = QLabel("严重度分布")
        sev_title.setStyleSheet(
            f"color: {DASH_NEUTRAL}; font-size: 11px; font-weight: 500;"
            f"border: none; background: transparent;"
        )
        sev_lay.addWidget(sev_title)
        self._severity_bar = _SeverityBar()
        sev_lay.addWidget(self._severity_bar)
        right.addWidget(sev_card)

        right.addStretch()
        cols.addLayout(right, 1)

        root.addLayout(cols)
        root.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    @staticmethod
    def _mk_section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: #1E293B; font-size: 13px; font-weight: bold;"
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

        # 健康度卡片
        self._health.refresh(
            score=data.health_score,
            plan_count=data.plan_count or 0,
            technician_count=data.technician_count or 0,
            last_update=data.last_update,
        )

        # 左栏 KPI
        self._card_total.set_value(str(data.task_total))
        self._card_done.set_value(str(data.task_completed))
        self._card_active.set_value(str(data.task_in_progress))
        self._card_wait.set_value(str(data.task_pending))

        # 环形图
        task_map = {
            "pending": "待开始", "in_progress": "进行中",
            "completed": "已完成", "skipped": "已跳过", "failed": "失败",
        }
        self._donut.setData(
            {task_map.get(k, k): v for k, v in (data.task_status_data or {}).items() if v > 0}
        )

        # 通过率
        pr = data.pass_rate
        if pr is not None:
            self._pass_pct_label.setText(f"{pr:.1f}%")
            self._pass_bar.setPercent(pr)
        else:
            self._pass_pct_label.setText("—%")
            self._pass_bar.setPercent(0)

        # 右栏 KPI
        self._card_fail_task.set_value(str(data.failed_task_count))
        self._card_issues.set_value(str(data.issue_count))
        self._card_issue_close.set_value(str(data.issue_closed_count))
        cr = data.capa_completion_rate
        self._card_capa.set_value(f"{cr:.0f}%" if cr is not None else "—%")

        # 进度环
        ic = data.issue_count or 0
        icc = data.issue_closed_count or 0
        self._ring_issue.setPercent(icc / ic * 100 if ic else 0)
        self._ring_capa.setPercent(cr if cr is not None else 0)

        # 严重度条
        self._severity_bar.setData(data.issue_severity_data or {})

    def _update_filter(self, project_name: str | None, plan_name: str | None) -> None:
        if project_name and plan_name:
            text = f"{project_name} / {plan_name}"
            ss = (
                f"color: {DASH_PRIMARY}; font-size: 12px; font-weight: bold;"
                f"background-color: {DASH_CARD_BG}; border: 1px solid {DASH_PRIMARY};"
                f"border-radius: 8px; padding: 4px 12px;"
            )
        elif project_name:
            text = project_name
            ss = (
                f"color: {DASH_PRIMARY}; font-size: 12px; font-weight: bold;"
                f"background-color: {DASH_CARD_BG}; border: 1px solid {DASH_PRIMARY};"
                f"border-radius: 8px; padding: 4px 12px;"
            )
        else:
            text = "全部项目"
            ss = (
                f"color: {DASH_NEUTRAL}; font-size: 12px; font-weight: 500;"
                f"background-color: {DASH_CARD_BG}; border: 1px solid {DASH_CARD_BORDER};"
                f"border-radius: 8px; padding: 4px 12px;"
            )
        self._filter_label.setText(text)
        self._filter_label.setStyleSheet(ss)
