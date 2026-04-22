"""可靠性测试甘特图 - PySide6 桌面应用入口"""

import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.views.main_window import MainWindow
from src.styles.theme import DARK_STYLE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("可测排程")
    app.setApplicationDisplayName("可靠性测试甘特图")
    app.setStyle("Fusion")

    # 深色主题
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()

    # 自动保存
    from src.core.auto_save import AutoSaveManager
    auto_save = AutoSaveManager(window.db.db_path, parent=window)
    auto_save.start(30000)  # 30 秒

    # 崩溃恢复检查
    bak_path = auto_save.check_crash_recovery()
    if bak_path:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            window, "恢复数据",
            "检测到上次异常关闭，是否恢复自动保存的数据？\n"
            f"备份时间: {datetime.fromtimestamp(Path(bak_path).stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            auto_save.recover_from_backup()
            window.gantt_view.refresh()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
