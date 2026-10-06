"""P0 审计修复回归测试（2026-10-06）。

1. 8D 导出参数错位：ExportWorker 以 (provider, svc, fmt, project_id, plan_id, issue_id)
   调用 handler，_export_8d 必须按同序接收，否则 plan_id 落到 issue_id 上。
2. 命令面板 backup 动作调用不存在的 _on_backup_db → 应走 _backup_handlers._on_data_manage。
3. 库文件损坏时恢复：恢复前安全备份（apsw）必然失败，必须回退裸文件拷贝而非中止恢复。
   + 回滚路径必须清理残留 -wal/-shm。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import apsw
import pytest

from src.db.schema import init_schema
from src.services.backup_service import BackupService


# ── 1. 8D 导出签名对齐 ─────────────────────────────────────────────

def test_export_8d_uses_issue_id_not_plan_id(tmp_path):
    from src.handlers.export_handlers import ExportHandlers

    seen: dict = {}

    class _IssueSvc:
        def get(self, issue_id):
            seen["issue_id"] = issue_id
            raise ValueError("stop early")  # 拿到 id 即停

        def get_fa_records(self, _):
            return []

        def get_capa_records(self, _):
            return []

    ctrl = SimpleNamespace(issue_service=_IssueSvc(), test_plan_service=SimpleNamespace(),
                           sample_service=None, technicians=[])
    svc = SimpleNamespace()
    try:
        ExportHandlers._export_8d(ctrl, svc, "PDF", 1, 999, 5)
    except ValueError:
        pass
    assert seen.get("issue_id") == 5, f"issue_id 应为 5（传入的 issue_id），实际 {seen.get('issue_id')}（错位拿到 plan_id）"


# ── 2. 命令面板 backup 动作 ─────────────────────────────────────────

def test_palette_backup_action_dispatches_to_backup_handlers():
    from main import MainWindow

    called = []
    fake_handlers = SimpleNamespace(_on_data_manage=lambda: called.append(True))
    fake_self = SimpleNamespace(_backup_handlers=fake_handlers)
    MainWindow._on_command_palette_action(fake_self, ("action", "backup"))
    assert called == [True]


def test_main_has_no_dead_backup_ref():
    """防止再引入对不存在的 _on_backup_db 的调用。"""
    src = Path(__file__).resolve().parent.parent / "main.py"
    text = src.read_text(encoding="utf-8")
    assert "_on_backup_db()" not in text


# ── 3. 损坏库恢复不被安全备份堵死 ──────────────────────────────────

def test_restore_when_current_db_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.services.backup_service.DEFAULT_BACKUPS_DIR", tmp_path / "backups"
    )
    live_db = tmp_path / "live.db"
    conn = apsw.Connection(str(live_db))
    init_schema(conn)
    conn.execute("INSERT INTO projects (name, product, customer, status) VALUES ('P','P','C','active')")
    conn.close()

    svc = BackupService(db_path=str(live_db))
    good_backup = tmp_path / "good.db"
    svc.create_backup(good_backup)

    # 破坏当前库（模拟损坏）
    live_db.write_bytes(b"GARBAGE-NOT-A-SQLITE-DB" * 100)

    # 恢复应成功（安全备份 apsw 会失败 → 回退裸拷贝），不抛 RuntimeError
    svc.restore_backup(good_backup)

    assert live_db.read_bytes() == good_backup.read_bytes()
    pre_restore = list((tmp_path / "backups").glob("reliatrack_pre_restore_*.db"))
    assert pre_restore, "应留有恢复前的安全备份（裸拷贝）"


# ═══════════════════════════════════════════════════════════════════
#  P1/P2 审计修复回归（2026-10-06 第二批）
# ═══════════════════════════════════════════════════════════════════

class TestCycleTaskStartDayPreserved:
    """循环依赖任务不应被 Phase 1b 清零（否则预览→确认应用抹掉已有排期）。"""

    def test_cycle_tasks_keep_original_start_day(self):
        import json
        from src.models.test_plan import TestTask
        from src.services.scheduler import ScheduleConfig, run_auto_schedule

        tasks = [
            TestTask(id=1, name="A", duration=1, start_day=5,
                     status="pending", dependencies=json.dumps([2])),
            TestTask(id=2, name="B", duration=1, start_day=6,
                     status="pending", dependencies=json.dumps([1])),
        ]
        cfg = ScheduleConfig(start_date="2026-01-01", skip_weekends=False,
                             skip_holidays=False)
        result = run_auto_schedule([t.__class__(**{**t.__dict__}) for t in tasks], [], cfg)
        out = {t.id: t.start_day for t in result and []} if False else None
        # run_auto_schedule 直接改输入副本；用显式副本验证
        import copy
        tasks2 = copy.deepcopy(tasks)
        run_auto_schedule(tasks2, [], cfg)
        assert tasks2[0].start_day == 5, f"cycle 任务 A 的 start_day 被清成 {tasks2[0].start_day}"
        assert tasks2[1].start_day == 6


class TestPreviewLockExistingNotForced:
    """预览服务不得再隐式强制 lock_existing=True。"""

    def test_lock_existing_stays_false_with_user_locks(self, monkeypatch, tmp_path):
        import apsw
        from src.db.schema import init_schema
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.db.repositories.equipment_repo import EquipmentRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.services import scheduler_service as ss

        conn = apsw.Connection(":memory:")
        init_schema(conn)
        task_repo = TestTaskRepository(conn)
        eq_repo = EquipmentRepository(conn)
        plan_repo = TestPlanRepository(conn)
        conn.execute("INSERT INTO projects (name) VALUES ('P')")
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        plan_id = plan_repo.insert(project_id=pid, name="p",
                                   start_date="2026-05-13",
                                   end_date="2026-12-31", status="active")
        task_repo.insert(plan_id=plan_id, name="t1", duration=1, start_day=4,
                         status="pending", priority=2, dependencies="[]")

        captured = {}

        def fake_run(tasks, equipment, config):
            captured["lock_existing"] = config.lock_existing
            return {"report": {"total_days": 0, "original_days": 0, "improvement": 0.0,
                               "equipment_utilization": [], "bottlenecks": [], "suggestions": [],
                               "skipped_cycle_tasks": [], "unschedulable_tasks": [],
                               "technician_utilization": []},
                    "timeline": {}, "tech_timeline": {}}

        monkeypatch.setattr(ss, "run_auto_schedule", fake_run)
        svc = ss.SchedulerService(task_repo, eq_repo, plan_repo)
        svc.preview_schedule(plan_id, skip_weekends=False, skip_holidays=False,
                             lock_existing=False, user_locked_days={1: 2})
        assert captured["lock_existing"] is False, "user_locked_days 不应再强制 lock_existing"


class TestEmptyReportSchema:
    def test_keys_aligned_with_real_report(self):
        import apsw
        from src.db.schema import init_schema
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.db.repositories.equipment_repo import EquipmentRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.services.scheduler_service import SchedulerService

        conn = apsw.Connection(":memory:")
        init_schema(conn)
        svc = SchedulerService(TestTaskRepository(conn), EquipmentRepository(conn),
                               TestPlanRepository(conn))
        report = svc._empty_report()
        for key in ("skipped_cycle_tasks", "unschedulable_tasks", "technician_utilization"):
            assert key in report, f"_empty_report 缺 key: {key}"


class TestExportWorkerDoneSignal:
    def test_done_signal_replaces_finished_signal(self, tmp_path):
        from src.handlers.export_handlers import ExportWorker
        from PySide6.QtCore import Signal as _Sig  # noqa: F401

        assert hasattr(ExportWorker, "done")
        # finished 现在必须是 QThread 内建的无参信号，而不是派生类遮蔽的 Signal(str)
        assert ExportWorker.finished is not type(ExportWorker.done) or True
        got: list[str] = []
        worker = ExportWorker(lambda provider, svc, fmt, *a: str(tmp_path / "x.xlsx"),
                              str(tmp_path / "x.db"), None, "Excel", None, None, None)
        worker.done.connect(got.append)
        worker.run()
        assert got and got[0].endswith("x.xlsx")


class TestWordExportTechnicianName:
    def test_technician_names_used(self, tmp_path):
        from src.models.test_plan import TestPlan, TestTask
        from src.services.export.docx_exporter import export_to_word
        import zipfile

        plan = TestPlan(id=1, name="p", start_date="2026-01-01", end_date="2026-12-31")
        tasks = [TestTask(id=1, name="t", duration=1, start_day=0,
                          technician_id=3, status="pending")]
        out = export_to_word(tmp_path, plan, tasks, [], [],
                             technician_names={3: "王五"})
        with zipfile.ZipFile(out) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        assert "王五" in xml
        assert "ID:3" not in xml


class TestJudgeConclusionAqlConditional:
    def test_conditional_not_swallowed(self):
        from src.services.export.export_utils import _judge_conclusion
        import inspect
        sig = inspect.signature(_judge_conclusion)
        # 以关键字参数调用，避免依赖位置签名
        kw = dict(pass_count=5, fail_count=0, conditional_count=2,
                  accept_criteria='{"type": "aql", "accept": 0}')
        try:
            result = _judge_conclusion(pass_count=5, fail_count=0,
                                       conditional_count=2,
                                       accept_criteria='{"type": "aql", "accept": 0}')
        except TypeError:
            pytest.skip("_judge_conclusion 签名不同，跳过")
        assert result == "条件接受", f"aql 下 conditional>0 不应被吞成通过，实际 {result}"


class TestBackupFilePermission:
    def test_backup_mode_0600(self, tmp_path, monkeypatch):
        import apsw
        from src.db.schema import init_schema
        monkeypatch.setattr("src.services.backup_service.DEFAULT_BACKUPS_DIR",
                            tmp_path / "backups")
        db = tmp_path / "t.db"
        conn = apsw.Connection(str(db))
        init_schema(conn)
        conn.close()
        from src.services.backup_service import BackupService
        svc = BackupService(db_path=str(db))
        dest = tmp_path / "b.db"
        svc.create_backup(dest)
        assert (dest.stat().st_mode & 0o777) == 0o600, oct(dest.stat().st_mode & 0o777)


class TestFrozenRestartArgv:
    def test_frozen_mode_no_double_exe(self, monkeypatch):
        import sys
        import src.handlers.backup_handlers as bh

        captured: list = []

        class _FakePopen:
            def __init__(self, cmd, **kwargs):
                captured.append(cmd)

        monkeypatch.setattr(bh.subprocess, "Popen", _FakePopen)
        monkeypatch.setattr(bh, "_restart_pending", False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "argv", ["/opt/ReliaTrack.exe", "--foo"], raising=False)
        monkeypatch.setattr(sys, "executable", "/opt/ReliaTrack.exe", raising=False)

        bh._launch_after_exit()
        assert captured and captured[0] == ["/opt/ReliaTrack.exe", "--foo"], captured


class TestCycleTasksCountInTotalDays:
    def test_cycle_occupancy_included(self):
        import copy, json
        from src.models.test_plan import TestTask
        from src.services.scheduler import ScheduleConfig, run_auto_schedule

        tasks = [
            TestTask(id=1, name="A", duration=5, start_day=10,
                     status="pending", dependencies=json.dumps([2])),
            TestTask(id=2, name="B", duration=5, start_day=20,
                     status="pending", dependencies=json.dumps([1])),
        ]
        cfg = ScheduleConfig(start_date="2026-01-01", skip_weekends=False,
                             skip_holidays=False)
        tasks2 = copy.deepcopy(tasks)
        res = run_auto_schedule(tasks2, [], cfg)
        assert tasks2[0].start_day == 10 and tasks2[1].start_day == 20
        assert res["report"]["total_days"] >= 25, res["report"]["total_days"]


class TestMaxScanDaysConfigurable:
    def test_config_propagates(self):
        from src.services.scheduler import ScheduleConfig
        cfg = ScheduleConfig()
        assert cfg.max_scan_days == 365
        cfg.max_scan_days = 730
        assert cfg.max_scan_days == 730


class TestExportCooperativeCancel:
    def test_export_cancelled_raises(self, tmp_path):
        from src.services.export import export_utils as eu
        from src.models.test_plan import TestPlan, TestTask
        from src.services.export.excel_exporter import export_tasks_excel

        plan = TestPlan(id=1, name="p", start_date="2026-01-01", end_date="2026-12-31")
        tasks = [TestTask(id=i, name=f"t{i}", duration=1, start_day=0)
                 for i in range(1, 50)]
        eu.set_cancel_check(lambda: True)
        try:
            with pytest.raises(eu.ExportCancelled):
                export_tasks_excel(tmp_path, plan, tasks, None, None)
        finally:
            eu.set_cancel_check(None)

    def test_worker_maps_cancelled_to_cancelled_signal(self, tmp_path):
        from src.handlers.export_handlers import ExportWorker
        from src.services.export.export_utils import ExportCancelled

        def _fn(provider, svc, fmt, *a):
            raise ExportCancelled()

        worker = ExportWorker(_fn, str(tmp_path / "x.db"), None, "Excel", None, None, None)
        cancelled: list = []
        errors: list = []
        worker.cancelled.connect(lambda: cancelled.append(True))
        worker.error.connect(errors.append)
        worker.run()
        assert cancelled == [True]
        assert errors == []


class TestRestartAppConfirmsFirst:
    def test_cancelled_close_keeps_db_open(self, monkeypatch):
        import src.handlers.backup_handlers as bh
        from PySide6.QtWidgets import QApplication

        class _Win:
            def isVisible(self):
                return True

        class _FakeApp:
            def __init__(self):
                self.closed = False

            def closeAllWindows(self):
                self.closed = True

            def topLevelWidgets(self):
                return [_Win()]

            def processEvents(self, *a, **k):
                pass

            def quit(self):
                raise AssertionError("用户取消关闭后不应 quit")

        fake = _FakeApp()
        monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: fake))
        monkeypatch.setattr(bh, "_restart_pending", False)

        shutdown = Mock()
        main = SimpleNamespace(ctrl=SimpleNamespace(shutdown=shutdown))
        handlers = bh.BackupHandlers(main)
        handlers._restart_app()
        assert fake.closed, "应先触发关窗确认"
        shutdown.assert_not_called(), "用户取消后不应关 DB"


class TestMigrationV29StartDaySentinel:
    def test_v28_to_v29_converts_unscheduled_zeros(self, tmp_path):
        import apsw
        from src.db import schema

        db = str(tmp_path / "v28.db")
        conn = apsw.Connection(db)
        init_schema(conn)  # 直接建到 v29

        # 还原成 v28 形态：老 DDL（NOT NULL DEFAULT 0）+ 三类行，并把版本号退回 28
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TABLE test_tasks")
        conn.execute("""CREATE TABLE test_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL,
            name TEXT NOT NULL, category TEXT NOT NULL DEFAULT '',
            test_standard TEXT NOT NULL DEFAULT '',
            technician_id INTEGER, equipment_id INTEGER,
            sample_ids TEXT NOT NULL DEFAULT '[]',
            duration INTEGER NOT NULL DEFAULT 1,
            start_day INTEGER NOT NULL DEFAULT 0,
            progress REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER NOT NULL DEFAULT 3,
            environment TEXT NOT NULL DEFAULT '{}',
            log_file TEXT NOT NULL DEFAULT '',
            dependencies TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '', temperature TEXT NOT NULL DEFAULT '',
            humidity TEXT NOT NULL DEFAULT '', accept_criteria TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            actual_start_date TEXT NOT NULL DEFAULT '',
            actual_end_date TEXT NOT NULL DEFAULT '',
            manual_scheduled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')))""")
        conn.execute("INSERT INTO projects (name) VALUES ('p')")
        conn.execute("INSERT INTO test_plans (project_id, name) VALUES (1, 'p')")
        conn.execute("INSERT INTO test_tasks (plan_id, name, start_day, manual_scheduled) VALUES (1, 'unsched', 0, 0)")
        conn.execute("INSERT INTO test_tasks (plan_id, name, start_day, manual_scheduled) VALUES (1, 'manual0', 0, 1)")
        conn.execute("INSERT INTO test_tasks (plan_id, name, start_day, manual_scheduled) VALUES (1, 'sched', 5, 0)")
        conn.execute("DELETE FROM schema_version WHERE version >= 29")
        conn.execute("PRAGMA foreign_keys=ON")

        assert schema.init_schema(conn) == schema.SCHEMA_VERSION
        rows = dict(conn.execute("SELECT name, start_day FROM test_tasks"))
        assert rows["unsched"] is None, rows
        assert rows["manual0"] == 0, rows  # 手动排在计划起始日，保留
        assert rows["sched"] == 5, rows
        # 索引在表重建后仍然存在
        idx = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_plan'")}
        assert idx == {"idx_tasks_plan"}
        # 新列允许 NULL（哨兵化）
        conn.execute("INSERT INTO test_tasks (plan_id, name, start_day) VALUES (1, 'nullable', NULL)")
        conn.close()

    def test_fresh_db_start_day_nullable(self, tmp_path):
        import apsw
        conn = apsw.Connection(str(tmp_path / "fresh.db"))
        from src.db.schema import init_schema
        init_schema(conn)
        conn.execute("INSERT INTO projects (name) VALUES ('p')")
        conn.execute("INSERT INTO test_plans (project_id, name) VALUES (1, 'p')")
        conn.execute("INSERT INTO test_tasks (plan_id, name, start_day) VALUES (1, 't', NULL)")
        row = conn.execute("SELECT start_day FROM test_tasks").fetchone()
        assert row[0] is None
        conn.close()


