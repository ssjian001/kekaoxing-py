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
from src.constants import PLAN_STATUS_OPTIONS


class PlanEditDialog(_BaseDialog):
    """测试计划新建 / 编辑弹窗。

    Parameters
    ----------
    plan:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    project_list:
        可选项目列表（用于关联项目下拉框）。
    """

    _STATUS_LABELS = PLAN_STATUS_OPTIONS

    def __init__(
        self,
        plan: TestPlan | None = None,
        project_list: list | None = None,
        default_project_id: int | None = None,
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
        self._prefix_edit = self._add_text_field(
            "任务编号前缀",
            default=plan.task_prefix if plan else "",
            placeholder="留空则用默认编号",
        )
        self._standard_edit = self._add_text_field(
            "测试标准",
            default=plan.test_standard if plan else "",
            placeholder="如：MIL-STD-810H",
        )

        # ── APQP 阶段 ──
        apqp_options = ["(无)", "P1 概念策划", "P2 产品设计", "P3 过程设计", "P4 产品确认", "P5 反馈改进"]
        apqp_default = plan.apqp_phase if plan and plan.apqp_phase else "(无)"
        self._apqp_combo = self._add_combo_field(
            "APQP 阶段",
            items=apqp_options,
            default=apqp_default,
        )

        # ── 关联项目 ──
        project_names = ["（无）"]
        project_names += [f"{p.id} — {p.name}" for p in self._project_list]
        project_default = "（无）"
        # 编辑模式：匹配已有 project_id
        if plan and plan.project_id:
            for p in self._project_list:
                if p.id == plan.project_id:
                    project_default = f"{p.id} — {p.name}"
                    break
        # 新建模式：匹配默认 project_id
        elif default_project_id is not None and not is_edit:
            for p in self._project_list:
                if p.id == default_project_id:
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
        is_archived = plan is not None and plan.status == "archived"
        if is_archived:
            # 归档计划：状态固定显示"已归档"，不可编辑
            editable_status_labels = [label for val, label in self._STATUS_LABELS
                                      if val == "archived"]
        else:
            # 非归档计划：排除 archived 选项
            editable_status_labels = [label for val, label in self._STATUS_LABELS
                                      if val != "archived"]
        current_status = "draft"
        if plan:
            for val, label in self._STATUS_LABELS:
                if val == plan.status:
                    current_status = label
                    break
        self._status_combo = self._add_combo_field(
            "状态",
            items=editable_status_labels,
            default=current_status,
        )
        if is_archived:
            self._status_combo.setEnabled(False)

        # 自动建议前缀
        if not is_edit or not (plan and plan.task_prefix):
            self._name_edit.textChanged.connect(self._auto_suggest_prefix)

    # ── 公开 API ───────────────────────────────────────────────

    def _auto_suggest_prefix(self, name: str) -> None:
        """计划名称变化时自动生成前缀建议（仅当前缀为空时）。"""
        if self._prefix_edit.text().strip():
            return  # 用户已手动输入，不覆盖
        import re
        name = name.strip()
        if not name:
            return
        eng_words = re.findall(r'[A-Za-z]+', name)
        if eng_words:
            prefix = ''.join(w[0].upper() for w in eng_words)[:4]
        else:
            prefix = re.sub(r'[^\w]', '', name)[:3].upper()
        if prefix:
            self._prefix_edit.setText(prefix)

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
            "task_prefix": self._prefix_edit.text().strip().upper(),
            "test_standard": self._standard_edit.text().strip(),
            "apqp_phase": self._apqp_combo.currentText() if self._apqp_combo.currentText() != "(无)" else "",
            "start_date": self._start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self._end_date_edit.date().toString("yyyy-MM-dd"),
            "status": status_value,
        }
        # 始终包含 project_id，未选择时默认为 0
        data["project_id"] = project_id

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
