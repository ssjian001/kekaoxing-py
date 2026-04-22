"""Stats Panel — 统计概览面板

A compact horizontal stats bar that sits between the search bar and the
Gantt chart.  Displays key metrics computed from the current task list:

    📋 Total / completed tasks
    📅 Estimated total duration (max of start_day + duration)
    📊 Overall progress (mean task progress %)
    🔧 Bottleneck device count
    🏷️ Section (category) count

Follows the Catppuccin Mocha dark theme used throughout the application.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# ═══════════════════════════════════════════════════════════════════════
#  Catppuccin Mocha palette
# ═══════════════════════════════════════════════════════════════════════

COL_BG: str = "#181825"
COL_VALUE: str = "#cdd6f4"
COL_LABEL: str = "#6c7086"
COL_BORDER: str = "#313244"

PANEL_HEIGHT: int = 60
BORDER_RADIUS: int = 8


class _StatItem(QFrame):
    """Single stat card: icon + big value + small description."""

    def __init__(self, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_label = QLabel(icon)
        self._value_label = QLabel("—")
        self._desc_label = QLabel("")
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setFixedHeight(PANEL_HEIGHT)
        self.setStyleSheet(
            f"""
            _StatItem {{
                background: {COL_BG};
                border: 1px solid {COL_BORDER};
                border-radius: {BORDER_RADIUS}px;
            }}
            """
        )

        # Icon
        self._icon_label.setFixedSize(28, 28)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 20px; background: transparent; border: none;")

        # Value (big number)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(
            f"color: {COL_VALUE}; background: transparent; border: none;"
        )
        self._value_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))

        # Description (small text)
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_label.setStyleSheet(
            f"color: {COL_LABEL}; background: transparent; border: none;"
        )
        self._desc_label.setFont(QFont("Microsoft YaHei", 9))

        # Layout: left column (icon) | right column (value + desc)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        text_col.addWidget(self._value_label)
        text_col.addWidget(self._desc_label)

        outer.addWidget(self._icon_label)
        outer.addLayout(text_col, stretch=1)

    # ── Public API ─────────────────────────────────────────────────────

    def set_data(self, value: str, description: str) -> None:
        """Update the displayed value and description text."""
        self._value_label.setText(value)
        self._desc_label.setText(description)


class StatsPanel(QWidget):
    """Horizontal stats bar showing project overview metrics.

    Usage::

        panel = StatsPanel()
        panel.update_stats(tasks, sections, bottleneck_count=3)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: dict[str, _StatItem] = {}
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        definitions = [
            ("tasks",     "📋", "总任务数 / 已完成"),
            ("duration",  "📅", "预计总工期"),
            ("progress",  "📊", "整体进度"),
            ("bottleneck","🔧", "瓶颈设备"),
            ("sections",  "🏷️", "分类数量"),
        ]

        for key, icon, _ in definitions:
            item = _StatItem(icon)
            self._items[key] = item
            layout.addWidget(item)

        layout.addStretch()

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _get_field(obj, name: str, default=0):
        """Safely read *name* from a dict **or** an object."""
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    # ── Public API ─────────────────────────────────────────────────────

    def update_stats(
        self,
        tasks: list,
        sections: list,
        bottleneck_count: int = 0,
    ) -> None:
        """Recalculate and display statistics from the given data.

        Parameters
        ----------
        tasks : list
            List of task dicts/objects.  Each must expose at least:
            ``start_day``, ``duration``, ``progress``, ``done``.
        sections : list
            List of section/category entries (length is used).
        bottleneck_count : int
            Pre-computed number of bottleneck devices (default 0).
        """
        # ── 1. Total / completed tasks ─────────────────────────────────
        total = len(tasks)
        completed = sum(
            1 for t in tasks
            if self._get_field(t, "done", False)
        )
        self._items["tasks"].set_data(
            f"{completed} / {total}",
            "总任务数 / 已完成",
        )

        # ── 2. Estimated total duration ────────────────────────────────
        max_end = 0
        for t in tasks:
            sd = self._get_field(t, "start_day", 0)
            dur = self._get_field(t, "duration", 0)
            max_end = max(max_end, sd + dur)
        self._items["duration"].set_data(f"{max_end} 天", "预计总工期")

        # ── 3. Overall progress ────────────────────────────────────────
        if total:
            prog_sum = sum(
                self._get_field(t, "progress", 0)
                for t in tasks
            )
            avg_prog = prog_sum / total
        else:
            avg_prog = 0.0
        self._items["progress"].set_data(f"{avg_prog:.1f}%", "整体进度")

        # ── 4. Bottleneck devices ──────────────────────────────────────
        self._items["bottleneck"].set_data(str(bottleneck_count), "瓶颈设备")

        # ── 5. Section count ───────────────────────────────────────────
        self._items["sections"].set_data(str(len(sections)), "分类数量")