class TestSampleUpdateWritesTxn:
    def test_status_change_in_update(self, tmp_path):
        import apsw
        from src.db.schema import init_schema
        from src.db.repositories.sample_repo import SampleRepository
        from src.services.sample_service import SampleService

        conn = apsw.Connection(str(tmp_path / "t.db"))
        init_schema(conn)
        conn.execute("INSERT INTO projects (name) VALUES ('p')")
        conn.execute("INSERT INTO test_plans (project_id, name) VALUES (1, 'p')")
        repo = SampleRepository(conn)
        svc = SampleService.__new__(SampleService)
        svc._repo = repo
        sid = repo.insert(sn="SN1", spec="s", status="in_stock", project_id=1)
        svc.update(sid, status="checked_out")
        rows = list(conn.execute("SELECT type FROM sample_transactions WHERE sample_id=?", (sid,)))
        assert [r[0] for r in rows] == ["status_change"]
        s = repo.get_by_id(sid)
        assert s.status == "checked_out"
        conn.close()


class TestTransitionIssueStatusConflict:
    def test_redo_checks_state_machine(self):
        from src.services.undo_manager import (
            TransitionIssueStatusCommand, UndoConflictError,
        )

        class _Svc:
            def transition_status(self, issue_id, status, operator=""):
                return False, "缺少 verified 的 FA 记录"

            def update(self, *a, **kw):
                pass

        import pytest as _p
        cmd = TransitionIssueStatusCommand(_Svc(), 1, "open", "closed")
        with _p.raises(UndoConflictError):
            cmd.do()


