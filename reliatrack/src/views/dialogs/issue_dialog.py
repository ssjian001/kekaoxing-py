"""Issue 编辑弹窗 — 新建 / 编辑 Issue。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
)

from src.models.issue import Issue
from src.views.dialogs.base_dialog import _BaseDialog

# 严重度选项：中文标签 → 英文存储值（按严重度降序）
_SEVERITY_OPTIONS: list[tuple[str, str]] = [
    ("严重", "critical"),
    ("主要", "major"),
    ("次要", "minor"),
    ("外观", "cosmetic"),
]


class IssueEditDialog(_BaseDialog):
    """Issue 新建 / 编辑弹窗。

    Parameters
    ----------
    issue:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    project_list:
        项目列表（用于关联项目下拉框）。
    default_project_id:
        默认选中的项目 ID（通常为当前筛选的项目）。
    """

    def __init__(
        self,
        issue: Issue | None = None,
        project_list: list | None = None,
        default_project_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = issue is not None
        super().__init__(
            "✏️ 编辑 Issue" if is_edit else "➕ 新建 Issue",
            parent,
            width=520,
        )
        self._issue = issue
        self._project_list = project_list or []

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
            items=[label for label, _ in _SEVERITY_OPTIONS],
            default="",
        )
        for i, (_, value) in enumerate(_SEVERITY_OPTIONS):
            self._severity_combo.setItemData(i, value, Qt.ItemDataRole.UserRole)
        # 根据英文值设置默认选中项
        default_severity = issue.severity if issue else "major"
        for i, (_, value) in enumerate(_SEVERITY_OPTIONS):
            if value == default_severity:
                self._severity_combo.setCurrentIndex(i)
                break
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

        # ── 关联项目 ──
        project_names = ["（无）"]
        project_names += [f"{p.name}" for p in self._project_list]
        project_default = "（无）"
        # 编辑模式：匹配已有 project_id
        if issue and issue.project_id:
            for p in self._project_list:
                if p.id == issue.project_id:
                    project_default = p.name
                    break
        # 新建模式：匹配默认 project_id
        elif default_project_id is not None and not is_edit:
            for p in self._project_list:
                if p.id == default_project_id:
                    project_default = p.name
                    break
        self._project_combo = self._add_combo_field(
            "关联项目",
            items=project_names,
            default=project_default,
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
        # 从下拉框解析 project_id
        project_id: int | None = None
        proj_text = self._project_combo.currentText()
        if proj_text != "（无）":
            for p in self._project_list:
                if p.name == proj_text:
                    project_id = p.id
                    break
        return {
            "title": self._title_edit.text().strip(),
            "failure_mode": self._failure_mode_edit.text().strip(),
            "failure_stage": self._failure_stage_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "severity": self._severity_combo.currentData(Qt.ItemDataRole.UserRole) or self._severity_combo.currentText(),
            "priority": self._priority_spin.value(),
            "status": self._status_combo.currentText(),
            "project_id": project_id,
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
