"""数据管理（备份/恢复）事件处理。"""

from __future__ import annotations

from src.views.dialogs.backup_dialog import BackupDialog


class BackupHandlers:
    """处理工具栏中数据管理按钮的事件。"""

    def __init__(self, main_window: object) -> None:
        # 使用 object 避免循环导入，运行时实际是 MainWindow
        self._main = main_window

    def _on_data_manage(self) -> None:
        """打开数据管理对话框。"""
        db_path = getattr(self._main, "_db_path", "")
        dlg = BackupDialog(parent=self._main, db_path=db_path)  # type: ignore[arg-type]
        dlg.exec()
        dlg.deleteLater()

        if dlg.restored:
            # 恢复后需要重新初始化整个应用
            self._restart_app()

    def _restart_app(self) -> None:
        """重启应用以加载恢复的数据库。先执行 shutdown 确保数据安全。"""
        # 先 shutdown — 确保 WAL checkpoint 和连接关闭
        ctrl = getattr(self._main, "_ctrl", None)
        if ctrl:
            ctrl.shutdown()

        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.closeAllWindows()
            import sys
            import os
            os.execv(sys.executable, [sys.executable] + sys.argv)
