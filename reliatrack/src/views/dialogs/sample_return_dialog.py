"""样品归还弹窗 — 填写归还日期和备注。"""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog
from src.constants import SAMPLE_STATUS_LABELS


class SampleReturnDialog(_BaseDialog):
    """样品归还弹窗。

    Parameters
    ----------
    sample:
        待归还的 Sample 对象，SN / 规格 / 状态以只读方式展示。
    technicians:
        技术员列表，供归还操作人选择。
    """

    def __init__(
        self,
        sample: Sample,
        technicians: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("样品归还", parent, width=460)
        self._sample = sample
        self._technicians = technicians or []

        # ── 只读信息展示 ──
        self._add_separator()
        self._add_label_field("SN", sample.sn)
        self._add_label_field("规格型号", sample.spec or "—")
        self._add_label_field("当前状态", SAMPLE_STATUS_LABELS.get(sample.status, sample.status))
        self._add_separator()

        # ── 归还表单 ──
        # 实际归还日期，默认为今天
        self._actual_return_edit = self._add_date_field(
            label="实际归还日期 *",
        )
        self._actual_return_edit.setDate(QDate.currentDate())

        # 操作人
        tech_names = [f"{t.id}: {t.name}" if hasattr(t, 'id') else str(t) for t in self._technicians]
        self._operator_combo = self._add_combo_field(
            label="操作人",
            items=tech_names,
            editable=True,
            placeholder="选择或输入技术员（选填）",
        )

        self._add_separator()

        self._notes_edit = self._add_text_field(
            label="备注",
            placeholder="选填，如：归还时状态、损坏情况等",
        )

    # ── 公开 API ─────────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        # 解析操作人 operator_id（从 "id: name" 格式提取 id）
        operator_text = self._operator_combo.currentText().strip()
        operator_id: int | None = None
        if operator_text and ':' in operator_text:
            try:
                operator_id = int(operator_text.split(':')[0].strip())
            except (ValueError, TypeError):
                operator_id = None

        return {
            "sample_id": self._sample.id,
            "actual_return": self._actual_return_edit.date().toString("yyyy-MM-dd"),
            "operator_id": operator_id,
            "notes": self._notes_edit.text().strip(),
        }

    # ── 校验 ─────────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以增加校验逻辑。"""
        from PySide6.QtWidgets import QMessageBox

        data = self.get_data()

        # 实际归还日期必填（默认今天，不会空）
        if not data["actual_return"]:
            QMessageBox.warning(self, "提示", "请填写实际归还日期。")
            return

        super().accept()
