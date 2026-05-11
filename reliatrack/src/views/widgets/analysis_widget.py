"""测试计划视图 — 失效模式分析组件。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen

from src.styles.theme import (
    BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    GREEN, RED, YELLOW,
)
from src.styles.constants import FONT_FAMILY, TABLE_QSS
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
    """失效模式分析 — 按类别统计 + 失效 Top-N + 未关联 Issue。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(12)

        # 占位
        self._placeholder = QLabel("选择测试计划后显示失效模式分析")
        self._placeholder.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px; padding: 24px;")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._placeholder)

        # 按类别统计区
        self._category_section = QLabel()
        self._category_section.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        self._category_layout = QVBoxLayout()
        self._category_layout.setSpacing(4)

        # 失效 Top-N 表格
        self._fail_table = QTableWidget()
        self._fail_table.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=SURFACE0, header_bg=SURFACE0, header_text=TEXT,
            font_size=11,
        ))
        self._fail_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._fail_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._fail_table.verticalHeader().setVisible(False)
        self._fail_table.horizontalHeader().setStretchLastSection(True)

        # 未关联 Issue 提示
        self._unlinked_label = QLabel()
        self._unlinked_label.setWordWrap(True)
        self._unlinked_label.setStyleSheet(f"color: {YELLOW}; font-size: 11px; padding: 4px 8px;")

    def refresh(
        self,
        tasks: list[TestTask],
        results: list,
        issues: list,
        sample_map: dict[int, str] | None = None,
    ) -> None:
        """根据数据更新分析视图。

        Args:
            tasks: 任务列表
            results: TestResult 列表
            issues: Issue 列表（当前计划关联的）
            sample_map: {sample_id: sn}
        """
        # 清空旧内容
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # 递归清空子 layout
                self._clear_layout(item.layout())

        sample_map = sample_map or {}

        if not tasks:
            self._layout.addWidget(self._placeholder)
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
        category_stats: dict[str, dict[str, int]] = {}  # {category: {pass, fail, total}}
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
            section_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
            self._layout.addWidget(section_label)

            for cat, stats in category_stats.items():
                row = QHBoxLayout()
                row.setSpacing(8)
                cat_label = QLabel(cat)
                cat_label.setFixedWidth(80)
                cat_label.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
                row.addWidget(cat_label)

                if stats["total"] > 0:
                    rate = stats["pass"] / stats["total"] * 100
                else:
                    rate = 0
                color = GREEN if rate >= 80 else YELLOW if rate >= 50 else RED
                bar = _BarWidget(rate, color)
                bar.setFixedHeight(18)
                row.addWidget(bar, stretch=1)

                detail = QLabel(f"{stats['pass']}/{stats['total']}")
                detail.setFixedWidth(50)
                detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                detail.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px;")
                row.addWidget(detail)

                self._layout.addLayout(row)

        # ── 区块 2: 失效 Top-N ──
        # 收集所有 fail 结果
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
            section2.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
            self._layout.addWidget(section2)

            self._fail_table.setRowCount(len(fail_entries))
            self._fail_table.setColumnCount(5)
            self._fail_table.setHorizontalHeaderLabels(
                ["任务", "类别", "样品", "Issue", "严重度"]
            )
            header = self._fail_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for c in range(1, 5):
                header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
                widths = [0, 80, 80, 60, 70]
                self._fail_table.setColumnWidth(c, widths[c])

            for row, entry in enumerate(fail_entries):
                self._fail_table.setItem(row, 0, self._make_item(entry["task_name"], TEXT))
                self._fail_table.setItem(row, 1, self._make_item(entry["category"], SUBTEXT1))
                self._fail_table.setItem(row, 2, self._make_item(entry["sample_sn"], SUBTEXT1))
                if entry["has_issue"]:
                    issue_item = self._make_item(f"{entry['issue_count']}个", GREEN)
                else:
                    issue_item = self._make_item("未创建", RED)
                self._fail_table.setItem(row, 3, issue_item)
                sev = entry["severity"]
                sev_color = RED if sev == "critical" else YELLOW if sev == "major" else SUBTEXT1
                self._fail_table.setItem(row, 4, self._make_item(sev, sev_color))

            self._layout.addWidget(self._fail_table)

        # ── 区块 3: 未关联 Issue ──
        unlinked = [e for e in fail_entries if not e["has_issue"]]
        if unlinked:
            names = ", ".join(f'{e["task_name"]}/{e["sample_sn"]}' for e in unlinked[:8])
            if len(unlinked) > 8:
                names += f" ... 共 {len(unlinked)} 条"
            self._unlinked_label.setText(
                f"⚠ {len(unlinked)} 条失败结果未创建 Issue: {names}"
            )
            self._layout.addWidget(self._unlinked_label)

        # 没有任何结果
        if not category_stats and not fail_entries:
            no_data = QLabel("暂无测试结果数据")
            no_data.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px; padding: 24px;")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(no_data)

        self._layout.addStretch()

    @staticmethod
    def _make_item(text: str, fg: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QColor(fg))
        return item

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                _AnalysisWidget._clear_layout(item.layout())
