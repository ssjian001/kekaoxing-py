"""Issue 编辑弹窗 — 新建 / 编辑 Issue。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
)

from src.models.issue import Issue
from src.views.dialogs.base_dialog import _BaseDialog


class IssueEditDialog(_BaseDialog):
    """Issue 新建 / 编辑弹窗。

    Parameters
    ----------
    issue:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    """

    def __init__(
        self,
        issue: Issue | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = issue is not None
        super().__init__(
            "✏️ 编辑 Issue" if is_edit else "➕ 新建 Issue",
            parent,
            width=520,
        )
        self._issue = issue

        # ── 基本信息 ──
        self._title_edit = self._add_text_field(
            "标题 *", default=issue.title if issue else "",
            placeholder="必填",
        )
        self._failure_mode_edit = self._add_text_field(
            "失效模式", default=issue.failure_mode if issue else "",
            placeholder="如：短路 / 开路 / 变形 …",
        )
        self._failure_stage_edit = self._add_text_field(
            "失效阶段", default=issue.failure_stage if issue else "",
            placeholder="如：48h 高温 / 跌落第3次 …",
        )
        self._description_edit = self._add_text_area(
            "描述", default=issue.description if issue else "",
        )
        self._add_separator()

        # ── 属性 ──
        self._severity_combo = self._add_combo_field(
            "严重度",
            items=["critical", "major", "minor", "cosmetic"],
            default=issue.severity if issue else "major",
        )
        self._priority_spin = self._add_spin_field(
            "优先级 (1-5)",
            default=issue.priority if issue else 3,
            min_val=1, max_val=5,
        )
        self._status_combo = self._add_combo_field(
            "状态",
            items=["open", "analyzing", "verified", "closed"],
            default=issue.status if issue else "open",
        )
        self._add_separator()

        # ── 根因 & 解决方案 ──
        self._root_cause_edit = self._add_text_area(
            "根因分析", default=issue.root_cause if issue else "",
        )
        self._resolution_edit = self._add_text_area(
            "解决方案", default=issue.resolution if issue else "",
        )

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        return {
            "title": self._title_edit.text().strip(),
            "failure_mode": self._failure_mode_edit.text().strip(),
            "failure_stage": self._failure_stage_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "severity": self._severity_combo.currentText(),
            "priority": self._priority_spin.value(),
            "status": self._status_combo.currentText(),
            "root_cause": self._root_cause_edit.toPlainText().strip(),
            "resolution": self._resolution_edit.toPlainText().strip(),
        }

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        from PySide6.QtWidgets import QMessageBox

        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(self, "校验失败", "标题为必填项，请输入。")
            self._title_edit.setFocus()
            return
        super().accept()
