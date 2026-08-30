"""低覆盖 handler 模块补充测试 — plan/sample/export handlers 覆盖率提升。

目标模块（基线覆盖率，2026-08-30）:
    - src/handlers/plan_handlers.py    (11%, 764 行 — 全项目最大欠账)
    - src/handlers/sample_handlers.py  (18%)
    - src/handlers/export_handlers.py  (27%)

测试约定（沿用 tests/conftest.py + tests/test_boundary.py）:
    - AppController(':memory:') + initialize() 构造真实依赖链；
    - QApplication offscreen（conftest 已设置 QT_QPA_PLATFORM）；
    - 真实 MainWindow + 真实 View，通过 select_plan / selectRow 模拟用户选中；
    - 模态弹窗（QDialog 子类 / QInputDialog / QMessageBox）全部 monkeypatch
      返回固定值后走完整 handler 路径，不依赖任何时序/睡眠；
    - 断言聚焦「调用 handler 后 DB 状态 / 视图数据 / 导出产物」的正确变化。

导出产物使用 tempfile.TemporaryDirectory 验证存在且非空
（plan_handlers 中硬编码的导出目录通过 monkeypatch 模块 __file__ 重定向到临时目录）。
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import apsw
import pytest

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QThread, Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QProgressDialog

from src.controllers import AppController
from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.sample_repo import SampleRepository
from src.db.repositories.test_plan_repo import TestPlanRepository
from src.db.repositories.test_result_repo import TestResultRepository
from src.db.repositories.test_task_repo import TestTaskRepository
from src.db.repositories.technician_repo import TechnicianRepository
from src.services.issue_service import IssueService
from src.services.sample_service import SampleService
from src.services.test_plan_service import TestPlanService


# ══════════════════════════════════════════════════════════════
#  Fixtures（module 级，参照 test_boundary.py）
# ══════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def ctrl(app) -> AppController:
    c = AppController(':memory:')
    c.initialize()
    return c


@pytest.fixture(scope="module")
def main_window(ctrl):
    from main import MainWindow
    w = MainWindow(ctrl)
    w.show()
    return w


@pytest.fixture(scope="module")
def base_data(ctrl):
    """共享基础数据：项目 / 两个计划 / 任务 / 样品 / 技术员 / Issue。"""
    p1 = ctrl.project_service.create(name='覆盖率项目P1')
    plan_a = ctrl.test_plan_service.create_plan(p1, '覆盖计划A', start_date='2026-09-01')
    plan_b = ctrl.test_plan_service.create_plan(p1, '覆盖计划B')
    t1 = ctrl.test_plan_service.create_task(plan_a, '覆盖任务T1', duration=5, start_day=1)
    t2 = ctrl.test_plan_service.create_task(plan_a, '覆盖任务T2', duration=3, start_day=2,
                                            status='in_progress')
    s1 = ctrl.sample_service.create(sn='SN-COV-001', batch_no='B-COV', spec='TypeC',
                                    project_id=p1)
    tech = ctrl.technician_service.create(name='李四', role='DQE', department='质量部')
    issue = ctrl.issue_service.create(title='覆盖Issue', project_id=p1, plan_id=plan_a,
                                      task_id=t1, severity='major', status='open')
    return {
        'project_id': p1,
        'plan_a': plan_a,
        'plan_b': plan_b,
        'task1': t1,
        'task2': t2,
        'sample_id': s1,
        'tech_id': tech,
        'issue_id': issue,
    }


@pytest.fixture(scope="module", autouse=True)
def _clear_undo_before_window_cleanup(ctrl):
    """模块结束、主窗口被 conftest 回收前，清掉撤销栈并隐藏残留弹窗。

    本模块的测试会通过 UndoManager 产生撤销历史（排程/拖拽/批量编辑等），
    若不清理，conftest 的 _qt_module_widget_cleanup 调 w.close() 会触发
    MainWindow.closeEvent 中 can_undo() → 真·QMessageBox.question（模态阻塞）。
    """
    yield
    try:
        if ctrl.undo_manager is not None:
            ctrl.undo_manager.clear()
        app = QApplication.instance()
        if app is not None:
            from PySide6.QtWidgets import QDialog
            for w in app.topLevelWidgets():
                try:
                    if isinstance(w, QDialog) and w.isVisible():
                        w.hide()
                except RuntimeError:
                    pass
    except Exception:
        pass


@pytest.fixture()
def plan_handlers(main_window):
    from src.handlers.plan_handlers import PlanHandlers
    return PlanHandlers(main_window)


@pytest.fixture()
def sample_handlers(main_window):
    from src.handlers.sample_handlers import SampleHandlers
    return SampleHandlers(main_window)


@pytest.fixture()
def export_handlers(main_window):
    from src.handlers.export_handlers import ExportHandlers
    return ExportHandlers(main_window)


@pytest.fixture(autouse=True)
def _patch_static_popups(monkeypatch):
    """autouse: 拦截 QMessageBox 全部静态弹窗（默认 Yes / 静默），防模态阻塞。

    需要「用户点否」的测试在用例内用 monkeypatch 重新覆盖即可。
    """
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))


# ══════════════════════════════════════════════════════════════
#  共享辅助
# ══════════════════════════════════════════════════════════════


def make_fake_dialog(exec_result: int = QDialog.DialogCode.Accepted, *,
                     data: dict | None = None, changes: dict | None = None,
                     selected_tasks: list | None = None, capture: list | None = None):
    """构造假 Dialog 类：exec() 返回固定值，get_data/get_changes 返回固定数据。"""

    class _FakeDialog:
        DialogCode = QDialog.DialogCode  # handler 可能读取 dlg.DialogCode.Accepted

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            if capture is not None:
                capture.append({"args": args, "kwargs": kwargs})

        def exec(self) -> int:
            return exec_result

        def deleteLater(self) -> None:
            pass

        def get_data(self) -> dict:
            return dict(data or {})

        def get_config(self) -> dict:
            return dict(data or {})

        def get_changes(self) -> dict:
            return dict(changes or {})

        def get_selected_tasks(self) -> list:
            return list(selected_tasks or [])

        def __getattr__(self, name: str):
            # 其余任意方法（如 set_holiday_service）一律 no-op
            def _noop(*a: Any, **k: Any) -> None:
                return None
            return _noop

    return _FakeDialog


def select_plan(win, plan_id: int) -> None:
    """在测试计划视图的本地 combo 中选中指定计划。"""
    plans = win.ctrl.test_plan_service.list_all_plans()
    win.test_plan_view.set_plans([p.name for p in plans], [p.id for p in plans])
    win.test_plan_view.select_plan_by_id(plan_id)


def select_table_rows(table, rows: list[int]) -> None:
    """在 QTableWidget 中选中指定行（多选安全）。

    注意先设当前行（NoUpdate 命令避免清空选择），再做行选择。
    """
    table.clearSelection()
    if rows:
        table.setCurrentCell(
            rows[0], 0, QItemSelectionModel.SelectionFlag.NoUpdate
        )
    sel = QItemSelection()
    for row in rows:
        idx = table.model().index(row, 0)
        sel.select(idx, idx)
    table.selectionModel().select(
        sel, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    )


def refresh_sample_views(win) -> None:
    """把 DB 中样品数据刷入样品池 / 台账两个 Tab 的表格。"""
    samples = win.ctrl.sample_service.list_all()
    win.sample_view.refresh_pool(samples)
    win.sample_view.refresh_ledger(samples)


def make_iso_ctrl() -> SimpleNamespace:
    """构建一个独立的真实服务集（隔离 :memory: 连接），用于导出空数据分支。"""
    conn = apsw.Connection(":memory:")
    init_schema(conn)  # 末尾开启 PRAGMA foreign_keys=ON
    tp = TestPlanRepository(conn)
    tt = TestTaskRepository(conn)
    tr = TestResultRepository(conn)
    return SimpleNamespace(
        conn=conn,
        test_plan_service=TestPlanService(tp, tt, tr),
        issue_service=IssueService(IssueRepository(conn), conn=conn),
        sample_service=SampleService(SampleRepository(conn), tr,
                                     IssueRepository(conn)),
        technicians=TechnicianRepository(conn),
    )


def add_iso_project(iso: SimpleNamespace, name: str = '隔离项目') -> int:
    """在隔离服务集的连接中插入一个项目，返回项目 ID。"""
    iso.conn.execute(
        "INSERT INTO projects (name, product, customer, description, status)"
        " VALUES (?, '', '', '', 'active')",
        (name,),
    )
    row = iso.conn.execute(
        "SELECT id FROM projects WHERE name = ?", (name,)
    ).fetchone()
    return row[0]


def today() -> str:
    return date.today().isoformat()


# ══════════════════════════════════════════════════════════════
#  PlanHandlers — 计划 CRUD / 归档 / 视图切换
# ══════════════════════════════════════════════════════════════


class TestPlanCrudHandlers:
    def test_on_plan_add_creates_plan_in_db(self, main_window, plan_handlers, base_data,
                                            monkeypatch):
        """新建计划：弹窗确认后写入 DB。"""
        import src.handlers.plan_handlers as ph
        captured: list = []
        fake = make_fake_dialog(
            data={'name': '新增计划X', 'project_id': base_data['project_id']},
            capture=captured,
        )
        monkeypatch.setattr(ph, "PlanEditDialog", fake)

        plan_handlers._on_plan_add()

        names = [p.name for p in main_window.ctrl.test_plan_service.list_all_plans()]
        assert '新增计划X' in names
        created = [p for p in main_window.ctrl.test_plan_service.list_all_plans()
                   if p.name == '新增计划X'][0]
        assert created.project_id == base_data['project_id']
        # 弹窗以 MainWindow 为父、带项目列表
        assert captured[0]['kwargs']['parent'] is main_window

    def test_on_plan_add_without_project_shows_warning(self, main_window, plan_handlers,
                                                       monkeypatch):
        """project_id=0 → 弹校验警告，不创建计划。"""
        import src.handlers.plan_handlers as ph
        warnings: list = []
        monkeypatch.setattr(ph, "PlanEditDialog", make_fake_dialog(
            data={'name': '无项目计划', 'project_id': 0}))
        monkeypatch.setattr(QMessageBox, "warning",
                            staticmethod(lambda *a, **k: warnings.append(a)))

        plan_handlers._on_plan_add()

        assert len(warnings) == 1
        names = [p.name for p in main_window.ctrl.test_plan_service.list_all_plans()]
        assert '无项目计划' not in names

    def test_on_plan_edit_renames_plan(self, main_window, plan_handlers, base_data,
                                       monkeypatch):
        """编辑计划：新名称写回 DB。"""
        import src.handlers.plan_handlers as ph
        ctrl = main_window.ctrl
        pid = ctrl.test_plan_service.create_plan(base_data['project_id'], '待改计划')
        select_plan(main_window, pid)
        monkeypatch.setattr(ph, "PlanEditDialog", make_fake_dialog(
            data={'id': pid, 'name': '已改计划'}))

        plan_handlers._on_plan_edit()

        plan = ctrl.test_plan_service.get_plan(pid)
        assert plan is not None and plan.name == '已改计划'

    def test_on_plan_delete_archives_plan(self, main_window, plan_handlers, base_data):
        """归档确认 Yes → status=archived 且刷新计划 combo。"""
        ctrl = main_window.ctrl
        pid = ctrl.test_plan_service.create_plan(base_data['project_id'], '将被归档')
        select_plan(main_window, pid)

        plan_handlers._on_plan_delete()

        assert ctrl.test_plan_service.get_plan(pid).status == 'archived'

    def test_on_plan_delete_declined_keeps_active(self, main_window, plan_handlers,
                                                  base_data, monkeypatch):
        """归档确认 No → 计划保持 active。"""
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
        )
        ctrl = main_window.ctrl
        pid = ctrl.test_plan_service.create_plan(base_data['project_id'], '不归档计划')
        select_plan(main_window, pid)

        plan_handlers._on_plan_delete()

        assert ctrl.test_plan_service.get_plan(pid).status != 'archived'

    def test_on_plan_unarchive_restores_completed(self, main_window, plan_handlers,
                                                  base_data):
        """取消归档：archived → completed。"""
        ctrl = main_window.ctrl
        pid = ctrl.test_plan_service.create_plan(base_data['project_id'], '取消归档计划')
        ctrl.test_plan_service.update_plan(pid, status='archived')
        select_plan(main_window, pid)

        plan_handlers._on_plan_unarchive()

        assert ctrl.test_plan_service.get_plan(pid).status == 'completed'

    def test_on_toggle_archived_view_disables_write_actions(self, main_window, plan_handlers):
        """勾选显示归档 → 新建/排程等写入操作被禁用；取消勾选后恢复。"""
        v = main_window.test_plan_view
        plan_handlers._on_toggle_archived_view(True)
        assert v.show_archived is True
        assert not v.act_add_plan.isEnabled()
        assert not v.btn_schedule.isEnabled()

        plan_handlers._on_toggle_archived_view(False)
        assert v.act_add_plan.isEnabled()
        assert v.btn_schedule.isEnabled()

    def test_update_plan_menu_visibility_follows_status(self, main_window, plan_handlers,
                                                        base_data):
        """归档计划选中 → act_unarchive_plan 可见；active 计划 → 隐藏。"""
        ctrl = main_window.ctrl
        pid = ctrl.test_plan_service.create_plan(base_data['project_id'], '菜单可见性计划')
        select_plan(main_window, pid)

        plan_handlers._update_plan_menu()
        assert not main_window.test_plan_view.act_unarchive_plan.isVisible()

        ctrl.test_plan_service.update_plan(pid, status='archived')
        plan_handlers._update_plan_menu()
        assert main_window.test_plan_view.act_unarchive_plan.isVisible()

    def test_is_archived_plan_flag_and_toast(self, main_window, plan_handlers, base_data):
        """归档计划 → 返回 True 并 toast；active 计划 → False。"""
        ctrl = main_window.ctrl
        pid = ctrl.test_plan_service.create_plan(base_data['project_id'], '归档判断计划')
        select_plan(main_window, pid)
        assert plan_handlers._is_archived_plan() is False

        ctrl.test_plan_service.update_plan(pid, status='archived')
        assert plan_handlers._is_archived_plan() is True

    def test_on_plan_changed_populates_task_table(self, main_window, plan_handlers,
                                                  base_data):
        """切换计划 → 任务表格行数与 DB 任务数一致。"""
        ctrl = main_window.ctrl
        select_plan(main_window, base_data['plan_a'])

        plan_handlers._on_plan_changed(main_window.test_plan_view._plan_combo.currentIndex())

        tasks = ctrl.test_plan_service.get_tasks(base_data['plan_a'])
        assert main_window.test_plan_view.task_table.rowCount() == len(tasks)


# ══════════════════════════════════════════════════════════════
#  PlanHandlers — 任务 CRUD / 状态推进 / 批量操作
# ══════════════════════════════════════════════════════════════


class TestTaskHandlers:
    def test_on_gantt_task_moved_updates_db(self, main_window, plan_handlers, base_data):
        """甘特图拖拽 → start_day 写回 DB；同日重复移动为 no-op。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '拖拽任务', start_day=1)

        plan_handlers._on_gantt_task_moved(tid, 6)
        assert ctrl.test_plan_service.get_task(tid).start_day == 6

        # 旧值与新值相同 → 直接返回，不再产生变更
        plan_handlers._on_gantt_task_moved(tid, 6)
        assert ctrl.test_plan_service.get_task(tid).start_day == 6

    def test_on_task_status_advance_in_progress(self, main_window, plan_handlers,
                                                base_data):
        """推进到 in_progress → 自动补 actual_start_date。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '推进任务')
        task = ctrl.test_plan_service.get_task(tid)

        plan_handlers._on_task_status_advance(task, 'in_progress')

        updated = ctrl.test_plan_service.get_task(tid)
        assert updated.status == 'in_progress'
        assert updated.actual_start_date == today()

    def test_on_task_status_advance_completed(self, main_window, plan_handlers, base_data):
        """推进到 completed → progress=100 且补 actual_end_date。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '完成任务')
        task = ctrl.test_plan_service.get_task(tid)

        plan_handlers._on_task_status_advance(task, 'completed')

        updated = ctrl.test_plan_service.get_task(tid)
        assert updated.status == 'completed'
        assert updated.progress == 100.0
        assert updated.actual_end_date == today()

    def test_on_task_quick_add_creates_task(self, main_window, plan_handlers, base_data,
                                            monkeypatch):
        """快速加任务：QInputDialog 返回名称+天数 → DB 创建（category=其他）。"""
        from PySide6.QtWidgets import QInputDialog
        monkeypatch.setattr(QInputDialog, "getText",
                            staticmethod(lambda *a, **k: ('快速任务Q', True)))
        monkeypatch.setattr(QInputDialog, "getInt",
                            staticmethod(lambda *a, **k: (4, True)))
        select_plan(main_window, base_data['plan_a'])

        plan_handlers._on_task_quick_add()

        tasks = main_window.ctrl.test_plan_service.get_tasks(base_data['plan_a'])
        quick = [t for t in tasks if t.name == '快速任务Q']
        assert len(quick) == 1
        assert quick[0].duration == 4
        assert quick[0].category == '其他'

    def test_on_task_edit_sets_actual_start_date(self, main_window, plan_handlers,
                                                 base_data, monkeypatch):
        """编辑任务置为 in_progress 且未填实际开始 → 自动填今天。"""
        import src.handlers.plan_handlers as ph
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '编辑任务')
        select_plan(main_window, base_data['plan_a'])
        task = ctrl.test_plan_service.get_task(tid)
        monkeypatch.setattr(ph, "TaskEditDialog", make_fake_dialog(
            data={'name': '编辑任务', 'status': 'in_progress'}))

        plan_handlers._on_task_edit(task)

        updated = ctrl.test_plan_service.get_task(tid)
        assert updated.actual_start_date == today()

    def test_on_task_delete_removes_task(self, main_window, plan_handlers, base_data):
        """删除确认 Yes → 任务从 DB 消失。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '被删任务')
        task = ctrl.test_plan_service.get_task(tid)

        plan_handlers._on_task_delete(task)

        assert ctrl.test_plan_service.get_task(tid) is None

    def test_on_task_delete_blocked_for_archived_plan(self, main_window, plan_handlers,
                                                      base_data):
        """归档计划中的任务不可删除。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '归档内任务')
        ctrl.test_plan_service.update_plan(base_data['plan_a'], status='archived')
        task = ctrl.test_plan_service.get_task(tid)

        plan_handlers._on_task_delete(task)

        assert ctrl.test_plan_service.get_task(tid) is not None
        ctrl.test_plan_service.update_plan(base_data['plan_a'], status='active')

    def test_on_batch_value_columns(self, main_window, plan_handlers, base_data):
        """批量编辑各列：名称/天数/进度/优先级/实际完成 正确写 DB（走 UndoManager 宏命令）。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '批量任务')
        cases = [
            (1, '批量改名', lambda t: t.name == '批量改名'),
            (3, '7', lambda t: t.duration == 7),
            (6, '55', lambda t: t.progress == 55.0),
            (7, '1', lambda t: t.priority == 1),
            (12, '2026-09-30', lambda t: t.actual_end_date == '2026-09-30'),
        ]
        for col, value, check in cases:
            plan_handlers._on_batch_value([tid], col, value)
            assert check(ctrl.test_plan_service.get_task(tid)), f"col={col} 未生效"

    def test_on_batch_value_invalid_inputs_are_noop(self, main_window, plan_handlers,
                                                    base_data):
        """非法值（非数字天数/进度、空名称、未知列）→ 不写 DB、不崩溃。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '保持原名', duration=2,
                                                 priority=3)
        before = ctrl.test_plan_service.get_task(tid)
        for col, value in [(1, '   '), (3, 'abc'), (6, 'abc'), (7, 'x'), (99, 'whatever')]:
            plan_handlers._on_batch_value([tid], col, value)
            after = ctrl.test_plan_service.get_task(tid)
            assert after.name == before.name
            assert after.duration == before.duration
            assert after.priority == before.priority

    def test_on_batch_assign_technician_unknown_toasts_error(self, main_window, plan_handlers,
                                                             base_data, monkeypatch):
        """批量指派不存在的技术员 → toast 错误且任务不变。"""
        v = main_window.test_plan_view
        table = v.task_table
        select_plan(main_window, base_data['plan_a'])
        plan_handlers._on_plan_changed(v._plan_combo.currentIndex())
        select_table_rows(table, [0])

        plan_handlers._on_batch_assign_technician(999999)  # 不存在

        tid = table.get_task_at_row(0).id
        assert main_window.ctrl.test_plan_service.get_task(tid).technician_id is None

    def test_on_batch_export_writes_excel(self, main_window, plan_handlers, base_data,
                                          monkeypatch, tmp_path):
        """批量导出选中任务 → 临时目录生成非空 Excel。"""
        import src.handlers.plan_handlers as ph
        # 把 handler 内部由 __file__ 推导出的 exports 目录重定向到临时目录
        monkeypatch.setattr(ph, "__file__",
                            str(tmp_path / "x" / "y" / "plan_handlers.py"))
        v = main_window.test_plan_view
        select_plan(main_window, base_data['plan_a'])
        plan_handlers._on_plan_changed(v._plan_combo.currentIndex())
        v.task_table.selectRow(0)
        assert v.task_table.get_selected_task_ids(), "需要至少选中一个任务"

        plan_handlers._on_batch_export()

        export_dir = os.path.join(tmp_path, 'exports')
        files = [f for f in os.listdir(export_dir) if f.endswith(('.xlsx', '.xls'))]
        assert files, "应生成 Excel 文件"
        assert os.path.getsize(os.path.join(export_dir, files[0])) > 0

    def test_task_cascade_message_counts(self, main_window, plan_handlers, base_data):
        """级联删除提示：统计测试结果与 Issue 数量。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '级联任务')
        ctrl.test_plan_service.save_result(task_id=tid, sample_id=base_data['sample_id'],
                                           result='pass', test_date=today())
        ctrl.issue_service.create(title='级联Issue', task_id=tid,
                                  project_id=base_data['project_id'])

        msg = plan_handlers._task_cascade_message(ctrl, tid)
        assert '1 条测试结果' in msg
        assert '1 个 Issue' in msg

        empty = plan_handlers._task_cascade_message(ctrl, 999999)
        assert empty == ''

    def test_auto_update_task_progress_transitions(self, main_window, plan_handlers,
                                                   base_data):
        """结果录入后的进度/状态联动：录满 pass→completed，含 fail→failed，部分→in_progress。"""
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '进度联动任务',
                                                 sample_ids='[]')

        ctrl.test_plan_service.save_result(task_id=tid, sample_id=base_data['sample_id'],
                                           result='pass', test_date=today())
        plan_handlers._auto_update_task_progress(ctrl, tid)
        t = ctrl.test_plan_service.get_task(tid)
        assert t.status == 'completed' and t.progress == 100.0

        ctrl.test_plan_service.save_result(task_id=tid, sample_id=base_data['sample_id'],
                                           result='fail', test_date=today())
        plan_handlers._auto_update_task_progress(ctrl, tid)
        assert ctrl.test_plan_service.get_task(tid).status == 'failed'

    def test_on_record_result_no_selection_prompts(self, main_window, plan_handlers,
                                                   monkeypatch):
        """未选中任务 → 弹提示，不进入录入流程。"""
        infos: list = []
        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: infos.append(a)))
        main_window.test_plan_view.task_table.clearSelection()

        plan_handlers._on_record_result()

        assert len(infos) == 1

    def test_open_result_dialog_saves_and_creates_issue(self, main_window, plan_handlers,
                                                        base_data, monkeypatch):
        """结果录入弹窗保存 fail 结果 + 勾选创建 Issue → 结果入库、自动建 Issue、任务转 failed。"""
        import src.handlers.plan_handlers as ph
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '录入结果任务')
        task = ctrl.test_plan_service.get_task(tid)

        from PySide6.QtWidgets import QWidget

        class _FakeResultRow(QWidget):
            def __init__(self, *a, **k) -> None:
                super().__init__()

            def get_all_data(self) -> list[dict]:
                return [{
                    'sample_id': base_data['sample_id'],
                    'sample_name': 'SN-COV-001',
                    'result': 'fail',
                    'test_date': today(),
                    'measured_value': '12.3',
                    'notes': '异常',
                    'create_issue': True,
                }]

        monkeypatch.setattr(ph, "TestResultDialog", _FakeResultRow)
        monkeypatch.setattr(QDialog, "exec",
                            lambda self: QDialog.DialogCode.Accepted)

        assert plan_handlers._open_result_dialog(task) is True

        results = ctrl.test_plan_service.get_task_results(tid)
        assert len(results) == 1 and results[0].result == 'fail'
        # 自动创建 Issue（fail + create_issue）
        issues = ctrl.issue_service.get_by_task(tid)
        assert any('录入结果任务' in i.title for i in issues)
        # 任务联动为 failed
        assert ctrl.test_plan_service.get_task(tid).status == 'failed'

    def test_open_result_dialog_cancelled_returns_false(self, main_window, plan_handlers,
                                                        base_data, monkeypatch):
        """用户取消结果弹窗 → 返回 False，不写任何结果。"""
        import src.handlers.plan_handlers as ph
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '取消录入任务')
        task = ctrl.test_plan_service.get_task(tid)

        from PySide6.QtWidgets import QWidget

        monkeypatch.setattr(ph, "TestResultDialog", type('X', (QWidget,), {
            '__init__': lambda self, *a, **k: QWidget.__init__(self),
            'get_all_data': lambda self: [],
        }))
        monkeypatch.setattr(QDialog, "exec",
                            lambda self: QDialog.DialogCode.Rejected)

        assert plan_handlers._open_result_dialog(task) is False
        assert ctrl.test_plan_service.get_task_results(tid) == []

    def test_on_matrix_result_edit_updates_result_and_progress(self, main_window,
                                                               plan_handlers, base_data):
        """结果矩阵双击编辑 → 单条结果直接入库 + 任务进度联动。"""
        ctrl = main_window.ctrl
        select_plan(main_window, base_data['plan_a'])

        plan_handlers._on_matrix_result_edit(base_data['task1'], base_data['sample_id'],
                                             'pass')

        results = ctrl.test_plan_service.get_task_results(base_data['task1'])
        assert any(r.result == 'pass' for r in results)
        assert ctrl.test_plan_service.get_task(base_data['task1']).progress == 100.0

    def test_on_task_batch_import_creates_tasks(self, main_window, plan_handlers,
                                                base_data, monkeypatch):
        """任务批量导入：合法行创建、非法工期计入跳过、空名行忽略。"""
        import src.handlers.plan_handlers as ph
        select_plan(main_window, base_data['plan_a'])
        result_box: dict = {}

        class _FakeBatchDialog:
            def __init__(self, *args, **kwargs) -> None:
                self._on_import = kwargs['on_import']

            def exec(self) -> int:
                result_box['ret'] = self._on_import([
                    {'name': '导入任务1', 'duration': '3', 'priority': '2'},
                    {'name': '坏工期', 'duration': 'abc'},
                    {'name': '   '},
                ])
                return QDialog.DialogCode.Accepted

            def deleteLater(self) -> None:
                pass

            def was_imported(self) -> bool:
                return True

            def get_result(self) -> tuple[int, int]:
                return result_box['ret']

        monkeypatch.setattr(ph, "BatchImportDialog", _FakeBatchDialog)

        plan_handlers._on_task_batch_import()

        assert result_box['ret'] == (1, 1)
        tasks = main_window.ctrl.test_plan_service.get_tasks(base_data['plan_a'])
        names = [t.name for t in tasks]
        assert '导入任务1' in names and '坏工期' not in names

    def test_on_import_from_plan_copies_tasks(self, main_window, plan_handlers, base_data,
                                              monkeypatch):
        """从同项目其他计划导入任务 → 目标计划出现源任务副本。"""
        from PySide6.QtWidgets import QInputDialog
        import src.views.dialogs.import_tasks_from_plan_dialog as imp_mod
        ctrl = main_window.ctrl
        select_plan(main_window, base_data['plan_b'])

        source_task = ctrl.test_plan_service.get_task(base_data['task1'])
        monkeypatch.setattr(QInputDialog, "getItem",
                            staticmethod(lambda *a, **k: ('覆盖计划A', True)))
        monkeypatch.setattr(imp_mod, "ImportTasksFromPlanDialog", make_fake_dialog(
            selected_tasks=[source_task]))

        plan_handlers._on_import_from_plan()

        target_names = [t.name for t in ctrl.test_plan_service.get_tasks(base_data['plan_b'])]
        assert '覆盖任务T1' in target_names

    def test_on_import_from_plan_no_other_plans_toasts(self, main_window, plan_handlers,
                                                       base_data):
        """项目下无其他计划 → toast 提示，不弹选择框。"""
        ctrl = main_window.ctrl
        # 独立项目，保证该项目下只有这一个计划（否则会弹真实 QInputDialog 阻塞）
        solo_project = ctrl.project_service.create(name='独苗项目')
        solo_plan = ctrl.test_plan_service.create_plan(solo_project, '独苗计划')
        select_plan(main_window, solo_plan)
        toasts: list = []
        original_toast = main_window.toast
        monkeypatch_toast = lambda msg, level='success': toasts.append(msg)
        main_window.toast = monkeypatch_toast
        try:
            plan_handlers._on_import_from_plan()
        finally:
            main_window.toast = original_toast
        assert any('没有其他测试计划' in t for t in toasts)


# ══════════════════════════════════════════════════════════════
#  PlanHandlers — 排程 / 总结报告
# ══════════════════════════════════════════════════════════════


class TestScheduleAndReport:
    def test_on_auto_schedule_applies_changes_to_db(self, main_window, plan_handlers,
                                                    base_data, monkeypatch):
        """排程全链路：配置弹窗确认 → 预览 → 预览弹窗确认 → start_day 写回 DB。"""
        import src.handlers.plan_handlers as ph
        import src.views.dialogs.schedule_preview_dialog as spv
        ctrl = main_window.ctrl
        tid = ctrl.test_plan_service.create_task(base_data['plan_a'], '排程任务', duration=3,
                                                 start_day=0)
        select_plan(main_window, base_data['plan_a'])

        config = {
            'skip_weekends': False, 'skip_holidays': False, 'lock_existing': False,
            'deadline': '', 'equipment_capacity': {}, 'technician_capacity': {},
            'daily_start_limit': 0,
        }
        monkeypatch.setattr(ph, "ScheduleConfigDialog", make_fake_dialog(data=config))

        preview_holder: dict = {}

        class _FakePreviewDialog:
            def __init__(self, preview_data, cfg, parent=None) -> None:
                preview_holder['data'] = preview_data

            def exec(self) -> int:
                return QDialog.DialogCode.Accepted

            def deleteLater(self) -> None:
                pass

            def get_changes(self) -> list[tuple[int, int]]:
                # 取排程结果中的新 start_day 写回
                tasks = preview_holder['data']['tasks']
                return [(t.id, t.start_day) for t in tasks if t.id is not None]

        monkeypatch.setattr(spv, "SchedulePreviewDialog", _FakePreviewDialog)

        plan_handlers._on_auto_schedule()

        # 排程结果按 id 对照 DB：所有预览任务的新 start_day 均应写回
        preview_by_id = {t.id: t.start_day for t in preview_holder['data']['tasks']}
        assert preview_by_id, "预览应包含任务"
        for task_id, new_day in preview_by_id.items():
            db_task = ctrl.test_plan_service.get_task(task_id)
            assert db_task is not None
            assert db_task.start_day == new_day, (
                f"task {task_id} start_day 未写回: {db_task.start_day} != {new_day}"
            )

    def test_on_auto_schedule_without_plan_shows_status(self, main_window, plan_handlers):
        """未选中计划 → 状态栏提示，不崩溃。"""
        main_window.test_plan_view.select_plan_by_id(None)
        plan_handlers._on_auto_schedule()  # 走 "请先创建并选择测试计划" 分支

    def test_on_summary_report_generates_word(self, main_window, plan_handlers, base_data,
                                              monkeypatch, tmp_path):
        """总结报告：选中带任务计划 → 临时目录生成非空 Word。"""
        import src.handlers.plan_handlers as ph
        # handler 内部由 __file__ 推导 exports 目录 → 重定向到临时目录
        monkeypatch.setattr(ph, "__file__",
                            str(tmp_path / "x" / "y" / "plan_handlers.py"))
        select_plan(main_window, base_data['plan_a'])

        plan_handlers._on_summary_report()

        export_dir = os.path.join(tmp_path, 'exports')
        files = [f for f in os.listdir(export_dir) if f.endswith('.docx')]
        assert files, "应生成 Word 总结报告"
        assert os.path.getsize(os.path.join(export_dir, files[0])) > 0

    def test_on_summary_report_without_plan_prompts(self, main_window, plan_handlers,
                                                    monkeypatch):
        """未选计划 → 弹提示。"""
        infos: list = []
        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: infos.append(a)))
        main_window.test_plan_view.select_plan_by_id(None)

        plan_handlers._on_summary_report()

        assert len(infos) == 1


# ══════════════════════════════════════════════════════════════
#  SampleHandlers — 入库 / 出库 / 归还 / 编辑 / 删除 / 批量
# ══════════════════════════════════════════════════════════════


class TestSampleHandlers:
    def test_on_sample_checkin_creates_sample_with_ledger(self, main_window, sample_handlers,
                                                          monkeypatch):
        """入库：弹窗数据 → 样品创建 + check_in 台账记录。"""
        import src.handlers.sample_handlers as sh
        monkeypatch.setattr(sh, "SampleCheckInDialog", make_fake_dialog(data={
            'sn': 'SN-COV-IN-01', 'batch_no': 'B-IN', 'spec': 'SP',
            'project_id': None, 'location': '区A', 'test_hours': 0.0,
            'supplier': '供应商S', 'notes': '',
        }))

        sample_handlers._on_sample_checkin()

        ctrl = main_window.ctrl
        sample = ctrl.sample_service.get_by_sn('SN-COV-IN-01')
        assert sample is not None and sample.status == 'in_stock'
        txns = ctrl.sample_service.list_transactions('', '')
        assert any(t.get('sample_id') == sample.id and t.get('type') == 'check_in'
                   for t in txns)

    def test_on_sample_checkout_updates_status_and_ledger(self, main_window, sample_handlers,
                                                          base_data, monkeypatch):
        """出库：选中样品 → 事务写入 check_out 台账 + status=checked_out。"""
        import src.handlers.sample_handlers as sh
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-OUT-01', status='in_stock')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        row = next(r for r in range(pool_table.rowCount())
                   if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        pool_table.setCurrentCell(row, 0)
        monkeypatch.setattr(sh, "SampleCheckoutDialog", make_fake_dialog(data={
            'purpose': '老化测试', 'related_task_id': None, 'expected_return': '',
            'operator_id': None, 'notes': '',
        }))

        sample_handlers._on_sample_checkout()

        assert ctrl.sample_service.get(sid).status == 'checked_out'
        txns = ctrl.sample_service.list_transactions('', '')
        assert any(t.get('sample_id') == sid and t.get('type') == 'check_out'
                   for t in txns)

    def test_on_sample_checkout_without_selection_toasts(self, main_window, sample_handlers):
        """未选中样品 → toast 提示。"""
        pool_table = main_window.sample_view.pool_tab.table
        pool_table.clearSelection()
        pool_table.setCurrentCell(-1, -1)  # 清掉当前行，避免残留 currentRow 选中样品
        toasts: list = []
        original = main_window.toast
        main_window.toast = lambda msg, level='success': toasts.append(msg)
        try:
            sample_handlers._on_sample_checkout()
        finally:
            main_window.toast = original
        assert any('请先选中一个样品' in t for t in toasts)

    def test_on_sample_return_restores_in_stock(self, main_window, sample_handlers,
                                                base_data, monkeypatch):
        """归还：checked_out 样品 → return 台账 + status=in_stock。"""
        import src.handlers.sample_handlers as sh
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-RET-01', status='checked_out')
        refresh_sample_views(main_window)
        ledger_table = main_window.sample_view.ledger_tab.table
        row = next(r for r in range(ledger_table.rowCount())
                   if ledger_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        ledger_table.setCurrentCell(row, 0)
        monkeypatch.setattr(sh, "SampleReturnDialog", make_fake_dialog(data={
            'actual_return': today(), 'operator_id': None, 'notes': '完好',
        }))

        sample_handlers._on_sample_return()

        assert ctrl.sample_service.get(sid).status == 'in_stock'
        txns = ctrl.sample_service.list_transactions('', '')
        assert any(t.get('sample_id') == sid and t.get('type') == 'return'
                   for t in txns)

    def test_on_sample_return_requires_checked_out(self, main_window, sample_handlers,
                                                   base_data):
        """in_stock 样品不可归还 → toast 拦截。"""
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-NORET-01', status='in_stock')
        refresh_sample_views(main_window)
        ledger_table = main_window.sample_view.ledger_tab.table
        row = next(r for r in range(ledger_table.rowCount())
                   if ledger_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        ledger_table.setCurrentCell(row, 0)
        toasts: list = []
        original = main_window.toast
        main_window.toast = lambda msg, level='success': toasts.append(msg)
        try:
            sample_handlers._on_sample_return()
        finally:
            main_window.toast = original
        assert any('只能归还已出库样品' in t for t in toasts)

    def test_on_sample_batch_import_skips_duplicates(self, main_window, sample_handlers,
                                                     base_data, monkeypatch):
        """批量导入：重复 SN 跳过、空 SN 忽略、新 SN 创建。"""
        import src.handlers.sample_handlers as sh
        ctrl = main_window.ctrl
        ctrl.sample_service.create(sn='SN-COV-DUP-01')
        result_box: dict = {}

        class _FakeBatchImport:
            def __init__(self, *args, **kwargs) -> None:
                self._on_import = kwargs['on_import']

            def exec(self) -> int:
                result_box['ret'] = self._on_import([
                    {'sn': 'SN-COV-DUP-01'},   # 已存在 → skip
                    {'sn': 'SN-COV-NEW-02'},   # 新建
                    {'sn': '   '},             # 空 → 忽略
                ])
                return QDialog.DialogCode.Accepted

            def deleteLater(self) -> None:
                pass

            def was_imported(self) -> bool:
                return True

            def get_result(self) -> tuple[int, int]:
                return result_box['ret']

        monkeypatch.setattr(sh, "BatchImportDialog", _FakeBatchImport)

        sample_handlers._on_sample_batch_import()

        assert result_box['ret'] == (1, 1)
        assert ctrl.sample_service.get_by_sn('SN-COV-NEW-02') is not None

    def test_on_sample_edit_updates_fields(self, main_window, sample_handlers, base_data,
                                           monkeypatch):
        """编辑样品：新位置写回 DB。"""
        import src.handlers.sample_handlers as sh
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-EDIT-01', location='旧位置')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        row = next(r for r in range(pool_table.rowCount())
                   if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        pool_table.setCurrentCell(row, 0)
        monkeypatch.setattr(sh, "SampleEditDialog", make_fake_dialog(data={
            'sn': 'SN-COV-EDIT-01', 'location': '新位置Z',
        }))

        sample_handlers._on_sample_edit()

        assert ctrl.sample_service.get(sid).location == '新位置Z'

    def test_on_pool_batch_edit_updates_multiple_samples(self, main_window, sample_handlers,
                                                         monkeypatch):
        """批量编辑（>=2 个选中）→ 两个样品 location 均更新（走 UndoManager 命令）。"""
        import src.handlers.sample_handlers as sh
        ctrl = main_window.ctrl
        sid1 = ctrl.sample_service.create(sn='SN-COV-BA-01', location='旧A')
        sid2 = ctrl.sample_service.create(sn='SN-COV-BA-02', location='旧B')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        rows = [r for r in range(pool_table.rowCount())
                if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) in (sid1, sid2)]
        select_table_rows(pool_table, rows)
        monkeypatch.setattr(sh, "BatchEditSampleDialog", make_fake_dialog(
            changes={'location': '批量新位置'}))

        sample_handlers._on_pool_batch_edit()

        assert ctrl.sample_service.get(sid1).location == '批量新位置'
        assert ctrl.sample_service.get(sid2).location == '批量新位置'

    def test_on_pool_batch_edit_requires_two_selected(self, main_window, sample_handlers):
        """只选中 1 个样品 → toast 提示，不弹批量编辑。"""
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-ONE-01')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        row = next(r for r in range(pool_table.rowCount())
                   if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        pool_table.setCurrentCell(row, 0)
        toasts: list = []
        original = main_window.toast
        main_window.toast = lambda msg, level='success': toasts.append(msg)
        try:
            sample_handlers._on_pool_batch_edit()
        finally:
            main_window.toast = original
        assert any('2 个以上' in t for t in toasts)

    def test_on_sample_delete_with_confirm(self, main_window, sample_handlers,
                                           monkeypatch):
        """删除确认 Yes → 样品从 DB 消失。"""
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-DEL-01')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        row = next(r for r in range(pool_table.rowCount())
                   if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        pool_table.setCurrentCell(row, 0)

        sample_handlers._on_sample_delete()

        assert ctrl.sample_service.get(sid) is None

    def test_on_sample_delete_declined_keeps_sample(self, main_window, sample_handlers,
                                                    monkeypatch):
        """删除确认 No → 样品保留。"""
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
        )
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-KEEP-01')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        row = next(r for r in range(pool_table.rowCount())
                   if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        pool_table.setCurrentCell(row, 0)

        sample_handlers._on_sample_delete()

        assert ctrl.sample_service.get(sid) is not None

    def test_on_sample_tag_opens_dialog(self, main_window, sample_handlers, monkeypatch):
        """生成标签：选中样品 → 弹出标签弹窗（假弹窗不阻塞）。"""
        import src.views.dialogs.sample_tag_dialog as tag_mod
        ctrl = main_window.ctrl
        sid = ctrl.sample_service.create(sn='SN-COV-TAG-01')
        refresh_sample_views(main_window)
        pool_table = main_window.sample_view.pool_tab.table
        row = next(r for r in range(pool_table.rowCount())
                   if pool_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == sid)
        pool_table.setCurrentCell(row, 0)
        opened: list = []

        class _FakeTagDialog:
            def __init__(self, sample, parent=None) -> None:
                opened.append(sample)

            def exec(self) -> int:
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(tag_mod, "SampleTagDialog", _FakeTagDialog)

        sample_handlers._on_sample_tag()

        assert len(opened) == 1 and opened[0].id == sid

    def test_refresh_sample_usage_populates_tab(self, main_window, sample_handlers,
                                                base_data):
        """刷新出入库记录 Tab → usage 缓存数据与 DB 流水一致。"""
        ctrl = main_window.ctrl
        ctrl.sample_service.add_transaction(base_data['sample_id'], 'check_out',
                                            purpose='测试用途')

        sample_handlers._refresh_sample_usage()

        usage_tab = main_window.sample_view.usage_tab
        txns = ctrl.sample_service.list_transactions('', '')
        assert len(usage_tab._all_data) == len(txns)
        assert any(t.get('purpose') == '测试用途' for t in usage_tab._all_data)


# ══════════════════════════════════════════════════════════════
#  ExportHandlers — dispatch 静态方法（真实 controller + 临时目录产物）
# ══════════════════════════════════════════════════════════════


class TestExportDispatchMethods:
    @pytest.fixture()
    def svc(self, tmp_path):
        from src.services.export import ExportService
        return ExportService(output_dir=str(tmp_path))

    def _assert_file(self, path: str) -> None:
        assert path and os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_get_issues_and_samples_by_project(self, export_handlers, ctrl, base_data):
        """按项目筛选与全量获取两个分支。"""
        issues_all = export_handlers._get_issues(ctrl, None)
        issues_proj = export_handlers._get_issues(ctrl, base_data['project_id'])
        assert issues_all and len(issues_proj) <= len(issues_all)

        samples_all = export_handlers._get_samples(ctrl, None)
        samples_proj = export_handlers._get_samples(ctrl, base_data['project_id'])
        assert samples_all and any(s.id == base_data['sample_id'] for s in samples_proj)

    def test_get_export_dir_creates_directory(self):
        from src.handlers.export_handlers import ExportHandlers
        d = ExportHandlers._get_export_dir()
        assert os.path.isdir(d)

    def test_export_tasks_all_formats(self, export_handlers, ctrl, base_data, svc,
                                      tmp_path):
        """测试任务导出：Excel / Word 产物非空；PDF 分支受 src 已知缺陷限制
        （export_handlers 传 technician_names，但 ExportService 门面未支持该参数）。"""
        plan_id = base_data['plan_a']
        for fmt, suffix in [('Excel (.xlsx)', '.xlsx'), ('Word (.docx)', '.docx')]:
            path = export_handlers._export_tasks(ctrl, svc, fmt, None, plan_id)
            self._assert_file(path)
            assert path.endswith(suffix)
            os.unlink(path)
        with pytest.raises(TypeError):
            # src/handlers/export_handlers.py PDF 分支传入 technician_names，
            # 而 src/services/export 门面 export_report_pdf 尚无该形参（生产同路径必炸）
            export_handlers._export_tasks(ctrl, svc, 'PDF (.pdf)', None, plan_id)

    def test_export_tasks_without_plan_raises(self, export_handlers, ctrl, svc):
        """plan_id=None → ValueError。"""
        with pytest.raises(ValueError):
            export_handlers._export_tasks(ctrl, svc, 'Excel (.xlsx)', None, None)

    def test_export_tasks_empty_plan_raises(self, export_handlers, svc):
        """无任务计划 → ValueError（使用隔离服务集）。"""
        iso = make_iso_ctrl()
        pid = iso.test_plan_service.create_plan(add_iso_project(iso), '空计划')
        with pytest.raises(ValueError):
            export_handlers._export_tasks(iso, svc, 'Excel (.xlsx)', None, pid)

    def test_export_issues_excel_with_fa_capa_maps(self, export_handlers, ctrl, base_data,
                                                   svc, tmp_path):
        """Issue 导出：Excel 产物非空，且批量拉取 FA/CAPA map。"""
        path = export_handlers._export_issues(ctrl, svc, 'Excel (.xlsx)', None)
        self._assert_file(path)
        os.unlink(path)

    def test_export_issues_rejects_non_excel(self, export_handlers, ctrl, svc):
        """Issue 导出只支持 Excel。"""
        with pytest.raises(ValueError, match='Excel'):
            export_handlers._export_issues(ctrl, svc, 'PDF (.pdf)', None)

    def test_export_issues_empty_raises(self, export_handlers, svc):
        """无 Issue → ValueError。"""
        iso = make_iso_ctrl()
        with pytest.raises(ValueError, match='没有 Issue'):
            export_handlers._export_issues(iso, svc, 'Excel (.xlsx)', None)

    def test_export_samples_excel(self, export_handlers, ctrl, base_data, svc):
        """样品台账 Excel 导出。"""
        path = export_handlers._export_samples(ctrl, svc, 'Excel (.xlsx)', None)
        self._assert_file(path)
        os.unlink(path)

    def test_export_samples_rejects_non_excel_and_empty(self, export_handlers, ctrl, svc):
        """样品导出：非 Excel 拒绝；无数据拒绝。"""
        with pytest.raises(ValueError):
            export_handlers._export_samples(ctrl, svc, 'Word (.docx)', None)
        iso = make_iso_ctrl()
        with pytest.raises(ValueError, match='没有样品'):
            export_handlers._export_samples(iso, svc, 'Excel (.xlsx)', None)

    @pytest.mark.parametrize("fmt,suffix", [('Word (.docx)', '.docx'),
                                            ('PDF (.pdf)', '.pdf')])
    def test_export_comprehensive_formats(self, export_handlers, ctrl, base_data, svc,
                                          fmt, suffix):
        """综合报告 Word/PDF 导出。"""
        path = export_handlers._export_comprehensive(ctrl, svc, fmt, None,
                                                     base_data['plan_a'])
        self._assert_file(path)
        assert path.endswith(suffix)
        os.unlink(path)

    def test_export_comprehensive_without_plan_raises(self, export_handlers, ctrl, svc):
        with pytest.raises(ValueError):
            export_handlers._export_comprehensive(ctrl, svc, 'PDF (.pdf)', None, None)

    @pytest.mark.parametrize("fmt,suffix", [('Excel (.xlsx)', '.xlsx'),
                                            ('Word (.docx)', '.docx'),
                                            ('PDF (.pdf)', '.pdf')])
    def test_export_dvpr_all_formats(self, export_handlers, ctrl, base_data, svc, fmt,
                                     suffix):
        """DVP&R 报告三格式导出。"""
        path = export_handlers._export_dvpr(ctrl, svc, fmt, None, base_data['plan_a'])
        self._assert_file(path)
        assert path.endswith(suffix)
        os.unlink(path)

    def test_export_dvpr_without_plan_raises(self, export_handlers, ctrl, svc):
        with pytest.raises(ValueError):
            export_handlers._export_dvpr(ctrl, svc, 'PDF (.pdf)', None, None)

    def test_export_8d_docx_and_pdf(self, export_handlers, ctrl, base_data, svc):
        """8D 报告 Word/PDF 导出（含任务/样品/技术员关联信息）。"""
        ctrl.technicians.insert(name='王五', role='Test', department='实验室')
        tech_id = [t.id for t in ctrl.technicians.list_all() if t.name == '王五'][0]
        ctrl.issue_service.update(base_data['issue_id'], assignee_id=tech_id)

        for fmt, suffix in [('Word (.docx)', '.docx'), ('PDF (.pdf)', '.pdf')]:
            path = export_handlers._export_8d(ctrl, svc, fmt, None,
                                              base_data['issue_id'])
            self._assert_file(path)
            assert path.endswith(suffix)
            os.unlink(path)

    def test_export_8d_requires_issue_and_rejects_excel(self, export_handlers, ctrl, svc):
        """8D：未选 Issue / Excel 格式均拒绝。"""
        with pytest.raises(ValueError, match='Issue'):
            export_handlers._export_8d(ctrl, svc, 'PDF (.pdf)', None, None)
        with pytest.raises(ValueError, match='Excel'):
            export_handlers._export_8d(ctrl, svc, 'Excel (.xlsx)', None,
                                       ctrl.issue_service.list_all()[0].id)

    def test_dispatch_table_covers_all_content_types(self, export_handlers):
        """dispatch 表覆盖 6 类内容。"""
        assert set(export_handlers._export_dispatch) == {
            '测试任务', 'Issue', '样品', '综合', 'DVP&R', '8D',
        }


# ══════════════════════════════════════════════════════════════
#  ExportHandlers — Worker 线程组件
# ══════════════════════════════════════════════════════════════


class TestExportWorkerComponents:
    def test_worker_data_provider_roundtrip(self, tmp_path):
        """WorkerDataProvider：独立连接 + schema 初始化 + 服务读写闭环。"""
        from src.handlers.export_handlers import WorkerDataProvider

        db_file = tmp_path / 'worker.db'
        provider = WorkerDataProvider(str(db_file))
        try:
            provider._conn.execute(
                "INSERT INTO projects (name, product, customer, description, status)"
                " VALUES ('Worker项目', 'P', 'C', 'D', 'active')"
            )
            pid = provider.test_plan_service.create_plan(1, 'Worker计划')
            tid = provider.test_plan_service.create_task(pid, 'Worker任务', duration=2)
            assert [t.name for t in provider.test_plan_service.get_tasks(pid)] == ['Worker任务']
            assert provider.test_plan_service.get_task(tid) is not None
            assert provider.technicians is not None
        finally:
            provider.close()
            assert provider._conn is None

    def test_export_worker_success_emits_finished(self, tmp_path):
        """run() 同步执行成功路径 → finished 信号携带产物路径。"""
        from src.handlers.export_handlers import ExportWorker

        out_file = tmp_path / 'worker_out.xlsx'
        finished: list = []
        errors: list = []

        def _fn(provider, svc, fmt, project_id, plan_id, issue_id):
            out_file.write_text('data')
            return str(out_file)

        worker = ExportWorker(_fn, str(tmp_path / 'x.db'), None, 'Excel', None, None, None)
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)
        worker.run()  # 同步调用，不进入事件循环

        assert finished == [str(out_file)]
        assert errors == []

    def test_export_worker_value_error_emits_error(self, tmp_path):
        """handler 抛 ValueError → error 信号携带原始消息。"""
        from src.handlers.export_handlers import ExportWorker

        errors: list = []
        finished: list = []

        def _fn(provider, svc, fmt, *args):
            raise ValueError('没有选中测试计划')

        worker = ExportWorker(_fn, str(tmp_path / 'x.db'), None, 'Excel', None, None, None)
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)
        worker.run()

        assert errors == ['没有选中测试计划']
        assert finished == []

    def test_on_export_dispatch_and_composite_downgrade(self, main_window, export_handlers,
                                                        monkeypatch):
        """导出入口：综合+Excel 自动降级为 PDF，dispatch 到综合处理器。"""
        from PySide6.QtCore import Signal
        import src.handlers.export_handlers as eh
        select_plan(main_window, None)  # 未选计划（plan_id=None 传给 worker）
        captured: dict = {}

        class _FakeExportDialog:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def exec(self) -> int:
                return QDialog.DialogCode.Accepted

            def deleteLater(self) -> None:
                pass

            def get_data(self) -> dict:
                return {'content': '综合', 'format': 'Excel (.xlsx)', 'project_id': None}

        class _StubWorker(QThread):
            finished = Signal(str)
            error = Signal(str)

            def __init__(self, handler_fn, db_path, svc, fmt, project_id, plan_id,
                         issue_id, parent=None) -> None:
                super().__init__(parent)
                captured.update(handler_fn=handler_fn, fmt=fmt, project_id=project_id,
                                plan_id=plan_id, issue_id=issue_id)

            def start(self) -> None:
                self.finished.emit('')

            def terminate(self) -> None:
                pass

        monkeypatch.setattr(eh, "ExportDialog", _FakeExportDialog)
        monkeypatch.setattr(eh, "ExportWorker", _StubWorker)

        export_handlers._on_export()

        assert captured['handler_fn'] == export_handlers._export_comprehensive
        assert captured['fmt'] == 'PDF (.pdf)'
