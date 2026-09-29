"""数据管理（备份/恢复）事件处理。"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import sys

from src.views.dialogs.backup_dialog import BackupDialog

logger = logging.getLogger(__name__)

# 是否已注册"退出后重启"钩子（避免重复注册导致拉起多个实例）
_restart_pending = False


class BackupHandlers:
    """处理工具栏中数据管理按钮的事件。"""

    def __init__(self, main_window: object) -> None:
        # 使用 object 避免循环导入，运行时实际是 MainWindow
        self._main = main_window

    def _on_data_manage(self) -> None:
        """打开数据管理对话框。"""
        db_path = getattr(self._main, "db_path", "")
        dlg = BackupDialog(parent=self._main, db_path=db_path)  # type: ignore[arg-type]
        dlg.exec()
        dlg.deleteLater()

        if dlg.restored:
            # 恢复后需要重新初始化整个应用
            self._restart_app()

    def _restart_app(self) -> None:
        """重启应用以加载恢复的数据库。先执行 shutdown 确保数据安全。

        单实例互斥锁是 ``main.py`` 里 ``main()`` 的局部 ``QLockFile``，只有
        ``main()`` 返回、局部变量析构时才释放。因此**不能**在这里直接
        ``QProcess.startDetached`` 拉起新进程：新进程会在旧进程仍持锁时抢锁
        失败，弹「ReliaTrack 已在运行中」后自行退出，恢复后的重启实际失效。
        正确做法是注册 atexit 钩子 —— 等本进程真正退出（锁已释放、数据库连接
        已由上面的 ``shutdown()`` 关闭）之后再启动新实例。
        """
        global _restart_pending

        # 先 shutdown — 确保 WAL checkpoint 和连接关闭
        ctrl = getattr(self._main, "ctrl", None)
        if ctrl:
            ctrl.shutdown()

        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.closeAllWindows()

        if not _restart_pending:
            _restart_pending = True
            atexit.register(_launch_after_exit)

        if app:
            app.quit()

    @staticmethod
    def _resolve_entry_argv() -> list[str] | None:
        """返回重启要用的 argv（入口脚本绝对化），非正常入口返回 None。"""
        args = list(sys.argv)
        if not args:
            return None
        if not getattr(sys, "frozen", False):
            # 开发模式只认 main.py / __main__.py 入口：被别的程序（测试、
            # 辅助脚本）import 调用时不应该在退出后把整个应用拉起来
            if os.path.basename(args[0]) not in ("main.py", "__main__.py"):
                return None
            if not os.path.isabs(args[0]) and os.path.exists(args[0]):
                args[0] = os.path.abspath(args[0])
        return args


def _launch_after_exit() -> None:
    """进程退出（单实例锁已释放）后启动新实例。"""
    args = BackupHandlers._resolve_entry_argv()
    if not args:
        logger.warning("非 main.py 入口，跳过恢复后的自动重启，请手动重启")
        return

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    try:
        subprocess.Popen(  # noqa: S603 - 用的就是本进程的解释器和 argv
            [sys.executable, *args],
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError:
        logger.exception("恢复后重启失败，请手动重新启动 ReliaTrack")
