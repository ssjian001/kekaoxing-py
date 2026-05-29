"""数据库备份管理对话框。

提供备份列表浏览、手动备份、从备份恢复、从文件恢复功能。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.views.dialogs.base_dialog import _BaseDialog
from src.services.backup_service import BackupInfo, BackupService

logger = logging.getLogger(__name__)


class BackupDialog(_BaseDialog):
    """数据库备份管理对话框。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        db_path: str = "",
    ) -> None:
        super().__init__("数据管理", parent, width=520, max_height=520)
        self._service = BackupService(db_path)
        self._selected_backup: BackupInfo | None = None
        self._restored = False  # 标记是否执行了恢复操作

        # ── 备份列表区 ──
        list_label = QLabel("备份历史")
        list_label.setProperty("class", "text-bold")
        self._root.insertWidget(self._root.count() - 1, list_label)

        self._backup_list = QListWidget()
        self._backup_list.setMinimumHeight(160)
        self._backup_list.currentRowChanged.connect(self._on_selection_changed)
        self._backup_list.itemDoubleClicked.connect(self._on_double_click)
        self._root.insertWidget(self._root.count() - 1, self._backup_list)

        # ── 备份详情 ──
        self._detail_label = QLabel("选择备份文件查看详情")
        self._detail_label.setWordWrap(True)
        self._detail_label.setProperty("class", "detail-text")
        self._root.insertWidget(self._root.count() - 1, self._detail_label)

        # ── 操作按钮区 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_backup_now = QPushButton("立即备份")
        self._btn_backup_now.setProperty("class", "primary")
        self._btn_backup_now.clicked.connect(self._on_backup_now)

        self._btn_restore = QPushButton("恢复选中")
        self._btn_restore.setProperty("class", "action")
        self._btn_restore.setEnabled(False)
        self._btn_restore.clicked.connect(self._on_restore_selected)

        self._btn_restore_file = QPushButton("从文件恢复...")
        self._btn_restore_file.setProperty("class", "action")
        self._btn_restore_file.clicked.connect(self._on_restore_from_file)

        self._btn_delete = QPushButton("删除选中")
        self._btn_delete.setProperty("class", "action")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete_selected)

        btn_layout.addWidget(self._btn_backup_now)
        btn_layout.addWidget(self._btn_restore)
        btn_layout.addWidget(self._btn_restore_file)
        btn_layout.addWidget(self._btn_delete)
        btn_layout.addStretch()

        self._root.insertLayout(self._root.count() - 1, btn_layout)

        # 加载备份列表
        self._refresh_list()

        # 隐藏默认的确定/取消按钮（不需要）
        self._btn_ok.hide()
        self._btn_cancel.setText("关闭")

    # ── 列表刷新 ──

    def _refresh_list(self) -> None:
        """刷新备份文件列表。"""
        self._backup_list.clear()
        self._selected_backup = None
        self._detail_label.setText("选择备份文件查看详情")

        backups = BackupService.list_backups()
        if not backups:
            item = QListWidgetItem("（无备份文件）")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._backup_list.addItem(item)
            return

        for info in backups:
            item = QListWidgetItem(info.display_name)
            item.setData(Qt.ItemDataRole.UserRole, info)
            self._backup_list.addItem(item)

    # ── 选择事件 ──

    def _on_selection_changed(self, row: int) -> None:
        item = self._backup_list.item(row)
        if item is None:
            self._selected_backup = None
            self._btn_restore.setEnabled(False)
            self._btn_delete.setEnabled(False)
            self._detail_label.setText("选择备份文件查看详情")
            return

        info: BackupInfo | None = item.data(Qt.ItemDataRole.UserRole)
        self._selected_backup = info
        has_selection = info is not None
        self._btn_restore.setEnabled(has_selection)
        self._btn_delete.setEnabled(has_selection)

        if info:
            self._detail_label.setText(
                f"文件: {info.path}\n"
                f"大小: {info.size_mb} MB | "
                f"修改: {info.modified.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Schema: v{info.schema_version}"
            )

    def _on_double_click(self, item: QListWidgetItem) -> None:
        """双击直接恢复。"""
        info: BackupInfo | None = item.data(Qt.ItemDataRole.UserRole)
        if info:
            self._do_restore(info)

    # ── 操作 ──

    def _on_backup_now(self) -> None:
        """立即创建备份。"""
        try:
            path = self._service.create_auto_backup()
            QMessageBox.information(
                self, "备份成功",
                f"备份已创建:\n{path}",
            )
            self._refresh_list()
        except Exception as exc:
            logger.exception("备份失败")
            QMessageBox.critical(self, "备份失败", str(exc))

    def _on_restore_selected(self) -> None:
        """恢复选中的备份。"""
        if self._selected_backup:
            self._do_restore(self._selected_backup)

    def _on_restore_from_file(self) -> None:
        """从外部文件恢复。"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择备份文件", str(Path.home()),
            "SQLite 数据库 (*.db);;所有文件 (*)",
        )
        if not filepath:
            return

        try:
            info = BackupService.validate_backup(filepath)
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "文件无效", str(exc))
            return

        self._do_restore(info)

    def _do_restore(self, info: BackupInfo) -> None:
        """执行恢复操作（含确认对话框）。"""
        reply = QMessageBox.warning(
            self, "确认恢复",
            f"即将从以下备份恢复数据库:\n\n"
            f"  文件: {info.path}\n"
            f"  Schema: v{info.schema_version}\n"
            f"  时间: {info.modified.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"当前数据库将被替换（恢复前会自动创建安全备份）。\n"
            f"恢复后需要重启应用。\n\n"
            f"是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._service.restore_backup(info.path)
            self._restored = True
            QMessageBox.information(
                self, "恢复成功",
                "数据库已成功恢复。\n应用将在关闭此对话框后重新加载。",
            )
            self.accept()
        except Exception as exc:
            logger.exception("恢复备份失败: %s", info.path)
            QMessageBox.critical(self, "恢复失败", str(exc))

    def _on_delete_selected(self) -> None:
        """删除选中的备份文件。"""
        if not self._selected_backup:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除备份文件?\n{self._selected_backup.path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        BackupService.delete_backup(self._selected_backup.path)
        self._refresh_list()

    # ── 公开接口 ──

    @property
    def restored(self) -> bool:
        """是否执行了恢复操作。"""
        return self._restored
