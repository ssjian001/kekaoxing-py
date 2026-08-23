"""数据体检对话框 — 后台扫描 + 结果展示 + 一键清理孤儿文件。"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from src.services.health_service import delete_orphan_files, scan_data_health

logger = logging.getLogger(__name__)


class _ScanWorker(QThread):
    """后台体检线程（只读扫描，不触碰 Qt widget）。"""

    finished_report = Signal(dict)

    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller

    def run(self) -> None:
        try:
            report = scan_data_health(self._controller)
        except Exception:
            logger.exception("体检扫描失败")
            report = {"missing_files": [], "orphan_files": [],
                      "broken_result_refs": [], "error": "扫描过程出错，详见日志"}
        self.finished_report.emit(report)


class DataHealthDialog(QDialog):
    """体检结果: 缺失附件 / 孤儿文件 / 断链引用。"""

    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("数据体检")
        self.setMinimumSize(560, 420)
        self._controller = controller
        self._report: dict[str, list[str]] = {}
        self._worker: _ScanWorker | None = None

        layout = QVBoxLayout(self)

        self._status = QLabel("正在扫描…")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._list = QListWidget()
        self._list.setWordWrap(True)
        layout.addWidget(self._list, stretch=1)

        self._btn_clean = QPushButton("清理选中的孤儿文件")
        self._btn_clean.setProperty("class", "primary")
        self._btn_clean.setToolTip("仅删除附件目录内、数据库无引用的文件（可多选）")
        self._btn_clean.clicked.connect(self._on_clean)
        self._btn_clean.setEnabled(False)
        layout.addWidget(self._btn_clean)

        btn_close = QPushButton("关闭")
        btn_close.setProperty("class", "action")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        # 启动后台扫描
        self._worker = _ScanWorker(controller, self)
        self._worker.finished_report.connect(self._on_report)
        self._worker.start()

    def _on_report(self, report: dict) -> None:
        self._report = report
        self._list.clear()

        if report.get("error"):
            self._status.setText(report["error"])
            return

        missing = report.get("missing_files", [])
        orphan = report.get("orphan_files", [])
        broken = report.get("broken_result_refs", [])
        total = len(missing) + len(orphan) + len(broken)

        if total == 0:
            self._status.setText("✓ 全部正常 — 附件完整、无孤儿文件、无断链引用")
            return

        self._status.setText(
            f"发现 {total} 处问题：缺失附件 {len(missing)} / 孤儿文件 {len(orphan)} / 断链结果 {len(broken)}\n"
            "（缺失附件与断链引用仅报告，需人工判断；孤儿文件可勾选后一键清理）"
        )

        for item in missing:
            it = QListWidgetItem(f"[缺失附件] {item}")
            it.setFlags(Qt.NoItemFlags)  # 不可勾选
            self._list.addItem(it)
        for item in broken:
            it = QListWidgetItem(f"[断链引用] {item}")
            it.setFlags(Qt.NoItemFlags)
            self._list.addItem(it)
        for item in orphan:
            it = QListWidgetItem(f"[孤儿文件] {item}")
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self._list.addItem(it)

        self._btn_clean.setEnabled(bool(orphan))

    def _on_clean(self) -> None:
        selected = [
            self._list.item(i).text().replace("[孤儿文件] ", "", 1)
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.Checked
        ]
        if not selected:
            return

        deleted, failures = delete_orphan_files(selected)
        msg = f"已清理 {deleted} 个文件"
        if failures:
            msg += f"，{len(failures)} 个失败：\n" + "\n".join(failures[:5])
        self._status.setText(msg)

        # 重新扫描刷新列表
        self._worker = _ScanWorker(self._controller, self)
        self._worker.finished_report.connect(self._on_report)
        self._worker.start()
