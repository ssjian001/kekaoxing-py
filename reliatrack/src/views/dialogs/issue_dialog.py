"""Issue 编辑弹窗 — 新建 / 编辑 Issue。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
)

from src.constants import SEVERITY_OPTIONS, ISSUE_STATUS_LABELS, RESOLUTION_OPTIONS
from src.models.issue import Issue
from src.views.dialogs.base_dialog import _BaseDialog

# 严重度选项：中文标签 → 英文存储值（按严重度降序）
_SEVERITY_OPTIONS = SEVERITY_OPTIONS


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
        task_list: list | None = None,
        default_task_id: int | None = None,
        sample_list: list | None = None,
        default_sample_id: int | None = None,
        knowledge_list: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = issue is not None
        super().__init__(
            "编辑 Issue" if is_edit else "新建 Issue",
            parent,
            width=520,
        )
        self._issue = issue
        self._project_list = project_list or []
        self._task_list = task_list or []
        self._sample_list = sample_list or []
        self._knowledge_list = knowledge_list or []

        # ── 基本信息 ──
        self._title_edit = self._add_text_field(
            "Issue描述 *", default=issue.title if issue else "",
            placeholder="必填",
        )
        self._failure_mode_edit = self._add_text_field(
            "失效模式", default=issue.failure_mode if issue else "",
            placeholder="如：短路 / 开路 / 变形 …",
        )
        self._failure_mode_edit.textChanged.connect(self._on_failure_mode_changed)
        self._failure_stage_edit = self._add_text_field(
            "失效阶段", default=issue.failure_stage if issue else "",
            placeholder="如：48h 高温 / 跌落第3次 …",
        )
        self._description_edit = self._add_text_area(
            "描述", default=issue.description if issue else "",
        )
        self._add_separator()

        # ── 知识库推荐（失效模式匹配时自动显示历史经验） ──
        self._kb_hint_label = self._add_label_field("知识库推荐", "输入失效模式后自动匹配历史经验")

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
        self._status_combo = self._add_combo_field("状态", items=list(ISSUE_STATUS_LABELS.values()))
        for i, (eng, chn) in enumerate(ISSUE_STATUS_LABELS.items()):
            self._status_combo.setItemData(i, eng, Qt.ItemDataRole.UserRole)
            if eng == (issue.status if issue else "open"):
                self._status_combo.setCurrentIndex(i)

        # ── 解决结果下拉 ──
        self._resolution_combo = self._add_combo_field(
            "解决结果",
            items=[label for label, _ in RESOLUTION_OPTIONS],
        )
        for i, (_, value) in enumerate(RESOLUTION_OPTIONS):
            self._resolution_combo.setItemData(i, value, Qt.ItemDataRole.UserRole)
        default_resolution = issue.resolution if issue else ""
        for i, (_, value) in enumerate(RESOLUTION_OPTIONS):
            if value == default_resolution:
                self._resolution_combo.setCurrentIndex(i)

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

        # ── 关联任务 ──
        task_names = ["（无）"]
        task_names += [f"{t.name}" for t in self._task_list]
        task_default = "（无）"
        # 编辑模式
        if issue and issue.task_id:
            for t in self._task_list:
                if t.id == issue.task_id:
                    task_default = t.name
                    break
        elif default_task_id is not None and not is_edit:
            for t in self._task_list:
                if t.id == default_task_id:
                    task_default = t.name
                    break
        self._task_combo = self._add_combo_field(
            "关联任务",
            items=task_names,
            default=task_default,
        )

        # ── 关联样品 ──
        sample_names = ["（无）"]
        sample_names += [f"{s.sn}" for s in self._sample_list]
        sample_default = "（无）"
        # 编辑模式
        if issue and issue.sample_id:
            for s in self._sample_list:
                if s.id == issue.sample_id:
                    sample_default = s.sn
                    break
        elif default_sample_id is not None and not is_edit:
            for s in self._sample_list:
                if s.id == default_sample_id:
                    sample_default = s.sn
                    break
        self._sample_combo = self._add_combo_field(
            "关联样品",
            items=sample_names,
            default=sample_default,
        )

        self._add_separator()

        # ── 失效代码 & 发生次数 ──
        self._failure_code_edit = self._add_text_field(
            "失效代码",
            default=issue.failure_code if issue else "",
            placeholder="如 GJB/Z 1391 编码",
        )
        self._occurrence_spin = self._add_spin_field(
            "发生次数",
            default=issue.occurrence_count if issue else 1,
            min_val=1, max_val=9999,
        )

        # ── DRI 责任人 ──
        self._dri_edit = self._add_text_field(
            "DRI 责任人",
            default=getattr(issue, "dri_name", "") or "" if issue else "",
            placeholder="输入责任人姓名",
        )

        # ── 报告人 ──
        self._reporter_edit = self._add_text_field(
            "报告人",
            default=getattr(issue, "reporter_name", "") or "" if issue else "",
            placeholder="发现问题的人",
        )

        # ── 根因 & 解决方案 ──
        self._root_cause_edit = self._add_text_area(
            "根因分析", default=issue.root_cause if issue else "",
        )
        self._improvement_edit = self._add_text_area(
            "改善对策",
            default=issue.improvement_measures if issue else "",
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
        # 解析 task_id
        task_id: int | None = None
        task_text = self._task_combo.currentText()
        if task_text != "（无）":
            for t in self._task_list:
                if t.name == task_text:
                    task_id = t.id
                    break
        # 解析 sample_id
        sample_id: int | None = None
        sample_text = self._sample_combo.currentText()
        if sample_text != "（无）":
            for s in self._sample_list:
                if s.sn == sample_text:
                    sample_id = s.id
                    break
        return {
            "title": self._title_edit.text().strip(),
            "failure_mode": self._failure_mode_edit.text().strip(),
            "failure_stage": self._failure_stage_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "severity": self._severity_combo.currentData(Qt.ItemDataRole.UserRole) or self._severity_combo.currentText(),
            "priority": self._priority_spin.value(),
            "status": self._status_combo.currentData(Qt.ItemDataRole.UserRole) or self._status_combo.currentText(),
            "project_id": project_id,
            "task_id": task_id,
            "sample_id": sample_id,
            "failure_code": self._failure_code_edit.text().strip(),
            "occurrence_count": self._occurrence_spin.value(),
            "dri_name": self._dri_edit.text().strip(),
            "reporter_name": self._reporter_edit.text().strip(),
            "root_cause": self._root_cause_edit.toPlainText().strip(),
            "improvement_measures": self._improvement_edit.toPlainText().strip(),
            "resolution": self._resolution_combo.currentData(Qt.ItemDataRole.UserRole) or "",
        }

    # ── 知识库推荐 ───────────────────────────────────────────

    def _on_failure_mode_changed(self, text: str) -> None:
        """失效模式输入变化时搜索知识库推荐。"""
        keyword = text.strip().lower()
        if not keyword or not self._knowledge_list:
            self._kb_hint_label.setText("输入失效模式后自动匹配历史经验")
            return

        # 模糊匹配：failure_mode / keywords / category 包含关键词
        matches = []
        for entry in self._knowledge_list:
            haystack = " ".join([
                entry.failure_mode or "",
                entry.keywords or "",
                entry.category or "",
                entry.summary or "",
            ]).lower()
            if keyword in haystack:
                matches.append(entry)
            if len(matches) >= 3:
                break

        if not matches:
            self._kb_hint_label.setText("未找到匹配的知识库条目")
            return

        parts = []
        for i, m in enumerate(matches, 1):
            hint = f"[{i}] {m.failure_mode or m.category}"
            if m.improvement:
                hint += f" → {m.improvement[:40]}"
            elif m.resolution:
                hint += f" → {m.resolution[:40]}"
            if m.reference_standard:
                hint += f" ({m.reference_standard})"
            parts.append(hint)
        self._kb_hint_label.setText("\n".join(parts))

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        from PySide6.QtWidgets import QMessageBox

        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(self, "校验失败", "Issue描述为必填项，请输入。")
            self._title_edit.setFocus()
            return
        super().accept()
