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
from typing import Optional

from src.models.test_plan import TestTask
from src.models.common import Equipment

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Schedule Config
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ScheduleConfig:
    """排程配置。"""
    start_date: str = ""           # 项目起始日期 "YYYY-MM-DD"
    skip_weekends: bool = True     # 跳过周末
    lock_existing: bool = False    # 锁定已有排期的任务
    deadline: str = ""             # 截止日期 "YYYY-MM-DD"（可选）
    # 设备并行数：equipment_id → 并行任务上限（默认 1）
    equipment_capacity: dict[int, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
#  Helpers – weekend / calendar arithmetic
# ═══════════════════════════════════════════════════════════════════

def _is_weekend(day_number: int, start_date_str: str) -> bool:
    """Return True if *day_number* (0-indexed calendar day from *start_date_str*)
    falls on Saturday or Sunday."""
    if not start_date_str:
        return False
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    target = start + timedelta(days=day_number)
    return target.weekday() >= 5


def _work_day_end(
    start_day: int, duration: int,
    skip_weekends: bool, start_date_str: str,
) -> int:
    """Return the calendar day index immediately *after* the task's last
    working day.  This is the earliest day a dependent task may start."""
    if start_day < 0:
        return 0
    day = start_day
    remaining = duration
    while remaining > 0:
        if skip_weekends and start_date_str and _is_weekend(day, start_date_str):
            day += 1
            continue
        remaining -= 1
        day += 1
    return day


def _iterate_work_days(
    start_day: int, duration: int,
    skip_weekends: bool, start_date_str: str,
) -> list[int]:
    """Return calendar-day indices for each working day of the task."""
    days: list[int] = []
    day = start_day
    placed = 0
    while placed < duration:
        if skip_weekends and start_date_str and _is_weekend(day, start_date_str):
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
        dep_map[task.id] = _parse_dependencies(task)
    return dep_map


def topological_order(
    tasks: list[TestTask],
    dep_map: dict[int, list[int]],
) -> list[TestTask]:
    """Return tasks sorted topologically using Kahn's algorithm.

    Ties broken by priority (lower number first), then duration (shorter first).
    """
    id_to_task: dict[int, TestTask] = {t.id: t for t in tasks if t.id is not None}

    in_deg: dict[int, int] = {t.id: len(dep_map.get(t.id, [])) for t in tasks if t.id is not None}
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
) -> bool:
    """Check whether *task* can begin at *start_day* without exceeding
    any equipment capacity on every working day."""
    work_days = _iterate_work_days(
        start_day, task.duration, config.skip_weekends, config.start_date,
    )
    cap = _get_equipment_capacity(task.equipment_id, config)

    for day in work_days:
        day_usage = timeline.get(day, {})
        eq_id = task.equipment_id if task.equipment_id is not None else -1
        used = day_usage.get(eq_id, 0)
        if used + 1 > cap:
            return False

    return True


def find_earliest_slot(
    task: TestTask,
    from_day: int,
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
    max_scan: int = 365,
) -> int:
    """Scan forward from *from_day* and return first valid placement day."""
    for day in range(from_day, from_day + max_scan):
        if can_place_at(task, day, timeline, config):
            return day
    return from_day + max_scan


def place_task(
    task: TestTask,
    start_day: int,
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
) -> None:
    """Allocate equipment resource in *timeline* for *task*."""
    work_days = _iterate_work_days(
        start_day, task.duration, config.skip_weekends, config.start_date,
    )
    for day in work_days:
        if day not in timeline:
            timeline[day] = {}
        eq_id = task.equipment_id if task.equipment_id is not None else -1
        timeline[day][eq_id] = timeline[day].get(eq_id, 0) + 1


def remove_task_from_timeline(
    task: TestTask,
    start_day: int,
    timeline: dict[int, dict[int, int]],
    config: ScheduleConfig,
) -> None:
    """Release equipment resource previously allocated."""
    work_days = _iterate_work_days(
        start_day, task.duration, config.skip_weekends, config.start_date,
    )
    for day in work_days:
        if day not in timeline:
            continue
        eq_id = task.equipment_id if task.equipment_id is not None else -1
        timeline[day][eq_id] = max(0, timeline[day].get(eq_id, 0) - 1)
        if timeline[day][eq_id] <= 0:
            timeline[day].pop(eq_id, None)
        if not timeline[day]:
            del timeline[day]


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
            task, task.start_day, timeline, config,
        )

        # Earliest allowed day from dependencies
        earliest = 0
        for dep_id in dep_map.get(task.id, []):
            dep_task = id_to_task.get(dep_id)
            if dep_task and dep_task.status != "completed" and dep_task.start_day >= 0:
                dep_end = _work_day_end(
                    dep_task.start_day, dep_task.duration,
                    config.skip_weekends, config.start_date,
                )
                earliest = max(earliest, dep_end)

        # Find & place at earliest valid slot
        new_start = find_earliest_slot(task, earliest, timeline, config)
        task.start_day = new_start
        place_task(task, new_start, timeline, config)


