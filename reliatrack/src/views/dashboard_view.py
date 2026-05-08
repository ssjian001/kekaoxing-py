"""仪表盘视图 — 左右两栏：A 区(测试状态+环形图) + B 区(测试结果+进度环)。"""

from __future__ import annotations

import math

import pyqtgraph as pg
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
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QConicalGradient

from src.styles.theme import (
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, MAUVE, PEACH, SURFACE0,
)
from src.styles.constants import VIEW_MARGINS, CHART_COLORS, FONT_FAMILY

# ── 通用字体 ──
_FAMILY = FONT_FAMILY.split(",")[0].strip()
_FONT_SM = QFont(_FAMILY, 9)
_FONT_MD = QFont(_FAMILY, 10)
_FONT_LG = QFont(_FAMILY, 13, QFont.Weight.Bold)
_FONT_XL = QFont(_FAMILY, 16, QFont.Weight.Bold)


# ═══════════════════════════════════════════════════════════════════
#  KPI 卡片
# ═══════════════════════════════════════════════════════════════════

class _KPICard(QFrame):
    """紧凑 KPI 卡片，点击可跳转 Tab。"""

    def __init__(self, title: str, value: str, color: str = BLUE,
                 tab_index: int = -1, parent: QWidget | None = None):
        super().__init__(parent)
        self._tab_index = tab_index
        self.setObjectName("kpi-card")
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(0)

        t = QLabel(title)
        t.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px; border: none;")
        lay.addWidget(t)

        self._val = QLabel(value)
        self._val.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold; border: none;")
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
#  环形图（Donut）— QPainter
# ═══════════════════════════════════════════════════════════════════

