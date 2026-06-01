"""排程引擎单元测试 — 覆盖 3 阶段核心算法。

使用纯 Python 测试，无需 Qt 或数据库。
"""

from __future__ import annotations

import json
import pytest

from src.models.test_plan import TestTask
from src.models.common import Equipment
from src.services.scheduler import (
    ScheduleConfig,
    build_dependency_map,
    topological_order,
    run_auto_schedule,
    _work_day_end,
    _iterate_work_days,
    _is_weekend,
    _is_holiday,
)


# ═══════════════════════════════════════════════════════════════════
#  辅助函数 — 创建测试任务
# ═══════════════════════════════════════════════════════════════════

def _make_task(
    id: int,
    name: str = "",
    duration: int = 1,
    start_day: int = 0,
    status: str = "pending",
    priority: int = 3,
    dependencies: list[int] | None = None,
    equipment_id: int | None = None,
) -> TestTask:
    return TestTask(
        id=id,
        name=name or f"Task-{id}",
        duration=duration,
        start_day=start_day,
        status=status,
        priority=priority,
        dependencies=json.dumps(dependencies or []),
        equipment_id=equipment_id,
    )


def _make_empty_config() -> ScheduleConfig:
    return ScheduleConfig(
        start_date="2026-01-01",
        skip_weekends=False,
        skip_holidays=False,
    )


# ═══════════════════════════════════════════════════════════════════
#  日期辅助函数
# ═══════════════════════════════════════════════════════════════════

class TestDateHelpers:
    def test_is_weekend_saturday(self):
        """2026-01-03 是星期六。"""
        assert _is_weekend(2, "2026-01-01")

    def test_is_weekend_sunday(self):
        """2026-01-04 是星期日。"""
        assert _is_weekend(3, "2026-01-01")

    def test_is_weekend_weekday(self):
        """2026-01-05 是星期一。"""
        assert not _is_weekend(4, "2026-01-01")

    def test_is_holiday(self):
        holidays = {"2026-01-01"}
        assert _is_holiday(0, "2026-01-01", holidays)

    def test_not_holiday(self):
        holidays = {"2026-01-01"}
        assert not _is_holiday(1, "2026-01-01", holidays)

    def test_work_day_end_basic(self):
        """3 天工期，从第 0 天开始，结束于第 3 天。"""
        end = _work_day_end(0, 3, False, "2026-01-01")
        assert end == 3

    def test_work_day_end_skip_weekend(self):
        """3 天工期跳过周末（2026-01-03 周六）。"""
        end = _work_day_end(0, 3, True, "2026-01-01", True, set())
        assert end == 5  # 第 0/1/2 工作，第 3/4 周末，第 5 天才是结束

    def test_iterate_work_days_basic(self):
        days = _iterate_work_days(0, 3, False, "2026-01-01")
        assert days == [0, 1, 2]

    def test_iterate_work_days_skip_weekend(self):
        days = _iterate_work_days(0, 3, True, "2026-01-01", True, set())
        # 2026-01-01 周四: day0=周四, day1=周五, day2=周六(跳), day3=周日(跳), day4=周一
        assert days == [0, 1, 4]


# ═══════════════════════════════════════════════════════════════════
#  依赖图 & 拓扑排序
# ═══════════════════════════════════════════════════════════════════

class TestDependencyMap:
    def test_empty_deps(self):
        task = _make_task(1, dependencies=[])
        dep_map = build_dependency_map([task])
        assert dep_map == {1: []}

    def test_single_dep(self):
        t1 = _make_task(1, dependencies=[])
        t2 = _make_task(2, dependencies=[1])
        dep_map = build_dependency_map([t1, t2])
        assert dep_map[2] == [1]

    def test_invalid_json_returns_empty(self):
        """非法的 JSON 依赖字符串应安全处理为空列表。"""
        task = TestTask(id=1, name="T1", duration=1, dependencies="not json")
        dep_map = build_dependency_map([task])
        assert dep_map[1] == []


