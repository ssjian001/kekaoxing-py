"""测试结果录入弹窗 — 对任务关联的样品批量录入测试结果。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.constants import RESULT_OPTIONS
from src.models.sample import Sample
from src.models.test_plan import TestResult, TestResultStatus, TestTask
from src.styles.theme import (
    BASE, MANTLE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    GREEN, GREEN_DARK, RED, YELLOW, BLUE,
    SELECTION_BG,
)
import src.styles.theme as _t


class _ResultRow(QFrame):
    """单个样品的结果录入行（双行布局）。"""

    _RESULT_OPTIONS = RESULT_OPTIONS
    _RESULT_COLORS: dict[str, str] = {
        "pass": GREEN, "fail": RED,
        "conditional": YELLOW, "pending": SUBTEXT0, "skip": SUBTEXT0,
    }

    def __init__(
        self,
        sample: Sample,
        existing_result: TestResult | None = None,
        technician_list: list | None = None,
        on_change: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sample = sample
        self._result_id: int | None = existing_result.id if existing_result else None
        self._initial_result: str | None = existing_result.result if existing_result else None
        self._deleted = False
        self._on_change = on_change
        self._needs_attention: bool = (existing_result is None)

        self.setObjectName("_result_row")
        self._update_row_style()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        # ── 第一行：样品 + 结果 + 日期 + 测试人 + 删除 ──
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        # 样品信息
        info_text = sample.sn
        if sample.batch_no:
            info_text += f"  ({sample.batch_no})"
        if sample.spec:
            info_text += f"  {sample.spec}"
        self._sample_lbl = QLabel(info_text)
        self._sample_lbl.setMinimumWidth(120)
        self._sample_lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 12px;")
        row1.addWidget(self._sample_lbl)

        # 结果下拉
        self._combo = QComboBox()
        self._combo.setFixedWidth(90)
        for value, label_text in self._RESULT_OPTIONS:
            self._combo.addItem(label_text, value)
        if existing_result:
            idx = self._combo.findData(existing_result.result)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        self._combo.currentIndexChanged.connect(self._on_result_changed)
        row1.addWidget(self._combo)

        # 测试日期
        self._date_edit = QDateEdit()
        self._date_edit.setFixedWidth(105)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        if existing_result and existing_result.test_date:
            d = QDate.fromString(existing_result.test_date[:10], "yyyy-MM-dd")
            if d.isValid():
                self._date_edit.setDate(d)
            else:
                self._date_edit.setDate(QDate.currentDate())
        else:
            self._date_edit.setDate(QDate.currentDate())
        row1.addWidget(self._date_edit)

        # 测试人
        self._tester_combo = QComboBox()
        self._tester_combo.setFixedWidth(80)
        self._tester_combo.addItem("（无）", None)
        if technician_list:
            for tech in technician_list:
                if hasattr(tech, "id") and hasattr(tech, "name"):
                    self._tester_combo.addItem(tech.name, tech.id)
        if existing_result and existing_result.tester_id:
            idx = self._tester_combo.findData(existing_result.tester_id)
            if idx >= 0:
                self._tester_combo.setCurrentIndex(idx)
        row1.addWidget(self._tester_combo)

        row1.addStretch()

        # 状态色块指示（新增行使用）
        self._indicator = QLabel()
        self._indicator.setFixedSize(12, 12)
        self._update_indicator()

        # 删除/撤销按钮（已有结果行使用）
        self._toggle_btn = QPushButton("删除")
        self._toggle_btn.setMinimumWidth(48)
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.setToolTip("删除此结果")
        self._toggle_btn.clicked.connect(self._on_toggle_delete)

        if self._result_id is not None:
            row1.addWidget(self._toggle_btn)
            self._indicator.hide()
        else:
            row1.addWidget(self._indicator)
            self._toggle_btn.hide()

        outer.addLayout(row1)

        # ── 第二行：备注 + 实测值 + 温湿度 + 创建Issue ──
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("备注")
        self._notes_edit.setMinimumWidth(60)
        self._notes_edit.setStyleSheet(f"color: {_t.TEXT}; font-size: 12px;")
        if existing_result and existing_result.notes:
            self._notes_edit.setText(existing_result.notes)
        row2.addWidget(self._notes_edit, stretch=2)

        self._measured_edit = QLineEdit()
        self._measured_edit.setPlaceholderText("实测值")
        self._measured_edit.setMinimumWidth(50)
        self._measured_edit.setStyleSheet(f"color: {_t.TEXT}; font-size: 12px;")
        if existing_result and existing_result.measured_value:
            self._measured_edit.setText(existing_result.measured_value)
        row2.addWidget(self._measured_edit, stretch=1)

        self._temp_edit = QLineEdit()
        self._temp_edit.setPlaceholderText("温度°C")
        self._temp_edit.setFixedWidth(68)
        self._temp_edit.setStyleSheet(f"color: {_t.TEXT}; font-size: 11px;")
        row2.addWidget(self._temp_edit)

        self._humidity_edit = QLineEdit()
        self._humidity_edit.setPlaceholderText("湿度%RH")
        self._humidity_edit.setFixedWidth(68)
        self._humidity_edit.setStyleSheet(f"color: {_t.TEXT}; font-size: 11px;")
        row2.addWidget(self._humidity_edit)

        # 解析已有的 environment JSON
        if existing_result and existing_result.environment:
            import json
            try:
                env = json.loads(existing_result.environment)
                if env.get("temperature"):
                    self._temp_edit.setText(str(env["temperature"]))
                if env.get("humidity"):
                    self._humidity_edit.setText(str(env["humidity"]))
            except (json.JSONDecodeError, TypeError):
                pass

        row2.addStretch()

        self._create_issue_cb = QCheckBox("创建Issue")
        self._create_issue_cb.setToolTip("不通过时自动创建 Issue 追踪")
        row2.addWidget(self._create_issue_cb)

        outer.addLayout(row2)

        # 收集需要 disable/enable 的输入控件（不含 indicator 和 toggle 按钮）
        self._widgets_to_toggle = [
            self._combo, self._date_edit, self._notes_edit,
            self._measured_edit, self._tester_combo,
            self._temp_edit, self._humidity_edit, self._create_issue_cb,
        ]

    def _update_row_style(self) -> None:
        """根据当前状态 (deleted > needs_attention > normal) 更新行样式。"""
        if self._deleted:
            bg, border = SURFACE2, RED
        elif self._needs_attention:
            bg, border = SELECTION_BG, BLUE
        else:
            bg, border = SURFACE0, SURFACE1
        self.setStyleSheet(f"""
            QFrame#_result_row {{
                background-color: {bg}; border: 1px solid {border};
                border-radius: 6px; padding: 4px;
            }}
        """)

    def _update_indicator(self) -> None:
        result = self._combo.currentData()
        color = self._RESULT_COLORS.get(str(result), SUBTEXT0)
        self._indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
        )

    def _on_result_changed(self) -> None:
        self._update_indicator()
        # 从 pending 首次改为有效结果 → 取消待测高亮
        if self._needs_attention and self._combo.currentData() != "pending":
            self._needs_attention = False
            self._update_row_style()
        # 仅从非 fail 变为 fail 时自动勾选（编辑已有 fail 不重复触发）
        if self._combo.currentData() == "fail" and self._initial_result != "fail":
            self._create_issue_cb.setChecked(True)

    def _on_toggle_delete(self) -> None:
        """切换删除/撤销状态。"""
        self._deleted = not self._deleted
        for w in self._widgets_to_toggle:
            w.setEnabled(not self._deleted)
        self._update_row_style()
        if self._deleted:
            self._toggle_btn.setText("撤销")
            self._toggle_btn.setToolTip("撤销删除")
        else:
            self._toggle_btn.setText("删除")
            self._toggle_btn.setToolTip("删除此结果")
        if self._on_change:
            self._on_change()

    def set_env_if_empty(self, temp: str, humidity: str) -> None:
        """仅当温湿度字段为空时填充（用于预填和"应用到全部"）。"""
        if temp and not self._temp_edit.text().strip():
            self._temp_edit.setText(temp)
        if humidity and not self._humidity_edit.text().strip():
            self._humidity_edit.setText(humidity)

    def get_env_values(self) -> tuple[str, str]:
        """返回当前温湿度文本。"""
        return self._temp_edit.text().strip(), self._humidity_edit.text().strip()

    def get_data(self) -> dict:
        """返回录入数据。"""
        import json
        env: dict[str, str] = {}
        temp = self._temp_edit.text().strip()
        humidity = self._humidity_edit.text().strip()
        if temp:
            env["temperature"] = temp
        if humidity:
            env["humidity"] = humidity
        return {
            "sample_id": self._sample.id,
            "result": self._combo.currentData() or TestResultStatus.PENDING.value,
            "test_date": self._date_edit.date().toString("yyyy-MM-dd"),
            "notes": self._notes_edit.text().strip(),
            "measured_value": self._measured_edit.text().strip(),
            "environment": json.dumps(env, ensure_ascii=False),
            "tester_id": self._tester_combo.currentData(),
            "create_issue": self._create_issue_cb.isChecked(),
            "sample_name": self._sample.sn,
            "result_id": self._result_id,
            "deleted": self._deleted,
        }

    @property
    def result_id(self) -> int | None:
        return self._result_id


class TestResultDialog(QWidget):
    """测试结果录入弹窗容器 — 嵌入 QScrollArea 的结果行列表。

    用法：创建后嵌入 QDialog 或作为独立 Widget 使用。
    这里直接继承 QWidget 以便在 main.py 中嵌入通用弹窗模式。
    """

    def __init__(
        self,
        task: TestTask,
        samples: list[Sample],
        existing_results: list[TestResult] | None = None,
        technician_list: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._task = task
        self._existing_results = existing_results or []
        self._technician_list = technician_list or []
        self._setup_ui(samples)

    def _setup_ui(self, samples: list[Sample]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 任务信息头
        header = QLabel(f"任务: {self._task.name}")
        header.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(header)

        # 判定准则（如有）
        if self._task.accept_criteria:
            criteria = QLabel(f"判定准则: {self._task.accept_criteria}")
            criteria.setProperty("class", "hint-label")
            criteria.setWordWrap(True)
            layout.addWidget(criteria)

        if not samples:
            lbl = QLabel("该任务未关联样品，请先在任务编辑中添加样品。")
            lbl.setProperty("class", "subtext")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            self._rows: list[_ResultRow] = []
            return

        # 结果统计 + 环境条件工具栏
        stats_row = QHBoxLayout()
        self._stats_label = QLabel()
        self._stats_label.setProperty("class", "subtext")
        stats_row.addWidget(self._stats_label, stretch=1)

        self._btn_apply_env = QPushButton("温湿度应用到全部")
        self._btn_apply_env.setFixedHeight(24)
        self._btn_apply_env.clicked.connect(self._apply_env_to_all)
        stats_row.addWidget(self._btn_apply_env)

        self._btn_pass_all = QPushButton("全部通过")
        self._btn_pass_all.setFixedHeight(24)
        self._btn_pass_all.setStyleSheet(
            f"QPushButton {{ color: {_t.MANTLE}; background-color: {_t.GREEN};"
            f" border: none; border-radius: 4px; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background-color: {GREEN_DARK}; }}"
            f"QPushButton:pressed {{ background-color: {GREEN_DARK}; }}"
        )
        self._btn_pass_all.clicked.connect(self._pass_all)
        stats_row.addWidget(self._btn_pass_all)
        layout.addLayout(stats_row)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setProperty("class", "separator")
        layout.addWidget(sep)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {_t.BASE}; }}")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(6)
        container_layout.setContentsMargins(0, 4, 0, 4)

        # 构建结果行
        result_map: dict[int, TestResult] = {}
        for r in self._existing_results:
            if r.sample_id is not None:
                result_map[r.sample_id] = r

        self._rows = []
        for sample in samples:
            existing = result_map.get(sample.id) if sample.id else None
            row = _ResultRow(
                sample, existing,
                technician_list=self._technician_list,
                on_change=self._update_stats,
                parent=self,
            )
            self._rows.append(row)
            container_layout.addWidget(row)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # 预填任务默认环境条件（仅未录入的行）
        task_temp = self._task.temperature or ""
        task_humid = self._task.humidity or ""
        if task_temp or task_humid:
            for row in self._rows:
                if row._needs_attention:
                    row.set_env_if_empty(task_temp, task_humid)

        self._update_stats()

    def _apply_env_to_all(self) -> None:
        """将首个非空行的温湿度值填充到所有空行。"""
        # 优先用 task 默认值，fallback 到首个非空行
        source_temp = self._task.temperature or ""
        source_humid = self._task.humidity or ""
        for row in self._rows:
            if not row._deleted:
                t, h = row.get_env_values()
                if not source_temp and t:
                    source_temp = t
                if not source_humid and h:
                    source_humid = h
                break
        if not source_temp and not source_humid:
            return
        count = 0
        for row in self._rows:
            if not row._deleted:
                old_t, old_h = row.get_env_values()
                row.set_env_if_empty(source_temp, source_humid)
                new_t, new_h = row.get_env_values()
                if (new_t, new_h) != (old_t, old_h):
                    count += 1
        if count:
            self._btn_apply_env.setText(f"已应用 ({count})")

    def _pass_all(self) -> None:
        """将所有未删除行的结果设为「通过」。"""
        count = 0
        for row in self._rows:
            if not row._deleted and row._combo.currentData() != "pass":
                # 找到 "pass" 的 index
                idx = row._combo.findData("pass")
                if idx >= 0:
                    row._combo.setCurrentIndex(idx)
                    count += 1
        if count:
            self._btn_pass_all.setText(f"全部通过 ({count})")

    def _update_stats(self) -> None:
        # 只统计未删除的行
        active_rows = [r for r in self._rows if not r._deleted]
        total = len(active_rows)
        if total == 0:
            self._stats_label.setText("")
            return
        results = [r._combo.currentData() for r in active_rows]
        pass_count = sum(1 for r in results if r == "pass")
        fail_count = sum(1 for r in results if r == "fail")
        cond_count = sum(1 for r in results if r == "conditional")
        pending_count = sum(1 for r in results if r == "pending")
        skip_count = sum(1 for r in results if r == "skip")
        deleted_count = sum(1 for r in self._rows if r._deleted)
        text = (
            f"共 {total} 个样品: "
            f"通过 {pass_count}  |  不通过 {fail_count}  |  "
            f"条件通过 {cond_count}  |  待定 {pending_count}  |  跳过 {skip_count}"
        )
        if deleted_count:
            text += f"  (已标记删除 {deleted_count})"
        self._stats_label.setText(text)

    def get_all_data(self) -> list[dict]:
        """返回所有样品的录入结果。"""
        return [row.get_data() for row in self._rows]
