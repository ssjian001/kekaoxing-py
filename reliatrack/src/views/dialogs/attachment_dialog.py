"""附件管理弹窗 — 查看、添加、删除 Issue 附件。"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
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

from src.styles.theme import (
    CRUST,
    MANTLE,
    BASE,
    SURFACE0,
    SURFACE1,
    SURFACE2,
    TEXT,
    SUBTEXT0,
    SUBTEXT1,
    BLUE,
    GREEN,
    YELLOW,
    RED,
    PEACH,
    MAUVE,
    LAVENDER,
    PINK,
)

from src.views.dialogs.base_dialog import _BaseDialog

if TYPE_CHECKING:
    from src.models.issue import IssueAttachment
    from src.services.issue_service import IssueService


def _format_file_size(size_bytes: int) -> str:
    """将字节数转换为可读的文件大小字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class AttachmentDialog(_BaseDialog):
    """Issue 附件管理弹窗。

    提供：
    - 已有附件列表（显示文件名 + 大小）
    - ➕ 添加附件按钮 → QFileDialog 多选
    - 🗑 删除按钮 → 删除选中附件
    - 双击附件 → QDesktopServices.openUrl 打开文件
    """

    def __init__(
        self,
        issue_id: int,
        issue_service: IssueService,
        parent: QWidget | None = None,
    ) -> None:
        # 使用 _BaseDialog 但隐藏默认 OK/Cancel 按钮栏
        super().__init__("管理附件", parent=parent, width=560)

        self._issue_id = issue_id
        self._issue_service = issue_service
        self._attachments: list[IssueAttachment] = []

        # 隐藏默认的 OK/Cancel 按钮栏（附件管理弹窗不需要）
        self._btn_box.setVisible(False)

        # 在表单区域上方添加附件管理 UI
        self._setup_attachment_ui()

        # 加载已有附件
        self._load_attachments()

    def _setup_attachment_ui(self) -> None:
        """构建附件列表和按钮区域。"""
        # 清空默认表单布局
        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 提示标签
        hint = QLabel(f"Issue #{self._issue_id} 的附件")
        hint.setStyleSheet(f"color: {BLUE}; font-size: 14px; font-weight: bold;")
        self._form.addRow(hint)

        # 附件列表
        self._list_widget = QListWidget()
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {BASE}; color: {TEXT};
                border: 1px solid {SURFACE1}; border-radius: 6px;
                min-height: 280px; font-size: 13px;
            }}
            QListWidget::item {{
                padding: 8px 10px; border-bottom: 1px solid {SURFACE0};
            }}
            QListWidget::item:alternate {{
                background-color: {MANTLE};
            }}
            QListWidget::item:selected {{
                background-color: {SURFACE1};
            }}
        """)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._form.addRow(self._list_widget)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self._btn_add = QPushButton("➕ 添加附件")
        self._btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {GREEN}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {SURFACE1}; }}
        """)
        self._btn_add.clicked.connect(self._on_add_attachments)
        btn_layout.addWidget(self._btn_add)

        self._btn_delete = QPushButton("🗑 删除")
        self._btn_delete.setStyleSheet(f"""
            QPushButton {{
                background-color: {RED}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {SURFACE1}; }}
            QPushButton:disabled {{
                background-color: {SURFACE0}; color: {SUBTEXT0};
            }}
        """)
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete_attachment)
        btn_layout.addWidget(self._btn_delete)

        btn_layout.addStretch()

        self._btn_close = QPushButton("关闭")
        self._btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE1}; color: {TEXT}; border: none;
                border-radius: 6px; padding: 8px 20px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {SURFACE2}; }}
        """)
        self._btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_close)

        self._form.addRow(btn_layout)

        # 选择变化时更新删除按钮状态
        self._list_widget.itemSelectionChanged.connect(self._update_delete_state)

    def _load_attachments(self) -> None:
        """从数据库加载附件列表。"""
        self._attachments = self._issue_service.get_attachments(self._issue_id)
        self._list_widget.clear()
        for att in self._attachments:
            display_name = os.path.basename(att.file_path) if att.file_path else "未知文件"
            # 获取文件大小
            size_str = ""
            if att.file_path and os.path.isfile(att.file_path):
                size_bytes = os.path.getsize(att.file_path)
                size_str = f"  ({_format_file_size(size_bytes)})"
            item_text = f"📎 {display_name}{size_str}"
            if att.description:
                item_text += f"  — {att.description}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, att.id)
            self._list_widget.addItem(item)

    def _update_delete_state(self) -> None:
        """更新删除按钮的启用状态。"""
        self._btn_delete.setEnabled(self._list_widget.currentRow() >= 0)

    def _on_add_attachments(self) -> None:
        """打开文件选择对话框，添加附件。"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择附件文件",
            "",
            "所有文件 (*);;图片 (*.png *.jpg *.jpeg *.bmp *.gif);;文档 (*.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx);;视频 (*.mp4 *.avi *.mov *.mkv)",
        )
        if not files:
            return

        added = 0
        for file_path in files:
            if not os.path.isfile(file_path):
                continue
            try:
                # 根据扩展名推断 file_type
                ext = os.path.splitext(file_path)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".svg"):
                    file_type = "image"
                elif ext in (".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"):
                    file_type = "video"
                elif ext in (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"):
                    file_type = "document"
                else:
                    file_type = "other"

                self._issue_service.add_attachment(
                    self._issue_id,
                    file_path=file_path,
                    file_type=file_type,
                    description=os.path.basename(file_path),
                )
                added += 1
            except Exception as e:
                QMessageBox.warning(self, "添加失败", f"添加文件失败: {file_path}\n{e}")

        if added > 0:
            self._load_attachments()

    def _on_delete_attachment(self) -> None:
        """删除选中的附件。"""
        current_item = self._list_widget.currentItem()
        if current_item is None:
            return
        attachment_id = current_item.data(Qt.ItemDataRole.UserRole)
        if attachment_id is None:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除选中的附件吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._issue_service.delete_attachment(attachment_id)
            self._load_attachments()
        except Exception as e:
            QMessageBox.warning(self, "删除失败", f"附件删除失败: {e}")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """双击附件项 → 打开文件。"""
        attachment_id = item.data(Qt.ItemDataRole.UserRole)
        if attachment_id is None:
            return

        # 从缓存中查找附件
        att = next((a for a in self._attachments if a.id == attachment_id), None)
        if att is None or not att.file_path:
            return

        file_url = QUrl.fromLocalFile(att.file_path)
        if not file_url.isValid():
            QMessageBox.warning(self, "打开失败", f"文件路径无效: {att.file_path}")
            return

        if not os.path.isfile(att.file_path):
            QMessageBox.warning(self, "打开失败", f"文件不存在: {att.file_path}")
            return

        QDesktopServices.openUrl(file_url)