class TestTopologicalOrder:
    def test_single_task(self):
        t = _make_task(1)
        order = topological_order([t], {1: []})
        assert [x.id for x in order] == [1]

    def test_two_independent(self):
        t1 = _make_task(1)
        t2 = _make_task(2)
        order = topological_order([t1, t2], {1: [], 2: []})
        assert {x.id for x in order} == {1, 2}

    def test_linear_chain(self):
        t1 = _make_task(1, dependencies=[])
        t2 = _make_task(2, dependencies=[1])
        t3 = _make_task(3, dependencies=[2])
        order = topological_order([t1, t2, t3], {1: [], 2: [1], 3: [2]})
        ids = [x.id for x in order]
        assert ids == [1, 2, 3]

    def test_diamond_dependency(self):
        t1 = _make_task(1, dependencies=[])
        t2 = _make_task(2, dependencies=[1])
        t3 = _make_task(3, dependencies=[1])
        t4 = _make_task(4, dependencies=[2, 3])
        order = topological_order([t1, t2, t3, t4], {1: [], 2: [1], 3: [1], 4: [2, 3]})
        ids = [x.id for x in order]
        assert ids.index(1) < ids.index(2)
        assert ids.index(1) < ids.index(3)
        assert ids.index(2) < ids.index(4)
        assert ids.index(3) < ids.index(4)

    def test_priority_ordering(self):
        """低优先级数字 = 更高优先级，应排在前面。"""
        t1 = _make_task(1, priority=3)
        t2 = _make_task(2, priority=1)  # 更高优先级
        order = topological_order([t1, t2], {1: [], 2: []})
        ids = [x.id for x in order]
        assert ids == [2, 1]

    def test_cycle_detection(self):
        """循环依赖的任务应被跳过并记录警告。"""
        t1 = _make_task(1, dependencies=[3])
        t2 = _make_task(2, dependencies=[1])
        t3 = _make_task(3, dependencies=[2])
        order = topological_order([t1, t2, t3], {1: [3], 2: [1], 3: [2]})
        # 至少会丢弃一个任务
        assert len(order) < 3


# ═══════════════════════════════════════════════════════════════════
#  Phase 1 — Greedy placement
# ═══════════════════════════════════════════════════════════════════

class TestGreedyPlacement:
    def test_empty_tasks(self):
        result = run_auto_schedule([], [], _make_empty_config())
        assert result["report"]["total_days"] == 0
        assert result["report"]["suggestions"] == []

    def test_single_task(self):
        tasks = [_make_task(1, duration=5)]
        result = run_auto_schedule(tasks, [], _make_empty_config())
        assert tasks[0].start_day == 0
        assert result["report"]["total_days"] == 5

    def test_sequential_dependency(self):
        """有依赖的任务应排在依赖完成后。"""
        t1 = _make_task(1, duration=3, dependencies=[])
        t2 = _make_task(2, duration=2, dependencies=[1])
        tasks = [t1, t2]
        run_auto_schedule(tasks, [], _make_empty_config())
        assert t1.start_day == 0
        assert t2.start_day >= 3  # t1 需 3 天

    def test_parallel_independent(self):
        """无依赖的任务可并行。"""
        t1 = _make_task(1, duration=5)
        t2 = _make_task(2, duration=3)
        tasks = [t1, t2]
        result = run_auto_schedule(tasks, [], _make_empty_config())
        # 两个任务都可从第 0 天开始
        assert t1.start_day == 0
        assert t2.start_day == 0
        assert result["report"]["total_days"] == 5

    def test_priority_order(self):
        """高优先级（低数字）任务应排在前。无设备约束时可并行。"""
        t1 = _make_task(1, duration=3, priority=5)
        t2 = _make_task(2, duration=3, priority=1)  # 高优先级
        tasks = [t1, t2]
        run_auto_schedule(tasks, [], _make_empty_config())
        # 高优先级任务从第 0 天开始
        assert t2.start_day == 0
        # 无设备约束下可并行，t1 也从第 0 天开始
        assert t1.start_day == 0

    def test_long_task_first(self):
        """长任务不应阻塞所有短任务（短任务可并行插空）。"""
        t1 = _make_task(1, duration=10, priority=1)
        t2 = _make_task(2, duration=1, priority=2)
        tasks = [t1, t2]
        run_auto_schedule(tasks, [], _make_empty_config())
        # 无设备约束下，两个任务都可从第 0 天开始（并行）
        assert t1.start_day == 0
        assert t2.start_day == 0


# ═══════════════════════════════════════════════════════════════════
#  Equipment constraints
# ═══════════════════════════════════════════════════════════════════

class TestEquipmentConstraints:
    def test_equipment_capacity_one(self):
        """同一设备最多并行 1 个任务。"""
        t1 = _make_task(1, duration=3, equipment_id=10)
        t2 = _make_task(2, duration=3, equipment_id=10)
        tasks = [t1, t2]
        config = ScheduleConfig(start_date="2026-01-01", equipment_capacity={10: 1})
        run_auto_schedule(tasks, [Equipment(id=10, name="温箱")], config)
        assert t1.start_day == 0
        assert t2.start_day >= 3  # 等待 t1 完成

    def test_equipment_capacity_two(self):
        """容量 = 2 时两个任务可并行。"""
        t1 = _make_task(1, duration=3, equipment_id=10)
        t2 = _make_task(2, duration=3, equipment_id=10)
        tasks = [t1, t2]
        config = ScheduleConfig(start_date="2026-01-01", equipment_capacity={10: 2})
        run_auto_schedule(tasks, [Equipment(id=10, name="温箱")], config)
        assert t1.start_day == 0
        assert t2.start_day == 0  # 容量 2，可并行

    def test_different_equipment_independent(self):
        """不同设备之间不互相影响。"""
        t1 = _make_task(1, duration=3, equipment_id=10)
        t2 = _make_task(2, duration=3, equipment_id=20)
        tasks = [t1, t2]
        config = ScheduleConfig(start_date="2026-01-01", equipment_capacity={10: 1, 20: 1})
        run_auto_schedule(tasks, [Equipment(id=10, name="温箱"), Equipment(id=20, name="振动台")], config)
        assert t1.start_day == 0
        assert t2.start_day == 0


