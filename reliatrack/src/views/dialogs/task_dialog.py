"""测试任务编辑弹窗 — 新建 / 编辑 TestTask。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLineEdit

from src.styles.theme import SUBTEXT0

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)
from PySide6.QtCore import Qt

from src.models.sample import Sample
from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician
from src.views.dialogs.base_dialog import _BaseDialog
from src.configs.test_type_templates import get_template_names, get_template_by_name


class TaskEditDialog(_BaseDialog):
    """测试任务新建 / 编辑弹窗。

    Parameters
    ----------
    task:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    equipment_list:
        可选设备列表（用于设备下拉框）。
    all_tasks:
        当前计划下所有任务（用于依赖选择提示）。
    sample_list:
        当前项目下的样品列表（用于样品多选弹窗）。
    """

    _CATEGORIES = ["环境试验", "机械试验", "表面处理", "工艺试验", "包装", "寿命试验", "EMC", "其他"]

    def __init__(
        self,
        task: TestTask | None = None,
        equipment_list: list[Equipment] | None = None,
        technician_list: list | None = None,  # kept for backward compat, unused
        all_tasks: list[TestTask] | None = None,
        sample_list: list[Sample] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = task is not None
        super().__init__(
            "编辑测试任务" if is_edit else "新建测试任务",
            parent,
            width=560,
        )
        self._task = task
        self._equipment_list = equipment_list or []
        self._technician_list = technician_list or []
        self._all_tasks = [t for t in (all_tasks or []) if t.id != (task.id if task else None)]
        self._sample_list = sample_list or []
        self._selected_sample_ids: list[int] = []
        # 编辑时解析已有的 sample_ids
        if task:
            try:
                self._selected_sample_ids = json.loads(task.sample_ids)
                if not isinstance(self._selected_sample_ids, list):
                    self._selected_sample_ids = []
            except (json.JSONDecodeError, TypeError):
                self._selected_sample_ids = []

        # ── 测试类型模板（自动填充） ──
        self._test_type_combo = self._add_combo_field(
            "测试类型",
            items=get_template_names(),
            default="（自定义）",
        )
        self._test_type_combo.currentTextChanged.connect(self._on_test_type_changed)

        # ── 基本信息 ──
        self._name_edit = self._add_text_field(
            "名称 *",
            default=task.name if task else "",
            placeholder="必填",
        )
        self._category_combo = self._add_combo_field(
            "类别",
            items=self._CATEGORIES,
            default=task.category if task else self._CATEGORIES[0],
        )
        self._standard_edit = self._add_text_field(
            "测试标准",
            default=task.test_standard if task else "",
            placeholder="如：GB/T 2423.3",
        )
        self._duration_spin = self._add_spin_field(
            "工期（天）",
            default=task.duration if task else 1,
            min_val=1, max_val=999,
        )
        self._priority_spin = self._add_spin_field(
            "优先级 (1-5)",
            default=task.priority if task else 3,
            min_val=1, max_val=5,
        )

        # ── 样品选择 ──
        sample_container = QWidget()
        sample_layout = QHBoxLayout(sample_container)
        sample_layout.setContentsMargins(0, 0, 0, 0)
        sample_layout.setSpacing(8)

        self._sample_select_btn = QPushButton("选择样品")
        self._sample_select_btn.setProperty("class", "action")
        self._sample_select_btn.setFixedWidth(100)
        self._sample_select_btn.clicked.connect(self._open_sample_select)

        self._sample_count_label = QLabel(
            self._format_sample_count()
        )
        self._sample_count_label.setStyleSheet(f"color: {SUBTEXT0};")

        sample_layout.addWidget(self._sample_select_btn)
        sample_layout.addWidget(self._sample_count_label, stretch=1)
        self._form.addRow("关联样品", sample_container)

        self._add_separator()

        # ── 执行状态 & 进度 ──
        from src.models.test_plan import TestTaskStatus
        status_options = [
            ("待开始", TestTaskStatus.PENDING.value),
            ("进行中", TestTaskStatus.IN_PROGRESS.value),
            ("已完成", TestTaskStatus.COMPLETED.value),
            ("已跳过", TestTaskStatus.SKIPPED.value),
        ]
        status_items = [label for label, _ in status_options]
        self._status_combo = self._add_combo_field(
            "状态",
            items=status_items,
            default=self._find_status_label(task) if task else status_items[0],
        )

        # 进度滑块
        from PySide6.QtWidgets import QSlider, QLabel as _QLabel
        from PySide6.QtCore import Qt as _Qt, QDate as _QDate
        prog_container = QWidget()
        prog_layout = QHBoxLayout(prog_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_slider = QSlider(_Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 100)
        self._progress_slider.setValue(int(task.progress) if task else 0)
        self._progress_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._progress_slider.setTickInterval(25)
        self._progress_label = _QLabel(f"{int(task.progress) if task else 0}%")
        self._progress_label.setFixedWidth(40)
        self._progress_slider.valueChanged.connect(
            lambda v: self._progress_label.setText(f"{v}%")
        )
        prog_layout.addWidget(self._progress_slider, stretch=1)
        prog_layout.addWidget(self._progress_label)
        self._form.addRow("进度", prog_container)

        # 日期字段
        self._actual_start_edit = self._add_date_field(
            "实际开始日期",
        )
        if task and task.actual_start_date:
            try:
                d = _QDate.fromString(task.actual_start_date, "yyyy-MM-dd")
                if d.isValid():
                    self._actual_start_edit.setDate(d)
            except (ValueError, RuntimeError) as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Invalid actual_start_date '%s' for task %s: %s",
                    task.actual_start_date, task.id, e
                )

        self._actual_end_edit = self._add_date_field(
            "实际完成日期",
        )
        if task and task.actual_end_date:
            try:
                d = _QDate.fromString(task.actual_end_date, "yyyy-MM-dd")
                if d.isValid():
                    self._actual_end_edit.setDate(d)
            except (ValueError, RuntimeError) as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Invalid actual_end_date '%s' for task %s: %s",
                    task.actual_end_date, task.id, e
                )

        self._add_separator()

        # ── 设备 & 技术员 ──
        equip_names = [f"{e.id} — {e.name}" for e in self._equipment_list]
        self._equipment_combo = self._add_combo_field(
            "设备",
            items=["（无）"] + equip_names,
            default=self._find_equip_label(task.equipment_id) if task else "（无）",
        )

        tech_names = [f"{t.id} — {t.name}" for t in self._technician_list]
        self._technician_combo = self._add_combo_field(
            "技术员",
            items=["（无）"] + tech_names,
            default=self._find_tech_label(task.technician_id) if task else "（无）",
        )
        self._add_separator()

        # ── 依赖 & 环境 ──
        # 解析已有依赖
        existing_dep_ids: list[int] = []
        if task and task.dependencies:
            try:
                existing_dep_ids = json.loads(task.dependencies)
                if not isinstance(existing_dep_ids, list):
                    existing_dep_ids = []
            except (json.JSONDecodeError, TypeError):
                existing_dep_ids = []
        self._selected_dep_ids: list[int] = existing_dep_ids

        dep_row = QHBoxLayout()
        dep_row.setSpacing(6)
        self._dep_summary = QLabel(self._format_dep_summary())
        self._dep_summary.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px;")
        self._dep_summary.setWordWrap(True)
        dep_btn = QPushButton("选择...")
        dep_btn.setProperty("class", "action")
        dep_btn.setFixedHeight(26)
        dep_btn.clicked.connect(self._open_dep_selector)
        dep_row.addWidget(self._dep_summary, stretch=1)
        dep_row.addWidget(dep_btn)
        self._form.addRow("依赖任务", dep_row)
        self._env_edit = self._add_text_field(
            "环境条件 (JSON)",
            default=task.environment if task else "",
            placeholder='如：{"temp":"85C","humidity":"85%RH"}',
        )

        # ── 环境参数分组框 ──
        self._add_env_group(task)

        # ── 判定准则 ──
        self._criteria_edit = self._add_text_field(
            "判定准则",
            default=task.accept_criteria if task else "",
            placeholder="如: C=0 (全部通过) / 5收0拒 / 自定义",
        )
        self._test_type_combo.currentTextChanged.connect(self._on_test_type_criteria)

        # ── 测试日志 ──
        self._add_log_file_field(task)

        # ── 备注 ──
        self._notes_edit = self._add_text_area(
            "备注",
            default=task.notes if task else "",
        )

    # ── 测试类型自动填充 ─────────────────────────────────────────

    def _on_test_type_changed(self, text: str) -> None:
        """选择测试类型后自动填充相关字段。"""
        if text == "（自定义）":
            return
        tpl = get_template_by_name(text)
        if tpl is None:
            return

        # 编辑模式下，如果用户已手动填写过则不覆盖（除非内容为空）
        is_edit = self._task is not None

        # 名称：用模板名填充（仅在新建或名称为空时）
        if not is_edit or not self._name_edit.text().strip():
            self._name_edit.setText(tpl.name)

        # 类别
        idx = self._category_combo.findText(tpl.category)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)

        # 测试标准
        if not is_edit or not self._standard_edit.text().strip():
            self._standard_edit.setText(tpl.test_standard)

        # 工期
        if not is_edit or self._duration_spin.value() == 1:
            self._duration_spin.setValue(tpl.duration)

        # 温度
        if not is_edit or not self._temp_edit.text().strip():
            self._temp_edit.setText(tpl.temperature)

        # 湿度
        if not is_edit or not self._humidity_edit.text().strip():
            self._humidity_edit.setText(tpl.humidity)

        # 备注：追加模板信息（不覆盖已有备注）
        notes = self._notes_edit.toPlainText().strip()
        tpl_note_parts = []
        if tpl.accept_criteria:
            tpl_note_parts.append(f"判定准则: {tpl.accept_criteria}")
        if tpl.suggested_samples:
            tpl_note_parts.append(f"建议样品数: {tpl.suggested_samples}")
        if tpl.notes:
            tpl_note_parts.append(tpl.notes)
        tpl_note = " | ".join(tpl_note_parts)
        if tpl_note and not notes:
            self._notes_edit.setPlainText(tpl_note)

        # 判定准则字段
        if tpl.accept_criteria and not self._criteria_edit.text().strip():
            self._criteria_edit.setText(tpl.accept_criteria)

    def _on_test_type_criteria(self, text: str) -> None:
        """测试类型变化时更新判定准则（仅当准则为空时）。"""
        if text == "（自定义）":
            return
        tpl = get_template_by_name(text)
        if tpl and tpl.accept_criteria and not self._criteria_edit.text().strip():
            self._criteria_edit.setText(tpl.accept_criteria)

    # ── 环境参数分组框 ─────────────────────────────────────────

    def _add_env_group(self, task: TestTask | None) -> None:
        """添加「🌡️ 环境参数」分组框（温度 + 湿度）。"""
        group = QGroupBox("环境参数")
        form = QHBoxLayout(group)
        form.setContentsMargins(8, 14, 8, 8)
        form.setSpacing(12)

        # 温度
        temp_label = self._make_group_label("温度")
        self._temp_edit = self._make_group_input(
            task.temperature if task else "",
            "例: -40°C ~ 85°C",
        )

        # 湿度
        hum_label = self._make_group_label("湿度")
        self._humidity_edit = self._make_group_input(
            task.humidity if task else "",
            "例: 85%RH",
        )

        form.addWidget(temp_label)
        form.addWidget(self._temp_edit, stretch=1)
        form.addWidget(hum_label)
        form.addWidget(self._humidity_edit, stretch=1)

        self._form.addRow(group)

    def _make_group_label(self, text: str) -> QWidget:
        """创建分组框内的标签。"""
        from PySide6.QtWidgets import QLabel
        lbl = QLabel(text)
        lbl.setMinimumWidth(50)
        return lbl

    def _make_group_input(self, default: str, placeholder: str) -> "QLineEdit":
        """创建分组框内的输入框。"""
        from PySide6.QtWidgets import QLineEdit
        edit = QLineEdit(default)
        edit.setPlaceholderText(placeholder)
        return edit

    # ── 测试日志文件选择 ─────────────────────────────────────

    def _add_log_file_field(self, task: TestTask | None) -> None:
        """添加日志文件路径输入 + 浏览按钮。"""
        from PySide6.QtWidgets import QLineEdit

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._log_file_edit = QLineEdit(task.log_file if task else "")
        self._log_file_edit.setPlaceholderText("选择设备原始日志文件路径…")

        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_log_file)

        layout.addWidget(self._log_file_edit, stretch=1)
        layout.addWidget(browse_btn)

        self._form.addRow("测试日志", container)

    def _browse_log_file(self) -> None:
        """打开文件对话框选择日志文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择测试日志文件",
            "",
            "日志文件 (*.log *.csv *.txt);;所有文件 (*)",
        )
        if path:
            self._log_file_edit.setText(path)

    # ── 样品选择 ───────────────────────────────────────────────

    def _open_sample_select(self) -> None:
        """打开样品多选弹窗。"""
        from src.views.dialogs.sample_select_dialog import SampleSelectDialog

        dlg = SampleSelectDialog(
            samples=self._sample_list,
            selected_ids=self._selected_sample_ids,
            parent=self,
        )
        if dlg.exec():
            self._selected_sample_ids = dlg.get_selected_ids()
            self._sample_count_label.setText(self._format_sample_count())

    def _format_sample_count(self) -> str:
        """格式化已选样品数量标签。"""
        count = len(self._selected_sample_ids)
        total = len(self._sample_list)
        if count == 0:
            return f"未选择（共 {total} 个可选）"
        # 展示已选样品的 SN
        selected_sns = []
        for sid in self._selected_sample_ids:
            for s in self._sample_list:
                if s.id == sid:
                    selected_sns.append(s.sn)
                    break
        sn_text = ", ".join(selected_sns[:5])
        if len(selected_sns) > 5:
            sn_text += f" …等 {len(selected_sns)} 个"
        return f"已选 {count} 个: {sn_text}"

    # ── 辅助方法 ───────────────────────────────────────────────

    def _find_equip_label(self, equip_id: Optional[int]) -> str:
        if equip_id is None:
            return "（无）"
        for e in self._equipment_list:
            if e.id == equip_id:
                return f"{e.id} — {e.name}"
        return "（无）"

    def _find_tech_label(self, tech_id: Optional[int]) -> str:
        if tech_id is None:
            return "（无）"
        for t in self._technician_list:
            if t.id == tech_id:
                return f"{t.id} — {t.name}"
        return "（无）"

    def _find_status_label(self, task: TestTask) -> str:
        status_map = {
            "pending": "待开始",
            "in_progress": "进行中",
            "completed": "已完成",
            "skipped": "已跳过",
        }
        return status_map.get(task.status, "待开始")

    # ── 依赖选择 ──────────────────────────────────────────────

    def _format_dep_summary(self) -> str:
        """格式化已选依赖摘要。"""
        if not self._selected_dep_ids:
            return "（无）"
        id_to_name: dict[int, str] = {
            t.id: t.name for t in self._all_tasks if t.id is not None
        }
        parts = [f"#{did} {id_to_name.get(did, '?')}" for did in self._selected_dep_ids]
        return ", ".join(parts)

    def _open_dep_selector(self) -> None:
        """弹出依赖任务多选对话框。"""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
            QHBoxLayout, QPushButton, QLabel,
        )
        from src.styles.theme import BASE, TEXT, SURFACE0, SURFACE1, SUBTEXT0, BLUE

        dlg = QDialog(self)
        dlg.setWindowTitle("选择依赖任务")
        dlg.setMinimumWidth(360)
        dlg.setMinimumHeight(300)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        hint = QLabel("勾选当前任务所依赖的前置任务：")
        hint.setStyleSheet(f"color: {SUBTEXT0}; font-size: 11px;")
        layout.addWidget(hint)

        lst = QListWidget()
        # 按 start_day 排序
        sorted_tasks = sorted(self._all_tasks, key=lambda t: (t.start_day or 0, t.id or 0))
        # 如果是编辑模式，插入当前任务作为分隔参照
        if self._task and self._task.id is not None:
            from PySide6.QtGui import QColor as _QColor
            cur = self._task
            cur_label = f"▶ #{cur.id} {cur.name}  (D{cur.start_day}~D{cur.start_day + cur.duration}) — 当前任务"
            cur_item = QListWidgetItem(cur_label)
            cur_item.setFlags(Qt.ItemFlag.NoItemFlags)  # 不可选、不可勾选
            cur_item.setForeground(_QColor(BLUE))
            # 找到插入位置（按 start_day 排序）
            insert_pos = 0
            for i, t in enumerate(sorted_tasks):
                if (t.start_day or 0) < (cur.start_day or 0) or (
                    (t.start_day or 0) == (cur.start_day or 0) and (t.id or 0) < (cur.id or 0)
                ):
                    insert_pos = i + 1
            sorted_tasks.insert(insert_pos, ("__current__", cur_item))
        for t in sorted_tasks:
            if isinstance(t, tuple) and t[0] == "__current__":
                lst.addItem(t[1])
                continue
            if t.id is None:
                continue
            label = f"#{t.id} {t.name}  (D{t.start_day}~D{t.start_day + t.duration})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            item.setCheckState(
                Qt.CheckState.Checked if t.id in self._selected_dep_ids
                else Qt.CheckState.Unchecked
            )
            lst.addItem(item)
        if lst.count() == 0:
            empty_item = QListWidgetItem("（当前计划无其他任务）")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            lst.addItem(empty_item)
        layout.addWidget(lst, stretch=1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setProperty("class", "action")
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok = QPushButton("确定")
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        if dlg.exec():
            selected: list[int] = []
            for i in range(lst.count()):
                item = lst.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    dep_id = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(dep_id, int):
                        selected.append(dep_id)
            self._selected_dep_ids = selected
            self._dep_summary.setText(self._format_dep_summary())

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        # 直接使用已选依赖 ID
        dep_ids = self._selected_dep_ids

        # 解析设备/技术员 ID
        equip_text = self._equipment_combo.currentText()
        equipment_id = None
        if equip_text != "（无）" and " — " in equip_text:
            try:
                equipment_id = int(equip_text.split(" — ")[0])
            except ValueError:
                pass

        tech_text = self._technician_combo.currentText()
        technician_id = None
        if tech_text != "（无）" and " — " in tech_text:
            try:
                technician_id = int(tech_text.split(" — ")[0])
            except ValueError:
                pass

        # 解析状态
        status_map = {
            "待开始": "pending",
            "进行中": "in_progress",
            "已完成": "completed",
            "已跳过": "skipped",
        }
        status_text = self._status_combo.currentText()
        task_status = status_map.get(status_text, "pending")

        return {
            "name": self._name_edit.text().strip(),
            "category": self._category_combo.currentText(),
            "test_standard": self._standard_edit.text().strip(),
            "duration": self._duration_spin.value(),
            "priority": self._priority_spin.value(),
            "status": task_status,
            "progress": float(self._progress_slider.value()),
            "actual_start_date": self._actual_start_edit.date().toString("yyyy-MM-dd") if self._actual_start_edit.date().isValid() and self._actual_start_edit.date().year() >= 2020 else "",
            "actual_end_date": self._actual_end_edit.date().toString("yyyy-MM-dd") if self._actual_end_edit.date().isValid() and self._actual_end_edit.date().year() >= 2020 else "",
            "equipment_id": equipment_id,
            "technician_id": technician_id,
            "sample_ids": json.dumps(self._selected_sample_ids, ensure_ascii=False),
            "dependencies": json.dumps(dep_ids, ensure_ascii=False),
            "environment": self._env_edit.text().strip(),
            "temperature": self._temp_edit.text().strip(),
            "humidity": self._humidity_edit.text().strip(),
            "log_file": self._log_file_edit.text().strip(),
            "accept_criteria": self._criteria_edit.text().strip(),
            "notes": self._notes_edit.toPlainText().strip(),
        }

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "校验失败", "名称为必填项，请输入。")
            self._name_edit.setFocus()
            return

        # 校验依赖 ID：检查自依赖
        dep_ids = json.loads(data["dependencies"])
        valid_task_ids = {t.id for t in self._all_tasks if t.id is not None}
        # 编辑模式下，排除自己
        self_id = self._task.id if self._task and self._task.id else None
        if self_id and self_id in dep_ids:
            QMessageBox.warning(self, "校验失败", "任务不能依赖自身。")
            return
        invalid_ids = [d for d in dep_ids if d not in valid_task_ids]
        if invalid_ids:
            QMessageBox.warning(
                self, "校验失败",
                f"依赖任务 ID 无效: {', '.join(str(i) for i in invalid_ids)}",
            )
            return

        # 校验环境条件 JSON 格式
        env_str = data["environment"]
        if env_str:
            try:
                json.loads(env_str)
            except json.JSONDecodeError:
                QMessageBox.warning(
                    self, "校验失败",
                    "环境条件不是合法的 JSON 格式，请检查。",
                )
                self._env_edit.setFocus()
                return

        super().accept()