# ═══════════════════════════════════════════════════════════════════
#  Main orchestrator – 3-phase auto-schedule
# ═══════════════════════════════════════════════════════════════════

def _compute_earliest_from_deps(
    task: TestTask,
    dep_map: dict[int, list[int]],
    id_to_task: dict[int, TestTask],
    skip_weekends: bool,
    start_date_str: str,
) -> int:
    """Determine the earliest calendar day a task may start."""
    earliest = 0
    for dep_id in dep_map.get(task.id or 0, []):
        dep_task = id_to_task.get(dep_id)
        if dep_task and dep_task.status != "completed":
            dep_end = _work_day_end(
                dep_task.start_day, dep_task.duration,
                skip_weekends, start_date_str,
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
    id_to_task: dict[int, TestTask] = {t.id: t for t in valid_tasks}

    # ── Identify locked tasks ───────────────────────────────────
    locked_ids: set[int] = set()
    if config.lock_existing:
        for t in valid_tasks:
            if t.start_day > 0 and t.status != "completed":
                locked_ids.add(t.id)

    # ── Record original schedule length ─────────────────────────
    active = [t for t in valid_tasks if t.start_day > 0 and t.status != "completed"]
    original_days = max(
        (t.start_day + t.duration for t in active),
        default=0,
    )

    # ════════════════════════════════════════════════════════════
    # Phase 1 – Greedy placement
    # ════════════════════════════════════════════════════════════
    timeline: dict[int, dict[int, int]] = {}

    # 1a. Place locked tasks first
    for t in valid_tasks:
        if t.id in locked_ids:
            place_task(t, t.start_day, timeline, config)

    # 1b. Clear start_day for non-locked, non-completed tasks
    for t in valid_tasks:
        if t.status != "completed" and t.id not in locked_ids:
            t.start_day = 0

    # 1c. Sort schedulable tasks: topo order → priority → duration
    topo_index = {t.id: idx for idx, t in enumerate(topo) if t.id is not None}
    schedulable = [
        t for t in valid_tasks
        if t.status != "completed" and t.id not in locked_ids
    ]
    schedulable.sort(key=lambda t: (
        topo_index.get(t.id or 0, 999),
        t.priority,
        -t.duration,
    ))

    # 1d. Greedily place each task
    for task in schedulable:
        earliest = _compute_earliest_from_deps(
            task, dep_map, id_to_task,
            config.skip_weekends, config.start_date,
        )
        slot = find_earliest_slot(task, earliest, timeline, config)
        task.start_day = slot
        place_task(task, slot, timeline, config)

    # ════════════════════════════════════════════════════════════
    # Phase 2 – Compress (left-shift)
    # ════════════════════════════════════════════════════════════
    compress_order = sorted(
        [t for t in valid_tasks
         if t.status != "completed" and t.id not in locked_ids and t.start_day > 0],
        key=lambda t: t.start_day,
    )
    compress_schedule(
        compress_order, timeline, config, dep_map, locked_ids,
        all_tasks=valid_tasks,
    )

    # ════════════════════════════════════════════════════════════
    # Phase 3 – Report generation
    # ════════════════════════════════════════════════════════════
    active_after = [t for t in valid_tasks if t.status != "completed" and t.start_day > 0]
    new_days = max(
        (t.start_day + t.duration for t in active_after),
        default=0,
    ) if active_after else 0

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
        if eq_id == -1:
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

    # ── Bottlenecks (>80 % utilisation) ────────────────────────
    bottlenecks = [u for u in equipment_utilization if u["utilization"] > 80]

    # ── Suggestions ─────────────────────────────────────────────
    suggestions: list[str] = []

    for b in bottlenecks:
        suggestions.append(
            f"⚠️ {b['name']} 利用率 {b['utilization']}%，建议增加设备以缓解瓶颈"
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
                    f"⚠️ 排期结束日 {end_date} 超出截止日期 {config.deadline}，"
                    f"请调整优先级或增加资源"
                )
        except ValueError:
            logger.debug("排程截止日期解析失败", exc_info=True)

    if improvement > 20:
        suggestions.append(f"✅ 自动排期相比原始方案优化了 {improvement}% 的工期")
    elif improvement < 0:
        suggestions.append(
            "💡 当前排期因资源冲突被延长，建议检查可并行的任务并增加资源"
        )

    return {
        "report": {
            "total_days": new_days,
            "original_days": original_days,
            "improvement": improvement,
            "equipment_utilization": equipment_utilization,
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
        },
        "timeline": timeline,
    }
