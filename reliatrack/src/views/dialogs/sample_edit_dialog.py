"""样品编辑弹窗 — 编辑 Sample 信息。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog
from src.styles.icon import RI_EDIT
from src.constants import (
    SAMPLE_STATUS_LABELS,
    SAMPLE_STATUS_OPTIONS,
    SAMPLE_STATUS_MAP,
    SAMPLE_STATUS_REVERSE,
)

# 枚举外/legacy 状态占位项后缀：保留原状态值并标记为不可手选
_LEGACY_STATUS_SUFFIX = "（原状态，不可改）"


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
            "编辑样品",
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

        self._supplier_edit = self._add_text_field(
            "供应商",
            default=sample.supplier or "",
            placeholder="如：村田/TDK",
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
        # 枚举外/legacy 状态不映射成默认标签（否则打开不改动直接保存就会
        # 把原状态洗成"在库"写回库，审计 P2-14）：追加占位项并默认选中，
        # get_data 对占位项按原值透传。
        self._legacy_status_value: str | None = None
        status_default = self._find_status_label(sample.status)
        status_items = list(self._STATUS_OPTIONS)
        if status_default not in status_items:
            status_items = [*status_items, status_default]
            self._legacy_status_value = sample.status
        self._status_combo = self._add_combo_field(
            "状态",
            items=status_items,
            default=status_default,
        )

        self._location_edit = self._add_text_field(
            "位置",
            default=sample.location or "",
            placeholder="如：A区-01柜",
        )
        self._test_hours_spin = self._add_spin_field(
            "累计测试(h)",
            min_val=0,
            max_val=99999,
            default=int(sample.test_hours) if sample and sample.test_hours else 0,
        )

        self._add_separator()

        # ── 备注 ──
        self._notes_edit = self._add_text_area(
            "备注",
            default=sample.notes or "",
        )

    # ── 状态标签 ↔ 状态值 ──────────────────────────────────────

    @staticmethod
    def _find_status_label(status: str | None) -> str:
        """样品状态的显示标签。

        枚举内值走 SAMPLE_STATUS_LABELS（唯一真源）；枚举外/legacy 值
        （如旧中文状态、'in_use'）保留原状态并加后缀，标记为不可手选，
        绝不回落成默认标签（否则保存即静默改写数据，审计 P2-14）。
        """
        label = SAMPLE_STATUS_LABELS.get(status or "")
        if label is not None and label in SAMPLE_STATUS_OPTIONS:
            return label
        if not status:
            return SAMPLE_STATUS_OPTIONS[0]
        return f"{SAMPLE_STATUS_LABELS.get(status, status)}{_LEGACY_STATUS_SUFFIX}"

    def _status_value_for(self, text: str) -> str:
        """下拉文本 → 状态值。

        占位项（枚举外原状态）原值透传；无法识别时保留原样品状态，
        绝不静默回落 "in_stock"。
        """
        if self._legacy_status_value is not None and text.endswith(_LEGACY_STATUS_SUFFIX):
            return self._legacy_status_value
        value = self._STATUS_MAP.get(text)
        if value is not None:
            return value
        if self._sample is not None and self._sample.status:
            return self._sample.status
        return "in_stock"

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
            "status": self._status_value_for(status_label),
            "location": self._location_edit.text().strip(),
            "test_hours": float(self._test_hours_spin.value()),
            "notes": self._notes_edit.toPlainText().strip(),
            "supplier": self._supplier_edit.text().strip(),
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
