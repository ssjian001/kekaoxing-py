"""Resource Timeline Heatmap — 设备利用率时间线热力图

A self-contained QWidget that visualises day-by-day equipment utilisation
as a colour-coded heatmap grid.  Each row is one piece of equipment; each
column is one calendar day.  Cell colour encodes the utilisation ratio
(used / available):

    0 %       → dark     (#1e1e2e)
    1 – 50 %  → green    (#a6e3a1)
    51 – 80 % → yellow   (#f9e2af)
    81 – 100 %→ orange   (#fab387)
    > 100 %   → red      (#f38ba8)

Painted entirely with QPainter (no child widgets for the grid).
Follows the Catppuccin Mocha dark theme used throughout the application.
"""

from __future__ import annotations

from typing import Optional
from datetime import date, timedelta

from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPen

from src.models import Resource, ResourceType

# ═══════════════════════════════════════════════════════════════════════
#  Layout constants
# ═══════════════════════════════════════════════════════════════════════

CELL_WIDTH: int = 36       # 每天单元格宽度 (px)
CELL_HEIGHT: int = 28      # 每行设备单元格高度 (px)
HEADER_HEIGHT: int = 30    # 日期标题行高度 (px)
LABEL_WIDTH: int = 150     # 左侧设备名称列宽度 (px)

# ═══════════════════════════════════════════════════════════════════════
#  Catppuccin Mocha palette
# ═══════════════════════════════════════════════════════════════════════

COL_BG: str = "#11111b"       # 整体背景
COL_HEADER_BG: str = "#181825"  # 标题行背景
COL_GRID: str = "#313244"     # 网格线
COL_TEXT: str = "#cdd6f4"     # 主文字
COL_LABEL: str = "#a6adc8"    # 设备名称标签

# 热力图色阶 — 按利用率区间
COL_EMPTY: str = "#1e1e2e"       # 0 % (未使用)
COL_LOW: str = "#a6e3a1"         # 1 – 50 %
COL_MED: str = "#f9e2af"         # 51 – 80 %
COL_HIGH: str = "#fab387"        # 81 – 100 %
COL_OVER: str = "#f38ba8"        # > 100 % (超载)


