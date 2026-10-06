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

from src.services.health_service import (
    HealthScanProvider,
    delete_orphan_files,
    open_health_scan_provider,
    scan_data_health,
)

logger = logging.getLogger(__name__)

# 关闭对话框时等待扫描线程退出的上限（扫描是只读的，正常毫秒级完成）
_WORKER_STOP_WAIT_MS = 5000


class _ScanWorker(QThread):
    """后台体检线程（只读扫描，不触碰 Qt widget）。

    线程内**自建独立 DB 连接**：主线程的 apsw 连接禁止跨线程使用
    （见 src/db/connection.py 的线程约定），共享连接在 serialized 模式下
    虽不立刻崩溃，但线程约定是硬约束。
    """

    finished_report = Signal(dict)

    def __init__(self, db_path: str, fallback_source=None, parent=None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._fallback_source = fallback_source

    def run(self) -> None:
        provider: HealthScanProvider | None = None
        try:
            if self._db_path:
                provider = open_health_scan_provider(self._db_path)
                source = provider
            else:
                # 无库文件路径（内存库 / 未初始化）时退化为调用方传入的源
                source = self._fallback_source
            report = scan_data_health(source)
        except Exception:
            logger.exception("体检扫描失败")
            report = {"missing_files": [], "orphan_files": [],
                      "broken_result_refs": [], "error": "扫描过程出错，详见日志"}
        finally:
            if provider is not None:
                provider.close()
        self.finished_report.emit(report)


class DataHealthDialog(QDialog):
    """体检结果: 缺失附件 / 孤儿文件 / 断链引用。"""

    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("数据体检")
        self.setMinimumSize(560, 420)
        self._controller = controller
        self._db_path = self._resolve_db_path(controller)
        self._report: dict[str, list[str]] = {}
        self._workers: list[_ScanWorker] = []

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
        self._start_scan()

    @staticmethod
    def _resolve_db_path(controller) -> str:
        """取库文件路径供后台线程自建连接。

        内存库（":memory:"）不能跨连接共享，等价于"无可用路径" —— 此时
        后台线程退化为使用传入的 source（调用方连接）。
        """
        db_path = getattr(controller, "_db_path", "")
        if not isinstance(db_path, str) or not db_path or db_path == ":memory:":
            return ""
        return db_path

    # ── 扫描线程生命周期 ──

    def _start_scan(self) -> None:
        """启动一次后台扫描。

        线程以本对话框为 Qt 父对象，生命周期由父子关系托管：**不调用
        deleteLater**。实测（PySide6 6.11 + offscreen）对「已结束且有父
        对象」的 QThread 调用 deleteLater —— 无论从 Python 槽还是
        finished 连接 —— 都会让随后的 processEvents 在 ~QObject 段错误；
        而单纯依赖父对象回收完全正常。一个对话框最多累积少数几个已结束
        的线程对象，不构成泄漏。
        """
        if not self._db_path:
            # 内存库 / 无库文件路径：主线程连接不能跨线程使用，改为主线程同步扫描
            # （原实现在 QThread 里复用主线程 controller 的连接，违反连接的线程约定）
            from src.services.health_service import scan_data_health
            try:
                report = scan_data_health(self._controller)
            except Exception:
                logger.exception("体检扫描失败")
                report = {"missing_files": [], "orphan_files": [],
                          "broken_result_refs": [], "error": "扫描过程出错，详见日志"}
            self._on_report(report)
            return

        worker = _ScanWorker(self._db_path,
                             None if self._db_path else self._controller,
                             self)
        worker.finished_report.connect(self._on_report)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._workers.append(worker)
        worker.start()

    def _on_worker_finished(self, worker: "_ScanWorker") -> None:
        """线程结束后仅做登记清理（QThread 由父对象回收，见 _start_scan）。"""
        if worker in self._workers:
            self._workers.remove(worker)

    def _stop_workers(self) -> None:
        """请求并等待所有扫描线程退出（关闭/接受对话框时调用）。

        不做 terminate：强杀线程可能停在只读查询中途，且会触发 Qt
        "QThread destroyed while running" 崩溃。扫描是只读的，正常立即结束。
        """
        for worker in list(self._workers):
            if worker.isRunning():
                worker.requestInterruption()
                if not worker.wait(_WORKER_STOP_WAIT_MS):
                    logger.warning("体检扫描线程未在 %dms 内退出", _WORKER_STOP_WAIT_MS)
        self._workers.clear()

    def closeEvent(self, event) -> None:
        self._stop_workers()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self._stop_workers()
        super().done(result)

    # ── 结果渲染 ──

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

        # 重新扫描刷新列表（扫描完成前禁用清理按钮，避免重复触发）
        self._btn_clean.setEnabled(False)
        self._start_scan()
