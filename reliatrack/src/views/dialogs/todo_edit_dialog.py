"""待办事项编辑弹窗 — 新建 / 编辑 TodoItem。"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget, QComboBox

from src.models.todo import TodoItem
from src.models.project import Project
from src.views.dialogs.base_dialog import _BaseDialog


class TodoEditDialog(_BaseDialog):
    """待办事项新建 / 编辑弹窗。"""

    _QUADRANT_MAP = {
        "未分类": 0,
        "① 重要且紧急": 1,
        "② 重要不紧急": 2,
        "③ 不重要但紧急": 3,
        "④ 不重要不紧急": 4,
    }
    _PRIORITIES = ["high", "medium", "low"]
    _PRIORITY_LABELS = {"high": "高", "medium": "中", "low": "低"}
    _STATUSES = ["pending", "in_progress", "done"]
    _STATUS_LABELS = {"pending": "待处理", "in_progress": "进行中", "done": "已完成"}

    def __init__(
        self,
        todo: TodoItem | None = None,
        parent: QWidget | None = None,
        projects: list[Project] | None = None,
        default_project_id: int | None = None,
    ) -> None:
        is_edit = todo is not None
        super().__init__(
            "编辑待办事项" if is_edit else "新增待办事项",
            parent,
            width=460,
        )
        self._todo = todo
        self._projects = projects or []
        self._default_project_id = default_project_id

        # ── 标题 ──
        self._title_edit = self._add_text_field(
            "标题 *",
            default=todo.title if todo else "",
            placeholder="必填，如：完成MTBF测试报告",
        )

        # ── 项目 ──
        if todo:
            current_project = todo.project_id
        elif default_project_id is not None:
            current_project = default_project_id
        else:
            current_project = None
        project_items = ["(无)"]
        project_data: list[int | None] = [None]
        for p in self._projects:
            project_items.append(p.name)
            project_data.append(p.id)
        self._project_combo = self._add_combo_field(
            "项目",
            items=project_items,
            default=project_items[0],
            placeholder="选择关联项目",
        )
        # 设置实际的 project data
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        for label, pid in zip(project_items, project_data):
            self._project_combo.addItem(label, pid)
        # 恢复默认选中
        if current_project is not None:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == current_project:
                    self._project_combo.setCurrentIndex(i)
                    break
        self._project_combo.blockSignals(False)

        # ── 优先级 ──
        default_priority = todo.priority if todo else "medium"
        self._priority_combo = self._add_combo_field(
            "优先级",
            items=[self._PRIORITY_LABELS[p] for p in self._PRIORITIES],
            default=self._PRIORITY_LABELS.get(default_priority, "中"),
        )

        # ── 状态 ──
        default_status = todo.status if todo else "pending"
        self._status_combo = self._add_combo_field(
            "状态",
            items=[self._STATUS_LABELS[s] for s in self._STATUSES],
            default=self._STATUS_LABELS.get(default_status, "待处理"),
        )

        # ── 四象限 ──
        quadrant_items = ["未分类", "① 重要且紧急", "② 重要不紧急", "③ 不重要但紧急", "④ 不重要不紧急"]
        default_quadrant = {0: "未分类", 1: "① 重要且紧急", 2: "② 重要不紧急",
                            3: "③ 不重要但紧急", 4: "④ 不重要不紧急"} \
            .get(todo.quadrant if todo else 0, "未分类")
        self._quadrant_combo = self._add_combo_field(
            "优先级象限",
            items=quadrant_items,
            default=default_quadrant,
        )

        # ── 截止日期 ──
        self._due_date_edit = self._add_text_field(
            "截止日期",
            default=todo.due_date if todo else "",
            placeholder="可选，如：2026-07-15",
        )

        # ── 提醒时间 ──
        self._remind_at_edit = self._add_text_field(
            "提醒时间",
            default=todo.remind_at if todo else "",
            placeholder="可选，如：2026-07-15 14:00",
        )

        # ── 分类 ──
        self._category_combo = self._add_combo_field(
            "分类",
            items=["", "文档", "测试", "设备", "样品", "报告", "会议", "其他"],
            default=todo.category if todo else "",
            editable=True,
            placeholder="选择或输入分类",
        )

        # ── 描述 ──
        self._desc_edit = self._add_text_area(
            "描述",
            default=todo.description if todo else "",
            placeholder="可选，补充说明",
        )

    def get_data(self) -> dict[str, Any]:
        """获取弹窗数据。"""
        priority_labels = {"高": "high", "中": "medium", "低": "low"}
        status_labels = {"待处理": "pending", "进行中": "in_progress", "已完成": "done"}
        return {
            "project_id": self._project_combo.currentData(),
            "title": self._title_edit.text().strip(),
            "description": self._desc_edit.toPlainText().strip(),
            "priority": priority_labels.get(self._priority_combo.currentText(), "medium"),
            "status": status_labels.get(self._status_combo.currentText(), "pending"),
            "category": self._category_combo.currentText().strip(),
            "due_date": self._due_date_edit.text().strip(),
            "remind_at": self._remind_at_edit.text().strip(),
            "quadrant": self._QUADRANT_MAP.get(self._quadrant_combo.currentText(), 0),
        }

    def accept(self) -> None:
        """覆盖 accept 校验必填字段（审计 #27：原实现空标题可入库）。"""
        from PySide6.QtWidgets import QMessageBox
        if not self._title_edit.text().strip():
            QMessageBox.warning(self, "校验失败", "标题为必填项，请输入。")
            self._title_edit.setFocus()
            return
        super().accept()
