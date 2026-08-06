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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

import src.styles.theme as _theme

from src.constants import SEVERITY_LABELS
from src.styles.constants import (
    FONT_FAMILY,
    VIEW_MARGINS,
    CHART_COLORS,
    ISSUE_SEVERITY_COLORS,
    DASH_PRIMARY,
    DASH_SUCCESS,
    DASH_WARNING,
    DASH_DANGER,
    add_shadow,
)

from src.views.widgets.dashboard_charts import (
    _DonutChart,
    _HProgressBar,
    _ProgressRing,
    _SeverityBar,
)
from src.views.widgets.dashboard_cards import (
    _StatCard,
    _AuxCard,
    _TestProgressCard,
)

class DashboardData:
    """Dashboard 刷新数据封装。"""

    __slots__ = (
        # 测试状态
        "task_total", "task_completed", "task_in_progress", "task_pending",
        "task_skipped", "task_paused",
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
        # Bug Tracker 4 指标
        "pending_count", "weekly_closed", "avg_age_days", "aging_warning_count",
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

    card_clicked = Signal(int, object)  # (tab_index, jump_data_or_None)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
    def _on_theme_changed(self) -> None:
        """Refresh QSS for all widgets on theme change."""
        # Scroll area — 主题迁移: class=scroll-base（全局 QSS 自动刷新）
        self._scroll.setProperty("class", "scroll-base")
        self._container.setProperty("class", "bg-base")

        # Header labels — 主题迁移: class=filter-chip / hint-label
        self._filter_label.setProperty("class", "filter-chip")
        self._time_label.setProperty("class", "hint-label")

        # Section titles — 主题迁移: class=text-bold
        for lbl in self._section_titles:
            lbl.setProperty("class", "text-bold")

        # Ring card frames — class-based
        for card in self._ring_cards:
            card.setProperty("class", "card-bg")

    def refresh_theme(self) -> None:
        """外部主题切换回调 — 刷新所有内联样式。"""
        self._on_theme_changed()

        # Stat cards — class-based
        for card in (
            self._card_done, self._card_active,
            self._card_wait, self._card_fail,
            self._card_issues, self._card_issue_close,
            self._card_capa,
            self._card_pending, self._card_week_close,
            self._card_avg_age, self._card_aging,
        ):
            card.setProperty("class", "card-bg")
            # 大数字颜色是语义色（DASH_SUCCESS/SUBTEXT0 等），需重新读取
            if card is self._card_wait:
                # 待开始卡片的颜色随主题切换变化
                color = _theme.SUBTEXT0
            else:
                color = card._color
            card._val.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: bold;"
                f"border: none; background: transparent;"
            )

        # 健康度环图区域
        for section in self._section_titles:
            section.setStyleSheet("")
            style = section.style()
            if style:
                style.unpolish(section)
                style.polish(section)

        # 筛选标签 — 主题迁移: class=summary-bar
        self._filter_label.setProperty("class", "summary-bar")

        # 图例圆点颜色
        for dot, key in zip(self._health._legend_dots, self._health._legend_color_keys):
            color = getattr(_theme, key)
            dot.setStyleSheet(f"color: {color}; font-size: 10px; border: none; background: transparent;")

    def _setup_ui(self) -> None:
        # 外层 QScrollArea 包裹，兜底小窗口
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setProperty("class", "scroll-base")  # 主题迁移: class=scroll-base

        self._container = QWidget()
        self._container.setProperty("class", "bg-base")
        root = QVBoxLayout(self._container)
        root.setContentsMargins(*VIEW_MARGINS)
        root.setSpacing(16)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(8)
        self._filter_label = QLabel("全部项目")
        self._filter_label.setProperty("class", "filter-chip")  # 主题迁移: class=filter-chip
        header.addWidget(self._filter_label)
        header.addStretch()

        self._time_label = QLabel("")
        self._time_label.setProperty("class", "hint-label")  # 主题迁移: class=hint-label
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
        tr1 = QHBoxLayout()
        tr1.setSpacing(8)
        tr1.addWidget(sec1)
        tr1.addStretch()
        self._ctx_label_left = QLabel("")
        self._ctx_label_left.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 11px;"
        )
        tr1.addWidget(self._ctx_label_left)
        left.addLayout(tr1)

        # KPI 4 卡（已完成 / 进行中 / 待开始 / Fail）
        ga = QHBoxLayout()
        ga.setSpacing(10)
        self._card_done   = _StatCard("已完成", "0", DASH_SUCCESS, 3, jump_data={"task_status": "completed"})
        self._card_active = _StatCard("进行中", "0", DASH_WARNING, 3, jump_data={"task_status": "in_progress"})
        self._card_wait   = _StatCard("待开始", "0", _theme.SUBTEXT0, 3, jump_data={"task_status": "pending"})
        self._card_fail   = _StatCard("Fail", "0", DASH_DANGER, 3, jump_data={"task_status": "fail"})
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
        tr2 = QHBoxLayout()
        tr2.setSpacing(8)
        tr2.addWidget(sec2)
        tr2.addStretch()
        self._ctx_label_right = QLabel("")
        self._ctx_label_right.setStyleSheet(
            f"color: {_theme.SUBTEXT0}; font-size: 11px;"
        )
        tr2.addWidget(self._ctx_label_right)
        right.addLayout(tr2)

        # KPI 3 卡
        gb = QHBoxLayout()
        gb.setSpacing(10)
        self._card_issues      = _StatCard("Issue 数", "0", DASH_WARNING, 4, jump_data={"issue_status": None})
        self._card_issue_close = _StatCard("Issue 闭环", "0", DASH_PRIMARY, 4, jump_data={"issue_status": "closed"})
        self._card_capa        = _StatCard("CAPA 率", "—%", DASH_PRIMARY, 4, jump_data={"issue_status": "closed"})
        gb.addWidget(self._card_issues)
        gb.addWidget(self._card_issue_close)
        gb.addWidget(self._card_capa)
        right.addLayout(gb)

        # Bug Tracker 4 指标
        gb2 = QHBoxLayout()
        gb2.setSpacing(10)
        self._card_pending    = _StatCard("待处理", "0", DASH_WARNING, 4, jump_data={"issue_status": "open"})
        self._card_week_close = _StatCard("本周关闭", "0", DASH_SUCCESS, 4, jump_data={"issue_status": "closed"})
        self._card_avg_age    = _StatCard("平均停留", "0天", DASH_PRIMARY, 4, jump_data={"issue_status": "open"})
        self._card_aging      = _StatCard("超期警告", "0", DASH_DANGER, 4, jump_data={"issue_status": "open"})
        gb2.addWidget(self._card_pending)
        gb2.addWidget(self._card_week_close)
        gb2.addWidget(self._card_avg_age)
        gb2.addWidget(self._card_aging)
        right.addLayout(gb2)


        # 进度环（两个独立卡片）
        ring_row = QHBoxLayout()
        ring_row.setSpacing(10)

        self._ring_issue = _ProgressRing("Issue 闭环率", DASH_PRIMARY)
        self._ring_capa  = _ProgressRing("CAPA 完成率", DASH_SUCCESS)

        self._ring_cards: list[QFrame] = []
        for ring_widget in (self._ring_issue, self._ring_capa):
            card = QFrame()
            card.setProperty("class", "card-bg")
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
        lbl.setProperty("class", "text-bold")  # 主题迁移: class=text-bold
        return lbl

    # ── 刷新 ──────────────────────────────────────────────────

    def refresh(self, data: DashboardData | None = None, **kwargs: object) -> None:
        if data is None:
            data = DashboardData(**kwargs)

        # Header
        self._update_filter(data.project_name, data.plan_name)
        ctx_plan = f"{data.project_name or '全部项目'}{' / ' + data.plan_name if data.plan_name else ''}"
        self._ctx_label_left.setText(ctx_plan)
        ctx_project = data.project_name or '全部项目'
        self._ctx_label_right.setText(ctx_project)
        self._time_label.setText(
            f"最后更新：{data.last_update}" if data.last_update else ""
        )

        # 测试进度卡片 — 基于任务状态计数（不混结果数）
        # 绿=已完成, 红=失败, 黄=进行中, 灰=待开始, 蓝=跳过, 紫=暂停
        self._health.refresh(
            total=data.task_total or 0,
            completed=data.task_completed or 0,
            failed=data.failed_task_count or 0,
            in_progress=data.task_in_progress or 0,
            pending=data.task_pending or 0,
            skipped=data.task_skipped or 0,
            paused=data.task_paused or 0,
            pass_rate=data.pass_rate,
            last_update=data.last_update,
        )

        # 左栏 KPI
        self._card_done.set_value(str(data.task_completed))
        self._card_active.set_value(str(data.task_in_progress))
        self._card_wait.set_value(str(data.task_pending))
        self._card_fail.set_value(str(data.failed_task_count or 0))

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

        # Bug Tracker 4 指标
        self._card_pending.set_value(str(data.pending_count))
        self._card_week_close.set_value(str(data.weekly_closed))
        self._card_avg_age.set_value(f"{data.avg_age_days:.0f}天" if data.avg_age_days else "—")
        self._card_aging.set_value(str(data.aging_warning_count))

        # 进度环
        ic = data.issue_count or 0
        icc = data.issue_closed_count or 0
        self._ring_issue.setPercent(icc / ic * 100 if ic else 0)
        self._ring_capa.setPercent(cr if cr is not None else 0)

    def _update_filter(self, project_name: str | None, plan_name: str | None) -> None:
        # DYNAMIC: 根据筛选状态切换两种视觉风格（默认 vs 激活），无法走单一 class 选择器
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
