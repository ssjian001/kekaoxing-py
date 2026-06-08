"""导出选项对话框 — 选择导出类型、格式和项目筛选。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QFormLayout
from PySide6.QtCore import Qt
from src.views.dialogs.base_dialog import _BaseDialog


class ExportDialog(_BaseDialog):
    """导出选项对话框。

    选择导出内容（测试任务/Issue/样品/综合报告）和格式（Excel/PDF/Word）。
    可选按项目筛选。
    """

    # 8D 报告基于单个 Issue，不需要项目筛选
    _NO_PROJECT_FILTER_TYPES = {"8D"}

    def __init__(
        self,
        parent: QWidget | None = None,
        projects: list[tuple[int, str]] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        projects:
            [(project_id, project_name), ...] 列表。若提供则显示项目筛选下拉框。
        """
        super().__init__("导出", parent, width=400)

        self._content_combo = self._add_combo_field(
            "导出内容",
            items=["测试任务 (当前计划)", "Issue 列表", "样品台账", "综合测试报告", "DVP&R 报告", "8D 报告"],
        )
        self._format_combo = self._add_combo_field(
            "格式",
            items=["Excel (.xlsx)", "PDF (.pdf)", "Word (.docx)"],
        )

        # 项目筛选（可选）
        proj_items = ["（全部项目）"] + [
            f"{pid} — {pname}" for pid, pname in (projects or [])
        ]
        self._project_combo = self._add_combo_field(
            "项目筛选",
            items=proj_items,
        )

        # 记住项目筛选所在行的索引，用于显示/隐藏
        self._project_row_idx = self._form.rowCount() - 1

        # 内容类型切换时动态控制项目筛选可见性
        self._content_combo.currentTextChanged.connect(self._on_content_changed)
        # 初始化一次
        self._on_content_changed(self._content_combo.currentText())

    def _on_content_changed(self, text: str) -> None:
        """根据内容类型控制项目筛选的可见性。"""
        hide = any(k in text for k in self._NO_PROJECT_FILTER_TYPES)
        # QFormLayout: 隐藏 label + field 整行
        label_item = self._form.itemAt(self._project_row_idx, QFormLayout.ItemRole.LabelRole)
        field_item = self._form.itemAt(self._project_row_idx, QFormLayout.ItemRole.FieldRole)
        if label_item and label_item.widget():
            label_item.widget().setVisible(not hide)
        if field_item and field_item.widget():
            field_item.widget().setVisible(not hide)

    def get_data(self) -> dict:
        """返回 {content: str, format: str, project_id: int|None}。"""
        proj_text = self._project_combo.currentText()
        project_id: int | None = None
        if proj_text and proj_text != "（全部项目）" and " — " in proj_text:
            try:
                project_id = int(proj_text.split(" — ")[0])
            except ValueError:
                pass
        return {
            "content": self._content_combo.currentText(),
            "format": self._format_combo.currentText(),
            "project_id": project_id,
        }