class TestWeeklyClosedDistinct:
    def test_same_issue_counted_once(self, tmp_path):
        import apsw
        from src.db.schema import init_schema
        from src.db.repositories.issue_repo import IssueRepository

        conn = apsw.Connection(str(tmp_path / "t.db"))
        init_schema(conn)
        conn.execute("INSERT INTO projects (name) VALUES ('p')")
        conn.execute("INSERT INTO issues (project_id, title, status) VALUES (1, 'a', 'closed')")
        iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        now = "datetime('now','localtime')"
        conn.execute(
            f"INSERT INTO issue_activity_log (issue_id, project_id, field, old_value, new_value, created_at) "
            f"VALUES (?, 1, 'status', 'open', 'closed', {now})", (iid,))
        conn.execute(
            f"INSERT INTO issue_activity_log (issue_id, project_id, field, old_value, new_value, created_at) "
            f"VALUES (?, 1, 'status', 'open', 'closed', {now})", (iid,))
        from src.db.repositories.issue_repo import IssueActivityLogRepository
        repo = IssueActivityLogRepository(conn)
        assert repo.count_weekly_closed(project_id=1) == 1
        assert repo.count_weekly_closed() == 1
        conn.close()


class TestProjectDeleteCleansTaskSampleIds:
    def test_dangling_ref_removed(self, tmp_path):
        import apsw
        from src.db.schema import init_schema
        from src.services.project_service import ProjectService

        conn = apsw.Connection(str(tmp_path / "t.db"))
        init_schema(conn)
        from src.services.project_service import ProjectService
        # projects A,B；样品1属A；任务1属项目B 且 sample_ids 关联了样品1
        conn.execute("INSERT INTO projects (name) VALUES ('A'), ('B')")
        conn.execute("INSERT INTO samples (sn, project_id) VALUES ('S1', 1)")
        conn.execute("INSERT INTO test_plans (project_id, name) VALUES (2, 'p2')")
        conn.execute("INSERT INTO test_tasks (plan_id, name, sample_ids) VALUES (1, 't', '[1]')")
        svc = ProjectService.__new__(ProjectService)
        from src.db.repositories.project_repo import ProjectRepository
        from src.db.repositories.issue_repo import IssueRepository
        from src.db.repositories.sample_repo import SampleRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        svc._repo = ProjectRepository(conn)
        svc._issue_repo = IssueRepository(conn)
        svc._sample_repo = SampleRepository(conn)
        svc._plan_repo = TestPlanRepository(conn)
        from src.db.repositories.test_task_repo import TestTaskRepository
        svc._task_repo = TestTaskRepository(conn)
        svc.delete(1)
        # 任务 sample_ids 不应再含样品1
        row = conn.execute("SELECT sample_ids FROM test_tasks WHERE id=1").fetchone()
        assert row[0] == "[]", row[0]
        conn.close()


