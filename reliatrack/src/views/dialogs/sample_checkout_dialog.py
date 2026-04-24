"""样品出库弹窗 — 显示样品信息 + 填写出库字段。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog


class SampleCheckoutDialog(_BaseDialog):
    """样品出库弹窗。

    Parameters
    ----------
    sample:
        待出库的 Sample 对象，SN / 规格 / 状态以只读方式展示。
    """

    def __init__(
        self,
        sample: Sample,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("📤 样品出库", parent, width=460)
        self._sample = sample

        # ── 只读信息展示 ──
        self._add_separator()
        self._add_label_field("SN", sample.sn)
        self._add_label_field("规格型号", sample.spec or "—")
        self._add_label_field("当前状态", sample.status)
        self._add_separator()

        # ── 出库表单 ──
        self._purpose_edit = self._add_text_field(
            label="出库目的 *",
            placeholder="测试 / 拆解分析 / 对比 / 借用 …",
        )
        self._task_edit = self._add_text_field(
            label="关联任务 ID",
            placeholder="选填",
        )
        self._return_edit = self._add_date_field(
            label="预计归还日期",
        )
        self._operator_edit = self._add_text_field(
            label="操作人 *",
            placeholder="必填",
        )

        self._add_separator()

        self._notes_edit = self._add_text_field(
            label="备注",
            placeholder="选填",
        )

    # ── 公开 API ─────────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        from PySide6.QtCore import QDate

        return {
            "sample_id": self._sample.id,
            "purpose": self._purpose_edit.text().strip(),
            "related_task_id": int(self._task_edit.text().strip()) if self._task_edit.text().strip() else None,
            "expected_return": self._return_edit.date().toString("yyyy-MM-dd"),
            "operator": self._operator_edit.text().strip(),
            "notes": self._notes_edit.text().strip(),
        }

    # ── 校验 ─────────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以增加校验逻辑。"""
        from PySide6.QtWidgets import QMessageBox

        data = self.get_data()

        if not data["purpose"]:
            QMessageBox.warning(self, "校验失败", "出库目的为必填项，请输入。")
            self._purpose_edit.setFocus()
            return

        if not data["operator"]:
            QMessageBox.warning(self, "校验失败", "操作人为必填项，请输入。")
            self._operator_edit.setFocus()
            return

        super().accept()
