"""样品入库弹窗 — SN(必填) / 批次号 / 规格型号 / 关联项目 / 位置 / 备注。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QMessageBox,
)

from src.views.dialogs.base_dialog import _BaseDialog


class SampleCheckInDialog(_BaseDialog):
    """样品入库弹窗。

    Parameters
    ----------
    sn_exists_cb:
        回调函数，接收 SN 字符串，返回 True 表示该 SN 已存在。
        由调用方注入，用于查库校验。
    project_list:
        项目列表（用于关联项目下拉框）。
    default_project_id:
        默认选中的项目 ID（通常为当前筛选的项目）。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        sn_exists_cb: Callable[[str], bool] | None = None,
        project_list: list | None = None,
        default_project_id: int | None = None,
    ) -> None:
        super().__init__("样品入库", parent, width=460)
        self._sn_exists_cb = sn_exists_cb or (lambda _: False)
        self._project_list = project_list or []

        # 表单字段
        self._sn_edit = self._add_text_field(
            label="SN *",
            placeholder="必填，唯一标识",
        )
        self._batch_edit = self._add_text_field(
            label="批次号",
            placeholder="选填",
        )
        self._spec_edit = self._add_text_field(
            label="规格型号",
            placeholder="选填",
        )

        # 关联项目下拉框
        project_names = ["（无）"]
        project_names += [f"{p.name}" for p in self._project_list]
        project_default = "（无）"
        if default_project_id is not None:
            for p in self._project_list:
                if p.id == default_project_id:
                    project_default = p.name
                    break
        self._project_combo = self._add_combo_field(
            "关联项目",
            items=project_names,
            default=project_default,
        )

        self._location_edit = self._add_text_field(
            label="存放位置",
            placeholder="选填，如 A-01-03",
        )

        self._add_separator()

        self._notes_edit = self._add_text_field(
            label="备注",
            placeholder="选填",
        )

    # ── 公开 API ─────────────────────────────────────────────────

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
            "sn": self._sn_edit.text().strip(),
            "batch_no": self._batch_edit.text().strip(),
            "spec": self._spec_edit.text().strip(),
            "project_id": project_id,
            "location": self._location_edit.text().strip(),
            "notes": self._notes_edit.text().strip(),
        }

    # ── 校验 ─────────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以增加校验逻辑。"""
        data = self.get_data()

        sn = data["sn"]
        if not sn:
            QMessageBox.warning(self, "校验失败", "SN 为必填项，请输入。")
            self._sn_edit.setFocus()
            return

        if self._sn_exists_cb(sn):
            QMessageBox.warning(
                self,
                "SN 重复",
                f"SN「{sn}」已存在于库中，请检查后重新输入。",
            )
            self._sn_edit.selectAll()
            self._sn_edit.setFocus()
            return

        super().accept()
