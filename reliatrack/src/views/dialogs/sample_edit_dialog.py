"""样品编辑弹窗 — 编辑 Sample 信息。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog


class SampleEditDialog(_BaseDialog):
    """样品编辑弹窗。

    Parameters
    ----------
    sample:
        必须提供已有的 Sample 对象以编辑。
    """

    _STATUS_OPTIONS = ["在库", "测试中", "已归还", "已报废"]
    _STATUS_MAP = {
        "在库": "in_stock",
        "测试中": "in_test",
        "已归还": "returned",
        "已报废": "scrapped",
    }
    _STATUS_REVERSE = {v: k for k, v in _STATUS_MAP.items()}

    def __init__(
        self,
        sample: Sample,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "✏️ 编辑样品",
            parent,
            width=440,
        )
        self._sample = sample

        # ── 基本信息 ──
        self._sn_edit = self._add_text_field(
            "SN *",
            default=sample.sn or "",
            placeholder="必填",
        )

        self._batch_no_edit = self._add_text_field(
            "批次号",
            default=sample.batch_no or "",
            placeholder="如：BATCH-001",
        )

        self._spec_edit = self._add_text_field(
            "规格",
            default=sample.spec or "",
            placeholder="如：DIP-14",
        )

        self._project_id_edit = self._add_text_field(
            "项目ID",
            default=str(sample.project_id) if sample.project_id else "",
            placeholder="关联项目编号",
        )

        self._add_separator()

        # ── 状态与位置 ──
        status_label = self._STATUS_REVERSE.get(
            sample.status, "在库"
        )
        self._status_combo = self._add_combo_field(
            "状态",
            items=self._STATUS_OPTIONS,
            default=status_label,
        )

        self._location_edit = self._add_text_field(
            "位置",
            default=sample.location or "",
            placeholder="如：A区-01柜",
        )

        self._add_separator()

        # ── 备注 ──
        self._notes_edit = self._add_text_area(
            "备注",
            default=sample.notes or "",
        )

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        status_label = self._status_combo.currentText()
        project_id_str = self._project_id_edit.text().strip()
        return {
            "sn": self._sn_edit.text().strip(),
            "batch_no": self._batch_no_edit.text().strip(),
            "spec": self._spec_edit.text().strip(),
            "project_id": int(project_id_str) if project_id_str else None,
            "status": self._STATUS_MAP.get(status_label, "in_stock"),
            "location": self._location_edit.text().strip(),
            "notes": self._notes_edit.toPlainText().strip(),
        }

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        sn = self._sn_edit.text().strip()
        if not sn:
            QMessageBox.warning(self, "校验失败", "SN 为必填项，请输入。")
            self._sn_edit.setFocus()
            return

        pid_str = self._project_id_edit.text().strip()
        if pid_str:
            try:
                int(pid_str)
            except ValueError:
                QMessageBox.warning(self, "校验失败", "项目ID 必须是数字。")
                self._project_id_edit.setFocus()
                return

        super().accept()
