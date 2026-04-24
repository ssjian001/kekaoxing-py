"""FA 分析记录弹窗 — 添加 FA 步骤。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
)

from src.views.dialogs.base_dialog import _BaseDialog


class FARecordDialog(_BaseDialog):
    """FA 分析步骤添加弹窗。

    Parameters
    ----------
    existing_step_nos:
        已有步骤号列表，用于自动计算下一个 step_no。
    """

    def __init__(
        self,
        existing_step_nos: list[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("🔬 新建 FA 分析步骤", parent, width=480)
        step_nos = existing_step_nos or []
        next_step = max(step_nos, default=0) + 1

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

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        return {
            "step_no": self._step_spin.value(),
            "step_title": self._title_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "method": self._method_combo.currentText(),
            "findings": self._findings_edit.toPlainText().strip(),
        }
