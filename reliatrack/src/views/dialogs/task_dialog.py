"""测试任务编辑弹窗 — 新建 / 编辑 TestTask。"""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QWidget,
    QMessageBox,
)

from src.models.test_plan import TestTask
from src.models.common import Equipment, Technician
from src.views.dialogs.base_dialog import _BaseDialog


class TaskEditDialog(_BaseDialog):
    """测试任务新建 / 编辑弹窗。

    Parameters
    ----------
    task:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    equipment_list:
        可选设备列表（用于设备下拉框）。
    technician_list:
        可选技术员列表（用于技术员下拉框）。
    all_tasks:
        当前计划下所有任务（用于依赖选择提示）。
    """

    _CATEGORIES = ["环境试验", "机械试验", "表面处理", "包装", "其他"]

    def __init__(
        self,
        task: TestTask | None = None,
        equipment_list: list[Equipment] | None = None,
        technician_list: list[Technician] | None = None,
        all_tasks: list[TestTask] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = task is not None
        super().__init__(
            "✏️ 编辑测试任务" if is_edit else "➕ 新建测试任务",
            parent,
            width=520,
        )
        self._task = task
        self._equipment_list = equipment_list or []
        self._technician_list = technician_list or []
        self._all_tasks = [t for t in (all_tasks or []) if t.id != (task.id if task else None)]

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
        dep_hint = self._build_dep_hint()
        self._dep_edit = self._add_text_field(
            "依赖任务 ID",
            default=self._format_deps(task) if task else "",
            placeholder=dep_hint,
        )
        self._env_edit = self._add_text_field(
            "环境条件 (JSON)",
            default=task.environment if task else "",
            placeholder='如：{"temp":"85C","humidity":"85%RH"}',
        )
        self._notes_edit = self._add_text_area(
            "备注",
            default=task.notes if task else "",
        )

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

    def _format_deps(self, task: TestTask) -> str:
        """将 JSON 依赖数组转为逗号分隔字符串。"""
        try:
            ids = json.loads(task.dependencies)
            if isinstance(ids, list):
                return ", ".join(str(i) for i in ids)
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    def _build_dep_hint(self) -> str:
        """构建依赖任务的提示文本。"""
        if not self._all_tasks:
            return "逗号分隔的 task_id，如：1, 3, 5"
        names = [f"#{t.id} {t.name}" for t in self._all_tasks[:8]]
        hint = "可选: " + ", ".join(names)
        if len(self._all_tasks) > 8:
            hint += f" … (共{len(self._all_tasks)}项)"
        return hint

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        # 解析依赖 ID
        dep_text = self._dep_edit.text().strip()
        if dep_text:
            try:
                dep_ids = [int(x.strip()) for x in dep_text.split(",") if x.strip()]
            except ValueError:
                dep_ids = []
        else:
            dep_ids = []

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

        return {
            "name": self._name_edit.text().strip(),
            "category": self._category_combo.currentText(),
            "test_standard": self._standard_edit.text().strip(),
            "duration": self._duration_spin.value(),
            "priority": self._priority_spin.value(),
            "equipment_id": equipment_id,
            "technician_id": technician_id,
            "dependencies": json.dumps(dep_ids, ensure_ascii=False),
            "environment": self._env_edit.text().strip(),
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
