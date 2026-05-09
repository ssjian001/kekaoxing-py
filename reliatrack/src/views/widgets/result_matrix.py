"""测试计划视图 — 结果矩阵组件。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.styles.theme import (
    MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    GREEN, RED, YELLOW,
)
from src.styles.constants import FONT_FAMILY, TABLE_QSS

from src.models.test_plan import TestTask

class _ResultMatrixWidget(QWidget):
    """任务×样品 的 pass/fail 结果矩阵。

    行 = 测试任务（task），列 = 样品（sample）。
    单元格显示 pass/fail/conditional/pending/skip，着色区分。
    末列 = 行统计（通过率），末行 = 列统计（各样品通过率）。
    """

    _RESULT_COLORS: dict[str, str] = {
        "pass": GREEN,
        "fail": RED,
        "conditional": YELLOW,
        "pending": SURFACE2,
        "skip": SUBTEXT0,
    }

    _RESULT_LABELS: dict[str, str] = {
        "pass": "P",
        "fail": "F",
        "conditional": "C",
        "pending": "—",
        "skip": "S",
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=12,
        ))
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(True)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setStyleSheet(self._table.styleSheet() + f"""
            QTableWidget::item {{
                padding: 0px;
            }}
        """)
        self._layout.addWidget(self._table)

        # 统计摘要行
        self._summary_label = QLabel("选择测试计划后显示结果矩阵")
        self._summary_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px; padding: 4px 8px;")
        self._layout.addWidget(self._summary_label)

    def _make_stat_item(self, text: str, fg: str, bg_alpha: int = 30) -> QTableWidgetItem:
        """创建统计单元格。"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor(fg))
        bg = QColor(fg)
        bg.setAlpha(bg_alpha)
        item.setBackground(bg)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        return item

    def refresh(
        self,
        tasks: list[TestTask],
        results: list,
        sample_map: dict[int, str],
    ) -> None:
        """根据任务和结果重建矩阵。

        Args:
            tasks: 任务列表
            results: TestResult 列表
            sample_map: {sample_id: sn}
        """
        if not tasks:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            self._summary_label.setText("当前计划无测试任务")
            return

        # 收集所有涉及到的 sample_id（按 id 排序）
        sample_ids_set: set[int] = set()
        for r in results:
            if r.sample_id is not None:
                sample_ids_set.add(r.sample_id)
        sample_ids = sorted(sample_ids_set)

        # 构建 (task_id, sample_id) → result 的映射
        lookup: dict[tuple[int, int], str] = {}
        for r in results:
            if r.task_id and r.sample_id is not None:
                lookup[(r.task_id, r.sample_id)] = r.result

        # 建立行映射 task_id → row
        task_id_to_row: dict[int, int] = {}
        for i, t in enumerate(tasks):
            if t.id is not None:
                task_id_to_row[t.id] = i

        # 设置表格：+1 列(行统计), +1 行(列统计)
        rows = len(tasks) + 1  # 末行为列统计
        cols = len(sample_ids) + 2  # 第一列任务名 + 末列行统计

        self._table.setRowCount(rows)
        self._table.setColumnCount(cols)

        # 表头
        headers = ["任务"]
        for sid in sample_ids:
            sn = sample_map.get(sid, f"#{sid}")
            headers.append(sn)
        headers.append("通过率")
        self._table.setHorizontalHeaderLabels(headers)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, cols):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self._table.setColumnWidth(c, 55 if c < cols - 1 else 70)

        # 列统计累加器
        col_stats: dict[int, dict[str, int]] = {sid: {"pass": 0, "total": 0} for sid in sample_ids}
        total_pass = 0
        total_fail = 0
        total_cells = 0

        for row, task in enumerate(tasks):
            # 任务名称
            name_item = QTableWidgetItem(task.name or f"Task#{task.id}")
            name_item.setData(Qt.ItemDataRole.UserRole, task.id)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._table.setVerticalHeaderItem(row, QTableWidgetItem(f"#{row + 1}"))
            self._table.setItem(row, 0, name_item)

            row_pass = 0
            row_total = 0

            for col_idx, sid in enumerate(sample_ids):
                col = col_idx + 1
                tid = task.id
                result_str = lookup.get((tid, sid), "") if tid else ""
                label = self._RESULT_LABELS.get(result_str, "")
                color = self._RESULT_COLORS.get(result_str, SURFACE2)

                item = QTableWidgetItem(label)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, (tid, sid))
                # 着色
                bg_color = QColor(color)
                bg_color.setAlpha(60)
                item.setBackground(bg_color)
                if result_str == "pass":
                    item.setForeground(QColor(GREEN))
                elif result_str == "fail":
                    item.setForeground(QColor(RED))
                else:
                    item.setForeground(QColor(SUBTEXT0))
                self._table.setItem(row, col, item)

                if result_str:
                    total_cells += 1
                    row_total += 1
                    col_stats[sid]["total"] += 1
                    if result_str == "pass":
                        total_pass += 1
                        row_pass += 1
                        col_stats[sid]["pass"] += 1
                    elif result_str == "fail":
                        total_fail += 1

            # 行统计（末列）
            if row_total > 0:
                rate = row_pass / row_total * 100
                fg = GREEN if rate >= 80 else YELLOW if rate >= 50 else RED
                stat = self._make_stat_item(f"{rate:.0f}%", fg)
            else:
                stat = self._make_stat_item("—", SUBTEXT0)
            self._table.setItem(row, cols - 1, stat)

        # 列统计行（末行）
        stat_row = len(tasks)
        self._table.setVerticalHeaderItem(stat_row, QTableWidgetItem(""))
        label_item = self._make_stat_item("合计", TEXT)
        self._table.setItem(stat_row, 0, label_item)

        for col_idx, sid in enumerate(sample_ids):
            col = col_idx + 1
            cs = col_stats[sid]
            if cs["total"] > 0:
                rate = cs["pass"] / cs["total"] * 100
                fg = GREEN if rate >= 80 else YELLOW if rate >= 50 else RED
                stat = self._make_stat_item(f"{rate:.0f}%", fg)
            else:
                stat = self._make_stat_item("—", SUBTEXT0)
            self._table.setItem(stat_row, col, stat)

        # 右下角总计
        if total_cells > 0:
            rate = total_pass / total_cells * 100
            fg = GREEN if rate >= 80 else YELLOW if rate >= 50 else RED
            total_item = self._make_stat_item(f"{total_pass}/{total_cells} ({rate:.0f}%)", fg, bg_alpha=50)
        else:
            total_item = self._make_stat_item("—", SUBTEXT0)
        self._table.setItem(stat_row, cols - 1, total_item)

        # 摘要
        if total_cells > 0:
            rate = total_pass / total_cells * 100
            self._summary_label.setText(
                f"共 {len(tasks)} 项任务 × {len(sample_ids)} 个样品 | "
                f"通过 {total_pass}/{total_cells} ({rate:.0f}%) | "
                f"失败 {total_fail}"
            )
            self._summary_label.setStyleSheet(
                f"color: {GREEN if rate >= 80 else YELLOW if rate >= 50 else RED}; "
                f"font-size: 11px; padding: 4px 8px; font-weight: bold;"
            )
        elif sample_ids:
            self._summary_label.setText(
                f"共 {len(tasks)} 项任务 × {len(sample_ids)} 个样品 — 暂无录入结果"
            )
            self._summary_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px; padding: 4px 8px;")
        else:
            self._summary_label.setText("暂无测试结果数据")
            self._summary_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 11px; padding: 4px 8px;")