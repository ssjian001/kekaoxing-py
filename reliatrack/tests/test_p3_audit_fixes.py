"""P3 审计项回归测试（backup 重启 / 自动备份撞名 / 排程 / 导出净化 / UI 拖放等）。

对应审计项：
- P3-3  恢复后 startDetached 重启与单实例锁竞态
- P3-4  自动备份时间戳精度只到秒，同秒二次调用 FileExistsError
- P3-7  排程逐日重复 strptime
- P3-8  user_locked_days 锁在 start_day=0 的任务锁不住
- P3-9  docx 导出用户显式路径不净化
- P3-17 列表视图空状态标签永不显示（return 后死代码）
- P3-18 todo/quadrant 同列拖放写库、gantt 滚轮劫持、结果弹窗 fallback、
        出库弹窗手输操作人、看板卡片 drag.exec 期间被销毁
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import types
from datetime import datetime
from pathlib import Path

import apsw
import pytest

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QPoint,
    QPointF,
    Qt,
)
from PySide6.QtGui import QDrag, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from src.db.repositories.equipment_repo import EquipmentRepository
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.test_plan_repo import TestPlanRepository
from src.db.repositories.test_task_repo import TestTaskRepository
from src.db.schema import init_schema
from src.models.issue import Issue
from src.models.sample import Sample
from src.models.test_plan import TestPlan, TestTask
from src.models.todo import TodoItem
from src.services.issue_service import IssueService
from src.services.scheduler_service import SchedulerService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures / helpers
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def issue_svc(db_conn) -> IssueService:
    return IssueService(IssueRepository(db_conn))


@pytest.fixture()
def mem_conn() -> apsw.Connection:
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def repos(mem_conn):
    return (TestTaskRepository(mem_conn), EquipmentRepository(mem_conn),
            TestPlanRepository(mem_conn))


def _issue(**overrides) -> Issue:
    defaults = dict(
        id=0, title="P3 测试 Issue", description="", status="open",
        severity="major", priority=3, dri_name="Alice", root_cause="",
    )
    defaults.update(overrides)
    return Issue(**defaults)


def _seed_plan(plan_repo: TestPlanRepository, start_date: str = "2026-05-13") -> int:
    conn = plan_repo.conn
    conn.execute("INSERT INTO projects (name) VALUES ('P3 项目')")
    project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return plan_repo.insert(
        project_id=project_id, name="P3 计划",
        start_date=start_date, end_date="2026-12-31", status="active",
    )


def _seed_equipment(eq_repo: EquipmentRepository) -> int:
    return eq_repo.insert(name="台架P3", model="T1", status="available")


class _FakeDropEvent:
    """duck-typed 拖放事件：只实现 dropEvent 会用到的方法。

    QDropEvent.source() 返回值来自正在进行的 QDrag，手工构造的 QDropEvent
    永远拿不到源控件，因此同列/同象限判定只能用这种假事件覆盖。
    """

    def __init__(self, source, payload: bytes, mime_type: str) -> None:
        self._source = source
        mime = QMimeData()
        mime.setData(mime_type, payload)
        self._mime = mime
        self.ignored = False
        self.accepted = False

    def source(self):
        return self._source

    def mimeData(self):
        return self._mime

    def ignore(self) -> None:
        self.ignored = True

    def acceptProposedAction(self) -> None:
        self.accepted = True


def _mouse_event(kind, pos: QPoint, button, buttons) -> QMouseEvent:
    return QMouseEvent(
        kind, QPointF(pos), QPointF(pos), button, buttons,
        Qt.KeyboardModifier.NoModifier,
    )


# ═══════════════════════════════════════════════════════════════════
#  P3-17  列表视图空状态标签
# ═══════════════════════════════════════════════════════════════════

class TestP317EmptyStateLabel:
    def test_label_visible_when_no_issues(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView

        v = BugListView(issue_svc)
        v.set_issues([])
        assert not v._empty_label.isHidden(), "无 Issue 时空状态标签必须显示"

    def test_label_hidden_when_issues_exist(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView

        v = BugListView(issue_svc)
        v.set_issues([_issue(id=1, title="A")])
        assert v._empty_label.isHidden()

    def test_label_tracks_filter_result(self, qapp, issue_svc):
        """筛选后为空也要显示空状态标签。"""
        from src.views.bug_tracker.list_view import BugListView

        v = BugListView(issue_svc)
        v.set_issues([_issue(id=1, title="A", status="open")])
        assert v._empty_label.isHidden()
        v._filter_status.setCurrentIndex(1)   # 第一个非“全部”过滤项
        v._filter_status.setCurrentIndex(
            [i for i in range(v._filter_status.count())
             if v._filter_status.itemData(i) == "closed"][0]
        )
        v._apply_filters()
        assert not v._empty_label.isHidden()


# ═══════════════════════════════════════════════════════════════════
#  P3-18a  同列 / 同象限拖放
# ═══════════════════════════════════════════════════════════════════

class TestP318SameColumnDrop:
    def test_todo_same_column_drop_is_ignored(self, qapp):
        from src.views.widgets.todo_column import _MIME_TODO_ID, KanbanColumn

        col = KanbanColumn("pending", "待办", "kanban-col")
        col.set_cards([TodoItem(id=7, title="A")])
        card = col._cards[0]

        emitted: list[tuple] = []
        col.todo_dropped.connect(lambda tid, status: emitted.append((tid, status)))

        ev = _FakeDropEvent(card, b"7", _MIME_TODO_ID)
        col.dropEvent(ev)

        assert emitted == [], "同列拖放不应写库刷新"
        assert ev.ignored is True

    def test_todo_cross_column_drop_still_emits(self, qapp):
        from src.views.widgets.todo_column import _MIME_TODO_ID, KanbanColumn

        src_col = KanbanColumn("pending", "待办", "kanban-col")
        src_col.set_cards([TodoItem(id=7, title="A")])
        dst_col = KanbanColumn("done", "完成", "kanban-col")

        emitted: list[tuple] = []
        dst_col.todo_dropped.connect(lambda tid, status: emitted.append((tid, status)))

        ev = _FakeDropEvent(src_col._cards[0], b"7", _MIME_TODO_ID)
        dst_col.dropEvent(ev)

        assert emitted == [(7, "done")]
        assert ev.accepted is True

    def test_quadrant_same_cell_drop_is_ignored(self, qapp):
        from src.views.widgets.quadrant_cell import _MIME_TODO_ID, QuadrantCell

        cell = QuadrantCell(1, "重要紧急", "quadrant-cell")
        cell.set_cards([TodoItem(id=9, title="B")])

        emitted: list[tuple] = []
        cell.quadrant_changed.connect(lambda tid, q: emitted.append((tid, q)))

        ev = _FakeDropEvent(cell._cards[0], b"9", _MIME_TODO_ID)
        cell.dropEvent(ev)

        assert emitted == [], "同象限拖放不应写库刷新"
        assert ev.ignored is True

    def test_quadrant_cross_cell_drop_still_emits(self, qapp):
        from src.views.widgets.quadrant_cell import _MIME_TODO_ID, QuadrantCell

        src_cell = QuadrantCell(1, "重要紧急", "quadrant-cell")
        src_cell.set_cards([TodoItem(id=9, title="B")])
        dst_cell = QuadrantCell(4, "不重要不紧急", "quadrant-cell")

        emitted: list[tuple] = []
        dst_cell.quadrant_changed.connect(lambda tid, q: emitted.append((tid, q)))

        ev = _FakeDropEvent(src_cell._cards[0], b"9", _MIME_TODO_ID)
        dst_cell.dropEvent(ev)

        assert emitted == [(9, 4)]


# ═══════════════════════════════════════════════════════════════════
#  P3-18b  甘特滚轮只在 Ctrl 下缩放
# ═══════════════════════════════════════════════════════════════════

def _wheel_event(delta: int, modifiers) -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, delta),
        Qt.MouseButton.NoButton, modifiers,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


class TestP318GanttWheel:
    def test_plain_wheel_does_not_zoom(self, qapp):
        from src.views.widgets.gantt_widget import _GanttWidget

        w = _GanttWidget()
        w.set_day_width(30.0)
        ev = _wheel_event(120, Qt.KeyboardModifier.NoModifier)
        w.wheelEvent(ev)
        assert w._day_w == pytest.approx(30.0), "普通滚轮不应缩放"
        assert ev.isAccepted() is False, "普通滚轮应交还父级滚动"

    def test_ctrl_wheel_zooms(self, qapp):
        from src.views.widgets.gantt_widget import _GanttWidget

        w = _GanttWidget()
        w.set_day_width(30.0)
        w.wheelEvent(_wheel_event(120, Qt.KeyboardModifier.ControlModifier))
        assert w._day_w == pytest.approx(33.0)
        w.wheelEvent(_wheel_event(-120, Qt.KeyboardModifier.ControlModifier))
        assert w._day_w == pytest.approx(33.0 * 0.9)


# ═══════════════════════════════════════════════════════════════════
#  P3-18c  结果弹窗「应用到全部」fallback
# ═══════════════════════════════════════════════════════════════════

class TestP318EnvApplyToAll:
    def test_fallback_finds_values_from_later_row(self, qapp):
        from src.views.dialogs.test_result_dialog import TestResultDialog

        task = TestTask(id=1, plan_id=1, name="T", start_day=0, duration=1)
        samples = [Sample(id=1, sn="SN1", project_id=1, status="in_stock"),
                   Sample(id=2, sn="SN2", project_id=1, status="in_stock")]
        dlg = TestResultDialog(task, samples)

        # 第 1 行温湿度都空；第 2 行只有湿度 → fallback 必须看到第 2 行
        assert dlg._rows[0].get_env_values() == ("", "")
        dlg._rows[1].set_env_if_empty("", "40%RH")

        dlg._apply_env_to_all()

        assert dlg._rows[0].get_env_values()[1] == "40%RH"
        assert dlg._rows[1].get_env_values()[1] == "40%RH"

    def test_task_defaults_take_precedence(self, qapp):
        from src.views.dialogs.test_result_dialog import TestResultDialog

        task = TestTask(id=1, plan_id=1, name="T", start_day=0, duration=1,
                        temperature="25C", humidity="50%RH")
        samples = [Sample(id=1, sn="SN1", project_id=1, status="in_stock"),
                   Sample(id=2, sn="SN2", project_id=1, status="in_stock")]
        dlg = TestResultDialog(task, samples)
        # 行内已有值不应被 task 默认值覆盖（直接改控件，绕过 set_env_if_empty 的空判定）
        dlg._rows[1]._temp_edit.setText("99C")
        dlg._rows[1]._humidity_edit.setText("99%RH")

        dlg._apply_env_to_all()

        assert dlg._rows[0].get_env_values() == ("25C", "50%RH")
        assert dlg._rows[1].get_env_values() == ("99C", "99%RH")


# ═══════════════════════════════════════════════════════════════════
#  P3-18d  出库弹窗手输操作人
# ═══════════════════════════════════════════════════════════════════

class TestP318SampleCheckoutOperator:
    def _dlg(self, technicians):
        from src.views.dialogs.sample_checkout_dialog import SampleCheckoutDialog

        sample = Sample(id=1, sn="SN-1", project_id=1, status="in_stock")
        return SampleCheckoutDialog(sample, technicians=technicians)

    def test_typed_name_resolves_to_id(self, qapp):
        tech = types.SimpleNamespace(id=3, name="张工")
        dlg = self._dlg([tech])
        dlg._purpose_edit.setText("测试")
        dlg._operator_combo.setEditText("张工")
        assert dlg.get_data()["operator_id"] == 3

    def test_typed_name_is_case_insensitive_and_trimmed(self, qapp):
        tech = types.SimpleNamespace(id=4, name="Alice")
        dlg = self._dlg([tech])
        dlg._purpose_edit.setText("拆解")
        dlg._operator_combo.setEditText("  alice ")
        assert dlg.get_data()["operator_id"] == 4

    def test_combo_selection_still_works(self, qapp):
        tech = types.SimpleNamespace(id=5, name="Bob")
        dlg = self._dlg([tech])
        dlg._purpose_edit.setText("测试")
        dlg._operator_combo.setCurrentText("5: Bob")
        assert dlg.get_data()["operator_id"] == 5

    def test_duplicate_names_are_not_resolved(self, qapp):
        techs = [types.SimpleNamespace(id=6, name="张工"),
                 types.SimpleNamespace(id=7, name="张工")]
        dlg = self._dlg(techs)
        dlg._purpose_edit.setText("测试")
        dlg._operator_combo.setEditText("张工")
        assert dlg.get_data()["operator_id"] is None, "重名不能猜人"

    def test_unknown_name_stays_unresolved(self, qapp):
        dlg = self._dlg([types.SimpleNamespace(id=8, name="Bob")])
        dlg._purpose_edit.setText("测试")
        dlg._operator_combo.setEditText("不存在的人")
        assert dlg.get_data()["operator_id"] is None


# ═══════════════════════════════════════════════════════════════════
#  P3-18e  看板卡片 drag.exec 期间被刷新销毁
# ═══════════════════════════════════════════════════════════════════

class TestP318KanbanDragDuringRefresh:
    def test_no_crash_when_card_destroyed_during_drag(self, qapp, monkeypatch):
        from src.views.widgets.kanban_card import _KanbanCard

        card = _KanbanCard(_issue(id=7, title="A"))
        card.resize(card.CARD_WIDTH, card.CARD_HEIGHT)

        press = _mouse_event(
            QEvent.Type.MouseButtonPress, QPoint(10, 10),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        )
        move = _mouse_event(
            QEvent.Type.MouseMove, QPoint(80, 80),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        )
        card.mousePressEvent(press)

        def fake_exec(self, *args, **kwargs):
            # 模拟拖放落库后看板全量刷新：本卡片 deleteLater 并被真正销毁
            card.deleteLater()
            qapp.sendPostedEvents(None, QEvent.DeferredDelete)
            return Qt.DropAction.MoveAction

        monkeypatch.setattr(QDrag, "exec", fake_exec)

        # drag.exec 返回后不得再碰已销毁的 C++ 对象
        card.mouseMoveEvent(move)


# ═══════════════════════════════════════════════════════════════════
#  P3-3  恢复后重启与单实例锁
# ═══════════════════════════════════════════════════════════════════

class _SpyQApplication:
    """QApplication 代理：记录 closeAllWindows/quit，其余全部转发给真身。

    只替换 ``PySide6.QtWidgets.QApplication`` 的 ``instance()``，且转发
    processEvents/topLevelWidgets 等 pytest-qt 与 conftest 会调用的方法，
    否则测试收尾阶段会因拿不到真 QApplication 而报错。
    """

    def __init__(self, real=None) -> None:
        self._real = real
        self.closed = False
        self.quit_called = False

    def closeAllWindows(self):
        self.closed = True
        if self._real is not None:
            self._real.closeAllWindows()

    def quit(self):
        self.quit_called = True

    def processEvents(self, *args, **kwargs):
        if self._real is not None:
            self._real.processEvents(*args, **kwargs)

    def topLevelWidgets(self):
        return self._real.topLevelWidgets() if self._real is not None else []

    def sendPostedEvents(self, *args, **kwargs):
        if self._real is not None:
            self._real.sendPostedEvents(*args, **kwargs)


class TestP33RestartDeferredToExit:
    def test_restart_registers_exit_hook_instead_of_spawning(
        self, monkeypatch, qapp,
    ):
        import src.handlers.backup_handlers as bh

        registered: list = []
        launched: list[str] = []
        monkeypatch.setattr(bh, "atexit",
                            types.SimpleNamespace(register=registered.append))
        monkeypatch.setattr(bh, "_launch_after_exit", lambda: launched.append("x"))
        monkeypatch.setattr(bh, "_restart_pending", False)

        shutdown_calls: list[int] = []

        class _Ctrl:
            def shutdown(self):
                shutdown_calls.append(1)

        class _Win:
            ctrl = _Ctrl()
            db_path = ""

        spy = _SpyQApplication(qapp)
        monkeypatch.setattr("PySide6.QtWidgets.QApplication",
                            types.SimpleNamespace(instance=lambda: spy))

        bh.BackupHandlers(_Win())._restart_app()

        assert shutdown_calls == [1], "重启前必须先 shutdown"
        assert spy.closed and spy.quit_called
        assert launched == [], "不能在旧进程仍持单实例锁时立即拉起新进程"
        assert registered == [bh._launch_after_exit], "应注册为退出钩子"

    def test_only_one_exit_hook_is_registered(self, monkeypatch, qapp):
        import src.handlers.backup_handlers as bh

        registered: list = []
        monkeypatch.setattr(bh, "atexit",
                            types.SimpleNamespace(register=registered.append))
        monkeypatch.setattr(bh, "_restart_pending", False)
        spy = _SpyQApplication(qapp)
        monkeypatch.setattr("PySide6.QtWidgets.QApplication",
                            types.SimpleNamespace(instance=lambda: spy))

        handlers = bh.BackupHandlers(object())
        handlers._restart_app()
        handlers._restart_app()

        assert len(registered) == 1

    def test_entry_argv_rejects_foreign_entry(self, monkeypatch):
        import src.handlers.backup_handlers as bh

        monkeypatch.setattr(sys, "argv", ["/usr/bin/pytest", "tests/test_x.py"])
        assert bh.BackupHandlers._resolve_entry_argv() is None

        monkeypatch.setattr(sys, "argv", [os.path.abspath("main.py")])
        assert bh.BackupHandlers._resolve_entry_argv() == [os.path.abspath("main.py")]


_APP_SCRIPT = '''\
import os
import pathlib
import sys
import time

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication

marker_dir = pathlib.Path(sys.argv[1])


def main() -> int:
    app = QApplication([])
    lock = QLockFile(str(marker_dir / "app.lock"))
    lock.setStaleLockTime(30000)
    if not lock.tryLock(100):
        (marker_dir / f"busy-{os.getpid()}").write_text("busy")
        return 1
    (marker_dir / f"running-{os.getpid()}").write_text("running")

    # 被重启拉起来的第二个实例：拿到锁就退出
    if (marker_dir / "parent.pid").exists():
        QTimer.singleShot(50, app.quit)
        app.exec()
        return 0
    (marker_dir / "parent.pid").write_text(str(os.getpid()))

    from src.handlers.backup_handlers import BackupHandlers

    class _Ctrl:
        def shutdown(self):
            (marker_dir / "shutdown.flag").write_text("ok")

    class _Win:
        def __init__(self):
            self.ctrl = _Ctrl()
            self.db_path = ""

    # 模拟“恢复数据库后重启”：旧进程仍持有单实例锁
    BackupHandlers(_Win())._restart_app()
    # 模拟 main() 返回前其余的收尾耗时（此期间锁仍被本地变量持有）
    time.sleep(1.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


class TestP33RelaunchAcquiresLock:
    """端到端：重启出来的新实例必须能抢到单实例锁（否则会自己退出）。"""

    def test_child_instance_locks_successfully(self, tmp_path):
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        app_script = tmp_path / "main.py"
        app_script.write_text(_APP_SCRIPT, encoding="utf-8")

        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONPATH"] = os.pathsep.join(
            [str(repo_root), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        log_path = tmp_path / "app.log"
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(
                [sys.executable, str(app_script), str(marker_dir)],
                cwd=str(repo_root), env=env, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.time() + 30
                while time.time() < deadline:
                    if (len(list(marker_dir.glob("running-*"))) >= 2
                            or list(marker_dir.glob("busy-*"))):
                        break
                    time.sleep(0.1)

                running = sorted(p.name for p in marker_dir.glob("running-*"))
                busy = sorted(p.name for p in marker_dir.glob("busy-*"))
                log_text = log_path.read_text(errors="replace")
                assert busy == [], (
                    f"重启实例在旧进程仍持锁时抢锁失败: {busy}\n{log_text}"
                )
                assert len(running) >= 2, (
                    f"重启后的实例没起来: running={running}\n{log_text}"
                )
                assert (marker_dir / "shutdown.flag").exists(), "重启前未收尾"
            finally:
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)


# ═══════════════════════════════════════════════════════════════════
#  P3-4  自动备份同秒撞名
# ═══════════════════════════════════════════════════════════════════

class TestP34AutoBackupSameSecond:
    @pytest.fixture()
    def backup_svc(self, tmp_path, monkeypatch):
        import src.services.backup_service as bs

        db_path = tmp_path / "src.db"
        conn = apsw.Connection(str(db_path))
        init_schema(conn)
        conn.execute("INSERT INTO projects (name) VALUES ('P3')")
        conn.close()

        backups = tmp_path / "backups"
        monkeypatch.setattr(bs, "DEFAULT_BACKUPS_DIR", backups)
        return bs.BackupService(db_path=str(db_path)), backups

    def test_two_backups_in_same_second_both_succeed(self, backup_svc):
        svc, backups = backup_svc
        first = svc.create_auto_backup()
        second = svc.create_auto_backup()

        assert first.exists() and second.exists()
        assert first != second
        assert second.name.endswith("_1.db"), f"撞名应加序号后缀: {second.name}"
        assert len(list(backups.glob("reliatrack_*.db"))) == 2
        # 两个备份都是可用的数据库
        conn = apsw.Connection(str(second))
        assert conn.execute("SELECT name FROM projects").fetchone() == ("P3",)
        conn.close()

    def test_third_call_keeps_incrementing(self, backup_svc):
        svc, _ = backup_svc
        names = [svc.create_auto_backup().name for _ in range(3)]
        assert len(set(names)) == 3
        assert names[2].endswith("_2.db")


# ═══════════════════════════════════════════════════════════════════
#  P3-7  起始日期只解析一次
# ═══════════════════════════════════════════════════════════════════

class TestP37StartDateParseCache:
    def test_start_date_parsed_once_for_long_task(self, monkeypatch, repos):
        import src.services.scheduler as scheduler_mod

        task_repo, eq_repo, plan_repo = repos
        # 起始日 + 长工期 + 跳周末 → 老实现会对每个日历天重复 strptime
        plan_id = _seed_plan(plan_repo, start_date="2027-03-01")
        eq_id = _seed_equipment(eq_repo)
        for i in range(3):
            task_repo.insert(
                plan_id=plan_id, name=f"任务{i}", duration=12, start_day=0,
                status="pending", priority=2, dependencies="[]",
                equipment_id=eq_id,
            )

        real_datetime = datetime
        calls: list[str] = []

        class _CountingDateTime(real_datetime):
            @classmethod
            def strptime(cls, date_string, fmt):
                calls.append(date_string)
                return real_datetime.strptime(date_string, fmt)

        monkeypatch.setattr(scheduler_mod, "datetime", _CountingDateTime)
        getattr(scheduler_mod._parse_start_date, "cache_clear", lambda: None)()

        svc = SchedulerService(task_repo, eq_repo, plan_repo)
        svc.preview_schedule(plan_id, skip_weekends=True, skip_holidays=True)

        assert len(calls) == 1, f"起始日期被重复解析 {len(calls)} 次"


# ═══════════════════════════════════════════════════════════════════
#  P3-8  锁在起始日（start_day=0）的任务
# ═══════════════════════════════════════════════════════════════════

class TestP38LockedTaskAtDayZero:
    def _seed_chain(self, repos, start_date: str = "2026-05-13"):
        task_repo, eq_repo, plan_repo = repos
        plan_id = _seed_plan(plan_repo, start_date=start_date)
        b_id = task_repo.insert(
            plan_id=plan_id, name="前置任务", duration=5, start_day=0,
            status="pending", priority=2, dependencies="[]", equipment_id=None,
        )
        a_id = task_repo.insert(
            plan_id=plan_id, name="后续任务", duration=1, start_day=0,
            status="pending", priority=2, dependencies=f"[{b_id}]",
            equipment_id=None,
        )
        return plan_id, a_id

    def test_locked_day_zero_is_preserved(self, repos):
        task_repo, eq_repo, plan_repo = repos
        plan_id, a_id = self._seed_chain(repos)
        svc = SchedulerService(task_repo, eq_repo, plan_repo)

        free = svc.preview_schedule(plan_id, skip_weekends=False,
                                    skip_holidays=False)
        a_free = next(t for t in free["tasks"] if t.id == a_id)
        assert a_free.start_day >= 5, (
            f"前置条件：未锁定时任务应被依赖推到第 5 天，实际 {a_free.start_day}"
        )

        locked = svc.preview_schedule(plan_id, skip_weekends=False,
                                      skip_holidays=False,
                                      user_locked_days={a_id: 0})
        a_locked = next(t for t in locked["tasks"] if t.id == a_id)
        assert a_locked.start_day == 0, (
            f"用户锁在起始日的任务被重新排程到第 {a_locked.start_day} 天"
        )

    def test_locked_day_zero_not_reported_as_changed(self, repos):
        task_repo, eq_repo, plan_repo = repos
        plan_id, a_id = self._seed_chain(repos, start_date="2026-06-01")
        svc = SchedulerService(task_repo, eq_repo, plan_repo)

        locked = svc.preview_schedule(plan_id, skip_weekends=False,
                                      skip_holidays=False,
                                      user_locked_days={a_id: 0})
        assert locked["report"]["updated_count"] == 0


# ═══════════════════════════════════════════════════════════════════
#  P3-9  docx 导出用户显式路径净化
# ═══════════════════════════════════════════════════════════════════

class TestP39DocxExplicitPathSanitized:
    def test_word_export_sanitizes_filepath(self, tmp_path):
        from src.services.export.docx_exporter import export_to_word

        plan = TestPlan(id=1, project_id=1, name="净化测试",
                        start_date="2026-01-01")
        tasks = [TestTask(id=1, plan_id=1, name="高温", start_day=0, duration=3)]
        samples = [Sample(id=1, sn="SN001", project_id=1, status="in_stock")]

        bad = tmp_path / "报告:2026*01?.docx"
        out = export_to_word(tmp_path, plan, tasks, [], samples,
                             filepath=str(bad))
        assert Path(out).name == "报告_2026_01_.docx"
        assert Path(out).exists()

    def test_clean_filepath_is_untouched(self, tmp_path):
        from src.services.export.docx_exporter import export_to_word

        plan = TestPlan(id=1, project_id=1, name="净化测试",
                        start_date="2026-01-01")
        good = tmp_path / "正常名称.docx"
        out = export_to_word(tmp_path, plan, [], [], [], filepath=str(good))
        assert Path(out) == good
        assert good.exists()

    def test_dvpr_docx_sanitizes_filepath(self, tmp_path):
        from src.services.export.docx_exporter import export_dvpr_docx
        from src.models.test_plan import TestResult

        plan = TestPlan(id=1, project_id=1, name="净化测试",
                        start_date="2026-01-01")
        tasks = [TestTask(id=1, plan_id=1, name="高温", start_day=0, duration=3)]
        results = [TestResult(id=1, task_id=1, sample_id=1, result="pass")]
        samples = [Sample(id=1, sn="SN001", project_id=1, status="in_stock")]

        bad = tmp_path / "DVP&R<2026>.docx"
        out = export_dvpr_docx(tmp_path, plan, tasks, results, [], samples,
                               filepath=str(bad))
        assert Path(out).name == "DVP&R_2026_.docx"
        assert Path(out).exists()

    def test_8d_docx_sanitizes_filepath(self, tmp_path):
        from src.services.export.docx_exporter import export_8d_docx

        issue = _issue(id=1, title="8D 测试", status="open")
        bad = tmp_path / "8D|报告?.docx"
        out = export_8d_docx(tmp_path, issue, [], [], "张工", None, "SN001",
                             filepath=str(bad))
        assert Path(out).name == "8D_报告_.docx"
        assert Path(out).exists()
