"""样品入库弹窗 — SN(必填) / 批次号 / 规格型号 / 项目ID / 位置 / 备注。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QMessageBox,
)

from src.styles.theme import RED
from src.views.dialogs.base_dialog import _BaseDialog


class SampleCheckInDialog(_BaseDialog):
    """样品入库弹窗。

    Parameters
    ----------
    sn_exists_cb:
        回调函数，接收 SN 字符串，返回 True 表示该 SN 已存在。
        由调用方注入，用于查库校验。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        sn_exists_cb: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__("📦 样品入库", parent, width=460)
        self._sn_exists_cb = sn_exists_cb or (lambda _: False)

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
        self._project_edit = self._add_text_field(
            label="项目 ID",
            placeholder="选填",
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

        # SN 必填标红提示
        self._sn_edit.setStyleSheet(self._sn_edit.styleSheet() or "")

    # ── 公开 API ─────────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        # project_id 需要转为 int（DB 列为 INTEGER）
        raw_project = self._project_edit.text().strip()
        project_id: int | None = None
        if raw_project:
            try:
                project_id = int(raw_project)
            except ValueError:
                pass  # 无效输入当作 None 处理
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
