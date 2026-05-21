"""样品出库弹窗 — 显示样品信息 + 填写出库字段。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog
from src.constants import SAMPLE_STATUS_LABELS


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
        technicians: list | None = None,
        task_list: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("样品出库", parent, width=460)
        self._sample = sample
        self._technicians = technicians or []
        self._task_list = task_list or []

        # ── 只读信息展示 ──
        self._add_separator()
        self._add_label_field("SN", sample.sn)
        self._add_label_field("规格型号", sample.spec or "—")
        self._add_label_field("当前状态", SAMPLE_STATUS_LABELS.get(sample.status, sample.status))
        self._add_separator()

        # ── 出库表单 ──
        self._purpose_edit = self._add_text_field(
            label="出库目的 *",
            placeholder="测试 / 拆解分析 / 对比 / 借用 …",
        )

        # 关联任务 — 下拉选择
        task_items = ["（无）"] + [f"#{t.id} {t.name}" for t in self._task_list]
        self._task_combo = self._add_combo_field(
            label="关联任务",
            items=task_items,
            default="（无）",
        )

        self._return_edit = self._add_date_field(
            label="预计归还日期",
        )
        tech_names = [f"{t.id}: {t.name}" if hasattr(t, 'id') else str(t) for t in self._technicians]
        self._operator_combo = self._add_combo_field(
            label="操作人 *",
            items=tech_names,
            editable=True,
            placeholder="选择或输入技术员",
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

        # 解析关联任务 ID（从下拉框提取）
        task_text = self._task_combo.currentText().strip()
        related_task_id: int | None = None
        if task_text != "（无）" and task_text.startswith("#"):
            try:
                related_task_id = int(task_text.split()[0][1:])  # "#3 xxx" → 3
            except (ValueError, TypeError, IndexError):
                pass

        # 解析操作人 operator_id（从 "id: name" 格式提取 id）
        operator_text = self._operator_combo.currentText().strip()
        operator_id: int | None = None
        if operator_text:
            if ':' in operator_text:
                try:
                    operator_id = int(operator_text.split(':')[0].strip())
                except (ValueError, TypeError):
                    operator_id = None
            # 纯文本输入时无法匹配 technician ID，设为 None

        return {
            "sample_id": self._sample.id,
            "purpose": self._purpose_edit.text().strip(),
            "related_task_id": related_task_id,
            "expected_return": self._return_edit.date().toString("yyyy-MM-dd"),
            "operator_id": operator_id,
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

        super().accept()
