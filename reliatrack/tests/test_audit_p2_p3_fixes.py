"""审计 P2-1..P2-7 / P3-16 / P3-18(datahealth) 修复回归测试。

覆盖点：
- P2-1 陈旧连接自愈捕 apsw.Error；损坏库不在 PRAGMA 阶段抛错 → check_db
  判定 → DbCorruptError 恢复引导
- P2-2 附件删除白名单用 is_relative_to（attachments_old/ 兄弟目录不可绕过）
- P2-3 "先删磁盘后删 DB" → 改为 DB 优先 + 事务提交后才删磁盘文件
- P2-4 体检线程自建独立连接（不跨线程共享主线程连接）
- P2-5 导出 worker 不在后台线程跑 schema 迁移
- P2-6 综合报告 PDF 失败清理统一捕 Exception（ValueError 也清半成品）
- P2-7 导入的行级单元格规整全类型兜底（数字单元格不再吞掉整批）
- P3-16 导出取消走标志位协作式退出（不 terminate 线程）
- P3-18 体检对话框关闭时等待扫描线程退出
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import apsw
import pytest
from PySide6.QtCore import QObject, QThread, Signal

from src.db.connection import close_connection, get_connection
from src.db.repositories import (
    IssueRepository,
    ProjectRepository,
    SampleRepository,
    TestPlanRepository,
    TestTaskRepository,
)
from src.db.schema import init_schema
from src.services.health_service import DbCorruptError, check_db
from src.services.import_service import import_equipment, import_technicians
from src.services.issue_service import IssueService
from src.services.project_service import ProjectService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures / 辅助
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def qapp():
    """模块级 QApplication（与 project 内其它 UI 测试文件一致）。

    function/session 之外的作用域差异会让 QApplication 在测试间被回收，
    后续 QWidget 构造直接 qFatal（SIGABRT），故与既有文件保持同一约定。
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db_conn():
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn


@pytest.fixture()
def attach_dir(tmp_path, monkeypatch):
    """把附件白名单指向临时目录，避免动到 ~/.reliatrack/attachments。"""
    d = (tmp_path / "attachments")
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(IssueRepository, "_ALLOWED_ATTACH_DIRS", (str(d.resolve()),))
    return d


def _raise_injected(*_args, **_kwargs):
    raise RuntimeError("注入失败")


def _seed_project(conn, name: str = "项目A") -> int:
    conn.execute("INSERT INTO projects (name, status) VALUES (?, 'active')", (name,))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_issue(conn, project_id: int, task_id: int | None = None) -> int:
    conn.execute(
        "INSERT INTO issues (title, project_id, task_id, severity, status, created_at, updated_at) "
        "VALUES ('问题', ?, ?, 'major', 'open', datetime('now'), datetime('now'))",
        (project_id, task_id),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_attachment(conn, issue_id: int, attach_dir: Path, name: str = "a.txt") -> Path:
    f = attach_dir / name
    f.write_bytes(b"attachment-bytes")
    conn.execute(
        "INSERT INTO issue_attachments (issue_id, file_path, file_type) VALUES (?, ?, 'other')",
        (issue_id, str(f)),
    )
    return f


def _seed_plan_with_task(conn, project_id: int) -> tuple[int, int]:
    conn.execute(
        "INSERT INTO test_plans (name, project_id, status, start_date) "
        "VALUES ('计划A1', ?, 'active', '2026-07-19')",
        (project_id,),
    )
    plan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO test_tasks (plan_id, name, category, duration, start_day, status, priority, sort_order) "
        "VALUES (?, '任务A-0', '功能', 3, 0, 'pending', 3, 0)",
        (plan_id,),
    )
    task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return plan_id, task_id


def _project_service(conn) -> ProjectService:
    return ProjectService(
        ProjectRepository(conn),
        TestPlanRepository(conn),
        TestTaskRepository(conn),
        SampleRepository(conn),
        IssueRepository(conn),
    )


