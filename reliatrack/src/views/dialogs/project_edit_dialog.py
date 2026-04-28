"""项目编辑弹窗 — 新建 / 编辑 Project。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)

from src.models.project import Project
from src.views.dialogs.base_dialog import _BaseDialog


class ProjectEditDialog(_BaseDialog):
    """项目新建 / 编辑弹窗。

    Parameters
    ----------
    project:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    """

    _STATUS_OPTIONS = ["进行中", "暂停", "已关闭"]
    _STATUS_MAP = {
        "进行中": "active",
        "暂停": "paused",
        "已关闭": "closed",
    }
    _STATUS_REVERSE = {v: k for k, v in _STATUS_MAP.items()}

    def __init__(
        self,
        project: Project | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = project is not None
        super().__init__(
            "✏️ 编辑项目" if is_edit else "➕ 新建项目",
            parent,
            width=440,
        )
        self._project = project

        # ── 基本信息 ──
        self._name_edit = self._add_text_field(
            "名称 *",
            default=project.name if project else "",
            placeholder="必填",
        )
        self._product_edit = self._add_text_field(
            "产品",
            default=project.product if project else "",
            placeholder="如：产品A",
        )
        self._customer_edit = self._add_text_field(
            "客户",
            default=project.customer if project else "",
            placeholder="如：客户B",
        )

        self._add_separator()

        # ── 描述 ──
        self._desc_edit = self._add_text_area(
            "描述",
            default=project.description if project else "",
        )

        self._add_separator()

        # ── 状态 ──
        status_label = self._STATUS_REVERSE.get(
            project.status, "进行中"
        ) if project else "进行中"
        self._status_combo = self._add_combo_field(
            "状态",
            items=self._STATUS_OPTIONS,
            default=status_label,
        )

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        status_label = self._status_combo.currentText()
        data: dict = {
            "name": self._name_edit.text().strip(),
            "product": self._product_edit.text().strip(),
            "customer": self._customer_edit.text().strip(),
            "description": self._desc_edit.toPlainText().strip(),
            "status": self._STATUS_MAP.get(status_label, "active"),
        }
        if self._project is not None and self._project.id is not None:
            data["id"] = self._project.id
        return data

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "校验失败", "项目名称为必填项，请输入。")
            self._name_edit.setFocus()
            return

        super().accept()
