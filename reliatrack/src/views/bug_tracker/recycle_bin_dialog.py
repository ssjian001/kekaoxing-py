"""Issue 回收站对话框 — 查看/恢复/彻底删除已软删除的 Issue。

2026-08-10 审计发现: issue_service.list_deleted/restore/purge_old 只有
repo+service 层实现，无任何 UI 调用。软删 Issue 逃出 undo 栈后重启即
永久不可见（数据在 DB 但无访问路径）。此对话框补上回收站入口。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.services.issue_service import IssueService


class RecycleBinDialog(QDialog):
    """已删除 Issue 回收站。"""

    def __init__(self, issue_service: IssueService, parent=None) -> None:
        super().__init__(parent)
        self._svc = issue_service
        self.setWindowTitle("Issue 回收站")
        self.setMinimumSize(720, 420)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        tip = QLabel("以下为已删除（软删）的 Issue，可恢复或彻底删除。彻底删除不可撤销。")
        tip.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(tip)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["标题", "严重度", "删除时间", "ID"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_restore = QPushButton("恢复选中")
        self._btn_restore.clicked.connect(self._on_restore)
        btn_row.addWidget(self._btn_restore)
        self._btn_purge = QPushButton("彻底删除选中")
        self._btn_purge.setStyleSheet("color: #d20f39;")
        self._btn_purge.clicked.connect(self._on_purge)
        btn_row.addWidget(self._btn_purge)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _load(self) -> None:
        items = self._svc.list_deleted()
        self._table.setRowCount(len(items))
        for row, issue in enumerate(items):
            title_item = QTableWidgetItem(issue.title or "(无标题)")
            sev_item = QTableWidgetItem(issue.severity or "")
            del_item = QTableWidgetItem(issue.deleted_at or "")
            id_item = QTableWidgetItem(str(issue.id or ""))
            for col, it in enumerate((title_item, sev_item, del_item, id_item)):
                self._table.setItem(row, col, it)
            # 存 id 到第一列 UserRole
            title_item.setData(Qt.ItemDataRole.UserRole, issue.id)

    def _selected_issue_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_restore(self) -> None:
        issue_id = self._selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "恢复", "请先选中一个 Issue")
            return
        self._svc.restore(issue_id)
        QMessageBox.information(self, "恢复", "已恢复该 Issue")
        self._load()

    def _on_purge(self) -> None:
        issue_id = self._selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "彻底删除", "请先选中一个 Issue")
            return
        reply = QMessageBox.question(
            self,
            "确认彻底删除",
            "彻底删除后该 Issue 及其关联记录（FA/CAPA/评论/附件）将不可恢复。\n确定继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # 彻底删除: 级联子表（FK CASCADE）+ 附件磁盘清理复用 delete 硬删路径
        try:
            self._svc.delete(issue_id)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "删除失败", str(e))
            return
        self._load()
