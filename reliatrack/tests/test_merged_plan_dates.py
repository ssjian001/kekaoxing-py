"""回归: "全部计划"合并视图必须按任务所属计划各自起算日期 (审计 P1-5)。

旧行为: 合并视图统一用 all_plans[0].start_date 推算所有任务的预计开始/结束,
各计划起算日不同时日期全错、超期误判(含任务表红底标红)、甘特条位置错,
且失效模式分析只取第一个计划的 Issue。
"""

from datetime import date, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from src.models.test_plan import TestTask
from src.views.widgets.gantt_widget import _GanttWidget
from src.views.widgets.plan_summary import compute_summary
from src.views.widgets.task_table import _TaskTable

PLAN_STARTS = {1: "2026-01-01", 2: "2026-03-01"}
# 2026-03-01 - 2026-01-01 = 31(1月) + 28(2月) = 59 天
PLAN_B_OFFSET = 59


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _task(tid: int, plan_id: int, name: str, start_day: int = 0,
          duration: int = 1, status: str = "pending") -> TestTask:
    return TestTask(
        id=tid, plan_id=plan_id, name=name, category="机械试验",
        start_day=start_day, duration=duration, status=status, progress=0.0,
    )


class TestGanttMergedPlans:
    def test_offset_added_for_later_plan(self, qapp):
        """B 计划条必须按其起算日偏移, 而不是与 A 计划同一原点。"""
        tasks = [_task(1, 1, "A计划任务"), _task(2, 2, "B计划任务")]
        g = _GanttWidget()
        g.set_tasks(tasks, total_days=120, start_date="2026-01-01",
                    plan_start_dates=PLAN_STARTS)
        assert g._task_day_range(tasks[0])[0] == 0
        assert g._task_day_range(tasks[1])[0] == PLAN_B_OFFSET

    def test_offset_ignored_without_map(self, qapp):
        """不传映射(单计划视图)时行为不变 — 不能引入回归。"""
        tasks = [_task(1, 1, "A计划任务", start_day=5)]
        g = _GanttWidget()
        g.set_tasks(tasks, total_days=30, start_date="2026-01-01")
        assert g._task_day_range(tasks[0])[0] == 5


class TestTaskTableMergedPlans:
    def test_planned_dates_use_own_plan_start(self, qapp):
        """列 4/5 = 预计开始/预计结束, 必须按各自计划起算。"""
        tasks = [
            _task(1, 1, "A计划任务", start_day=0, duration=2),
            _task(2, 2, "B计划任务", start_day=3, duration=2),
        ]
        t = _TaskTable()
        t.set_tasks(tasks, {}, {}, start_date="2026-01-01",
                    plan_start_dates=PLAN_STARTS)
        assert t.item(0, 4).text() == "2026-01-01"
        assert t.item(1, 4).text() == "2026-03-04"   # 2026-03-01 + 3 天
        # 列 5 可能追加超期标注, 只校验日期前缀
        assert t.item(0, 5).text().startswith("2026-01-02")


class TestSummaryMergedPlans:
    def test_due_counted_against_own_plan(self):
        """B 计划今天起算的 1 天任务 = 今天到期; 若错用 A 计划起算会误判超期。"""
        today = date.today()
        plan_a_start = (today - timedelta(days=60)).isoformat()
        task = _task(1, 2, "B计划今天任务", start_day=0, duration=1)
        due, pending, overdue = compute_summary(
            [task], {}, plan_a_start, plan_start_dates={2: today.isoformat()},
        )
        assert due == 1, "应按 B 计划起算判为今天到期"
        assert overdue == 0, "错用 A 计划起算会误判超期"

    def test_overdue_counted_against_own_plan(self):
        """A 计划 60 天前的任务应判超期。"""
        today = date.today()
        plan_a_start = (today - timedelta(days=60)).isoformat()
        task = _task(1, 1, "A计划旧任务", start_day=0, duration=1)
        due, pending, overdue = compute_summary(
            [task], {}, plan_a_start, plan_start_dates={1: plan_a_start},
        )
        assert overdue == 1
        assert due == 0

    def test_falls_back_to_global_start_date(self):
        """计划日期缺失时回落全局 start_date(不能变成 0 统计)。"""
        today = date.today()
        plan_a_start = (today - timedelta(days=10)).isoformat()
        task = _task(1, 99, "无日期计划任务", start_day=0, duration=1)
        due, pending, overdue = compute_summary(
            [task], {}, plan_a_start, plan_start_dates={},
        )
        assert overdue == 1

    def test_legacy_signature_still_works(self):
        """未传 plan_start_dates 的旧调用点必须保持可用。"""
        today = date.today()
        task = _task(1, 1, "任务", start_day=0, duration=1)
        assert compute_summary([task], {}, today.isoformat()) == (1, 0, 0)
        assert compute_summary([task], {}, "") == (0, 0, 0)
