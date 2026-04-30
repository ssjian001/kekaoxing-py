"""Issue tracking handlers — attachments, CRUD callbacks, FA records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.views.dialogs.attachment_dialog import AttachmentDialog

if TYPE_CHECKING:
    from main import MainWindow


class IssueHandlers:
    """Handles issue/FA operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win
        self._current_fa_records: list = []

    def connect_signals(self) -> None:
        win = self._win
        v = win._issue_view
        v.issue_saved.connect(self._handle_issue_saved)
        v.issue_deleted.connect(self._handle_issue_deleted)
        v.issue_selected.connect(self._handle_issue_selected)
        v.fa_record_added.connect(self._handle_fa_record_added)
        v.btn_attachments.clicked.connect(self._on_issue_attachments)

    def _on_issue_attachments(self) -> None:
        """打开 Issue 附件管理弹窗。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = self._win._issue_view.get_selected_issue_id()
        if issue_id is None:
            self._win.statusBar().showMessage("⚠️ 请先选中一个 Issue", 5000)
            return
        dlg = AttachmentDialog(
            issue_id=issue_id,
            issue_service=ctrl.issue_service,
            parent=self._win,
        )
        dlg.exec()

    def _handle_issue_saved(self, data: dict) -> None:
        """Issue 新建/编辑后回调。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            if "id" in data:
                kwargs = {k: v for k, v in data.items() if k != "id"}
                ctrl.issue_service.update(data["id"], **kwargs)
                self._win.statusBar().showMessage(
                    f"✅ Issue #{data['id']} 已更新", 5000
                )
            else:
                ctrl.issue_service.create(**data)
                self._win.statusBar().showMessage("✅ Issue 已创建", 5000)
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            QMessageBox.critical(self._win, "保存失败", f"Issue 保存失败: {e}")

    def _handle_issue_deleted(self, issue_id: int) -> None:
        """Issue 删除后回调。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            ctrl.issue_service.delete(issue_id)
            self._win.statusBar().showMessage(
                f"✅ Issue #{issue_id} 已删除", 5000
            )
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            QMessageBox.critical(self._win, "删除失败", f"Issue 删除失败: {e}")

    def _handle_issue_selected(self, issue_id: int | None) -> None:
        """Issue 选中时加载 FA 记录。"""
        if issue_id is None:
            self._current_fa_records = []
            self._win._issue_view.refresh_fa([])
            return
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
        self._win._issue_view.refresh_fa(self._current_fa_records)

    def _handle_fa_record_added(self, data: dict) -> None:
        """FA 记录添加后回调。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = data.pop("issue_id", None)
        if issue_id is None:
            return
        try:
            ctrl.issue_service.add_fa_record(issue_id, **data)
            # 刷新 FA 面板
            self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
            self._win._issue_view.refresh_fa(self._current_fa_records)
            self._win.statusBar().showMessage("✅ FA 步骤已添加", 5000)
        except Exception as e:
            QMessageBox.critical(self._win, "保存失败", f"FA 记录添加失败: {e}")
