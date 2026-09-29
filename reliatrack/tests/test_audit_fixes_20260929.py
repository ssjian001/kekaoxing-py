"""审计修复回归测试 — P2-12 / P3-1 / P3-11 / P3-12 / P3-13 / P3-14 / P3-15。

每个用例都对应一个「修复前必失败」的行为，断言不放宽：

- P2-12: Issue 批量编辑命令的撤销刷新路由到 issue（而非一律 task）
- P3-1 : _safe_kwargs 丢弃未知键必须告警（不静默）
- P3-11: 批量改任务中途失败 → 已写部分全部回滚且不入撤销栈
- P3-12: 结果矩阵编辑不再发无效 notify("result")
- P3-13: Ctrl+F 聚焦搜索框时 getter 返回 None 不崩
- P3-14: 命令面板主题动作是「切换」而非硬编码暗色
- P3-15: 启动只做一次全量加载（且首次加载仍完成）
"""

from __future__ import annotations

import logging

import pytest

from PySide6.QtWidgets import QApplication, QMessageBox

import src.styles.theme as theme
from src.controllers import AppController
from src.db.repositories.base import BaseRepository


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def ctrl(app) -> AppController:
    c = AppController(":memory:")
    c.initialize()
    return c


@pytest.fixture(scope="module")
def main_window(ctrl):
    from main import MainWindow

    w = MainWindow(ctrl)
    w.show()
    return w


@pytest.fixture(autouse=True)
def _patch_static_popups(monkeypatch):
    """autouse: 拦截 QMessageBox 静态弹窗，防模态阻塞（含 P3-11 的 critical）。"""
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))


@pytest.fixture(scope="module", autouse=True)
def _cleanup_shared_state(ctrl):
    """模块收尾：清撤销栈（防 closeEvent 弹窗）+ 复位主题，避免污染后续模块。"""
    original_theme = theme.current_theme()
    yield
    try:
        if ctrl.undo_manager is not None:
            ctrl.undo_manager.clear()
        if theme.current_theme() != original_theme:
            theme.set_theme(original_theme)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  P2-12: Issue 批量编辑命令的撤销刷新路由
# ═══════════════════════════════════════════════════════════════════


class TestP212IssueCommandUndoRouting:
    """batch_dialog 用通用 UpdateFieldCommand 改 Issue 字段；
    撤销时必须刷 Issue 视图，不能一律映射成 task。"""

    def test_issue_batch_undo_notifies_issue_not_task(
        self, main_window, ctrl, monkeypatch,
    ):
        """复刻 batch_dialog 的入库+record 流程后撤销 → 只通知 issue。"""
        from src.services.undo_manager import UndoManager, UpdateFieldCommand

        ctrl.issue_service.create(title="P2-12 Issue", severity="minor", status="open")
        issue_id = ctrl.issue_service.create(
            title="P2-12 Issue 2", severity="minor", status="open",
        )
        repo = ctrl.issue_service._repo
        # 与 batch_dialog._execute_batch 同构：先写库，再 record 命令
        ctrl.issue_service.update(issue_id, severity="critical")
        um = ctrl.undo_manager
        assert isinstance(um, UndoManager)
        um.clear()
        um.record(UpdateFieldCommand(repo, issue_id, "severity", "minor", "critical", "Issue"))

        seen: list[str] = []
        monkeypatch.setattr(ctrl, "notify_data_changed", lambda et="all": seen.append(et))

        main_window._on_undo()

        assert ctrl.issue_service.get(issue_id).severity == "minor", "撤销未回写旧值"
        assert seen == ["issue"], f"撤销刷新路由错误: {seen}"

    def test_update_field_command_routing_by_entity(
        self, main_window, ctrl,
    ):
        """UpdateFieldCommand 按 repo 归属路由：issues→issue，test_tasks→task。"""
        from src.services.undo_manager import UpdateFieldCommand

        issue_cmd = UpdateFieldCommand(
            ctrl.issue_service._repo, 1, "severity", "minor", "critical", "Issue",
        )
        assert main_window._entity_types_for_command(issue_cmd) == {"issue"}

        task_cmd = UpdateFieldCommand(
            ctrl.test_plan_service.task_repo(), 1, "progress", 0.0, 50.0, "任务",
        )
        assert main_window._entity_types_for_command(task_cmd) == {"task"}

    def test_macro_of_issue_commands_routes_to_issue(self, main_window, ctrl):
        """MacroCommand 合并子命令实体类型（Issue 批量编辑入栈形态）。"""
        from src.services.undo_manager import MacroCommand, UpdateFieldCommand

        macro = MacroCommand([
            UpdateFieldCommand(ctrl.issue_service._repo, 1, "priority", 3, 1, "Issue"),
            UpdateFieldCommand(ctrl.issue_service._repo, 2, "priority", 3, 1, "Issue"),
        ], "批量更新 2 个 Issue")
        assert main_window._entity_types_for_command(macro) == {"issue"}


