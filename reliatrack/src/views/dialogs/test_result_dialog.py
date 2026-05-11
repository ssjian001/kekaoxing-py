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
    BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    GREEN, RED, YELLOW, BLUE,
)


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

        self.setObjectName("_result_row")
        self._apply_normal_style()

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
        self._sample_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        row1.addWidget(self._sample_lbl)

        # 结果下拉
        self._combo = QComboBox()
        self._combo.setFixedWidth(90)
        for label_text, value in self._RESULT_OPTIONS:
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
        self._toggle_btn = QPushButton("×")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setToolTip("删除此结果")
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ color: {RED}; border: 1px solid {SURFACE1};"
            f" background-color: {SURFACE1}; font-size: 15px; font-weight: bold;"
            f" border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {RED}; color: white; }}"
        )
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
        self._notes_edit.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        if existing_result and existing_result.notes:
            self._notes_edit.setText(existing_result.notes)
        row2.addWidget(self._notes_edit, stretch=2)

        self._measured_edit = QLineEdit()
        self._measured_edit.setPlaceholderText("实测值")
        self._measured_edit.setMinimumWidth(50)
        self._measured_edit.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        if existing_result and existing_result.measured_value:
            self._measured_edit.setText(existing_result.measured_value)
        row2.addWidget(self._measured_edit, stretch=1)

        self._temp_edit = QLineEdit()
        self._temp_edit.setPlaceholderText("温度°C")
        self._temp_edit.setFixedWidth(68)
        self._temp_edit.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
        row2.addWidget(self._temp_edit)

        self._humidity_edit = QLineEdit()
        self._humidity_edit.setPlaceholderText("湿度%RH")
        self._humidity_edit.setFixedWidth(68)
        self._humidity_edit.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
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
        self._create_issue_cb.setStyleSheet(
            f"color: {RED}; font-size: 10px; border: none; background: transparent;"
        )
        self._create_issue_cb.setToolTip("不通过时自动创建 Issue 追踪")
        row2.addWidget(self._create_issue_cb)

        outer.addLayout(row2)

        # 收集需要 disable/enable 的输入控件（不含 indicator 和 toggle 按钮）
        self._widgets_to_toggle = [
            self._combo, self._date_edit, self._notes_edit,
            self._measured_edit, self._tester_combo,
            self._temp_edit, self._humidity_edit, self._create_issue_cb,
        ]

    def _apply_normal_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#_result_row {{
                background-color: {SURFACE0}; border: 1px solid {SURFACE1};
                border-radius: 6px; padding: 4px;
            }}
        """)

    def _apply_deleted_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#_result_row {{
                background-color: {SURFACE2}; border: 1px solid {RED};
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
        # 仅从非 fail 变为 fail 时自动勾选（编辑已有 fail 不重复触发）
        if self._combo.currentData() == "fail" and self._initial_result != "fail":
            self._create_issue_cb.setChecked(True)

    def _on_toggle_delete(self) -> None:
        """切换删除/撤销状态。"""
        self._deleted = not self._deleted
        for w in self._widgets_to_toggle:
            w.setEnabled(not self._deleted)
        if self._deleted:
            self._apply_deleted_style()
            self._toggle_btn.setText("↩")
            self._toggle_btn.setToolTip("撤销删除")
        else:
            self._apply_normal_style()
            self._toggle_btn.setText("×")
            self._toggle_btn.setToolTip("删除此结果")
        if self._on_change:
            self._on_change()

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
        header.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(header)

        if not samples:
            lbl = QLabel("该任务未关联样品，请先在任务编辑中添加样品。")
            lbl.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px; padding: 16px;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            self._rows: list[_ResultRow] = []
            return

        # 结果统计
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet(f"color: {SUBTEXT1}; font-size: 12px;")
        layout.addWidget(self._stats_label)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {SURFACE1};")
        layout.addWidget(sep)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {BASE}; }}")

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

        self._update_stats()

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
