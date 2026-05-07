"""导出选项对话框 — 选择导出类型、格式和项目筛选。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from src.views.dialogs.base_dialog import _BaseDialog


class ExportDialog(_BaseDialog):
    """导出选项对话框。

    选择导出内容（测试任务/Issue/样品/综合报告）和格式（Excel/PDF/Word）。
    可选按项目筛选。
    """

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