class _DonutChart(QWidget):
    """紧凑环形图 — 中心总数 + 图例水平排列于下方。"""

    _RING_W = 14

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setMinimumSize(140, 150)

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

        # ── 环形图（上方 72%）──
        chart_h = int(h * 0.68)
        ring_d = min(w * 0.75, chart_h - 12)
        cx, cy = w / 2, chart_h / 2
        outer_r = ring_d / 2
        inner_r = outer_r - self._RING_W
        rect = QRectF(cx - outer_r, cy - outer_r, ring_d, ring_d)

        # 底环
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(SUBTEXT0 + "22"))
        p.drawEllipse(rect)

        # 扇形
        start = 0
        items = list(self._data.items())
        for i, (_, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            span = int(val / total * 360 * 16)
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.setBrush(QBrush(color))
            p.drawPie(rect, -start, -span)
            start += span

        # 挖空中心
        p.setPen(Qt.PenStyle.NoPen)
        bg = self.parentWidget()
        bg_color = bg.palette().window().color() if bg else QColor("#ffffff")
        p.setBrush(bg_color)
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        # 中心总数
        p.setPen(QColor(TEXT))
        p.setFont(_FONT_LG)
        p.drawText(QRectF(cx - 36, cy - 12, 72, 24),
                   Qt.AlignmentFlag.AlignCenter, str(total))

        # ── 图例（下方水平）──
        p.setFont(_FONT_SM)
        col_w = w / max(len(items), 1)
        ly = chart_h + 4
        for i, (label, val) in enumerate(items):
            color = QColor(CHART_COLORS[i % len(CHART_COLORS)])
            lx = col_w * i
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(lx + 4, ly, 8, 8), 2, 2)
            pct = val / total * 100
            p.setPen(QColor(SUBTEXT1))
            p.drawText(QRectF(lx + 16, ly - 2, col_w - 20, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{label} {val}({pct:.0f}%)")
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  进度环（Progress Ring）— QPainter
# ═══════════════════════════════════════════════════════════════════

class _ProgressRing(QWidget):
    """紧凑圆弧进度指示。"""

    _ARC_W = 8

    def __init__(self, label: str, color: str = BLUE, parent: QWidget | None = None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._pct: float = 0.0
        self.setFixedSize(76, 76)

    def setPercent(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, (h - 14) / 2  # 底部留标签
        r = min(cx, cy) - 2
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # 背景弧
        p.setPen(QPen(QColor(SUBTEXT0 + "44"), self._ARC_W,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)

        # 进度弧
        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), self._ARC_W,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(self._pct / 100 * 360 * 16))

        # 中心数字
        p.setPen(QColor(TEXT))
        p.setFont(QFont(_FAMILY, 11, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 28, cy - 9, 56, 18),
                   Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")

        # 底部标签
        p.setPen(QColor(SUBTEXT1))
        p.setFont(QFont(_FAMILY, 8))
        p.drawText(QRectF(0, h - 14, w, 12),
                   Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  数据封装
# ═══════════════════════════════════════════════════════════════════

class DashboardData:
    """Dashboard 刷新数据封装。"""

    __slots__ = (
        "task_total", "task_completed", "task_in_progress", "task_pending",
        "pass_rate", "failure_rate", "task_status_data",
        "issue_count", "issue_closed_count",
        "capa_completion_rate", "failed_task_count",
        "issue_severity_data",
        "project_name", "plan_name",
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
    """仪表盘 — 左右两栏紧凑布局。

    左栏(A)：6 个 KPI 卡片(2×3) + 环形图(任务状态分布)
    右栏(B)：4 个 KPI 卡片(2×2) + 2 个进度环(Issue闭环率 / CAPA完成率)
    """

    card_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*VIEW_MARGINS)
        root.setSpacing(4)

        # ── 顶部筛选指示器 ──
        self._filter_label = QLabel("全部项目")
        self._filter_label.setStyleSheet(
            f"color: {SUBTEXT0}; font-size: 11px; "
            f"background-color: {SUBTEXT0}18; border-radius: 4px; "
            f"padding: 2px 8px;"
        )
        root.addWidget(self._filter_label)

        # ── 左右两栏 ──
        cols = QHBoxLayout()
        cols.setSpacing(10)

        # ═══ 左栏 ═══
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(self._mk_title("测试状态"))

        # KPI 2×3
        ga = QGridLayout()
        ga.setSpacing(4)
        self._card_total     = _KPICard("任务数", "0", BLUE, 3)
        self._card_done      = _KPICard("已完成", "0", GREEN, 3)
        self._card_active    = _KPICard("进行中", "0", YELLOW, 3)
        self._card_wait      = _KPICard("待开始", "0", SUBTEXT1, 3)
        self._card_pass      = _KPICard("通过率", "—%", GREEN, 3)
        self._card_fail      = _KPICard("失效率", "—%", RED, 4)
        for c, r, co in [
            (self._card_total, 0, 0), (self._card_done, 0, 1), (self._card_active, 0, 2),
            (self._card_wait, 1, 0), (self._card_pass, 1, 1), (self._card_fail, 1, 2),
        ]:
            ga.addWidget(c, r, co)
        left.addLayout(ga)

        # 环形图
        self._donut = _DonutChart()
        left.addWidget(self._donut, 1)

        cols.addLayout(left, 1)

        # ═══ 右栏 ═══
        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(self._mk_title("测试结果"))

        # KPI 2×2
        gb = QGridLayout()
        gb.setSpacing(4)
        self._card_fail_task   = _KPICard("Fail 项", "0", RED, 3)
        self._card_issues      = _KPICard("Issue 数", "0", PEACH, 4)
        self._card_issue_close = _KPICard("Issue 闭环", "0", BLUE, 4)
        self._card_capa        = _KPICard("CAPA 率", "—%", MAUVE, 4)
        gb.addWidget(self._card_fail_task, 0, 0)
        gb.addWidget(self._card_issues, 0, 1)
        gb.addWidget(self._card_issue_close, 1, 0)
        gb.addWidget(self._card_capa, 1, 1)
        right.addLayout(gb)

        # 进度环（居中）
        rings = QHBoxLayout()
        rings.setSpacing(16)
        rings.addStretch()
        self._ring_issue = _ProgressRing("Issue 闭环率", BLUE)
        self._ring_capa  = _ProgressRing("CAPA 完成率", MAUVE)
        rings.addWidget(self._ring_issue)
        rings.addWidget(self._ring_capa)
        rings.addStretch()
        right.addLayout(rings)

        right.addStretch()
        cols.addLayout(right, 1)

        root.addLayout(cols)

    @staticmethod
    def _mk_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: bold; "
            f"border-bottom: 1px solid {SUBTEXT0}33; padding-bottom: 2px;"
        )
        return lbl

    # ── 刷新 ──────────────────────────────────────────────────

    def refresh(self, data: DashboardData | None = None, **kwargs: object) -> None:
        if data is None:
            data = DashboardData(**kwargs)

        # 筛选指示器
        self._update_filter(data.project_name, data.plan_name)

        # A 区 KPI
        self._card_total.set_value(str(data.task_total))
        self._card_done.set_value(str(data.task_completed))
        self._card_active.set_value(str(data.task_in_progress))
        self._card_wait.set_value(str(data.task_pending))
        self._card_pass.set_value(f"{data.pass_rate:.0f}%" if data.pass_rate is not None else "—%")
        self._card_fail.set_value(f"{data.failure_rate:.0f}%" if data.failure_rate is not None else "—%")

        # B 区 KPI
        self._card_fail_task.set_value(str(data.failed_task_count))
        self._card_issues.set_value(str(data.issue_count))
        self._card_issue_close.set_value(str(data.issue_closed_count))
        self._card_capa.set_value(
            f"{data.capa_completion_rate:.0f}%" if data.capa_completion_rate is not None else "—%"
        )

        # 环形图
        task_map = {"pending": "待开始", "in_progress": "进行中",
                     "completed": "已完成", "skipped": "已跳过", "failed": "失败"}
        self._donut.setData(
            {task_map.get(k, k): v for k, v in (data.task_status_data or {}).items() if v > 0}
        )

        # 进度环
        ic = data.issue_count or 0
        icc = data.issue_closed_count or 0
        self._ring_issue.setPercent(icc / ic * 100 if ic else 0)
        self._ring_capa.setPercent(data.capa_completion_rate if data.capa_completion_rate is not None else 0)

    def _update_filter(self, project_name: str | None, plan_name: str | None) -> None:
        if project_name and plan_name:
            text = f"{project_name} / {plan_name}"
            ss = (f"color: {BLUE}; font-size: 11px; font-weight: bold; "
                  f"background-color: {SUBTEXT0}18; border-radius: 4px; "
                  f"border: 1px solid {BLUE}; padding: 2px 8px;")
        elif project_name:
            text = project_name
            ss = (f"color: {BLUE}; font-size: 11px; font-weight: bold; "
                  f"background-color: {SUBTEXT0}18; border-radius: 4px; "
                  f"border: 1px solid {BLUE}; padding: 2px 8px;")
        else:
            text = "全部项目"
            ss = (f"color: {SUBTEXT0}; font-size: 11px; "
                  f"background-color: {SUBTEXT0}18; border-radius: 4px; "
                  f"padding: 2px 8px;")
        self._filter_label.setText(text)
        self._filter_label.setStyleSheet(ss)
