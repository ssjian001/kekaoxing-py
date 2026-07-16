"""批量操作对话框 — BatchOperationDialog。"""

from __future__ import annotations

import logging

logger = logging.getLogger("views.bug_tracker.batch_dialog")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.services.issue_service import IssueService
from src.styles.constants import PADDING_LARGE, SPACING_MEDIUM
from src.styles.toast import ToastWidget


class BatchOperationDialog(QDialog):
    """批量操作对话框 — 改状态/改严重度/改优先级/设置DRI。"""

    def __init__(
        self,
        issue_ids: list[int],
        issue_service: IssueService,
        parent: QWidget | None = None,
        undo_manager=None,
        dri_names: list[str] | None = None,
    ):
        super().__init__(parent)
        self._issue_ids = issue_ids
        self._service = issue_service
        self._undo_manager = undo_manager
        self._dri_names = dri_names or []

        self.setWindowTitle(f"批量操作 — 已选 {len(issue_ids)} 个 Issue")
        self.setMinimumSize(400, 300)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._result_summary: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE)
        layout.setSpacing(SPACING_MEDIUM)

        # 已选列表
        layout.addWidget(QLabel(f"已选 {len(self._issue_ids)} 个 Issue:"))
        id_list = QListWidget()
        id_list.setMaximumHeight(120)
        for iid in self._issue_ids[:20]:
            item = QListWidgetItem(f"#{iid}")
            id_list.addItem(item)
        if len(self._issue_ids) > 20:
            id_list.addItem(f"... 还有 {len(self._issue_ids) - 20} 个")
        layout.addWidget(id_list)

        # 操作类型
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("操作:"))
        self._op_combo = QComboBox()
        self._op_combo.addItems(["改状态", "改严重度", "改优先级", "设置DRI"])
        self._op_combo.currentTextChanged.connect(self._update_value_widget)
        op_row.addWidget(self._op_combo, stretch=1)
        layout.addLayout(op_row)

        # 目标值
        val_row = QHBoxLayout()
        val_row.addWidget(QLabel("目标值:"))
        self._value_combo = QComboBox()
        self._value_combo.setMinimumWidth(140)
        val_row.addWidget(self._value_combo, stretch=1)
        layout.addLayout(val_row)
        self._update_value_widget(self._op_combo.currentText())

        # 按钮
        btn_box = QDialogButtonBox()
        btn_cancel = btn_box.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        btn_cancel.clicked.connect(self.reject)
        self._btn_confirm = btn_box.addButton("确认执行", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_confirm.clicked.connect(self._execute_batch)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _update_value_widget(self, operation: str) -> None:
        """根据操作类型更新目标值下拉选项。"""
        self._value_combo.setEditable(False)
        self._value_combo.clear()
        if operation == "改状态":
            for eng, chn in [("open", "待处理"), ("analyzing", "分析中"),
                             ("verified", "已验证"), ("closed", "已关闭")]:
                self._value_combo.addItem(chn, eng)
        elif operation == "改严重度":
            for eng, chn in [("critical", "严重"), ("major", "主要"),
                             ("minor", "次要"), ("cosmetic", "外观")]:
                self._value_combo.addItem(chn, eng)
        elif operation == "改优先级":
            for i in range(1, 6):
                self._value_combo.addItem(f"P{i}", i)
        elif operation == "设置DRI":
            self._value_combo.setEditable(True)
            self._value_combo.addItem("（清除DRI）", "")
            for name in sorted(set(self._dri_names)):
                self._value_combo.addItem(name, name)

    def _execute_batch(self) -> None:
        """执行批量操作，逐个 issue 调用 update()。"""
        operation = self._op_combo.currentText()
        target_value = self._value_combo.currentData()
        # 设置DRI 可编辑模式：手动输入时 currentData() 返回 None，取文本
        if operation == "设置DRI" and target_value is None:
            target_value = self._value_combo.currentText().strip()

        # 映射操作 → kwargs field
        field_map = {
            "改状态": "status",
            "改严重度": "severity",
            "改优先级": "priority",
            "设置DRI": "dri_name",
        }
        field = field_map.get(operation, "")
        if not field:
            return

        updated = 0
        failed = 0
        for issue_id in self._issue_ids:
            try:
                # 获取旧值用于 undo
                old_issue = self._service.get(issue_id)
                old_value = getattr(old_issue, field, None) if old_issue else None

                self._service.update(issue_id, operator="batch", **{field: target_value})
                updated += 1

                # 推送 undo 命令（用 record 而非直接 push，确保 redo_stack 清空）
                if self._undo_manager is not None and old_issue is not None:
                    from src.services.undo_manager import UpdateFieldCommand
                    cmd = UpdateFieldCommand(
                        self._service._repo, issue_id, field,
                        old_value, target_value, "Issue",
                    )
                    self._undo_manager.record(cmd)
            except Exception:
                logger.exception("Error in batch_dialog")
                failed += 1

        self._result_summary = f"已更新 {updated} 条，失败 {failed} 条"
        ToastWidget.show_toast(self.parent(), self._result_summary,
                               ToastWidget.SUCCESS if failed == 0 else ToastWidget.WARNING)
        self.accept()

    def result_summary(self) -> str:
        return self._result_summary
