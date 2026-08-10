"""排程引擎 — 适配 ReliaTrack 新模型（TestTask + Equipment）。

3-phase auto-scheduling algorithm with resource constraints:
  Phase 1 – Greedy placement respecting dependencies and equipment limits
  Phase 2 – Left-shift compression to minimise total schedule length
  Phase 3 – Report generation (utilisation, bottlenecks, suggestions)

完全重写，不依赖旧版 Task/Resource/ScheduleConfig 模型。
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta


from src.models.test_plan import TestTask
from src.models.common import Equipment

# 用于表示"无设备约束"的占位符（不为 None 方便字典 key）
_NO_EQUIPMENT: int = -1
_NO_TECHNICIAN: int = -1

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Schedule Config
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ScheduleConfig:
    """排程配置。"""
    start_date: str = ""           # 项目起始日期 "YYYY-MM-DD"
    skip_weekends: bool = True     # 跳过周末
    skip_holidays: bool = True     # 跳过法定节假日
    lock_existing: bool = False    # 锁定已有排期的任务
    deadline: str = ""             # 截止日期 "YYYY-MM-DD"（可选）
    # 设备并行数：equipment_id → 并行任务上限（默认 1）
    equipment_capacity: dict[int, int] = field(default_factory=dict)
    # 法定节假日集合 {"2025-01-01", "2025-01-28", ...}
    holidays: set[str] = field(default_factory=set)
    # 每天最多启动的新任务数，0 = 不限
    daily_start_limit: int = 0
    # 技术员并行任务上限：technician_id → 上限（默认 1）
    technician_capacity: dict[int, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
#  Helpers – weekend / calendar / holiday arithmetic
# ═══════════════════════════════════════════════════════════════════


def _is_weekend(day_number: int, start_date_str: str) -> bool:
    """Return True if *day_number* (0-indexed calendar day from *start_date_str*)
    falls on Saturday or Sunday."""
    if not start_date_str:
        return False
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    target = start + timedelta(days=day_number)
    return target.weekday() >= 5


def _is_holiday(day_number: int, start_date_str: str, holidays: set[str]) -> bool:
    """Return True if the date is a configured holiday."""
    if not start_date_str or not holidays:
        return False
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    target = start + timedelta(days=day_number)
    return target.strftime("%Y-%m-%d") in holidays


def _is_non_working(day_number: int, start_date_str: str,
                     skip_weekends: bool, skip_holidays: bool,
                     holidays: set[str]) -> bool:
    """Return True if the day is a non-working day (weekend or holiday)."""
    if skip_weekends and _is_weekend(day_number, start_date_str):
        return True
    if skip_holidays and _is_holiday(day_number, start_date_str, holidays):
        return True
    return False


def _work_day_end(
    start_day: int, duration: int,
    skip_weekends: bool, start_date_str: str,
    skip_holidays: bool = False, holidays: set[str] | None = None,
) -> int:
    """Return the calendar day index immediately *after* the task's last
    working day.  This is the earliest day a dependent task may start."""
    if start_day < 0:
        return 0
    _holidays = holidays or set()
    day = start_day
    remaining = duration
    iterations = 0
    while remaining > 0:
        iterations += 1
        if iterations > 7300:
            logger.warning(
                "_work_day_end exceeded 7300 iterations (duration=%d), "
                "task 工期截断 — 请检查任务 duration 是否异常", duration,
            )
            break
        if _is_non_working(day, start_date_str, skip_weekends, skip_holidays, _holidays):
            day += 1
            continue
        remaining -= 1
        day += 1
    return day


def _iterate_work_days(
    start_day: int, duration: int,
    skip_weekends: bool, start_date_str: str,
    skip_holidays: bool = False, holidays: set[str] | None = None,
) -> list[int]:
    """Return calendar-day indices for each working day of the task."""
    _holidays = holidays or set()
    days: list[int] = []
    day = start_day
    placed = 0
    iterations = 0
    while placed < duration:
        iterations += 1
        if iterations > 7300:
            logger.warning(
                "_iterate_work_days exceeded 7300 iterations (duration=%d), "
                "task 工期截断 — 请检查任务 duration 是否异常", duration,
            )
            break
        if _is_non_working(day, start_date_str, skip_weekends, skip_holidays, _holidays):
            day += 1
            continue
        days.append(day)
        placed += 1
        day += 1
    return days


# ═══════════════════════════════════════════════════════════════════
#  Dependency & topological sort
# ═══════════════════════════════════════════════════════════════════

def _parse_dependencies(task: TestTask) -> list[int]:
    """Parse JSON dependencies string to list of task IDs."""
    if not task.dependencies:
        return []
    try:
        deps = json.loads(task.dependencies)
        return [int(d) for d in deps if isinstance(d, (int, float, str))]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def build_dependency_map(tasks: list[TestTask]) -> dict[int, list[int]]:
    """Map task.id → list of dependency task IDs (integers)."""
    dep_map: dict[int, list[int]] = {}
    for task in tasks:
        if task.id is not None:
            dep_map[task.id] = _parse_dependencies(task)
    return dep_map


def topological_order(
    tasks: list[TestTask],
    dep_map: dict[int, list[int]],
) -> list[TestTask]:
    """Return tasks sorted topologically using Kahn's algorithm.

    Ties broken by priority (lower number first), then duration (shorter first).
    """
    tasks = [t for t in tasks if t.id is not None]
    id_to_task: dict[int, TestTask] = {t.id: t for t in tasks if t.id is not None}

    in_deg: dict[int, int] = {
        t.id: len([d for d in dep_map.get(t.id, []) if d in id_to_task])
        for t in tasks if t.id is not None
    }
    rev: dict[int, list[int]] = {t.id: [] for t in tasks if t.id is not None}
    for tid, deps in dep_map.items():
        for dep_id in deps:
            if dep_id in rev:
                rev[dep_id].append(tid)

    ready: deque[int] = deque(tid for tid, d in in_deg.items() if d == 0)
    result: list[TestTask] = []

    while ready:
        candidates = [
            (id_to_task[tid].priority, id_to_task[tid].duration, tid)
            for tid in ready
        ]
        candidates.sort()
        chosen_id = candidates[0][2]
        result.append(id_to_task[chosen_id])
        ready.remove(chosen_id)
        for dep_id in rev[chosen_id]:
            in_deg[dep_id] -= 1
            if in_deg[dep_id] == 0:
                ready.append(dep_id)

    if len(result) != len(id_to_task):
        missing = len(id_to_task) - len(result)
        result_ids = {t.id for t in result}
        cycle_ids = [t.id for t in tasks if t.id is not None and t.id not in result_ids]
        logger.warning(
            "排程检测到循环依赖：共 %d 个任务无法排入（task_id: %s）",
            missing, cycle_ids,
        )

    return result


# ═══════════════════════════════════════════════════════════════════
#  Core scheduling primitives (equipment only)
# ═══════════════════════════════════════════════════════════════════

def _get_equipment_capacity(
    eq_id: int | None,
    config: ScheduleConfig,
) -> int:
    """Get max parallel tasks for an equipment. Default 1."""
    if eq_id is None:
        return 999  # no equipment constraint
    return config.equipment_capacity.get(eq_id, 1)


def can_place_at(
    task: TestTask,
    start_day: int,
    timeline: dict[int, dict[int, int]],  # day → {eq_id: count}
    config: ScheduleConfig,
    starts: dict[int, int] | None = None,  # day → 当天已启动任务数
    tech_timeline: dict[int, dict[int, int]] | None = None,  # day → {tech_id: count}
) -> bool:
    """Check whether *task* can begin at *start_day* without exceeding
    any equipment or technician capacity on every working day."""
    # 每日启动数上限
    if config.daily_start_limit > 0 and starts is not None:
        if starts.get(start_day, 0) >= config.daily_start_limit:
            return False

    work_days = _iterate_work_days(
        start_day, task.duration, config.skip_weekends, config.start_date,
        config.skip_holidays, config.holidays,
    )
    cap = _get_equipment_capacity(task.equipment_id, config)
    tech_cap = 1  # 技术员默认每天只能做一个任务

    for day in work_days:
        day_usage = timeline.get(day, {})
        eq_id = task.equipment_id if task.equipment_id is not None else _NO_EQUIPMENT
        used = day_usage.get(eq_id, 0)
        if used + 1 > cap:
            return False
        # 技术员冲突检测
        if tech_timeline is not None and task.technician_id is not None:
            tech_cap = config.technician_capacity.get(task.technician_id, 1)
            tech_day = tech_timeline.get(day, {})
            tech_used = tech_day.get(task.technician_id, 0)
            if tech_used + 1 > tech_cap:
                return False

    return True


def find_earliest_slot(
    task: TestTask,
    from_day: int,
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
    max_scan: int = 365,
    starts: dict[int, int] | None = None,
    tech_timeline: dict[int, dict[int, int]] | None = None,
) -> int | None:
    """Scan forward from *from_day* and return first valid placement day.

    Skips non-working days (weekends/holidays when configured) so that
    ``task.start_day`` always falls on a working day.

    Returns ``None`` when no valid slot is found within ``max_scan`` days —
    callers must treat this as "cannot schedule" instead of placing the task
    on an invalid day (weekend/holiday/over-capacity), which would silently
    violate resource constraints.
    """
    for day in range(from_day, from_day + max_scan):
        if _is_non_working(day, config.start_date,
                           config.skip_weekends, config.skip_holidays,
                           config.holidays):
            continue
        if can_place_at(task, day, timeline, config, starts, tech_timeline):
            return day
    logger.warning(
        "find_earliest_slot: task=%s no valid slot within max_scan=%d days (from day %d)",
        getattr(task, 'name', task.id), max_scan, from_day,
    )
    return None


def place_task(
    task: TestTask,
    start_day: int,
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
    starts: dict[int, int] | None = None,
    tech_timeline: dict[int, dict[int, int]] | None = None,
) -> None:
    """Allocate equipment and technician resources for *task*."""
    work_days = _iterate_work_days(
        start_day, task.duration, config.skip_weekends, config.start_date,
        config.skip_holidays, config.holidays,
    )
    for day in work_days:
        if day not in timeline:
            timeline[day] = {}
        eq_id = task.equipment_id if task.equipment_id is not None else _NO_EQUIPMENT
        timeline[day][eq_id] = timeline[day].get(eq_id, 0) + 1
        # 技术员资源分配
        if tech_timeline is not None and task.technician_id is not None:
            if day not in tech_timeline:
                tech_timeline[day] = {}
            tech_timeline[day][task.technician_id] = tech_timeline[day].get(task.technician_id, 0) + 1
    # 每日启动数计数
    if starts is not None and config.daily_start_limit > 0:
        starts[start_day] = starts.get(start_day, 0) + 1


def remove_task_from_timeline(
    task: TestTask,
    start_day: int,
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
    starts: dict[int, int] | None = None,
    tech_timeline: dict[int, dict[int, int]] | None = None,
) -> None:
    """Release equipment and technician resources previously allocated."""
    work_days = _iterate_work_days(
        start_day, task.duration, config.skip_weekends, config.start_date,
        config.skip_holidays, config.holidays,
    )
    for day in work_days:
        if day not in timeline:
            continue
        eq_id = task.equipment_id if task.equipment_id is not None else _NO_EQUIPMENT
        timeline[day][eq_id] = max(0, timeline[day].get(eq_id, 0) - 1)
        if timeline[day][eq_id] <= 0:
            timeline[day].pop(eq_id, None)
        if not timeline[day]:
            del timeline[day]
        # 技术员资源释放
        if tech_timeline is not None and task.technician_id is not None and day in tech_timeline:
            tech_timeline[day][task.technician_id] = max(0, tech_timeline[day].get(task.technician_id, 0) - 1)
            if tech_timeline[day].get(task.technician_id, 0) <= 0:
                tech_timeline[day].pop(task.technician_id, None)
            if not tech_timeline[day]:
                del tech_timeline[day]
    # 每日启动数减计数
    if starts is not None and config.daily_start_limit > 0:
        starts[start_day] = max(0, starts.get(start_day, 0) - 1)


# ═══════════════════════════════════════════════════════════════════
#  Phase 2 – schedule compression (left-shift)
# ═══════════════════════════════════════════════════════════════════

def compress_schedule(
    sorted_tasks: list[TestTask],
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
    dep_map: dict[int, list[int]],
    locked_ids: set[int] | None = None,
    all_tasks: list[TestTask] | None = None,
    starts: dict[int, int] | None = None,
    tech_timeline: dict[int, dict[int, int]] | None = None,
) -> None:
    """Left-shift each non-locked, non-done task to the earliest possible
    slot, respecting dependencies and equipment constraints."""
    if locked_ids is None:
        locked_ids = set()

    id_to_task: dict[int, TestTask] = {
        t.id: t for t in (all_tasks or sorted_tasks) if t.id is not None
    }

    for task in sorted_tasks:
        if task.id is None:
            continue
        if task.status == "completed" or task.id in locked_ids:
            continue
        if task.start_day <= 0:
            continue

        # Remove from current position
        remove_task_from_timeline(
            task, task.start_day, timeline, config, starts, tech_timeline,
        )

        # Earliest allowed day from dependencies
        earliest = 0
        for dep_id in dep_map.get(task.id, []):
            dep_task = id_to_task.get(dep_id)
            if dep_task and dep_task.start_day >= 0:
                dep_end = _work_day_end(
                    dep_task.start_day, dep_task.duration,
                    config.skip_weekends, config.start_date,
                    config.skip_holidays, config.holidays,
                )
                earliest = max(earliest, dep_end)

        # Find & place at earliest valid slot
        new_start = find_earliest_slot(task, earliest, timeline, config, starts=starts, tech_timeline=tech_timeline)
        if new_start is None:
            # 找不到合法槽位：跳过（保留原 start_day），不静默放到非法日期
            continue
        task.start_day = new_start
        place_task(task, new_start, timeline, config, starts, tech_timeline=tech_timeline)


# ═══════════════════════════════════════════════════════════════════
#  Main orchestrator – 3-phase auto-schedule
# ═══════════════════════════════════════════════════════════════════

def _compute_earliest_from_deps(
    task: TestTask,
    dep_map: dict[int, list[int]],
    id_to_task: dict[int, TestTask],
    skip_weekends: bool,
    start_date_str: str,
    skip_holidays: bool = False,
    holidays: set[str] | None = None,
) -> int:
    """Determine the earliest calendar day a task may start."""
    earliest = 0
    for dep_id in dep_map.get(task.id or 0, []):
        dep_task = id_to_task.get(dep_id)
        if dep_task and dep_task.status != "completed":
            dep_end = _work_day_end(
                dep_task.start_day, dep_task.duration,
                skip_weekends, start_date_str,
                skip_holidays, holidays,
            )
            earliest = max(earliest, dep_end)
    return earliest


def run_auto_schedule(
    tasks: list[TestTask],
    equipment: list[Equipment],
    config: ScheduleConfig | None = None,
) -> dict:
    """Run the 3-phase auto-scheduling algorithm.

    Parameters
    ----------
    tasks : list[TestTask]
        All test tasks in the plan (including completed ones, which are skipped).
    equipment : list[Equipment]
        Available equipment (for capacity reference).
    config : ScheduleConfig
        Scheduling configuration. Defaults to sensible defaults.

    Returns
    -------
    dict with keys:
        ``report`` – dict containing total_days, original_days, improvement,
                     equipment_utilization, bottlenecks, suggestions
        ``timeline`` – dict[int, dict[int, int]] resource usage per calendar day
    """
    if config is None:
        config = ScheduleConfig()

    # Filter to tasks with valid IDs
    valid_tasks = [t for t in tasks if t.id is not None]

    # ── Dependency structures ───────────────────────────────────
    dep_map = build_dependency_map(valid_tasks)
    topo = topological_order(valid_tasks, dep_map)
    id_to_task: dict[int, TestTask] = {t.id: t for t in valid_tasks if t.id is not None}

    # 检测循环依赖被丢弃的任务
    topo_ids = {t.id for t in topo if t.id is not None}
    cycle_task_ids = [t.id for t in valid_tasks if t.id is not None and t.id not in topo_ids]

    # ── Identify locked tasks ───────────────────────────────────
    locked_ids: set[int] = set()
    if config.lock_existing:
        for t in valid_tasks:
            # start_day > 0 表示已排期（默认值 0 表示未排）
            if t.start_day > 0 and t.status != "completed" and t.id is not None:
                locked_ids.add(t.id)

    # ── Record original schedule length ─────────────────────────
    active = [t for t in valid_tasks if t.start_day >= 0 and t.status != "completed"]
    original_days = max(
        (_work_day_end(t.start_day, t.duration, config.skip_weekends,
                       config.start_date, config.skip_holidays, config.holidays)
         for t in active),
        default=0,
    )

    # ════════════════════════════════════════════════════════════
    # Phase 1 – Greedy placement
    # ════════════════════════════════════════════════════════════
    timeline: dict[int, dict[int, int]] = {}
    tech_timeline: dict[int, dict[int, int]] = {}
    starts: dict[int, int] = {}  # day → 当天已启动任务数

    # 1a. Place locked tasks first
    for t in valid_tasks:
        if t.id in locked_ids:
            place_task(t, t.start_day, timeline, config, starts, tech_timeline)

    # 1b. Clear start_day for non-locked, non-completed tasks
    for t in valid_tasks:
        if t.status != "completed" and t.id not in locked_ids:
            t.start_day = 0

    # 1c. Sort schedulable tasks: topo order → priority → duration
    topo_index = {t.id: idx for idx, t in enumerate(topo) if t.id is not None}
    # 排除循环依赖任务（与报告一致：cycle_task_ids 任务不排入、不占资源）
    schedulable = [
        t for t in valid_tasks
        if t.status != "completed" and t.id not in locked_ids
        and t.id not in cycle_task_ids
    ]
    # 排序策略：拓扑序 → 优先级 → 短任务优先（与 topological_order 一致）
    schedulable.sort(key=lambda t: (
        topo_index.get(t.id or 0, 999),
        t.priority,
        t.duration,  # 短任务优先，与 Kahn 算法的 tie-break 一致
    ))

    # 1d. Greedily place each task
    for task in schedulable:
        earliest = _compute_earliest_from_deps(
            task, dep_map, id_to_task,
            config.skip_weekends, config.start_date,
            config.skip_holidays, config.holidays,
        )
        slot = find_earliest_slot(task, earliest, timeline, config, starts=starts, tech_timeline=tech_timeline)
        if slot is None:
            # 找不到合法槽位：跳过该任务，不静默违反约束
            continue
        task.start_day = slot
        place_task(task, slot, timeline, config, starts, tech_timeline)

    # ════════════════════════════════════════════════════════════
    # Phase 2 – Compress (left-shift)
    # ════════════════════════════════════════════════════════════
    compress_order = sorted(
        [t for t in valid_tasks
         if t.status != "completed" and t.id not in locked_ids and t.start_day >= 0],
        key=lambda t: (t.start_day, topo_index.get(t.id or 0, 999), t.priority),
    )
    compress_schedule(
        compress_order, timeline, config, dep_map, locked_ids,
        all_tasks=valid_tasks, starts=starts, tech_timeline=tech_timeline,
    )

    # ════════════════════════════════════════════════════════════
    # Phase 3 – Report generation
    # ════════════════════════════════════════════════════════════
    active_after = [t for t in valid_tasks if t.status != "completed" and t.start_day >= 0]
    new_days = max(
        (_work_day_end(t.start_day, t.duration, config.skip_weekends,
                       config.start_date, config.skip_holidays, config.holidays)
         for t in active_after),
        default=0,
    )

    improvement: float = 0.0
    if original_days > 0 and new_days > 0:
        improvement = round((1.0 - new_days / original_days) * 100, 1)

    # ── Equipment utilisation ───────────────────────────────────
    all_days = sorted(timeline.keys()) if timeline else []
    eq_map: dict[int, Equipment] = {
        e.id: e for e in equipment if e.id is not None
    }
    equipment_utilization: list[dict] = []

    for eq_id in set(
        eq_id for day_usage in timeline.values() for eq_id in day_usage
    ):
        if eq_id == _NO_EQUIPMENT:
            continue  # skip "no equipment" placeholder
        cap = config.equipment_capacity.get(eq_id, 1)
        total_avail = cap * len(all_days) if all_days else 1
        total_used = sum(
            day_usage.get(eq_id, 0) for day_usage in timeline.values()
        )
        util = round(total_used / total_avail * 100, 1) if total_avail > 0 else 0.0
        eq = eq_map.get(eq_id)
        equipment_utilization.append({
            "equipment_id": eq_id,
            "name": eq.name if eq else f"设备#{eq_id}",
            "utilization": util,
        })

    # ── Technician utilisation ─────────────────────────────────
    tech_utilization: list[dict] = []
    for tech_id in set(
        tid for day_usage in tech_timeline.values() for tid in day_usage
    ):
        tech_cap = config.technician_capacity.get(tech_id, 1)
        total_avail = tech_cap * len(all_days) if all_days else 1
        total_used = sum(
            day_usage.get(tech_id, 0) for day_usage in tech_timeline.values()
        )
        util = round(total_used / total_avail * 100, 1) if total_avail > 0 else 0.0
        tech_utilization.append({
            "technician_id": tech_id,
            "utilization": util,
        })

    # ── Bottlenecks (>80 % utilisation) ────────────────────────
    bottlenecks = [u for u in equipment_utilization if u["utilization"] > 80]
    tech_bottlenecks = [u for u in tech_utilization if u["utilization"] > 80]

    # ── Suggestions ─────────────────────────────────────────────
    suggestions: list[str] = []

    if cycle_task_ids:
        suggestions.append(
            f"注意: {len(cycle_task_ids)} 个任务因循环依赖被跳过（ID: {cycle_task_ids[:5]}）"
        )

    for b in bottlenecks:
        suggestions.append(
            f"注意: {b['name']} 利用率 {b['utilization']}%，建议增加设备以缓解瓶颈"
        )

    for tb in tech_bottlenecks:
        suggestions.append(
            f"注意: 技术员#{tb['technician_id']} 利用率 {tb['utilization']}%，存在任务冲突风险"
        )

    if config.deadline and config.start_date and new_days > 0:
        try:
            end_date = (
                datetime.strptime(config.start_date, "%Y-%m-%d")
                + timedelta(days=new_days)
            ).strftime("%Y-%m-%d")
            deadline_dt = datetime.strptime(config.deadline, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if end_dt > deadline_dt:
                suggestions.append(
                    f"注意: 排期结束日 {end_date} 超出截止日期 {config.deadline}，"
                    f"请调整优先级或增加资源"
                )
        except ValueError:
            logger.debug("排程截止日期解析失败", exc_info=True)

    if improvement > 20:
        suggestions.append(f"已完成: 自动排期相比原始方案优化了 {improvement}% 的工期")
    elif improvement < 0:
        suggestions.append(
            "提示: 当前排期因资源冲突被延长，建议检查可并行的任务并增加资源"
        )

    # ── Daily start limit utilization ──────────────────────────
    if config.daily_start_limit > 0 and starts:
        capped_days = [d for d, c in starts.items() if c >= config.daily_start_limit]
        if capped_days:
            suggestions.append(
                f"每日启动上限 {config.daily_start_limit}："
                f"共 {len(capped_days)} 天达到上限"
            )

    return {
        "report": {
            "total_days": new_days,
            "original_days": original_days,
            "improvement": improvement,
            "equipment_utilization": equipment_utilization,
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
            "skipped_cycle_tasks": cycle_task_ids,
            "technician_utilization": tech_utilization,
        },
        "timeline": timeline,
        "tech_timeline": tech_timeline,
    }