# ═══════════════════════════════════════════════════════════════════
#  P2-1  陈旧连接自愈 + 损坏库走 DbCorruptError 引导
# ═══════════════════════════════════════════════════════════════════


class TestStaleConnectionSelfHeal:
    def test_closed_connection_error_is_not_sql_error(self):
        """前提核实：ConnectionClosedError 不是 apsw.SQLError 的子类。"""
        assert not issubclass(apsw.ConnectionClosedError, apsw.SQLError)
        assert issubclass(apsw.ConnectionClosedError, apsw.Error)

    def test_recreates_externally_closed_connection(self, tmp_path):
        """连接被外部 close() 后，get_connection 必须重建而不是抛出。"""
        db_file = str(tmp_path / "stale.db")
        first = get_connection(db_file)
        first.close()  # 模拟外部关闭
        try:
            second = get_connection(db_file)
            assert second is not first
            assert second.execute("SELECT 1").fetchone() == (1,)
        finally:
            close_connection(db_file)

    def test_corrupt_file_does_not_raise_at_connect_time(self, tmp_path):
        """损坏库在 PRAGMA 阶段不抛未处理异常，交给 check_db 判定。"""
        db_file = tmp_path / "corrupt.db"
        db_file.write_bytes(b"this is not a sqlite database" * 64)

        conn = get_connection(str(db_file))  # 旧代码在此抛 NotADBError
        try:
            assert check_db(conn).ok is False
        finally:
            try:
                close_connection(str(db_file))
            except Exception:
                pass

    def test_app_controller_initialize_raises_db_corrupt_error(self, tmp_path):
        """端到端：损坏库启动 → DbCorruptError（用户可见备份恢复引导）。"""
        from src.controllers.app_controller import AppController

        db_file = tmp_path / "corrupt2.db"
        db_file.write_bytes(b"\x00garbage\x00" * 128)

        with pytest.raises(DbCorruptError):
            AppController(str(db_file)).initialize()
        try:
            close_connection(str(db_file))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
#  P2-2  附件删除白名单：is_relative_to 而非 startswith
# ═══════════════════════════════════════════════════════════════════


class TestAttachmentPathWhitelist:
    def test_sibling_directory_with_common_prefix_is_rejected(
        self, tmp_path, monkeypatch
    ):
        """attachments_old/ 与 attachments/ 同前缀，不得被误删。"""
        allowed = tmp_path / "attachments"
        allowed.mkdir()
        sibling = tmp_path / "attachments_old"
        sibling.mkdir()
        victim = sibling / "keep.txt"
        victim.write_text("别删我")
        monkeypatch.setattr(
            IssueRepository, "_ALLOWED_ATTACH_DIRS", (str(allowed.resolve()),)
        )

        IssueRepository._remove_disk_file(str(victim))

        assert victim.exists(), "兄弟目录（同前缀）文件被误删"

    def test_file_inside_allowed_directory_is_removed(self, tmp_path, monkeypatch):
        """正向对照：白名单目录内的文件仍应正常删除。"""
        allowed = tmp_path / "attachments"
        nested = allowed / "sub"
        nested.mkdir(parents=True)
        target = nested / "gone.txt"
        target.write_text("删我")
        monkeypatch.setattr(
            IssueRepository, "_ALLOWED_ATTACH_DIRS", (str(allowed.resolve()),)
        )

        IssueRepository._remove_disk_file(str(target))

        assert not target.exists()


# ═══════════════════════════════════════════════════════════════════
#  P2-3  先删 DB 行，事务提交后才删磁盘文件
# ═══════════════════════════════════════════════════════════════════


