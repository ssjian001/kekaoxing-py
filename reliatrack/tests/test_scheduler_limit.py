"""排程引擎单元测试 — 覆盖 daily_start_limit、周末/节假日跳过、starts 字典维护。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

import pytest

from src.models.test_plan import TestTask
from src.services.scheduler import (
    ScheduleConfig,
    can_place_at,
    compress_schedule,
    find_earliest_slot,
    place_task,
    remove_task_from_timeline,
    run_auto_schedule,
)

# ── Helpers ────────────────────────────────────────────────────────

_START = "2026-05-13"  # Wednesday


def _task(tid: int, dur: int = 1, **kw) -> TestTask:
    """快速构造测试任务。"""
    defaults = dict(
        id=tid, plan_id=1, name=f"T{tid}", duration=dur,
        start_day=0, status="pending", priority=2, dependencies="[]",
    )
    defaults.update(kw)
    return TestTask(**defaults)


def _date(day: int, start: str = _START) -> str:
    """day_number → "YYYY-MM-DD"。"""
    return (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=day)).strftime("%Y-%m-%d")


def _weekday(day: int, start: str = _START) -> int:
    """day_number → weekday (0=Mon … 6=Sun)。"""
    return (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=day)).weekday()


def _daily_start_counts(tasks: list[TestTask]) -> dict[int, int]:
    """统计每个 start_day 的任务启动数。"""
    return dict(sorted(Counter(t.start_day for t in tasks).items()))


# ═══════════════════════════════════════════════════════════════════
#  1. ScheduleConfig 默认值
# ═══════════════════════════════════════════════════════════════════

class TestScheduleConfig:
    def test_default_daily_start_limit_is_zero(self):
        cfg = ScheduleConfig()
        assert cfg.daily_start_limit == 0

    def test_default_holidays_empty(self):
        cfg = ScheduleConfig()
        assert cfg.holidays == set()


# ═══════════════════════════════════════════════════════════════════
#  2. can_place_at — starts 上限检查
# ═══════════════════════════════════════════════════════════════════

class TestCanPlaceAt:
    def test_rejects_when_starts_full(self):
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=2)
        starts: dict[int, int] = {0: 2}
        t = _task(1)
        assert can_place_at(t, 0, {}, cfg, starts) is False

    def test_allows_when_starts_below_limit(self):
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=2)
        starts: dict[int, int] = {0: 1}
        t = _task(1)
        assert can_place_at(t, 0, {}, cfg, starts) is True

    def test_allows_when_limit_zero(self):
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=0)
        starts: dict[int, int] = {0: 100}
        t = _task(1)
        assert can_place_at(t, 0, {}, cfg, starts) is True

    def test_allows_when_starts_none(self):
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=2)
        t = _task(1)
        assert can_place_at(t, 0, {}, cfg, None) is True


# ═══════════════════════════════════════════════════════════════════
#  3. place_task / remove_task_from_timeline — starts 增减
# ═══════════════════════════════════════════════════════════════════

class TestStartsRoundtrip:
    def test_place_increments_starts(self):
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=5)
        starts: dict[int, int] = {}
        t = _task(1, dur=2)
        timeline: dict = {}
        place_task(t, 0, timeline, cfg, starts)
        assert starts.get(0) == 1
        place_task(t, 0, timeline, cfg, starts)
        assert starts.get(0) == 2

    def test_remove_decrements_starts(self):
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=5)
        starts: dict[int, int] = {0: 2}
        t = _task(1, dur=2)
        timeline: dict = {}
        place_task(t, 0, timeline, cfg, starts)
        assert starts[0] == 3
        remove_task_from_timeline(t, 0, timeline, cfg, starts)
        assert starts[0] == 2

    def test_starts_no_underflow(self):
        """remove 后不低于 0。"""
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=5)
        starts: dict[int, int] = {}
        t = _task(1, dur=1)
        timeline: dict = {}
        remove_task_from_timeline(t, 0, timeline, cfg, starts)
        assert starts.get(0, 0) == 0

    def test_place_skip_when_limit_zero(self):
        """limit=0 时不计数。"""
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=0)
        starts: dict[int, int] = {}
        t = _task(1, dur=1)
        place_task(t, 0, {}, cfg, starts)
        assert starts == {}


# ═══════════════════════════════════════════════════════════════════
#  4. run_auto_schedule — daily_start_limit 集成
# ═══════════════════════════════════════════════════════════════════

class TestDailyStartLimit:
    def test_limit_2_spreads_5_tasks(self):
        """5 个独立任务，limit=2，应分散到 3 天（2+2+1）。"""
        tasks = [_task(i, dur=2) for i in range(1, 6)]
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False, daily_start_limit=2,
        )
        run_auto_schedule(tasks, [], cfg)
        counts = _daily_start_counts(tasks)
        assert all(c <= 2 for c in counts.values()), f"超限: {counts}"
        assert len(counts) == 3

    def test_limit_0_all_same_day(self):
        """limit=0（不限），5 个任务全在 Day 0。"""
        tasks = [_task(i, dur=2) for i in range(1, 6)]
        cfg = ScheduleConfig(start_date=_START, daily_start_limit=0)
        run_auto_schedule(tasks, [], cfg)
        assert all(t.start_day == 0 for t in tasks)

    def test_limit_1_strict_serial(self):
        """limit=1，5 个独立任务逐天启动。"""
        tasks = [_task(i, dur=1) for i in range(1, 6)]
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False, daily_start_limit=1,
        )
        run_auto_schedule(tasks, [], cfg)
        counts = _daily_start_counts(tasks)
        assert all(c == 1 for c in counts.values()), f"不是严格逐天: {counts}"
        days = sorted(t.start_day for t in tasks)
        assert days == [0, 1, 2, 3, 4]

    def test_limit_with_dependencies(self):
        """依赖链 + limit=1，依赖约束不被破坏。"""
        tasks = [
            _task(1, dur=2, dependencies="[]"),
            _task(2, dur=2, dependencies="[]"),
            _task(3, dur=1, dependencies="[1]"),
        ]
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False, daily_start_limit=1,
        )
        run_auto_schedule(tasks, [], cfg)
        # T3 必须在 T1 完成后
        assert tasks[2].start_day >= tasks[0].start_day + tasks[0].duration
        counts = _daily_start_counts(tasks)
        assert all(c <= 1 for c in counts.values()), f"超限: {counts}"


# ═══════════════════════════════════════════════════════════════════
#  5. 周末跳过
# ═══════════════════════════════════════════════════════════════════

class TestSkipWeekends:
    def test_no_task_starts_on_weekend(self):
        """skip_weekends=True 时，无任务 start_day 落在周末。"""
        tasks = [_task(i, dur=2) for i in range(1, 10)]
        cfg = ScheduleConfig(start_date=_START, skip_weekends=True, daily_start_limit=1)
        run_auto_schedule(tasks, [], cfg)
        for t in tasks:
            wd = _weekday(t.start_day)
            assert wd < 5, f"{t.name} start_day={t.start_day} 是 {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][wd]}"

    def test_weekend_skipped_in_chain(self):
        """依赖链跨越周末时，后续任务不在周六/日启动。"""
        tasks = [
            _task(1, dur=3, dependencies="[]"),  # Wed→Fri
            _task(2, dur=2, dependencies="[1]"),
        ]
        cfg = ScheduleConfig(start_date=_START, skip_weekends=True, daily_start_limit=0)
        run_auto_schedule(tasks, [], cfg)
        wd = _weekday(tasks[1].start_day)
        assert wd < 5, f"T2 在 {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][wd]} 启动"


# ═══════════════════════════════════════════════════════════════════
#  6. 节假日跳过
# ═══════════════════════════════════════════════════════════════════

class TestSkipHolidays:
    # 2026-05-25=Mon, 05-26=Tue, 05-27=Wed 做节假日
    _HOLIDAYS = {"2026-05-25", "2026-05-26", "2026-05-27"}

    def test_no_task_starts_on_holiday(self):
        tasks = [_task(i, dur=2) for i in range(1, 8)]
        cfg = ScheduleConfig(
            start_date="2026-05-22",  # Friday
            skip_weekends=True,
            skip_holidays=True,
            holidays=self._HOLIDAYS,
            daily_start_limit=1,
        )
        run_auto_schedule(tasks, [], cfg)
        start = datetime.strptime("2026-05-22", "%Y-%m-%d")
        for t in tasks:
            date_str = (start + timedelta(days=t.start_day)).strftime("%Y-%m-%d")
            assert date_str not in self._HOLIDAYS, f"{t.name} 在节假日 {date_str} 启动"

    def test_holiday_and_weekend_combined(self):
        """节假日+周末同时跳过。"""
        tasks = [_task(i, dur=1) for i in range(1, 6)]
        cfg = ScheduleConfig(
            start_date="2026-05-22",  # Friday
            skip_weekends=True,
            skip_holidays=True,
            holidays=self._HOLIDAYS,
            daily_start_limit=1,
        )
        run_auto_schedule(tasks, [], cfg)
        start = datetime.strptime("2026-05-22", "%Y-%m-%d")
        for t in tasks:
            dt = start + timedelta(days=t.start_day)
            wd = dt.weekday()
            date_str = dt.strftime("%Y-%m-%d")
            assert wd < 5, f"{t.name} 在周末"
            assert date_str not in self._HOLIDAYS, f"{t.name} 在节假日"


# ═══════════════════════════════════════════════════════════════════
#  7. compress_schedule — starts 一致性
# ═══════════════════════════════════════════════════════════════════

class TestCompressSchedule:
    def test_compress_preserves_start_limit(self):
        """compress 后每天启动数仍不超过 limit。"""
        tasks = [_task(i, dur=3) for i in range(1, 7)]
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False, daily_start_limit=2,
        )
        run_auto_schedule(tasks, [], cfg)
        counts = _daily_start_counts(tasks)
        assert all(c <= 2 for c in counts.values()), f"compress 后超限: {counts}"


# ═══════════════════════════════════════════════════════════════════
#  8. locked tasks 占名额
# ═══════════════════════════════════════════════════════════════════

class TestLockedTasks:
    def test_locked_tasks_count_against_limit(self):
        """locked tasks 占用启动名额，新任务需避让到下一天。"""
        tasks = [
            _task(1, dur=2, start_day=0, status="pending"),   # locked
            _task(2, dur=2, start_day=0, status="pending"),   # locked
            _task(3, dur=2, start_day=0, status="pending"),   # new
        ]
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False,
            lock_existing=True, daily_start_limit=2,
        )
        run_auto_schedule(tasks, [], cfg)
        # T1, T2 locked at day 0, T3 应避让到 day 1
        assert tasks[0].start_day == 0
        assert tasks[1].start_day == 0
        assert tasks[2].start_day == 1, f"T3 应在 day 1, 实际 {tasks[2].start_day}"


# ═══════════════════════════════════════════════════════════════════
#  9. find_earliest_slot 透传 starts
# ═══════════════════════════════════════════════════════════════════

class TestFindEarliestSlot:
    def test_skips_full_days(self):
        """starts 满的 day 被跳过。"""
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False, daily_start_limit=1,
        )
        starts: dict[int, int] = {0: 1, 1: 1}
        t = _task(1, dur=1)
        slot = find_earliest_slot(t, 0, {}, cfg, starts=starts)
        assert slot == 2

    def test_respects_from_day(self):
        """from_day=5 时，不会放到更早的天。"""
        cfg = ScheduleConfig(
            start_date=_START, skip_weekends=False, daily_start_limit=1,
        )
        starts: dict[int, int] = {}
        t = _task(1, dur=1)
        slot = find_earliest_slot(t, 5, {}, cfg, starts=starts)
        assert slot == 5
