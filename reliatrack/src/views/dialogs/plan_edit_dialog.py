"""测试计划编辑弹窗 — 新建 / 编辑 TestPlan。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)
from PySide6.QtCore import QDate

from src.models.test_plan import TestPlan, TestPlanStatus
from src.views.dialogs.base_dialog import _BaseDialog


class PlanEditDialog(_BaseDialog):
    """测试计划新建 / 编辑弹窗。

    Parameters
    ----------
    plan:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    project_list:
        可选项目列表（用于关联项目下拉框）。
    """

    _STATUS_LABELS = [
        ("draft", "草稿"),
        ("in_progress", "进行中"),
        ("completed", "已完成"),
        ("paused", "已暂停"),
    ]

    def __init__(
        self,
        plan: TestPlan | None = None,
        project_list: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = plan is not None
        super().__init__(
            "✏️ 编辑测试计划" if is_edit else "➕ 新建测试计划",
            parent,
            width=460,
        )
        self._plan = plan
        self._project_list = project_list or []

        # ── 基本信息 ──
        self._name_edit = self._add_text_field(
            "计划名称 *",
            default=plan.name if plan else "",
            placeholder="必填",
        )
        self._standard_edit = self._add_text_field(
            "测试标准",
            default=plan.test_standard if plan else "",
            placeholder="如：MIL-STD-810H",
        )

        # ── 关联项目 ──
        project_names = ["（无）"]
        project_names += [f"{p.id} — {p.name}" for p in self._project_list]
        project_default = "（无）"
        if plan and plan.project_id:
            for p in self._project_list:
                if p.id == plan.project_id:
                    project_default = f"{p.id} — {p.name}"
                    break
        self._project_combo = self._add_combo_field(
            "关联项目",
            items=project_names,
            default=project_default,
        )

        # ── 日期 ──
        self._start_date_edit = self._add_date_field("起始日期")
        self._end_date_edit = self._add_date_field("结束日期")

        # 预填日期
        if plan and plan.start_date:
            d = QDate.fromString(plan.start_date, "yyyy-MM-dd")
            if d.isValid():
                self._start_date_edit.setDate(d)
        if plan and plan.end_date:
            d = QDate.fromString(plan.end_date, "yyyy-MM-dd")
            if d.isValid():
                self._end_date_edit.setDate(d)

        self._add_separator()

        # ── 状态 ──
        status_labels = [label for _, label in self._STATUS_LABELS]
        current_status = "draft"
        if plan:
            for val, label in self._STATUS_LABELS:
                if val == plan.status:
                    current_status = label
                    break
        self._status_combo = self._add_combo_field(
            "状态",
            items=status_labels,
            default=current_status,
        )

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。

        新建时不返回 id，编辑时返回 id。
        """
        # 解析项目 ID
        project_id: int | None = None
        proj_text = self._project_combo.currentText()
        if proj_text != "（无）" and " — " in proj_text:
            try:
                project_id = int(proj_text.split(" — ")[0])
            except ValueError:
                pass

        # 解析状态值
        status_label = self._status_combo.currentText()
        status_value = "draft"
        for val, label in self._STATUS_LABELS:
            if label == status_label:
                status_value = val
                break

        data: dict = {
            "name": self._name_edit.text().strip(),
            "test_standard": self._standard_edit.text().strip(),
            "start_date": self._start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self._end_date_edit.date().toString("yyyy-MM-dd"),
            "status": status_value,
        }
        # 始终包含 project_id，未选择时默认为 0
        data["project_id"] = project_id if project_id is not None else 0

        # 编辑模式：附带 id
        if self._plan and self._plan.id is not None:
            data["id"] = self._plan.id

        return data

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "校验失败", "计划名称为必填项，请输入。")
            self._name_edit.setFocus()
            return

        # 校验日期逻辑：结束日期 >= 起始日期
        if self._end_date_edit.date() < self._start_date_edit.date():
            QMessageBox.warning(
                self, "校验失败",
                "结束日期不能早于起始日期，请检查。",
            )
            self._end_date_edit.setFocus()
            return

        super().accept()