class TestAttachmentDeleteOrdering:
    def test_delete_by_project_rollback_keeps_file_and_rows(self, db_conn, attach_dir):
        """issue_repo 事务回滚 → 文件必须还在（旧代码此时已 unlink）。"""
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)
        repo = IssueRepository(db_conn)

        with pytest.raises(RuntimeError):
            with repo.transaction():
                repo.delete_by_project(pid)
                raise RuntimeError("注入失败")

        assert db_conn.execute(
            "SELECT COUNT(*) FROM issues WHERE id = ?", (iid,)
        ).fetchone()[0] == 1
        assert db_conn.execute(
            "SELECT COUNT(*) FROM issue_attachments WHERE issue_id = ?", (iid,)
        ).fetchone()[0] == 1
        assert f.exists(), "回滚后附件文件被删 → 悬空附件记录"

    def test_delete_by_project_commit_removes_file(self, db_conn, attach_dir):
        """提交后磁盘文件才真正删除（避免修成"永不删除"）。"""
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)
        repo = IssueRepository(db_conn)

        with repo.transaction():
            repo.delete_by_project(pid)

        assert not f.exists()
        assert db_conn.execute(
            "SELECT COUNT(*) FROM issue_attachments"
        ).fetchone()[0] == 0

    def test_delete_by_project_without_transaction_removes_file_now(
        self, db_conn, attach_dir
    ):
        """autocommit 路径：DB 行删除即生效，文件可以立刻清理。"""
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)

        IssueRepository(db_conn).delete_by_project(pid)

        assert not f.exists()

    def test_project_service_delete_rollback_keeps_file(self, db_conn, attach_dir, monkeypatch):
        """ProjectService.delete 事务回滚 → 附件记录与文件都必须保留。"""
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)
        svc = _project_service(db_conn)
        monkeypatch.setattr(svc._repo, "delete", _raise_injected)

        with pytest.raises(RuntimeError):
            svc.delete(pid)

        assert db_conn.execute(
            "SELECT COUNT(*) FROM projects WHERE id = ?", (pid,)
        ).fetchone()[0] == 1
        assert db_conn.execute(
            "SELECT COUNT(*) FROM issue_attachments WHERE issue_id = ?", (iid,)
        ).fetchone()[0] == 1
        assert f.exists(), "项目删除回滚后附件文件被删 → 悬空附件记录"

    def test_project_service_delete_commit_removes_file(self, db_conn, attach_dir):
        """提交成功 → 文件清理（回归保护：延后删除不能变成不删除）。"""
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)

        _project_service(db_conn).delete(pid)

        assert not f.exists()
        assert db_conn.execute(
            "SELECT COUNT(*) FROM projects WHERE id = ?", (pid,)
        ).fetchone()[0] == 0

    def test_issue_service_delete_rollback_keeps_file(self, db_conn, attach_dir, monkeypatch):
        """IssueService.delete 走 IssueRepository.transaction() 包装。"""
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)
        repo = IssueRepository(db_conn)
        svc = IssueService(repo, conn=db_conn)
        monkeypatch.setattr(repo, "delete", _raise_injected)

        with pytest.raises(RuntimeError):
            svc.delete(iid)

        assert db_conn.execute(
            "SELECT COUNT(*) FROM issue_attachments WHERE issue_id = ?", (iid,)
        ).fetchone()[0] == 1
        assert f.exists(), "Issue 删除回滚后附件文件被删"

    def test_issue_service_delete_commit_removes_file(self, db_conn, attach_dir):
        pid = _seed_project(db_conn)
        iid = _seed_issue(db_conn, pid)
        f = _seed_attachment(db_conn, iid, attach_dir)
        svc = IssueService(IssueRepository(db_conn), conn=db_conn)

        svc.delete(iid)

        assert not f.exists()
        assert db_conn.execute(
            "SELECT COUNT(*) FROM issue_attachments WHERE issue_id = ?", (iid,)
        ).fetchone()[0] == 0

    def test_delete_by_plan_nested_transaction_defers_disk_removal(
        self, db_conn, attach_dir
    ):
        """test_task_repo.delete_by_plan 嵌在调用方事务中时不得提前 unlink。"""
        pid = _seed_project(db_conn)
        plan_id, task_id = _seed_plan_with_task(db_conn, pid)
        iid = _seed_issue(db_conn, pid, task_id=task_id)
        f = _seed_attachment(db_conn, iid, attach_dir)
        issue_repo = IssueRepository(db_conn)
        task_repo = TestTaskRepository(db_conn)

        with issue_repo.transaction():  # 模拟 ProjectService 的外层事务
            task_repo.delete_by_plan(plan_id)
            assert f.exists(), "外层事务提交前附件文件已被删除"

        assert not f.exists(), "提交后应完成磁盘清理"

    def test_delete_by_plan_standalone_removes_file(self, db_conn, attach_dir):
        """独立调用（自持事务）时仍需完成磁盘清理。"""
        pid = _seed_project(db_conn)
        plan_id, task_id = _seed_plan_with_task(db_conn, pid)
        iid = _seed_issue(db_conn, pid, task_id=task_id)
        f = _seed_attachment(db_conn, iid, attach_dir)

        TestTaskRepository(db_conn).delete_by_plan(plan_id)

        assert not f.exists()


