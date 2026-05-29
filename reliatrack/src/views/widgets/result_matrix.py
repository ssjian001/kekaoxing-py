"""测试计划视图 — 结果矩阵组件。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QButtonGroup,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import src.styles.theme as _t
from src.styles.theme import (
    MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    GREEN, RED, YELLOW, BLUE,
    SELECTION_BG,
)
from src.styles.constants import FONT_FAMILY, FONT_SIZE_SMALL, install_copy_handler

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

    _DISPLAY_MODES = ["符号", "实测值", "日期"]
    _MODE_SYMBOL = 0
    _MODE_MEASURED = 1
    _MODE_DATE = 2

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # 显示模式切换栏
        mode_bar = QHBoxLayout()
        mode_bar.setContentsMargins(4, 2, 4, 2)
        mode_label = QLabel("显示模式:")
        mode_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: {FONT_SIZE_SMALL}px;")
        mode_bar.addWidget(mode_label)
        self._mode_group = QButtonGroup(self)
        self._mode_checked_qss = (
            f"QPushButton {{ background-color: {SURFACE1}; color: {TEXT}; "
            f"border: 1px solid {BLUE}; border-radius: 4px; "
            f"padding: 1px 8px; font-size: 12px; }}"
        )
        self._mode_unchecked_qss = (
            f"QPushButton {{ background-color: transparent; color: {SUBTEXT0}; "
            f"border: 1px solid {SURFACE1}; border-radius: 4px; "
            f"padding: 1px 8px; font-size: 12px; }}"
        )
        for i, label in enumerate(self._DISPLAY_MODES):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setCheckable(True)
            btn.setStyleSheet(self._mode_unchecked_qss if i != 0 else self._mode_checked_qss)
            self._mode_group.addButton(btn, i)
            mode_bar.addWidget(btn)
        self._mode_group.button(0).setChecked(True)
        self._mode_group.idClicked.connect(self._on_mode_changed)
        mode_bar.addStretch()
        self._layout.addLayout(mode_bar)

        self._table = QTableWidget()
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._table.setAlternatingRowColors(False)
        install_copy_handler(self._table)
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
        self._summary_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px; padding: 4px 8px;")
        self._layout.addWidget(self._summary_label)

        # 缓存数据用于模式切换时重新渲染
        self._last_tasks: list[TestTask] = []
        self._last_results: list = []
        self._last_sample_map: dict[int, str] = {}
        _t.theme_host.theme_changed.connect(self._refresh_theme)

    def _refresh_theme(self) -> None:
        """主题切换时刷新表格和控件样式。"""
        self._table.setStyleSheet("""
            QTableWidget::item {
                padding: 0px;
            }
        """)
        self._summary_label.setStyleSheet(
            f"color: {_t.SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px; padding: 4px 8px;"
        )
        self._mode_checked_qss = (
            f"QPushButton {{ background-color: {_t.SURFACE1}; color: {_t.TEXT}; "
            f"border: 1px solid {_t.BLUE}; border-radius: 4px; "
            f"padding: 1px 8px; font-size: 12px; }}"
        )
        self._mode_unchecked_qss = (
            f"QPushButton {{ background-color: transparent; color: {_t.SUBTEXT0}; "
            f"border: 1px solid {_t.SURFACE1}; border-radius: 4px; "
            f"padding: 1px 8px; font-size: 12px; }}"
        )
        btn_id = self._mode_group.checkedId()
        for i, btn in enumerate(self._mode_group.buttons()):
            btn.setStyleSheet(self._mode_checked_qss if i == btn_id else self._mode_unchecked_qss)

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

    def _on_mode_changed(self, btn_id: int) -> None:
        """切换显示模式后重新渲染。"""
        # 更新按钮选中样式
        for i, btn in enumerate(self._mode_group.buttons()):
            btn.setStyleSheet(self._mode_checked_qss if i == btn_id else self._mode_unchecked_qss)
        self.refresh(self._last_tasks, self._last_results, self._last_sample_map)

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

        # 缓存数据
        self._last_tasks = tasks
        self._last_results = results
        self._last_sample_map = sample_map

        mode = self._mode_group.checkedId()

        # 收集所有涉及到的 sample_id（按 id 排序）
        sample_ids_set: set[int] = set()
        for r in results:
            if r.sample_id is not None:
                sample_ids_set.add(r.sample_id)
        sample_ids = sorted(sample_ids_set)

        # 构建 (task_id, sample_id) → TestResult 的映射
        lookup: dict[tuple[int, int], object] = {}
        for r in results:
            if r.task_id and r.sample_id is not None:
                lookup[(r.task_id, r.sample_id)] = r

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
            col_w = 70 if c < cols - 1 else 70  # 稍宽以容纳实测值和日期
            self._table.setColumnWidth(c, col_w)

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
                result_obj = lookup.get((tid, sid)) if tid else None
                result_str = result_obj.result if result_obj else ""
                color = self._RESULT_COLORS.get(result_str, SURFACE2)

                # 根据模式选择显示文本
                if mode == self._MODE_MEASURED and result_obj and hasattr(result_obj, "measured_value"):
                    label = result_obj.measured_value or ""
                elif mode == self._MODE_DATE and result_obj and hasattr(result_obj, "test_date"):
                    label = result_obj.test_date[:10] if result_obj.test_date else ""
                else:
                    label = self._RESULT_LABELS.get(result_str, "")

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

                # Tooltip: 始终显示完整信息（不受模式影响）
                if result_obj:
                    tip_parts = [f"结果: {result_str or '未录入'}"]
                    if hasattr(result_obj, "measured_value") and result_obj.measured_value:
                        tip_parts.append(f"实测值: {result_obj.measured_value}")
                    if hasattr(result_obj, "test_date") and result_obj.test_date:
                        tip_parts.append(f"日期: {result_obj.test_date[:10]}")
                    if hasattr(result_obj, "notes") and result_obj.notes:
                        tip_parts.append(f"备注: {result_obj.notes}")
                    item.setToolTip("\n".join(tip_parts))

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
                f"font-size: {FONT_SIZE_SMALL}px; padding: 4px 8px; font-weight: bold;"
            )
        elif sample_ids:
            self._summary_label.setText(
                f"共 {len(tasks)} 项任务 × {len(sample_ids)} 个样品 — 暂无录入结果"
            )
            self._summary_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px; padding: 4px 8px;")
        else:
            self._summary_label.setText("暂无测试结果数据")
            self._summary_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: {FONT_SIZE_SMALL}px; padding: 4px 8px;")