"""测试计划视图 — 失效模式分析组件。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter

import src.styles.theme as _t
from src.styles.theme import (
    BASE, SURFACE0, SURFACE1,
    TEXT, SUBTEXT1,
    GREEN, RED, YELLOW,
    SELECTION_BG,
)
from src.styles.constants import FONT_SIZE_SMALL, TABLE_QSS, apply_column_specs
from src.models.test_plan import TestTask


class _BarWidget(QWidget):
    """水平进度条 — 用于按类别通过率展示。"""

    def __init__(self, value: float, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = value  # 0-100
        self._color = color
        self.setFixedHeight(18)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景
        p.fillRect(0, 0, w, h, QColor(SURFACE1))

        # 前景条
        bar_w = int(w * self._value / 100.0)
        if bar_w > 0:
            p.fillRect(0, 0, bar_w, h, QColor(self._color))

        # 文字
        p.setPen(QColor(TEXT))
        p.setFont(p.font())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self._value:.0f}%")
        p.end()


class _AnalysisWidget(QWidget):
    """失效模式分析 — 按类别统计 + 失效 Top-N + 未关联 Issue。

    采用纯重建模式：__init__ 只创建空 layout，所有内容由 refresh()
    按需创建。避免实例成员 widget 与渲染生命周期冲突导致的僵尸引用。
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(12)

        # 初始占位
        ph = self._make_placeholder("选择测试计划后显示失效模式分析")
        self._layout.addWidget(ph)
        _t.theme_host.theme_changed.connect(self._refresh_theme)

    def _refresh_theme(self) -> None:
        """主题切换时刷新所有子表格的 TABLE_QSS。"""
        for tbl in self.findChildren(QTableWidget):
            tbl.setStyleSheet(TABLE_QSS.format(
                bg=_t.BASE, text=_t.TEXT, gridline=_t.SURFACE1,
                alt_row=_t.SURFACE0, header_bg=_t.SURFACE0, header_text=_t.TEXT,
                font_size=13, selection_bg=_t.SELECTION_BG,
            ))

    # ── 工厂方法（每次 refresh 创建新实例） ──────────────

    @staticmethod
    def _make_placeholder(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px; padding: 24px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def refresh(
        self,
        tasks: list[TestTask],
        results: list | None = None,
        issues: list | None = None,
        sample_map: dict[int, str] | None = None,
    ) -> None:
        """根据数据更新分析视图（完全重建）。"""
        results = results or []
        issues = issues or []
        sample_map = sample_map or {}

        # 清空旧内容（包括 spacer）
        self._rebuild_layout()

        if not tasks:
            self._layout.addWidget(
                self._make_placeholder("选择测试计划后显示失效模式分析")
            )
            return

        # 按 task_id 收集结果
        task_results: dict[int, list] = {}
        for r in results:
            if r.task_id:
                task_results.setdefault(r.task_id, []).append(r)

        # 按 task_id 收集 Issue
        task_issues: dict[int, list] = {}
        for iss in issues:
            if iss.task_id:
                task_issues.setdefault(iss.task_id, []).append(iss)

        # ── 区块 1: 按类别统计 ──
        category_stats: dict[str, dict[str, int]] = {}
        for task in tasks:
            cat = task.category or "未分类"
            if cat not in category_stats:
                category_stats[cat] = {"pass": 0, "fail": 0, "total": 0}
            if task.id is not None and task.id in task_results:
                for r in task_results[task.id]:
                    if r.result in ("pass", "fail", "conditional"):
                        category_stats[cat]["total"] += 1
                        if r.result == "pass":
                            category_stats[cat]["pass"] += 1
                        elif r.result == "fail":
                            category_stats[cat]["fail"] += 1

        if category_stats:
            section_label = QLabel("按类别通过率")
            section_label.setStyleSheet(f"color: {TEXT}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold;")
            self._layout.addWidget(section_label)

            for cat, stats in category_stats.items():
                row = QHBoxLayout()
                row.setSpacing(8)
                cat_label = QLabel(cat)
                cat_label.setFixedWidth(80)
                cat_label.setStyleSheet(f"color: {TEXT}; font-size: {FONT_SIZE_SMALL}px;")
                row.addWidget(cat_label)

                rate = stats["pass"] / stats["total"] * 100 if stats["total"] > 0 else 0
                color = GREEN if rate >= 80 else YELLOW if rate >= 50 else RED
                bar = _BarWidget(rate, color)
                bar.setFixedHeight(18)
                row.addWidget(bar, stretch=1)

                detail = QLabel(f"{stats['pass']}/{stats['total']}")
                detail.setFixedWidth(50)
                detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                detail.setStyleSheet(f"color: {SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px;")
                row.addWidget(detail)

                self._layout.addLayout(row)

        # ── 区块 2: 失效 Top-N ──
        fail_entries: list[dict] = []
        for task in tasks:
            if task.id is None or task.id not in task_results:
                continue
            for r in task_results[task.id]:
                if r.result == "fail":
                    has_issue = task.id in task_issues
                    fail_entries.append({
                        "task_name": task.name,
                        "category": task.category or "-",
                        "sample_sn": sample_map.get(r.sample_id, f"#{r.sample_id}") if r.sample_id else "-",
                        "issue_count": len(task_issues.get(task.id, [])),
                        "has_issue": has_issue,
                        "severity": task_issues[task.id][0].severity if has_issue and task_issues[task.id] else "-",
                    })

        if fail_entries:
            section2 = QLabel(f"失效详情 ({len(fail_entries)} 条)")
            section2.setStyleSheet(f"color: {TEXT}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold;")
            self._layout.addWidget(section2)

            tbl = QTableWidget(len(fail_entries), 5)
            tbl.setStyleSheet(TABLE_QSS.format(
                bg=BASE, text=TEXT, gridline=SURFACE1,
                alt_row=SURFACE0, header_bg=SURFACE0, header_text=TEXT,
                font_size=13,
                            selection_bg=SELECTION_BG,
                        ))
            tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            tbl.verticalHeader().setVisible(False)
            tbl.setHorizontalHeaderLabels(["任务", "类别", "样品", "Issue", "严重度"])
            apply_column_specs(tbl, [
                ("任务", "stretch", 0),
                ("类别", "fixed", 80),
                ("样品", "fixed", 80),
                ("Issue", "fixed", 60),
                ("严重度", "fixed", 70),
            ])

            for row, entry in enumerate(fail_entries):
                tbl.setItem(row, 0, self._make_item(entry["task_name"], TEXT))
                tbl.setItem(row, 1, self._make_item(entry["category"], SUBTEXT1))
                tbl.setItem(row, 2, self._make_item(entry["sample_sn"], SUBTEXT1))
                if entry["has_issue"]:
                    issue_item = self._make_item(f"{entry['issue_count']}个", GREEN)
                else:
                    issue_item = self._make_item("未创建", RED)
                tbl.setItem(row, 3, issue_item)
                sev = entry["severity"]
                sev_color = RED if sev == "critical" else YELLOW if sev == "major" else SUBTEXT1
                tbl.setItem(row, 4, self._make_item(sev, sev_color))

            self._layout.addWidget(tbl)

        # ── 区块 3: 未关联 Issue ──
        unlinked = [e for e in fail_entries if not e["has_issue"]]
        if unlinked:
            names = ", ".join(f'{e["task_name"]}/{e["sample_sn"]}' for e in unlinked[:8])
            if len(unlinked) > 8:
                names += f" ... 共 {len(unlinked)} 条"
            warn = QLabel(f"{len(unlinked)} 条失败结果未创建 Issue: {names}")
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {YELLOW}; font-size: {FONT_SIZE_SMALL}px; padding: 4px 8px;")
            self._layout.addWidget(warn)

        # 没有任何结果
        if not category_stats and not fail_entries:
            no_data = QLabel("暂无测试结果数据")
            no_data.setStyleSheet(f"color: {SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px; padding: 24px;")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(no_data)

        self._layout.addStretch()

    # ── 内部工具 ──────────────────────────────────────

    def _rebuild_layout(self) -> None:
        """完全清空 layout 中所有项目（widget/layout/spacer），为重建做准备。"""
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
                continue
            sub = item.layout()
            if sub:
                self._clear_sub_layout(sub)
                sub.setParent(None)  # type: ignore[arg-type]
                sub.deleteLater()  # type: ignore[attr-defined]
            # QSpacerItem: takeAt 转移所有权给调用者，直接丢弃即可

    @staticmethod
    def _clear_sub_layout(layout) -> None:
        """递归清空子 layout 中的所有 widget。"""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                _AnalysisWidget._clear_sub_layout(item.layout())
                item.layout().deleteLater()

    @staticmethod
    def _make_item(text: str, fg: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QColor(fg))
        return item
