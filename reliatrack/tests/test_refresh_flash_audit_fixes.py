"""回归测试: 审计 P2-8 / P2-11 / P2-13。

P2-8  src/handlers/refresh_handlers.py — `_do_refresh_all` 顶层
      `except Exception: pass` 吞掉全部刷新异常: 单个视图失败后后半段视图
      停在旧数据, 既无日志也无提示。
P2-11 src/views/test_plan_view.py — 选中具体计划时 `set_plans_and_restore`
      手动 emit currentIndexChanged → `_on_plan_changed` 重跑全套查询+
      重渲染, 而唯一调用方 `_refresh_plans` 紧接着自己又刷一遍
      → 最重的测试计划页每次刷新跑两遍。
P2-13 src/views/widgets/task_table.py — `flash_row` 闪烁结束把整行背景刷成
      透明, 永久抹掉超期红/未指派黄行底色, 直到下次全量刷新。
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import src.styles.theme as _t
from src.controllers import AppController
from src.models.test_plan import TestTask
from src.views.test_plan_view import TestPlanView
from src.views.widgets.task_table import _TaskTable


# ══════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


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


@pytest.fixture(scope="module")
def rt_data(ctrl) -> dict:
    """本项目独立的基础数据: 1 项目 / 1 计划 / 1 任务。"""
    pid = ctrl.project_service.create(name="P2 回归项目")
    plan_id = ctrl.test_plan_service.create_plan(pid, "P2 回归计划", start_date="2026-09-01")
    task_id = ctrl.test_plan_service.create_task(
        plan_id, name="P2 回归任务", duration=2, category="机械试验",
    )
    return {"project_id": pid, "plan_id": plan_id, "task_id": task_id}


# ══════════════════════════════════════════════════════════════
#  P2-8: 刷新失败不再被静默吞掉, 且不中断其余视图
# ══════════════════════════════════════════════════════════════


class TestRefreshFailureIsolation:
    def test_failing_view_keeps_rest_refreshing_and_reports(
        self, main_window, rt_data, monkeypatch, caplog,
    ):
        """仪表盘刷新抛错 → 记日志 + 提示用户, 后续视图(待办)仍必须刷新。"""
        win = main_window
        win._refresh_error_warned = False  # 一次性提示标志, 逐测试隔离
        refreshed: list[str] = []
        toasts: list[tuple] = []
        monkeypatch.setattr(win, "toast", lambda msg, level="success": toasts.append((msg, level)))

        def boom(*_a, **_k):
            refreshed.append("dashboard")
            raise RuntimeError("模拟仪表盘刷新失败")

        monkeypatch.setattr(win.dashboard, "refresh", boom)

        original_todo = win.todo_view.refresh

        def spy_todo(*a, **k):
            refreshed.append("todo")
            return original_todo(*a, **k)

        monkeypatch.setattr(win.todo_view, "refresh", spy_todo)

        with caplog.at_level(logging.ERROR, logger="src.handlers.refresh_handlers"):
            win._refresh_all()

        assert "dashboard" in refreshed, "前置条件: 失败步骤确实被执行过"
        assert "todo" in refreshed, "单个视图失败不得中断其余视图刷新"
        assert any(
            "刷新「仪表盘」失败" in r.getMessage() for r in caplog.records
        ), "刷新异常必须留日志(原实现 except Exception: pass 静默吞掉)"
        assert any("仪表盘" in msg for msg, _lvl in toasts), "刷新失败必须提示用户, 不能无提示"
        assert toasts and toasts[0][1] == "error"

    def test_failure_toast_is_one_shot_per_window(
        self, main_window, rt_data, monkeypatch, caplog,
    ):
        """多个视图失败 + 反复刷新 → 用户只被提示一次(不刷屏), 日志仍每次记。"""
        win = main_window
        win._refresh_error_warned = False
        toasts: list[tuple] = []
        monkeypatch.setattr(win, "toast", lambda msg, level="success": toasts.append((msg, level)))

        for target in (win.dashboard, win.knowledge_view, win.equipment_view):
            monkeypatch.setattr(
                target, "refresh",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("模拟刷新失败")),
            )

        with caplog.at_level(logging.ERROR, logger="src.handlers.refresh_handlers"):
            win._refresh_all()

        assert len(toasts) == 1, f"同一次刷新内多个视图失败只提示一次, 实际 {toasts}"
        win._refresh_all()
        assert len(toasts) == 1, "后续刷新不再重复打扰用户"
        assert len(caplog.records) >= 3, "每次失败都必须记日志(提示可以只弹一次)"


# ══════════════════════════════════════════════════════════════
#  P2-11: 选中具体计划时不再重复跑整套查询
# ══════════════════════════════════════════════════════════════


class TestPlanComboSignalDedup:
    def test_set_plans_and_restore_emits_only_on_real_change(self, app):
        """选中计划未变 → 不 emit(去掉重复刷新路径); 真变了 → 仍必须 emit(首次加载不能坏)。"""
        view = TestPlanView()
        emitted: list[int] = []
        view._plan_combo.currentIndexChanged.connect(lambda idx: emitted.append(idx))

        view.set_plans_and_restore(["计划 A", "计划 B"], [10, 20], restore_id=20)
        assert view.get_selected_plan_id() == 20
        assert len(emitted) == 1, "首次选中变化必须 emit(否则首次加载不刷新)"

        view.set_plans_and_restore(["计划 A", "计划 B"], [10, 20], restore_id=20)
        assert view.get_selected_plan_id() == 20
        assert len(emitted) == 1, "选中计划未变时不得再 emit(重复刷新路径)"

        view.set_plans_and_restore(["计划 A", "计划 B"], [10, 20], restore_id=10)
        assert view.get_selected_plan_id() == 10
        assert len(emitted) == 2, "选中计划真的变化时必须 emit"

    def test_refresh_plans_runs_full_query_set_once(
        self, main_window, rt_data, monkeypatch,
    ):
        """选中具体计划后 _refresh_plans 只跑一遍全套查询+渲染(原来跑两遍)。"""
        win = main_window
        handlers = win._refresh_handlers
        plan_id = rt_data["plan_id"]

        # 先完成一次加载, 再让本地 combo 选中具体计划(模拟用户选择)
        handlers._do_refresh_all()
        win.test_plan_view.select_plan_by_id(plan_id)
        assert win.test_plan_view.get_selected_plan_id() == plan_id

        renders: list[int] = []
        original_render = win.test_plan_view.refresh

        def spy_render(*a, **k):
            renders.append(1)
            return original_render(*a, **k)

        monkeypatch.setattr(win.test_plan_view, "refresh", spy_render)

        task_queries: list = []
        service = win.ctrl.test_plan_service
        original_get_tasks = service.get_tasks

        def spy_get_tasks(*a, **k):
            task_queries.append(a[0] if a else k.get("plan_id"))
            return original_get_tasks(*a, **k)

        monkeypatch.setattr(service, "get_tasks", spy_get_tasks)

        handlers._refresh_plans()

        assert task_queries == [plan_id], (
            f"全套任务查询应只跑一次(plan_id={plan_id}), 实际 {task_queries}"
        )
        assert len(renders) == 1, f"测试计划页应只渲染一次, 实际 {len(renders)} 次"

    def test_refresh_plans_still_renders_selected_plan(self, main_window, rt_data):
        """去重后选中计划的数据仍正确落表(不能为了去重把刷新也去掉)。"""
        win = main_window
        win.test_plan_view.select_plan_by_id(rt_data["plan_id"])
        win._refresh_handlers._refresh_plans()

        table = win.test_plan_view.task_table
        assert table.rowCount() == 1
        assert table.item(0, 1).text() == "P2 回归任务"
        assert win.test_plan_view.get_selected_plan_id() == rt_data["plan_id"]


# ══════════════════════════════════════════════════════════════
#  P2-13: 闪烁结束后恢复行「应有底色」(而不是透明)
# ══════════════════════════════════════════════════════════════

_START = (date.today() - timedelta(days=30)).isoformat()


def _expected(hex_color: str, alpha: int) -> tuple:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c.getRgb()


def _bg(table: _TaskTable, row: int, col: int = 0) -> tuple:
    return table.item(row, col).background().color().getRgb()


def _task(tid: int, name: str, start_day: int, duration: int = 1,
          status: str = "pending", technician_id: int | None = 7) -> TestTask:
    return TestTask(
        id=tid, plan_id=1, name=name, category="机械试验", start_day=start_day,
        duration=duration, status=status, progress=0.0, technician_id=technician_id,
    )


class TestFlashRestoresRowBackground:
    """行底色约定(见 task_table.set_tasks): 超期→红25 / 未指派→黄35 / 完成→无底色。"""

    def _table(self) -> _TaskTable:
        table = _TaskTable()
        table.set_tasks(
            [
                _task(1, "超期未完成", start_day=0),                 # 预计结束 = 29 天前 → 红
                _task(2, "未指派且不超期", start_day=29, duration=2, technician_id=None),  # 黄
                _task(3, "已指派且不超期", start_day=29, duration=2),  # 无底色
                _task(4, "已完成超期任务", start_day=0, status="completed"),  # 完成 → 无底色
            ],
            {7: "张工"}, {}, start_date=_START,
        )
        return table

    def test_setup_baseline(self, app):
        """前置: 各行的应有底色符合约定(否则下面的断言无意义)。"""
        table = self._table()
        assert _bg(table, 0) == _expected(_t.RED, 25)
        assert _bg(table, 1) == _expected(_t.YELLOW, 35)
        assert table.item(2, 0).data(Qt.ItemDataRole.BackgroundRole) is None
        assert table.item(3, 0).data(Qt.ItemDataRole.BackgroundRole) is None

    def test_unflash_restores_overdue_red(self, app):
        table = self._table()
        table.flash_row(1, duration_ms=500)
        assert _bg(table, 0) == _expected(_t.YELLOW, 120), "闪烁期间应整行黄色高亮"

        table._unflash_row(0)

        for col in range(table.columnCount()):
            assert _bg(table, 0, col) == _expected(_t.RED, 25), (
                f"闪烁结束必须恢复超期红底色, col={col} 实际 {_bg(table, 0, col)}"
            )

    def test_unflash_restores_unassigned_yellow(self, app):
        table = self._table()
        table.flash_row(2, duration_ms=500)
        table._unflash_row(1)

        for col in range(table.columnCount()):
            assert _bg(table, 1, col) == _expected(_t.YELLOW, 35), (
                f"闪烁结束必须恢复未指派黄底色, col={col} 实际 {_bg(table, 1, col)}"
            )

    def test_unflash_clears_background_of_plain_row(self, app):
        """本无底色的行: 闪烁结束后真正清除 BackgroundRole(不是留透明 brush)。"""
        table = self._table()
        table.flash_row(3, duration_ms=500)
        assert _bg(table, 2) == _expected(_t.YELLOW, 120)

        table._unflash_row(2)

        for col in range(table.columnCount()):
            cell = table.item(2, col)
            assert cell.data(Qt.ItemDataRole.BackgroundRole) is None, (
                f"无底色行闪烁后必须是「无显式底色」, col={col}"
            )
            assert cell.background().style() == Qt.BrushStyle.NoBrush

    def test_flash_timer_restores_overdue_red(self, app):
        """端到端: 由 QTimer 触发的闪烁结束同样恢复红底色。"""
        table = self._table()
        table.flash_row(1, duration_ms=10)
        assert _bg(table, 0) == _expected(_t.YELLOW, 120)

        QTest.qWait(120)

        assert _bg(table, 0) == _expected(_t.RED, 25)

    def test_unflash_keeps_other_rows_untouched(self, app):
        """闪烁只影响目标行, 其余行底色不变。"""
        table = self._table()
        table.flash_row(1, duration_ms=500)
        table._unflash_row(0)
        assert _bg(table, 1) == _expected(_t.YELLOW, 35)
        assert table.item(2, 0).data(Qt.ItemDataRole.BackgroundRole) is None