class ResourceTimeline(QWidget):
    """Equipment utilisation heatmap widget.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget.

    Usage
    -----
    >>> widget = ResourceTimeline()
    >>> widget.set_data(timeline, resources, total_days)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # ── Data stores ────────────────────────────────────────────
        self._start_date: date = date.today()

        self._timeline: dict[int, dict[str, int]] = {}
        self._resources: list[Resource] = []        # equipment only
        self._total_days: int = 30

        # Build lookup from resource-key ("eq_{id}") → Resource
        self._eq_map: dict[str, Resource] = {}

        # ── Dynamic cell width (synced with GanttCanvas zoom) ─────
        self._cell_width: int = CELL_WIDTH

        # ── Hover tracking ─────────────────────────────────────────
        self._hover_day: int = -1
        self._hover_row: int = -1

        # ── Widget setup ───────────────────────────────────────────
        self.setMouseTracking(True)
        self.setMinimumHeight(HEADER_HEIGHT + 3 * CELL_HEIGHT)

    # ───────────────────────────────────────────────────────────────
    #  Public API
    # ───────────────────────────────────────────────────────────────

    def set_data(
        self,
        timeline: dict[int, dict[str, int]],
        resources: list[Resource],
        total_days: int,
    ) -> None:
        """Update the heatmap with new scheduling data.

        Parameters
        ----------
        timeline : dict[int, dict[str, int]]
            ``day → resource_key → qty_used`` as produced by the scheduler.
        resources : list[Resource]
            All resources; only ``ResourceType.EQUIPMENT`` entries are shown.
        total_days : int
            Total number of calendar days in the schedule.
        """
        self._timeline = timeline
        self._resources = [r for r in resources if r.type == ResourceType.EQUIPMENT]
        self._total_days = max(total_days, 1)

        # Rebuild key → Resource lookup
        self._eq_map = {f"eq_{r.id}": r for r in self._resources}

        # Resize widget to fit content — use minimum so it can be stretched
        cw = self._cell_width
        grid_w = LABEL_WIDTH + self._total_days * cw + 1
        grid_h = HEADER_HEIGHT + len(self._resources) * CELL_HEIGHT + 1
        self.setMinimumSize(grid_w, grid_h)

        self.update()

    def set_start_date(self, d: date) -> None:
        """Set the calendar date corresponding to day index 0."""
        self._start_date = d
        self.update()

    def date_for_day(self, day: int) -> date:
        """Return the real calendar date for a given day index."""
        return self._start_date + timedelta(days=day)

    # ───────────────────────────────────────────────────────────────
    #  Colour helpers
    # ───────────────────────────────────────────────────────────────

    @staticmethod
    def _colour_for_ratio(ratio: float) -> QColor:
        """Return a heatmap colour for a utilisation ratio.

        Parameters
        ----------
        ratio : float
            ``used / available``.  Can be zero or exceed 1.0 (overloaded).

        Returns
        -------
        QColor
        """
        if ratio <= 0:
            return QColor(COL_EMPTY)
        if ratio <= 0.50:
            return QColor(COL_LOW)
        if ratio <= 0.80:
            return QColor(COL_MED)
        if ratio <= 1.00:
            return QColor(COL_HIGH)
        return QColor(COL_OVER)

    @staticmethod
    def _text_colour_for_ratio(ratio: float) -> QColor:
        """Return a readable text colour (dark or light) for the cell.

        Uses dark text on bright cells (green/yellow) and light text
        on dark cells (empty/overloaded).
        """
        if ratio <= 0 or ratio > 1.0:
            return QColor(COL_TEXT)
        # For low/med/high bands use dark text for contrast
        return QColor("#1e1e2e")

    # ───────────────────────────────────────────────────────────────
    #  Painting
    # ───────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # ── Background ─────────────────────────────────────────────
        p.fillRect(0, 0, w, h, QColor(COL_BG))

        # ── Header row background ──────────────────────────────────
        p.fillRect(0, 0, w, HEADER_HEIGHT, QColor(COL_HEADER_BG))

        # ── Fonts ──────────────────────────────────────────────────
        font_header = QFont("Microsoft YaHei", 8)
        font_header.setBold(True)
        font_cell = QFont("Microsoft YaHei", 8)
        font_label = QFont("Microsoft YaHei", 9)
        font_label.setBold(False)

        num_resources = len(self._resources)
        total_days = self._total_days

        # ── Day header labels ──────────────────────────────────────
        p.setFont(font_header)
        p.setPen(QColor(COL_LABEL))

        # "Day" header for the label column
        p.drawText(
            QRect(0, 0, LABEL_WIDTH, HEADER_HEIGHT),
            Qt.AlignCenter,
            "设备 / 天",
        )

        for d in range(total_days):
            x = LABEL_WIDTH + d * self._cell_width
            if x > w:
                break
            dt = self.date_for_day(d)
            cw = self._cell_width
            p.setPen(QColor(COL_LABEL))
            p.drawText(QRect(x + 1, 2, cw - 2, 14), Qt.AlignCenter, f"{dt.month}/{dt.day}")
            if cw >= 40:
                wd = ["一","二","三","四","五","六","日"][dt.weekday()]
                p.setPen(QColor("#6c7086"))
                p.drawText(QRect(x + 1, 14, cw - 2, 14), Qt.AlignCenter, f"周{wd}")
                p.setPen(QColor(COL_TEXT))

        # ── Separator line below header ────────────────────────────
        pen_sep = QPen(QColor(COL_GRID), 1)
        p.setPen(pen_sep)
        p.drawLine(0, HEADER_HEIGHT, w, HEADER_HEIGHT)

        # ── Equipment rows ─────────────────────────────────────────
        for row_idx, resource in enumerate(self._resources):
            y = HEADER_HEIGHT + row_idx * CELL_HEIGHT
            resource_key = f"eq_{resource.id}"
            available = resource.available_qty

            # ── Label column ───────────────────────────────────────
            # Slightly tinted label background for alternating rows
            if row_idx % 2 == 1:
                p.fillRect(0, y, LABEL_WIDTH, CELL_HEIGHT, QColor("#181825"))

            p.setFont(font_label)
            p.setPen(QColor(COL_LABEL))

            # Show icon + name, truncate if too long
            label_text = f"{resource.icon} {resource.name}"
            label_rect = QRect(4, y, LABEL_WIDTH - 8, CELL_HEIGHT)
            p.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, label_text)

            # ── Vertical separator after label column ──────────────
            p.setPen(pen_sep)
            p.drawLine(LABEL_WIDTH, y, LABEL_WIDTH, y + CELL_HEIGHT)

            # ── Day cells ──────────────────────────────────────────
            for d in range(total_days):
                x = LABEL_WIDTH + d * self._cell_width
                if x > w:
                    break

                # Get usage for this day + resource
                day_usage = self._timeline.get(d, {})
                used = day_usage.get(resource_key, 0)
                # Weekend column highlight
                if self.date_for_day(d).weekday() >= 5:
                    grid_h = CELL_HEIGHT * num_resources
                    p.fillRect(QRect(x, HEADER_HEIGHT, cw, grid_h), QColor("#18182580"))

                # Utilisation ratio (handle 0 availability guard)
                ratio = (used / available) if available > 0 else (1.0 if used > 0 else 0.0)

                # Alternating row tint behind cell (subtle)
                if row_idx % 2 == 1 and ratio <= 0:
                    p.fillRect(x + 1, y + 1, self._cell_width - 1, CELL_HEIGHT - 1, QColor("#181825"))

                # Cell fill colour based on utilisation
                cell_colour = self._colour_for_ratio(ratio)
                cell_rect = QRect(x + 1, y + 1, self._cell_width - 1, CELL_HEIGHT - 1)
                p.fillRect(cell_rect, cell_colour)

                # Cell text: "used/avail"
                if used > 0 or ratio > 0:
                    p.setFont(font_cell)
                    p.setPen(self._text_colour_for_ratio(ratio))
                    cell_text = f"{used}/{available}"
                    p.drawText(cell_rect, Qt.AlignCenter, cell_text)

                # Grid border
                p.setPen(pen_sep)
                p.drawRect(cell_rect)

        # ── Hover highlight ────────────────────────────────────────
        if 0 <= self._hover_day < total_days and 0 <= self._hover_row < num_resources:
            hx = LABEL_WIDTH + self._hover_day * self._cell_width
            hy = HEADER_HEIGHT + self._hover_row * CELL_HEIGHT
            highlight_rect = QRect(hx, hy, self._cell_width, CELL_HEIGHT)
            p.setPen(QPen(QColor("#cdd6f4"), 2))
            p.drawRect(highlight_rect)

        p.end()

    # ───────────────────────────────────────────────────────────────
    #  Mouse interaction — hover / tooltip
    # ───────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event) -> None:
        """Track hover position and show a tooltip with usage details."""
        mx = event.position().x()
        my = event.position().y()

        # Determine which cell the cursor is over
        day = (mx - LABEL_WIDTH) // self._cell_width
        row = (my - HEADER_HEIGHT) // CELL_HEIGHT

        if mx < LABEL_WIDTH or my < HEADER_HEIGHT:
            # Cursor is in the label area or header — clear hover
            if self._hover_day != -1 or self._hover_row != -1:
                self._hover_day = -1
                self._hover_row = -1
                self.update()
            QToolTip.hideText()
            return

        if day < 0 or day >= self._total_days or row < 0 or row >= len(self._resources):
            if self._hover_day != -1 or self._hover_row != -1:
                self._hover_day = -1
                self._hover_row = -1
                self.update()
            QToolTip.hideText()
            return

        # Update hover state
        changed = (day != self._hover_day or row != self._hover_row)
        self._hover_day = day
        self._hover_row = row

        if changed:
            self.update()

        # Build tooltip
        resource = self._resources[row]
        resource_key = f"eq_{resource.id}"
        available = resource.available_qty
        used = self._timeline.get(day, {}).get(resource_key, 0)
        ratio = (used / available * 100) if available > 0 else (100.0 if used > 0 else 0.0)

        # Status label
        if ratio <= 0:
            status = "空闲"
        elif ratio <= 50:
            status = "正常"
        elif ratio <= 80:
            status = "较忙"
        elif ratio <= 100:
            status = "繁忙"
        else:
            status = "⚠️ 超载"

        dt = self.date_for_day(day)
        week_label = ["一","二","三","四","五","六","日"][dt.weekday()]
        tooltip = (
            f"📅 {dt.isoformat()} 周{week_label}\n"
            f"🔧 {resource.icon} {resource.name}\n"
            f"使用: {used} / {available} {resource.unit}\n"
            f"利用率: {ratio:.0f}%  {status}"
        )
        QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)

    def leaveEvent(self, event) -> None:
        """Clear hover state when cursor leaves the widget."""
        self._hover_day = -1
        self._hover_row = -1
        QToolTip.hideText()
        self.update()