# ═══════════════════════════════════════════════════════════════════
#  P2-4  体检线程自建独立连接
# ═══════════════════════════════════════════════════════════════════


class _ThreadGuardConn:
    """主线程连接替身：被其它线程使用时立刻断言失败。"""

    def __init__(self, owner_tid: int, real: apsw.Connection) -> None:
        self._owner_tid = owner_tid
        self._real = real

    def execute(self, *args, **kwargs):
        assert threading.get_ident() == self._owner_tid, "主线程 apsw 连接被后台线程使用"
        return self._real.execute(*args, **kwargs)


class _ThreadGuardService:
    """主线程 issue_service 替身：同上。"""

    def __init__(self, owner_tid: int, real: IssueService) -> None:
        self._owner_tid = owner_tid
        self._real = real

    def scan_attachment_integrity(self) -> dict:
        assert threading.get_ident() == self._owner_tid, "主线程 service 被后台线程调用"
        return self._real.scan_attachment_integrity()


class _FakeController:
    """带 _db_path 的最小控制器（模拟 AppController 的子集）。"""

    def __init__(self, conn, issue_service, db_path: str = "") -> None:
        self._conn = conn
        self.issue_service = issue_service
        self._db_path = db_path


def _wait_report(dialog, timeout: float = 10.0) -> dict:
    """驱动事件循环直到对话框收到一次扫描报告。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not dialog._report:
        if app is not None:
            app.processEvents()
        time.sleep(0.01)
    return dialog._report


@pytest.fixture()
def file_db(tmp_path) -> Path:
    """临时库文件（后台线程必须连文件库，内存库无法跨连接）。"""
    db_file = tmp_path / "health.db"
    conn = apsw.Connection(str(db_file))
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("INSERT INTO test_results (task_id, result) VALUES (4242, 'fail')")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.close()
    return db_file


class TestHealthDialogThreadIsolation:
    def test_scan_uses_own_connection_not_main_thread_conn(self, qapp, file_db):
        """后台扫描不得触碰主线程连接 / service（旧代码直接共享）。"""
        from src.views.dialogs.data_health_dialog import DataHealthDialog

        owner_tid = threading.get_ident()
        real_conn = apsw.Connection(str(file_db))
        guard_service = _ThreadGuardService(
            owner_tid, IssueService(IssueRepository(real_conn), conn=real_conn)
        )
        controller = _FakeController(
            _ThreadGuardConn(owner_tid, real_conn), guard_service, db_path=str(file_db)
        )

        dialog = DataHealthDialog(controller)
        try:
            report = _wait_report(dialog)
        finally:
            dialog.close()
            real_conn.close()

        assert report, "扫描未在超时内完成"
        assert "error" not in report, f"扫描走了主线程连接/服务: {report}"
        assert any("4242" in r for r in report["broken_result_refs"])

    def test_scan_provider_closes_its_connection(self, file_db):
        """独立连接用完必须关闭。"""
        from src.services.health_service import open_health_scan_provider

        provider = open_health_scan_provider(str(file_db))
        assert provider._conn is not None
        provider.close()
        assert provider._conn is None
        provider.close()  # 幂等


class _StubCursor:
    def fetchall(self):
        return []

    def fetchone(self):
        return (0,)


class _StubSource:
    """无 DB 的扫描源替身（内存库无法跨连接时的退化路径用）。"""

    class _Conn:
        def execute(self, *_args, **_kwargs):
            return _StubCursor()

    class _Service:
        def scan_attachment_integrity(self):
            return {"missing_files": [], "orphan_files": []}

    def __init__(self) -> None:
        self._conn = _StubSource._Conn()
        self.issue_service = _StubSource._Service()


class TestHealthDialogWorkerLifecycle:
    def test_close_waits_for_running_scan(self, qapp, tmp_path, monkeypatch):
        """关闭对话框必须等待扫描线程退出（防止 QThread 运行中被销毁）。"""
        import src.views.dialogs.data_health_dialog as dhd

        finished = threading.Event()

        def _slow_scan(_source):
            time.sleep(0.4)
            finished.set()
            return {"missing_files": [], "orphan_files": [], "broken_result_refs": []}

        monkeypatch.setattr(dhd, "scan_data_health", _slow_scan)
        db_file = tmp_path / "slow.db"
        conn = apsw.Connection(str(db_file))
        init_schema(conn)
        conn.close()

        dialog = dhd.DataHealthDialog(_FakeController(None, None, db_path=str(db_file)))
        worker = dialog._workers[0]
        assert worker.isRunning()

        dialog.close()

        assert finished.is_set(), "关闭时未等待扫描线程"
        assert not worker.isRunning(), "关闭后线程仍在运行"
        assert dialog._workers == []

    def test_memory_db_path_falls_back_to_given_source(self, qapp):
        """内存库无法跨连接共享 → 退化用传入 source，不炸。"""
        from src.views.dialogs.data_health_dialog import DataHealthDialog

        controller = _FakeController(None, None, db_path=":memory:")
        assert DataHealthDialog._resolve_db_path(controller) == ""
        assert DataHealthDialog._resolve_db_path(
            _FakeController(None, None, db_path="")
        ) == ""

        dialog = DataHealthDialog(_StubSource())
        try:
            report = _wait_report(dialog)
        finally:
            dialog.close()
        assert report.get("error") is None
        assert report["missing_files"] == []


# ═══════════════════════════════════════════════════════════════════
#  P2-5  导出 worker 不在后台线程跑迁移
# ═══════════════════════════════════════════════════════════════════


class TestExportWorkerSchemaPolicy:
    def test_does_not_migrate_existing_older_schema(self, tmp_path):
        """旧版本库（含旧备份恢复）不得在导出线程里被迁移。"""
        from src.handlers.export_handlers import WorkerDataProvider

        db_file = tmp_path / "old.db"
        conn = apsw.Connection(str(db_file))
        init_schema(conn)
        # 模拟"旧版本库"：抹掉 20 之后的版本行（_get_current_version 取 MAX）
        conn.execute("DELETE FROM schema_version WHERE version > 20")
        before = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert before == 20
        conn.close()

        provider = WorkerDataProvider(str(db_file))
        try:
            conn = provider._conn
            assert conn is not None
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()[0]
            assert version == 20, "导出线程触发了 schema 迁移"
        finally:
            provider.close()

    def test_still_bootstraps_fully_empty_db(self, tmp_path):
        """完全未初始化的空库仍要建表（导出一致性依赖，保持既有行为）。"""
        from src.handlers.export_handlers import WorkerDataProvider

        db_file = tmp_path / "empty.db"
        apsw.Connection(str(db_file)).close()  # 建出空文件

        provider = WorkerDataProvider(str(db_file))
        try:
            conn = provider._conn
            assert conn is not None
            count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            assert count > 5
        finally:
            provider.close()


# ═══════════════════════════════════════════════════════════════════
#  P3-16 导出取消：标志位 + 协作式退出
# ═══════════════════════════════════════════════════════════════════


class TestExportCancelCooperative:
    def test_cancel_discards_partial_output(self, tmp_path):
        """请求取消后：产物被清理，发 cancelled，不把路径写回 UI。"""
        from src.handlers.export_handlers import ExportWorker

        out_file = tmp_path / "cancel.xlsx"
        finished: list = []
        errors: list = []
        cancelled: list = []

        def _fn(provider, svc, fmt, *args):
            out_file.write_text("partial")
            return str(out_file)

        worker = ExportWorker(_fn, str(tmp_path / "x.db"), None, "Excel", None, None, None)
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)
        worker.cancelled.connect(lambda: cancelled.append(True))
        worker.request_cancel()
        assert worker.is_cancel_requested()
        worker.run()  # 同步调用（不进入事件循环）

        assert cancelled == [True]
        assert finished == []
        assert errors == []
        assert not out_file.exists(), "取消后残留半成品产物"

    def test_cancel_without_request_emits_finished(self, tmp_path):
        from src.handlers.export_handlers import ExportWorker

        out_file = tmp_path / "ok.xlsx"
        finished: list = []

        def _fn(provider, svc, fmt, *args):
            out_file.write_text("data")
            return str(out_file)

        worker = ExportWorker(_fn, str(tmp_path / "x.db"), None, "Excel", None, None, None)
        worker.finished.connect(finished.append)
        worker.run()

        assert finished == [str(out_file)]
        assert out_file.exists()


class _StubExportDialog:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def exec(self) -> int:
        from PySide6.QtWidgets import QDialog

        return QDialog.DialogCode.Accepted

    def deleteLater(self) -> None:
        pass

    def get_data(self) -> dict:
        return {"content": "综合", "format": "PDF (.pdf)", "project_id": None}


class _FakeProgressDialog(QObject):
    """替代 QProgressDialog：捕获实例以便测试里手动触发 canceled。"""

    canceled = Signal()
    last: "_FakeProgressDialog | None" = None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        _FakeProgressDialog.last = self

    def setWindowTitle(self, *_args) -> None:
        pass

    def setWindowModality(self, *_args) -> None:
        pass

    def show(self) -> None:
        pass

    def close(self) -> None:
        pass


class _StubExportWorker(QThread):
    finished = Signal(str)
    error = Signal(str)
    cancelled = Signal()

    instances: list["_StubExportWorker"] = []

    def __init__(self, handler_fn, db_path, svc, fmt, project_id, plan_id,
                 issue_id, parent=None) -> None:
        super().__init__()  # parent 是测试替身控件，不是 QObject
        self.terminate_calls = 0
        self.request_cancel_calls = 0
        _StubExportWorker.instances.append(self)

    def start(self) -> None:  # 不同步执行 handler
        pass

    def terminate(self) -> None:  # pragma: no cover - 出现即说明接线回退
        self.terminate_calls += 1

    def request_cancel(self) -> None:
        self.request_cancel_calls += 1


class _FakeWindow:
    def __init__(self) -> None:
        class _Svc:
            def list_all(self):
                return []

        ctrl = type("Ctrl", (), {})()
        ctrl.test_plan_service = _Svc()
        ctrl.issue_service = _Svc()
        ctrl.sample_service = _Svc()
        ctrl.project_service = None
        ctrl._db_path = "/tmp/fake.db"
        self.ctrl = ctrl
        self.toasts: list[tuple] = []

    def toast(self, msg, level="info") -> None:
        self.toasts.append((msg, level))


class TestExportCancelWiring:
    def test_progress_cancel_requests_cancel_not_terminate(self, qapp, monkeypatch):
        """取消按钮必须走 request_cancel（terminate 会让连接停在写入中途）。"""
        import src.handlers.export_handlers as eh

        monkeypatch.setattr(eh, "ExportDialog", _StubExportDialog)
        monkeypatch.setattr(eh, "ExportWorker", _StubExportWorker)
        monkeypatch.setattr(eh, "QProgressDialog", _FakeProgressDialog)
        _StubExportWorker.instances.clear()

        handlers = eh.ExportHandlers(_FakeWindow())
        handlers._on_export()

        progress = _FakeProgressDialog.last
        assert progress is not None
        assert len(_StubExportWorker.instances) == 1
        worker = _StubExportWorker.instances[0]

        progress.canceled.emit()

        assert worker.request_cancel_calls == 1
        assert worker.terminate_calls == 0, "取消仍走 terminate"


# ═══════════════════════════════════════════════════════════════════
#  P2-6  综合报告 PDF 失败清理半成品
# ═══════════════════════════════════════════════════════════════════


class TestReportPdfFailureCleanup:
    def test_value_error_during_build_removes_partial_file(self, tmp_path, monkeypatch):
        """reportlab 布局错误是 ValueError → 半成品 PDF 必须清掉。"""
        from src.models.issue import Issue
        from src.models.sample import Sample
        from src.models.test_plan import TestPlan, TestTask
        from src.services.export import pdf_exporter as px

        out = tmp_path / "report.pdf"

        def _boom(self, story, **kwargs):
            Path(self.filename).write_bytes(b"%PDF-1.4 partial")
            raise ValueError("布局失败")

        monkeypatch.setattr(px.SimpleDocTemplate, "build", _boom)
        with pytest.raises(ValueError):
            px.export_report_pdf(
                tmp_path,
                TestPlan(id=1, project_id=1, name="计划", start_date="2026-01-01"),
                [TestTask(id=1, plan_id=1, name="任务", start_day=0, duration=1)],
                [Issue(id=1, title="问题", project_id=1, status="open")],
                [Sample(id=1, sn="SN1", project_id=1, status="in_stock")],
                filepath=str(out),
            )

        assert not out.exists(), "ValueError 后残留半成品 PDF"


# ═══════════════════════════════════════════════════════════════════
#  P2-7  导入：单元格规整全类型兜底
# ═══════════════════════════════════════════════════════════════════


class TestImportCellTypeTolerance:
    def test_numeric_name_cell_does_not_abort_batch(self, db_conn):
        """Excel 数字单元格不再触发整批回滚且无原因。"""
        from src.db.repositories import EquipmentRepository
        from src.services.equipment_service import EquipmentService

        svc = EquipmentService(EquipmentRepository(db_conn))
        rows = [
            {"name": 123.0, "type": "环境"},          # 数字名称单元格
            {"name": "正常设备", "type": "机械"},
        ]

        result = import_equipment(rows, svc)

        assert result.success == 2, f"整批被吞: {result}"
        assert result.errors == []
        assert sorted(e.name for e in svc.list_all()) == ["123.0", "正常设备"]

    def test_numeric_employee_id_cell_does_not_abort_batch(self, db_conn):
        from src.db.repositories import TechnicianRepository
        from src.services.technician_service import TechnicianService

        svc = TechnicianService(TechnicianRepository(db_conn), None, None)
        rows = [
            {"name": "张三", "employee_id": 1001},      # 数字工号
            {"name": "李四", "employee_id": "E002"},
        ]

        result = import_technicians(rows, svc)

        assert result.success == 2, f"整批被吞: {result}"
        assert result.errors == []
        ids = sorted(t.employee_id for t in svc.list_all())
        assert ids == ["1001", "E002"]

    def test_none_and_numeric_cells_in_text_columns(self, db_conn):
        """文本列给 None / 数字也必须能导入。"""
        from src.db.repositories import EquipmentRepository
        from src.services.equipment_service import EquipmentService

        svc = EquipmentService(EquipmentRepository(db_conn))
        rows = [{"name": "混合设备", "type": None, "model": 42, "location": "  实验室A  "}]

        result = import_equipment(rows, svc)

        assert result.success == 1
        eq = svc.list_all()[0]
        assert eq.type == ""
        assert eq.model == "42"
        assert eq.location == "实验室A"
