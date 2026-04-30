"""样品编辑弹窗 — 编辑 Sample 信息。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog
from src.constants import (
    SAMPLE_STATUS_OPTIONS,
    SAMPLE_STATUS_MAP,
    SAMPLE_STATUS_REVERSE,
)


class SampleEditDialog(_BaseDialog):
    """样品编辑弹窗。

    Parameters
    ----------
    sample:
        必须提供已有的 Sample 对象以编辑。
    project_list:
        项目列表（用于关联项目下拉框）。
    """

    _STATUS_OPTIONS = SAMPLE_STATUS_OPTIONS
    _STATUS_MAP = SAMPLE_STATUS_MAP
    _STATUS_REVERSE = SAMPLE_STATUS_REVERSE

    def __init__(
        self,
        sample: Sample,
        project_list: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "✏️ 编辑样品",
            parent,
            width=440,
        )
        self._sample = sample
        self._project_list = project_list or []

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

        # ── 关联项目下拉框 ──
        project_names = ["（无）"]
        project_names += [f"{p.name}" for p in self._project_list]
        project_default = "（无）"
        if sample.project_id:
            for p in self._project_list:
                if p.id == sample.project_id:
                    project_default = p.name
                    break
        self._project_combo = self._add_combo_field(
            "关联项目",
            items=project_names,
            default=project_default,
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
        # 从下拉框解析 project_id
        project_id: int | None = None
        proj_text = self._project_combo.currentText()
        if proj_text != "（无）":
            for p in self._project_list:
                if p.name == proj_text:
                    project_id = p.id
                    break
        return {
            "sn": self._sn_edit.text().strip(),
            "batch_no": self._batch_no_edit.text().strip(),
            "spec": self._spec_edit.text().strip(),
            "project_id": project_id,
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

        super().accept()