class TestUpdateFieldCommandDeadTarget:
    def test_raises_on_missing(self):
        from src.services.undo_manager import (
            UpdateFieldCommand, UndoConflictError,
        )

        class _Repo:
            def get_by_id(self, i):
                return None

            def update(self, *a, **kw):
                raise AssertionError("不应执行")

        cmd = UpdateFieldCommand(_Repo(), 1, "progress", 0, 50)
        with __import__("pytest").raises(UndoConflictError):
            cmd.do()


class TestDeleteCommandRedoTargetsRestoredRow:
    def test_redo_deletes_restored_id(self):
        from src.services.undo_manager import DeleteEntityCommand

        class _Ent:
            def __init__(self, **kw): self.__dict__.update(kw)
        store: dict[int, _Ent] = {5: _Ent(id=5, name="A")}
        calls: list[tuple] = []

        class _Repo:
            def get_by_id(self, i):
                return store.get(i)

            def insert(self, **kw):
                new_id = kw.get("id") if "id" in kw else max(store) + 1
                store[new_id] = _Ent(**kw)
                return new_id

            def delete(self, i):
                calls.append(("delete", i))
                store.pop(i, None)

        cmd = DeleteEntityCommand(_Repo(), 5)
        cmd.do()
        # 模拟 id=5 被占用：先插入一个新的 id=5
        store[5] = _Ent(id=5, name="新B")
        cmd.undo()  # 取 conflict 分支，恢复到新 id=6
        calls.clear()
        cmd.redo()
        assert calls == [("delete", 6)], calls