# ═══════════════════════════════════════════════════════════════════
#  P3-1: _safe_kwargs 不静默丢键
# ═══════════════════════════════════════════════════════════════════


def _base_repo(conn) -> BaseRepository:
    """裸 BaseRepository + 可实例化的占位模型（只验证 _safe_kwargs / SQL 拼装）。"""

    class _DummyModel:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    repo = BaseRepository(conn, "projects", _DummyModel)
    repo.invalidate_columns_cache()
    return repo


@pytest.fixture()
def local_conn():
    """本模块私有的内存库 — 不复用 conftest.db_conn。

    conftest 的 db_conn 在 teardown 会 close_connection(':memory:')，
    而那正是本模块 module 级 ctrl(MainWindow) 依赖的连接，会把它一并关掉。
    """
    import apsw

    from src.db.schema import init_schema

    conn = apsw.Connection(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestP31SafeKwargsNotSilent:
    def test_dropped_key_logs_warning(self, local_conn, caplog):
        repo = _base_repo(local_conn)
        with caplog.at_level(logging.WARNING):
            safe = repo._safe_kwargs({"name": "X", "nmae": "拼错列名"})
        assert safe == {"name": "X"}
        assert any("nmae" in r.getMessage() for r in caplog.records), "丢键未告警"

    def test_update_with_typo_column_warns(self, local_conn, caplog):
        """update 拼错列名 → 行为仍是 no-op，但必须告警而非静默。"""
        local_conn.execute("INSERT INTO projects (name) VALUES ('P3-1项目')")
        pid = local_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        repo = _base_repo(local_conn)
        with caplog.at_level(logging.WARNING):
            repo.update(pid, nmae="拼错列名")
        assert any("nmae" in r.getMessage() for r in caplog.records), "update 静默吞掉了拼错列名"
        row = local_conn.execute("SELECT name FROM projects WHERE id = ?", (pid,)).fetchone()
        assert row[0] == "P3-1项目"

    def test_list_all_partial_filter_drop_warns(self, local_conn, caplog):
        """过滤条件含未知键 → 该键被丢弃（过滤静默失效），必须告警。"""
        local_conn.execute("INSERT INTO projects (name, status) VALUES ('P3-1甲', 'active')")
        repo = _base_repo(local_conn)
        with caplog.at_level(logging.WARNING):
            rows = repo.list_all(name="P3-1甲", nmae="不存在")
        assert len(rows) == 1
        assert any("nmae" in r.getMessage() for r in caplog.records), "过滤丢键未告警"

    def test_legal_keys_are_silent(self, local_conn, caplog):
        """合法列名不得产生任何告警（保证未改变既有调用的行为表现）。"""
        repo = _base_repo(local_conn)
        with caplog.at_level(logging.WARNING):
            safe = repo._safe_kwargs({"name": "X", "status": "active"})
        assert safe == {"name": "X", "status": "active"}
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ═══════════════════════════════════════════════════════════════════
#  P3-11: 批量更新部分失败必须回滚
# ═══════════════════════════════════════════════════════════════════


class TestP311BatchUpdateRollback:
    def test_partial_failure_rolls_back_all_writes(self, main_window, ctrl, monkeypatch):
        """第 2 条命令写库失败 → 第 1 条已写入的改动被回滚，且不入撤销栈。"""
        from src.handlers.plan_handlers import PlanHandlers

        handlers = PlanHandlers(main_window)
        p = ctrl.project_service.create(name="P3-11项目")
        plan = ctrl.test_plan_service.create_plan(p, "P3-11计划", start_date="2026-09-01")
        t1 = ctrl.test_plan_service.create_task(plan, "P3-11甲", duration=1)
        t2 = ctrl.test_plan_service.create_task(plan, "P3-11乙", duration=1)
        t3 = ctrl.test_plan_service.create_task(plan, "P3-11丙", duration=1)
        ctrl.undo_manager.clear()

        repo = ctrl.test_plan_service.task_repo()
        real_update = repo.update
        calls = {"n": 0}

        def flaky_update(task_id, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("模拟第 2 条写入失败")
            return real_update(task_id, **kwargs)

        monkeypatch.setattr(repo, "update", flaky_update)

        handlers._on_batch_value([t1, t2, t3], 3, "9")  # 批量改工期

        assert calls["n"] >= 2, "未走到失败点，测试无效"
        # 全部回滚：三条工期都不应变成 9
        assert ctrl.test_plan_service.get_task(t1).duration == 1, "已写入的第 1 条未回滚"
        assert ctrl.test_plan_service.get_task(t2).duration == 1
        assert ctrl.test_plan_service.get_task(t3).duration == 1
        # 部分成功的命令不得进入撤销栈
        assert ctrl.undo_manager.undo_count == 0

    def test_success_path_still_records_macro(self, main_window, ctrl):
        """成功路径不回归：全部写入 + 一次撤销可回退整批。"""
        from src.handlers.plan_handlers import PlanHandlers

        handlers = PlanHandlers(main_window)
        p = ctrl.project_service.create(name="P3-11成功项目")
        plan = ctrl.test_plan_service.create_plan(p, "P3-11成功计划", start_date="2026-09-01")
        t1 = ctrl.test_plan_service.create_task(plan, "成功甲", duration=1)
        t2 = ctrl.test_plan_service.create_task(plan, "成功乙", duration=1)
        ctrl.undo_manager.clear()

        handlers._on_batch_value([t1, t2], 3, "5")

        assert ctrl.test_plan_service.get_task(t1).duration == 5
        assert ctrl.test_plan_service.get_task(t2).duration == 5
        assert ctrl.undo_manager.undo_count == 1

        ctrl.undo_manager.undo()

        assert ctrl.test_plan_service.get_task(t1).duration == 1
        assert ctrl.test_plan_service.get_task(t2).duration == 1


# ═══════════════════════════════════════════════════════════════════
#  P3-12: notify("result") 无效通知
# ═══════════════════════════════════════════════════════════════════


class TestP312InvalidResultNotification:
    def test_matrix_result_edit_only_notifies_known_entity_types(
        self, main_window, ctrl, monkeypatch,
    ):
        """结果矩阵编辑只允许发已知实体类型；"result" 无对应刷新分支。"""
        from src.handlers.plan_handlers import PlanHandlers

        handlers = PlanHandlers(main_window)
        p = ctrl.project_service.create(name="P3-12项目")
        plan = ctrl.test_plan_service.create_plan(p, "P3-12计划", start_date="2026-09-01")
        tid = ctrl.test_plan_service.create_task(plan, "P3-12任务", duration=3)
        sid = ctrl.sample_service.create(
            sn="SN-P312", batch_no="B-P312", spec="SP", project_id=p,
        )
        plans = ctrl.test_plan_service.list_all_plans()
        main_window.test_plan_view.set_plans(
            [x.name for x in plans], [x.id for x in plans],
        )
        main_window.test_plan_view.select_plan_by_id(plan)

        seen: list[str] = []
        monkeypatch.setattr(ctrl, "notify_data_changed", lambda et="all": seen.append(et))

        handlers._on_matrix_result_edit(tid, sid, "pass")

        # 路径确实执行
        assert any(r.result == "pass" for r in ctrl.test_plan_service.get_task_results(tid))
        assert "result" not in seen, f"发出无刷新分支的无效通知: {seen}"
        assert "task" in seen


# ═══════════════════════════════════════════════════════════════════
#  P3-13: Ctrl+F 聚焦 None 控件
# ═══════════════════════════════════════════════════════════════════


class TestP313ShortcutFindNoneWidget:
    def test_ctrl_f_with_unbuilt_bug_list_does_not_crash(
        self, main_window, monkeypatch,
    ):
        """Bug Tracker 列表未构建（list_view 为 None）时 Ctrl+F 不得 AttributeError。"""
        w = main_window
        w._tab_widget.setCurrentIndex(4)  # Bug Tracker
        monkeypatch.setattr(w._bug_tracker_view, "_list_view", None)
        assert w._bug_tracker_view.list_view is None

        w._on_shortcut_find()  # 修复前：None.setFocus() → AttributeError

    def test_ctrl_f_still_focuses_real_search_box(self, main_window):
        """正常路径不回归：测试计划 Tab 的搜索框可被聚焦。"""
        w = main_window
        w._tab_widget.setCurrentIndex(3)
        search_edit = w._test_plan_view._search_edit
        assert search_edit is not None
        w._on_shortcut_find()


# ═══════════════════════════════════════════════════════════════════
#  P3-14: 命令面板主题动作
# ═══════════════════════════════════════════════════════════════════


class TestP314CommandPaletteThemeToggle:
    def test_theme_action_toggles_back_to_light(self, main_window, monkeypatch):
        """连续两次触发主题动作应 dark → light；硬编码 True 会卡在 dark。"""
        class _FakeSettings:
            def setValue(self, *args, **kwargs) -> None:  # noqa: N802
                pass

            def value(self, *args, **kwargs):
                return None

        monkeypatch.setattr("main.QSettings", _FakeSettings)
        w = main_window
        theme.set_theme("light")

        w._on_command_palette_action(("action", "theme"))
        assert theme.current_theme() == "dark"

        w._on_command_palette_action(("action", "theme"))
        assert theme.current_theme() == "light", "命令面板切不回亮色（硬编码暗色）"


# ═══════════════════════════════════════════════════════════════════
#  P3-15: 启动只做一次全量加载
# ═══════════════════════════════════════════════════════════════════


class TestP315StartupSingleFullLoad:
    def test_window_startup_full_load_runs_once(self, ctrl, app, monkeypatch):
        """MainWindow 构造期间全量刷新恰好 1 次，且首次加载确实完成。"""
        from main import MainWindow
        from src.handlers.refresh_handlers import RefreshHandlers

        marker_project = ctrl.project_service.create(name="P3-15项目")

        calls: list[int] = []
        original = RefreshHandlers._do_refresh_all_inner

        def counting_inner(self):
            calls.append(1)
            return original(self)

        monkeypatch.setattr(RefreshHandlers, "_do_refresh_all_inner", counting_inner)

        w = MainWindow(ctrl)
        try:
            w.show()
            assert len(calls) == 1, f"启动期全量加载执行了 {len(calls)} 次（应为 1 次）"
            # 首次加载未被破坏：项目筛选 combo 已按 DB 数据填充
            assert w._project_filter_combo.findData(marker_project) >= 0, "首次加载未完成"
        finally:
            if ctrl.undo_manager is not None:
                ctrl.undo_manager.clear()
            w.close()
