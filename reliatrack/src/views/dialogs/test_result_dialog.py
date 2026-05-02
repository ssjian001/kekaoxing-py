"""测试结果录入弹窗 — 对任务关联的样品批量录入测试结果。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor

from src.constants import RESULT_OPTIONS
from src.models.test_plan import TestResult, TestResultStatus, TestTask
from src.models.sample import Sample
from src.styles.theme import (
    BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    GREEN, RED, YELLOW, BLUE,
)


class _ResultRow(QFrame):
    """单个样品的结果录入行。"""

    _RESULT_OPTIONS = RESULT_OPTIONS
    _RESULT_COLORS: dict[str, str] = {
        "pass": GREEN, "fail": RED,
        "conditional": YELLOW, "pending": SUBTEXT0, "skip": SUBTEXT0,
    }

    def __init__(
        self,
        sample: Sample,
        existing_result: TestResult | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sample = sample
        self._result_id: int | None = existing_result.id if existing_result else None

        self.setObjectName("_result_row")
        self.setStyleSheet(f"""
            QFrame#_result_row {{
                background-color: {SURFACE0}; border: 1px solid {SURFACE1};
                border-radius: 6px; padding: 4px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 样品信息
        info_text = f"{sample.sn}"
        if sample.batch_no:
            info_text += f"  ({sample.batch_no})"
        if sample.spec:
            info_text += f"  {sample.spec}"
        lbl = QLabel(info_text)
        lbl.setMinimumWidth(160)
        lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        layout.addWidget(lbl)

        # 结果下拉
        self._combo = QComboBox()
        self._combo.setFixedWidth(100)
        for label_text, value in self._RESULT_OPTIONS:
            self._combo.addItem(label_text, value)
        if existing_result:
            idx = self._combo.findData(existing_result.result)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        self._combo.currentIndexChanged.connect(self._on_result_changed)
        layout.addWidget(self._combo)

        # 测试日期
        self._date_edit = QDateEdit()
        self._date_edit.setFixedWidth(110)
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
        layout.addWidget(self._date_edit)

        # 备注
        from PySide6.QtWidgets import QLineEdit
        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("备注")
        self._notes_edit.setFixedWidth(140)
        self._notes_edit.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        if existing_result and existing_result.notes:
            self._notes_edit.setText(existing_result.notes)
        layout.addWidget(self._notes_edit)

        # 实测值
        self._measured_edit = QLineEdit()
        self._measured_edit.setPlaceholderText("实测值")
        self._measured_edit.setFixedWidth(100)
        self._measured_edit.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        if existing_result and existing_result.measured_value:
            self._measured_edit.setText(existing_result.measured_value)
        layout.addWidget(self._measured_edit)

        # 环境参数（温度/湿度）
        self._temp_edit = QLineEdit()
        self._temp_edit.setPlaceholderText("温度°C")
        self._temp_edit.setFixedWidth(72)
        self._temp_edit.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
        self._humidity_edit = QLineEdit()
        self._humidity_edit.setPlaceholderText("湿度%RH")
        self._humidity_edit.setFixedWidth(72)
        self._humidity_edit.setStyleSheet(f"color: {TEXT}; font-size: 11px;")

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

        layout.addWidget(self._temp_edit)
        layout.addWidget(self._humidity_edit)

        layout.addStretch()

        # 状态色块指示
        self._indicator = QLabel()
        self._indicator.setFixedSize(12, 12)
        self._update_indicator()
        layout.addWidget(self._indicator)

    def _update_indicator(self) -> None:
        result = self._combo.currentData()
        color = self._RESULT_COLORS.get(str(result), SUBTEXT0)
        self._indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
        )

    def _on_result_changed(self) -> None:
        self._update_indicator()

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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._task = task
        self._existing_results = existing_results or []
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
            row = _ResultRow(sample, existing, self)
            self._rows.append(row)
            container_layout.addWidget(row)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        self._update_stats()

    def _update_stats(self) -> None:
        total = len(self._rows)
        if total == 0:
            self._stats_label.setText("")
            return
        results = [r._combo.currentData() for r in self._rows]
        pass_count = sum(1 for r in results if r == "pass")
        fail_count = sum(1 for r in results if r == "fail")
        cond_count = sum(1 for r in results if r == "conditional")
        pending_count = sum(1 for r in results if r == "pending")
        skip_count = sum(1 for r in results if r == "skip")
        self._stats_label.setText(
            f"共 {total} 个样品: "
            f"通过 {pass_count}  |  不通过 {fail_count}  |  "
            f"条件通过 {cond_count}  |  待定 {pending_count}  |  跳过 {skip_count}"
        )

    def get_all_data(self) -> list[dict]:
        """返回所有样品的录入结果。"""
        return [row.get_data() for row in self._rows]
