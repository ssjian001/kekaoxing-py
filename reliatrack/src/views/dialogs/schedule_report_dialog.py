"""排程报告对话框 — 展示排程结果摘要、设备利用率图表、瓶颈和建议。"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.constants import (
    BASE,
    BLUE,
    CRUST,
    GREEN,
    LAVENDER,
    MAUVE,
    PEACH,
    RED,
    SUBTEXT0,
    SUBTEXT1,
    SURFACE0,
    SURFACE1,
    SURFACE2,
    TEXT,
    YELLOW,
    FONT_FAMILY,
)

# ── 利用率条形图 ──────────────────────────────────────────


class _UtilBarChart(QWidget):
    """设备利用率横向条形图。"""

    _BAR_H = 20
    _LABEL_W = 120
    _SPACING = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[dict] = []
        self.setMinimumHeight(60)

    def set_data(self, utilization: list[dict]) -> None:
        """设置利用率数据 [{name, total_slots, used_slots, utilization}, ...]。"""
        # 按利用率降序
        self._data = sorted(utilization, key=lambda x: x.get("utilization", 0), reverse=True)
        h = max(60, len(self._data) * (self._BAR_H + self._SPACING) + 20)
        self.setFixedHeight(h)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._data:
            p = QPainter(self)
            p.setPen(QColor(SUBTEXT0))
            p.setFont(QFont(FONT_FAMILY, 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无设备利用率数据")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        label_w = self._LABEL_W
        chart_w = self.width() - label_w - 40  # 右侧留数字空间

        for i, item in enumerate(self._data):
            y = i * (self._BAR_H + self._SPACING) + 4
            name = item.get("name", "?")
            util = item.get("utilization", 0)

            # 名称标签
            p.setPen(QColor(TEXT))
            p.setFont(QFont(FONT_FAMILY, 10))
            fm = p.fontMetrics()
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, label_w - 8)
            p.drawText(4, y, label_w - 8, self._BAR_H,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, elided)

            # 背景条
            bar_x = label_w
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(SURFACE2))
            p.drawRoundedRect(QRect(bar_x, y, chart_w, self._BAR_H), 4, 4)

            # 利用率条 — 颜色按阈值
            if util >= 80:
                color = QColor(RED)
            elif util >= 60:
                color = QColor(YELLOW)
            else:
                color = QColor(GREEN)
            fill_w = max(0, chart_w * util / 100.0)
            p.setBrush(color)
            p.drawRoundedRect(QRect(bar_x, y, int(fill_w), self._BAR_H), 4, 4)

            # 百分比文字
            p.setPen(QColor(CRUST) if util >= 50 else QColor(TEXT))
            p.setFont(QFont(FONT_FAMILY, 9))
            p.drawText(QRect(bar_x, y, chart_w, self._BAR_H),
                       Qt.AlignmentFlag.AlignCenter, f"{util:.0f}%")

        p.end()


# ── 排程报告对话框 ──────────────────────────────────────────


class ScheduleReportDialog(QDialog):
    """排程结果报告弹窗。"""

    def __init__(self, report: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("排程报告")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        total_days = report.get("total_days", 0)
        original_days = report.get("original_days", 0)
        improvement = report.get("improvement", 0.0)
        task_count = report.get("task_count", 0)
        updated_count = report.get("updated_count", 0)

        # ── 摘要区域 ──
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)

        cards = [
            ("总工期", f"{total_days} 天", BLUE),
            ("优化率", f"{improvement:+.0f}%", GREEN if improvement >= 0 else RED),
            ("任务数", f"{task_count}", MAUVE),
            ("已更新", f"{updated_count}", PEACH),
        ]
        for label, value, color in cards:
            card = QWidget()
            card.setStyleSheet(
                f"background-color: {SURFACE0}; border-radius: 8px; "
                f"border-left: 3px solid {color};"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px;")
            card_layout.addWidget(lbl)
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 18px; font-weight: bold;"
            )
            card_layout.addWidget(val_lbl)
            summary_layout.addWidget(card)

        layout.addLayout(summary_layout)

        # ── 原始工期对比（仅在有差异时显示）──
        if original_days > 0 and original_days != total_days:
            compare = QLabel(
                f"原始工期 {original_days} 天 → 优化后 {total_days} 天 "
                f"（{improvement:+.0f}%）"
            )
            compare.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px; padding: 2px 4px;")
            layout.addWidget(compare)

        # ── 设备利用率图表 ──
        util_label = QLabel("设备利用率")
        util_label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(util_label)

        self._util_chart = _UtilBarChart()
        utilization = report.get("equipment_utilization", [])
        self._util_chart.set_data(utilization)
        layout.addWidget(self._util_chart)

        # ── 瓶颈列表 ──
        bottlenecks = report.get("bottlenecks", [])
        if bottlenecks:
            bn_label = QLabel("瓶颈设备（利用率 > 80%）")
            bn_label.setStyleSheet(
                f"color: {RED}; font-size: 13px; font-weight: bold;"
            )
            layout.addWidget(bn_label)
            for bn in bottlenecks[:5]:
                row = QLabel(
                    f"  {bn.get('name', '?')} — {bn.get('utilization', 0):.0f}%"
                )
                row.setStyleSheet(
                    f"color: {TEXT}; font-size: 12px; "
                    f"background-color: {SURFACE0}; border-radius: 4px; "
                    f"padding: 4px 8px;"
                )
                layout.addWidget(row)

        # ── 建议 ──
        suggestions = report.get("suggestions", [])
        if suggestions:
            sug_label = QLabel("排程建议")
            sug_label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: bold;")
            layout.addWidget(sug_label)
            for sug in suggestions:
                row = QLabel(sug)
                row.setWordWrap(True)
                row.setStyleSheet(
                    f"color: {SUBTEXT0}; font-size: 12px; "
                    f"background-color: {SURFACE0}; border-radius: 4px; "
                    f"padding: 6px 8px;"
                )
                layout.addWidget(row)

        layout.addStretch()

        # ── 关闭按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setProperty("class", "primary")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
