"""FA 分析记录弹窗 — 添加 FA 步骤。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
)

from src.views.dialogs.base_dialog import _BaseDialog

if TYPE_CHECKING:
    from src.models.issue import FARecord


class FARecordDialog(_BaseDialog):
    """FA 分析步骤添加弹窗。

    Parameters
    ----------
    existing_step_nos:
        已有步骤号列表，用于自动计算下一个 step_no。
    """

    _CAUSE_CATEGORIES = ["（无）", "人", "机", "料", "法", "环", "测"]

    _FAILURE_MECHANISMS = [
        "（无）", "疲劳", "蠕变", "电迁移", "热应力开裂",
        "腐蚀", "磨损", "脆断", "屈曲", "绝缘击穿",
        "离子污染", "银迁移", "锡须", "其他",
    ]

    def __init__(
        self,
        existing_step_nos: list[int] | None = None,
        technician_list: list | None = None,
        parent: QWidget | None = None,
        edit_record: FARecord | None = None,
    ) -> None:
        self._edit_record = edit_record
        title = "编辑 FA 分析步骤" if edit_record else "新建 FA 分析步骤"
        super().__init__(title, parent, width=500)
        step_nos = existing_step_nos or []
        next_step = max(step_nos, default=0) + 1
        self._technician_list = technician_list or []

        self._step_spin = self._add_spin_field(
            "步骤号", default=next_step, min_val=1, max_val=999,
        )
        self._title_edit = self._add_text_field(
            "步骤标题", placeholder="如：外观检查",
        )
        self._description_edit = self._add_text_area(
            "描述",
        )
        self._method_combo = self._add_combo_field(
            "分析方法",
            items=["外观检查", "切片分析", "CT扫描", "SEM", "X-ray", "电测", "其他"],
        )
        self._findings_edit = self._add_text_area(
            "发现",
        )
        self._add_separator()
        self._cause_edit = self._add_text_field(
            "可能原因",
            placeholder="该步骤发现的可能原因",
        )
        self._cause_category_combo = self._add_combo_field(
            "原因分类（鱼骨图）",
            items=self._CAUSE_CATEGORIES,
        )
        self._failure_mechanism_combo = self._add_combo_field(
            "失效机理",
            items=self._FAILURE_MECHANISMS,
        )
        self._confirmed_combo = self._add_combo_field(
            "确认状态",
            items=["待定", "确认", "排除"],
        )
        tech_names = ["（无）"] + [t.name for t in self._technician_list if t.id is not None]
        self._analyst_edit = self._add_text_field(
            "分析人",
            placeholder="自由输入姓名",
        )

        # 编辑模式：回填数据
        if edit_record:
            self._step_spin.setValue(edit_record.step_no)
            self._title_edit.setText(edit_record.step_title or "")
            self._description_edit.setPlainText(edit_record.description or "")
            idx = self._method_combo.findText(edit_record.method or "")
            if idx >= 0:
                self._method_combo.setCurrentIndex(idx)
            self._findings_edit.setPlainText(edit_record.findings or "")
            self._cause_edit.setText(edit_record.possible_cause or "")
            idx = self._cause_category_combo.findText(
                edit_record.cause_category if edit_record.cause_category else "（无）"
            )
            if idx >= 0:
                self._cause_category_combo.setCurrentIndex(idx)
            idx = self._failure_mechanism_combo.findText(
                edit_record.failure_mechanism if edit_record.failure_mechanism else "（无）"
            )
            if idx >= 0:
                self._failure_mechanism_combo.setCurrentIndex(idx)
            confirmed_labels = {0: "待定", 1: "确认", 2: "排除"}
            idx = self._confirmed_combo.findText(
                confirmed_labels.get(edit_record.confirmed, "待定")
            )
            if idx >= 0:
                self._confirmed_combo.setCurrentIndex(idx)
            if edit_record.analyst_id:
                for t in self._technician_list:
                    if t.id == edit_record.analyst_id:
                        self._analyst_edit.setText(t.name)
                        break

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        confirmed_map = {"待定": 0, "确认": 1, "排除": 2}
        category_text = self._cause_category_combo.currentText()
        fm_text = self._failure_mechanism_combo.currentText()
        analyst_name = self._analyst_edit.text().strip()
        analyst_id: int | None = None
        if analyst_name:
            for t in self._technician_list:
                if t.name == analyst_name and t.id is not None:
                    analyst_id = t.id
                    break
        return {
            "step_no": self._step_spin.value(),
            "step_title": self._title_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "method": self._method_combo.currentText(),
            "findings": self._findings_edit.toPlainText().strip(),
            "possible_cause": self._cause_edit.text().strip(),
            "cause_category": category_text if category_text != "（无）" else "",
            "failure_mechanism": fm_text if fm_text != "（无）" else "",
            "confirmed": confirmed_map.get(self._confirmed_combo.currentText(), 0),
            "analyst_id": analyst_id,
        }

    def accept(self) -> None:
        """覆盖 accept 以增加校验逻辑。"""
        from PySide6.QtWidgets import QMessageBox

        if not self._title_edit.text().strip():
            QMessageBox.warning(self, "校验失败", "步骤标题为必填项。")
            self._title_edit.setFocus()
            return
        super().accept()
