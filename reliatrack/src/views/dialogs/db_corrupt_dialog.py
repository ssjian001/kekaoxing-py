"""数据库损坏恢复引导对话框 — 启动自检失败时使用。

参考 Calibre db/restore.py 模式: 检测损坏 → 列出可用备份 → 用户选择恢复。
仅在选择"恢复"且恢复成功后才放行启动; 关闭对话框 = 放弃启动。
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.services.backup_service import BackupService
from src.services.health_service import DbCorruptError

logger = logging.getLogger(__name__)


class DbCorruptDialog(QDialog):
    """损坏详情 + 备份选择 + 恢复/退出。

    Args:
        error: AppController.initialize() 抛出的 DbCorruptError。
        db_path: 当前数据库路径（传给 BackupService 做恢复）。
    """

    def __init__(self, error: DbCorruptError, db_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("数据库完整性检查失败")
        self.setMinimumWidth(480)
        self._restored = False
        self._db_path = db_path

        layout = QVBoxLayout(self)

        detail = QLabel(
            "启动自检发现数据库存在问题，为避免进一步损坏已停止加载。\n\n"
            f"{error.check_result.summary()}\n\n"
            "可从下方备份恢复（恢复前会自动对当前库再做一次安全备份）。"
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)

        # 备份选择
        backups = BackupService.list_backups()
        self._combo = QComboBox()
        if backups:
            for info in backups:
                self._combo.addItem(info.display_name, str(info.path))
        else:
            self._combo.addItem("（无可用备份）", "")
            self._combo.setEnabled(False)
        layout.addWidget(self._combo)

        # 按钮
        btn_restore = QPushButton("从备份恢复")
        btn_restore.setProperty("class", "primary")
        btn_restore.setToolTip("验证备份 → 安全备份当前库 → 替换文件 → 重试启动")
        btn_restore.setEnabled(bool(backups))
        btn_restore.clicked.connect(self._on_restore)

        btn_quit = QPushButton("退出")
        btn_quit.setProperty("class", "action")
        btn_quit.setToolTip("不恢复，退出程序（可手动处理数据库文件）")
        btn_quit.clicked.connect(self.reject)

        layout.addWidget(btn_restore)
        layout.addWidget(btn_quit)

    def _on_restore(self) -> None:
        path = self._combo.currentData()
        if not path:
            return
        try:
            BackupService(self._db_path).restore_backup(path)
            self._restored = True
            self.accept()
        except Exception as exc:
            logger.exception("恢复失败")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "恢复失败",
                f"从备份恢复时出错：\n{exc}\n\n"
                "原数据库未被破坏（恢复过程自带回滚），可选择其他备份重试。",
            )

    @property
    def restored(self) -> bool:
        return self._restored
