"""导出选项对话框 — 选择导出类型和格式。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from src.views.dialogs.base_dialog import _BaseDialog


class ExportDialog(_BaseDialog):
    """导出选项对话框。

    选择导出内容（测试任务/Issue/样品/综合报告）和格式（Excel/PDF）。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("📤 导出", parent, width=400)

        self._content_combo = self._add_combo_field(
            "导出内容",
            items=["测试任务 (当前计划)", "Issue 列表", "样品台账", "综合测试报告 (PDF)"],
        )
        self._format_combo = self._add_combo_field(
            "格式",
            items=["Excel (.xlsx)", "PDF (.pdf)"],
        )

    def get_data(self) -> dict:
        """返回 {content: str, format: str}。"""
        return {
            "content": self._content_combo.currentText(),
            "format": self._format_combo.currentText(),
        }