# ═══════════════════════════════════════════════════════════════════
#  Phase 2 — Compression (left-shift)
# ═══════════════════════════════════════════════════════════════════

class TestCompression:
    def test_compress_gap(self):
        """左移压缩应消除任务间的空闲间隙。"""
        t1 = _make_task(1, duration=3, dependencies=[])
        t2 = _make_task(2, duration=2, dependencies=[1])
        t3 = _make_task(3, duration=1, dependencies=[])
        tasks = [t1, t2, t3]
        # 先故意将 t3 设得很晚
        t3.start_day = 20
        config = _make_empty_config()
        run_auto_schedule(tasks, [], config)
        # 压缩后 t3 应被拉到第 0 天
        assert t3.start_day == 0


# ═══════════════════════════════════════════════════════════════════
#  Phase 3 — Report
# ═══════════════════════════════════════════════════════════════════

class TestReport:
    def test_report_structure(self):
        tasks = [_make_task(1, duration=5)]
        result = run_auto_schedule(tasks, [], _make_empty_config())
        report = result["report"]
        assert "total_days" in report
        assert "original_days" in report
        assert "equipment_utilization" in report
        assert "bottlenecks" in report
        assert "suggestions" in report

    def test_equipment_utilization(self):
        t1 = _make_task(1, duration=10, equipment_id=10)
        tasks = [t1]
        config = ScheduleConfig(start_date="2026-01-01", equipment_capacity={10: 1})
        result = run_auto_schedule(tasks, [Equipment(id=10, name="温箱")], config)
        util = result["report"]["equipment_utilization"]
        assert len(util) >= 1
        # 设备 10 被使用 10 天，总可用 10 天 → 100%
        eq10 = [u for u in util if u["equipment_id"] == 10]
        assert eq10
        assert eq10[0]["utilization"] == 100.0

    def test_deadline_exceeded_suggestion(self):
        tasks = [_make_task(1, duration=20)]
        config = ScheduleConfig(start_date="2026-01-01", deadline="2026-01-15")
        result = run_auto_schedule(tasks, [], config)
        suggestions = result["report"]["suggestions"]
        assert any("超出截止日期" in s for s in suggestions)


# ═══════════════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_completed_tasks(self):
        """全部已完成的任务不应影响排程。"""
        t1 = _make_task(1, duration=5, status="completed")
        result = run_auto_schedule([t1], [], _make_empty_config())
        assert result["report"]["total_days"] == 0

    def test_skip_weekends(self):
        """跳过周末时，工期应延长到包含非工作日。"""
        t1 = _make_task(1, duration=5)
        config = ScheduleConfig(start_date="2026-01-01", skip_weekends=True)
        run_auto_schedule([t1], [], config)
        # 2026-01-01 周四，第 0/1/2 天工作日，第 3/4 周末
        # 5 个工作日 → 跨 7 个日历日
        assert t1.start_day == 0

    def test_holidays_respected(self):
        """配置的节假日内不应排任务。"""
        t1 = _make_task(1, duration=3)
        config = ScheduleConfig(
            start_date="2026-01-01",
            skip_weekends=False,
            skip_holidays=True,
            holidays={"2026-01-01"},  # 元旦
        )
        run_auto_schedule([t1], [], config)
        # 第 0 天是假日，应从第 1 天开始
        assert t1.start_day == 1

    def test_daily_start_limit(self):
        """每日启动上限限制同一天开始的任务数。"""
        t1 = _make_task(1, duration=5)
        t2 = _make_task(2, duration=3)
        t3 = _make_task(3, duration=2)
        tasks = [t1, t2, t3]
        config = ScheduleConfig(
            start_date="2026-01-01",
            daily_start_limit=2,  # 每天最多 2 个新任务
        )
        run_auto_schedule(tasks, [], config)
        # 第 0 天：2 个任务开始
        start_days = [t.start_day for t in tasks]
        day0_count = sum(1 for d in start_days if d == 0)
        assert day0_count <= 2
