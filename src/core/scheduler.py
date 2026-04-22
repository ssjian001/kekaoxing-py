"""Scheduling engine for reliability test tasks.

3-phase auto-scheduling algorithm with resource constraints:
  Phase 1 – Greedy placement respecting dependencies, serial chains, and resource limits
  Phase 2 – Left-shift compression to minimise total schedule length
  Phase 3 – Report generation (utilisation, bottlenecks, suggestions)

Uses only Python stdlib.  All type hints; well-commented.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from src.models import (
    Task,
    Resource,
    ResourceType,
    ScheduleConfig,
    ScheduleMode,
    EquipmentRequirement,
)


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
    return target.weekday() >= 5  # Sat=5, Sun=6


def _work_day_end(task: Task, skip_weekends: bool, start_date_str: str) -> int:
    """Return the calendar day index immediately *after* the task's last
    working day.  This is the earliest day a dependent task may start."""
    if task.start_day < 0:
        return 0
    day = task.start_day
    remaining = task.duration
    while remaining > 0:
        if skip_weekends and start_date_str and _is_weekend(day, start_date_str):
            day += 1
            continue
        remaining -= 1
        day += 1
    return day


# ═══════════════════════════════════════════════════════════════════
#  Resource-map construction
# ═══════════════════════════════════════════════════════════════════

def _build_resource_maps(
    resources: list[Resource],
    config: ScheduleConfig,
) -> tuple[dict[int, Resource], dict[str, Resource]]:
    """Build lookup dicts for equipment and sample pools, applying config
    overrides for ``equipment_config`` and ``sample_pool_config``.

    Returns
    -------
    resource_map : dict[int, Resource]
        Equipment keyed by resource id.
    sample_pool_map : dict[str, Resource]
        Sample pools keyed by pool name.
    """
    resource_map: dict[int, Resource] = {}
    sample_pool_map: dict[str, Resource] = {}

    for r in resources:
        if r.type == ResourceType.EQUIPMENT:
            qty = config.equipment_config.get(r.id, r.available_qty)
            resource_map[r.id] = Resource(
                id=r.id, name=r.name, type=r.type, category=r.category,
                unit=r.unit, available_qty=qty, icon=r.icon,
                description=r.description,
                unavailable_periods=list(r.unavailable_periods),
            )
        elif r.type == ResourceType.SAMPLE_POOL:
            qty = config.sample_pool_config.get(r.name, r.available_qty)
            sample_pool_map[r.name] = Resource(
                id=r.id, name=r.name, type=r.type, category=r.category,
                unit=r.unit, available_qty=qty, icon=r.icon,
                description=r.description,
                unavailable_periods=list(r.unavailable_periods),
            )

    return resource_map, sample_pool_map


def _effective_capacity(
    resource_key: str,
    day: int,
    resource_map: dict[int, Resource],
    sample_pool_map: dict[str, Resource],
) -> int:
    """Return the available quantity of a resource on *day*, accounting
    for any ``unavailable_periods``."""
    if resource_key.startswith("pool_"):
        pool_id = int(resource_key[len("pool_"):])
        for pool in sample_pool_map.values():
            if pool.id == pool_id:
                for p in pool.unavailable_periods:
                    if p.start_day <= day <= p.end_day:
                        return 0
                return pool.available_qty
        return 0

    if resource_key.startswith("eq_"):
        eq_id = int(resource_key[len("eq_"):])
        res = resource_map.get(eq_id)
        if res is None:
            return 0
        for p in res.unavailable_periods:
            if p.start_day <= day <= p.end_day:
                return 0
        return res.available_qty

    return 0


# ═══════════════════════════════════════════════════════════════════
#  Dependency & chain helpers
# ═══════════════════════════════════════════════════════════════════

def build_dependency_map(tasks: list[Task]) -> dict[int, list[int]]:
    """Map ``task.id`` → list of dependency *task ids*.

    Tasks reference dependencies by their ``num`` string (e.g. ``"2.6"``);
    this function resolves those to integer ids.
    """
    num_to_id: dict[str, int] = {t.num: t.id for t in tasks}
    dep_map: dict[int, list[int]] = {}
    for task in tasks:
        dep_map[task.id] = [
            num_to_id[d] for d in task.dependencies if d in num_to_id
        ]
    return dep_map


def build_serial_chains(tasks: list[Task]) -> dict[str, list[Task]]:
    """Group serial tasks by ``serial_group``, topologically sorted within
    each chain so that dependency order is respected.

    Returns
    -------
    dict mapping serial_group key → ordered list of Task.
    """
    num_to_id: dict[str, int] = {t.num: t.id for t in tasks}
    chains: dict[str, list[Task]] = {}

    for task in tasks:
        if task.is_serial and task.serial_group:
            chains.setdefault(task.serial_group, []).append(task)

    # Topological sort within each chain (Kahn's algorithm)
    for group_key, chain_tasks in chains.items():
        id_set = {t.id for t in chain_tasks}
        id_to_task = {t.id: t for t in chain_tasks}

        local_deps: dict[int, list[int]] = {}
        for t in chain_tasks:
            local_deps[t.id] = [
                num_to_id[d]
                for d in t.dependencies
                if d in num_to_id and num_to_id[d] in id_set
            ]

        in_deg: dict[int, int] = {t.id: len(local_deps[t.id]) for t in chain_tasks}
        queue: deque[int] = deque(tid for tid, d in in_deg.items() if d == 0)
        ordered: list[Task] = []

        while queue:
            tid = queue.popleft()
            ordered.append(id_to_task[tid])
            for t in chain_tasks:
                if tid in local_deps[t.id]:
                    in_deg[t.id] -= 1
                    if in_deg[t.id] == 0:
                        queue.append(t.id)

        chains[group_key] = ordered

    return chains


def topological_order(
    tasks: list[Task],
    dep_map: dict[int, list[int]],
) -> list[Task]:
    """Return tasks sorted topologically using Kahn's algorithm.

    When several tasks have zero in-degree simultaneously they are ordered by
    priority (lower number first), then duration (shorter first for stability).
    """
    id_to_task: dict[int, Task] = {t.id: t for t in tasks}

    in_deg: dict[int, int] = {t.id: len(dep_map.get(t.id, [])) for t in tasks}
    rev: dict[int, list[int]] = {t.id: [] for t in tasks}
    for tid, deps in dep_map.items():
        for dep_id in deps:
            if dep_id in rev:
                rev[dep_id].append(tid)

    ready: deque[int] = deque(tid for tid, d in in_deg.items() if d == 0)
    result: list[Task] = []

    while ready:
        # Pick best candidate: lower priority number, then shorter duration
        candidates = [(id_to_task[tid].priority, id_to_task[tid].duration, tid)
                      for tid in ready]
        candidates.sort()
        chosen_id = candidates[0][2]
        result.append(id_to_task[chosen_id])
        ready.remove(chosen_id)
        for dep_id in rev[chosen_id]:
            in_deg[dep_id] -= 1
            if in_deg[dep_id] == 0:
                ready.append(dep_id)

    if len(result) != len(tasks):
        missing = len(tasks) - len(result)
        # 找出被遗漏的任务（循环依赖中的节点）
        result_ids = {t.id for t in result}
        cycle_ids = [t.id for t in tasks if t.id not in result_ids]
        import logging
        logging.warning(
            "排程检测到循环依赖：共 %d 个任务无法排入（涉及的 task_id: %s）",
            missing, cycle_ids,
        )

    return result


# ═══════════════════════════════════════════════════════════════════
#  Core scheduling primitives
# ═══════════════════════════════════════════════════════════════════

def _iterate_work_days(
    start_day: int,
    duration: int,
    skip_weekends: bool,
    start_date_str: str,
) -> list[int]:
    """Return the list of calendar-day indices on which a task with the given
    *duration* (in work-days) would be active, starting at *start_day*."""
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


def can_place_at(
    task: Task,
    start_day: int,
    timeline: dict[int, dict[str, int]],
    resource_map: dict[int, Resource],
    sample_pool_map: dict[str, Resource],
    skip_weekends: bool,
    start_date_str: str,
) -> bool:
    """Check whether *task* can begin at *start_day* without exceeding any
    resource capacity on every working day of its duration."""
    work_days = _iterate_work_days(
        start_day, task.duration, skip_weekends, start_date_str,
    )

    for day in work_days:
        day_usage = timeline.get(day, {})

        # Sample pool check
        if task.sample_pool and task.sample_pool in sample_pool_map:
            pool = sample_pool_map[task.sample_pool]
            key = f"pool_{pool.id}"
            used = day_usage.get(key, 0)
            cap = _effective_capacity(key, day, resource_map, sample_pool_map)
            if used + task.sample_qty > cap:
                return False

        # Equipment checks
        for req in task.requirements:
            key = f"eq_{req.resource_id}"
            used = day_usage.get(key, 0)
            cap = _effective_capacity(key, day, resource_map, sample_pool_map)
            if used + req.quantity > cap:
                return False

    return True


def find_earliest_slot(
    task: Task,
    from_day: int,
    timeline: dict[int, dict[str, int]],
    resource_map: dict[int, Resource],
    sample_pool_map: dict[str, Resource],
    skip_weekends: bool,
    start_date_str: str,
    max_scan: int = 200,
) -> int:
    """Scan forward from *from_day* (up to *max_scan* calendar days) and
    return the first day where *task* can be placed.

    Falls back to ``from_day + max_scan`` if no valid slot is found.
    """
    for day in range(from_day, from_day + max_scan):
        if can_place_at(
            task, day, timeline, resource_map, sample_pool_map,
            skip_weekends, start_date_str,
        ):
            return day
    return from_day + max_scan


def place_task(
    task: Task,
    start_day: int,
    timeline: dict[int, dict[str, int]],
    resource_map: dict[int, Resource],
    sample_pool_map: dict[str, Resource],
    skip_weekends: bool,
    start_date_str: str,
) -> None:
    """Allocate resources in *timeline* for *task* starting at *start_day*.

    Mutates *timeline* in place.
    """
    work_days = _iterate_work_days(
        start_day, task.duration, skip_weekends, start_date_str,
    )

    for day in work_days:
        if day not in timeline:
            timeline[day] = {}

        # Consume sample pool
        if task.sample_pool and task.sample_pool in sample_pool_map:
            pool = sample_pool_map[task.sample_pool]
            key = f"pool_{pool.id}"
            timeline[day][key] = timeline[day].get(key, 0) + task.sample_qty

        # Consume equipment
        for req in task.requirements:
            key = f"eq_{req.resource_id}"
            timeline[day][key] = timeline[day].get(key, 0) + req.quantity


def remove_task_from_timeline(
    task: Task,
    start_day: int,
    timeline: dict[int, dict[str, int]],
    resource_map: dict[int, Resource],
    sample_pool_map: dict[str, Resource],
    skip_weekends: bool,
    start_date_str: str,
) -> None:
    """Release resources previously allocated by ``place_task``.

    Mutates *timeline* in place.
    """
    work_days = _iterate_work_days(
        start_day, task.duration, skip_weekends, start_date_str,
    )

    for day in work_days:
        if day not in timeline:
            continue

        # Release sample pool
        if task.sample_pool and task.sample_pool in sample_pool_map:
            pool = sample_pool_map[task.sample_pool]
            key = f"pool_{pool.id}"
            timeline[day][key] = max(0, timeline[day].get(key, 0) - task.sample_qty)
            if timeline[day][key] == 0:
                timeline[day].pop(key, None)

        # Release equipment
        for req in task.requirements:
            key = f"eq_{req.resource_id}"
            timeline[day][key] = max(0, timeline[day].get(key, 0) - req.quantity)
            if timeline[day][key] == 0:
                timeline[day].pop(key, None)

        # Clean up empty day entries
        if not timeline[day]:
            del timeline[day]


# ═══════════════════════════════════════════════════════════════════
#  Phase 2 – schedule compression (left-shift)
# ═══════════════════════════════════════════════════════════════════

def compress_schedule(
    sorted_tasks: list[Task],
    timeline: dict[int, dict[str, int]],
    resource_map: dict[int, Resource],
    sample_pool_map: dict[str, Resource],
    skip_weekends: bool,
    start_date_str: str,
    dep_map: dict[int, list[int]],
    locked_ids: Optional[set[int]] = None,
    all_tasks: Optional[list[Task]] = None,
) -> None:
    """Left-shift each non-locked, non-done task to the earliest possible
    slot, respecting dependencies and resource constraints.

    *sorted_tasks* should be ordered so that dependencies appear before
    dependents (e.g. topological or start-day order).

    Mutates tasks' ``start_day`` and *timeline* in place.
    """
    if locked_ids is None:
        locked_ids = set()

    id_to_task: dict[int, Task] = {t.id: t for t in (all_tasks or sorted_tasks)}

    for task in sorted_tasks:
        # Skip done tasks and locked (pre-existing) tasks
        if task.done or task.id in locked_ids:
            continue
        if task.start_day <= 0:
            # Task was never placed – nothing to compress
            continue

        # ── Remove from current position ────────────────────────
        remove_task_from_timeline(
            task, task.start_day, timeline,
            resource_map, sample_pool_map, skip_weekends, start_date_str,
        )

        # ── Earliest allowed day from dependencies ──────────────
        earliest = 0
        for dep_id in dep_map.get(task.id, []):
            dep_task = id_to_task.get(dep_id)
            if dep_task and not dep_task.done and dep_task.start_day >= 0:
                dep_end = _work_day_end(dep_task, skip_weekends, start_date_str)
                earliest = max(earliest, dep_end)

        # ── Find & place at earliest valid slot ─────────────────
        new_start = find_earliest_slot(
            task, earliest, timeline, resource_map, sample_pool_map,
            skip_weekends, start_date_str,
        )
        task.start_day = new_start
        place_task(
            task, new_start, timeline,
            resource_map, sample_pool_map, skip_weekends, start_date_str,
        )


# ═══════════════════════════════════════════════════════════════════
#  Main orchestrator – 3-phase auto-schedule
# ═══════════════════════════════════════════════════════════════════

def _compute_earliest_from_deps(
    task: Task,
    dep_map: dict[int, list[int]],
    id_to_task: dict[int, Task],
    chains: dict[str, list[Task]],
    skip_weekends: bool,
    start_date_str: str,
) -> int:
    """Determine the earliest calendar day a task may start, considering
    both explicit dependencies and serial-chain predecessor constraints."""
    earliest = 0

    # Explicit dependencies
    for dep_id in dep_map.get(task.id, []):
        dep_task = id_to_task.get(dep_id)
        if dep_task and not dep_task.done:
            dep_end = _work_day_end(dep_task, skip_weekends, start_date_str)
            earliest = max(earliest, dep_end)

    # Serial-chain predecessor
    if task.is_serial and task.serial_group and task.serial_group in chains:
        chain = chains[task.serial_group]
        for idx, ct in enumerate(chain):
            if ct.id == task.id and idx > 0:
                pred = chain[idx - 1]
                if not pred.done:
                    earliest = max(
                        earliest,
                        _work_day_end(pred, skip_weekends, start_date_str),
                    )
                break

    return earliest


def run_auto_schedule(
    tasks: list[Task],
    resources: list[Resource],
    config: ScheduleConfig,
) -> dict:
    """Run the 3-phase auto-scheduling algorithm.

    Parameters
    ----------
    tasks : list[Task]
        All reliability test tasks (including done ones, which are skipped).
    resources : list[Resource]
        Available resources (sample pools + equipment).
    config : ScheduleConfig
        Scheduling configuration (mode, skip_weekends, lock_existing, …).

    Returns
    -------
    dict with keys:
        ``scheduled_tasks`` – list[Task] with updated ``start_day`` values
        ``report`` – dict containing total_days, original_days, improvement,
                     device_utilization, bottlenecks, suggestions
        ``timeline`` – dict[int, dict[str, int]] resource usage per calendar day
    """
    # ── Resource maps ───────────────────────────────────────────
    resource_map, sample_pool_map = _build_resource_maps(resources, config)

    # ── Dependency & chain structures ───────────────────────────
    dep_map = build_dependency_map(tasks)
    chains = build_serial_chains(tasks)
    topo = topological_order(tasks, dep_map)
    id_to_task: dict[int, Task] = {t.id: t for t in tasks}

    # ── Identify locked tasks ───────────────────────────────────
    locked_ids: set[int] = set()
    if config.lock_existing:
        for t in tasks:
            if t.start_day > 0 and not t.done:
                locked_ids.add(t.id)

    # ── Record original schedule length ─────────────────────────
    original_days = max(
        (t.start_day + t.duration for t in tasks if t.start_day > 0),
        default=0,
    )

    # ── Chain metadata for sorting ──────────────────────────────
    # (chain_index, position_in_chain, chain_length) per task id
    chain_info: dict[int, tuple[int, int, int]] = {}
    for chain_idx, (group_key, chain_tasks) in enumerate(chains.items()):
        for pos, ct in enumerate(chain_tasks):
            chain_info[ct.id] = (chain_idx, pos, len(chain_tasks))

    # ════════════════════════════════════════════════════════════
    # Phase 1 – Greedy placement
    # ════════════════════════════════════════════════════════════
    timeline: dict[int, dict[str, int]] = {}

    # 1a. Place locked tasks first so their resources are reserved
    for t in tasks:
        if t.id in locked_ids:
            place_task(
                t, t.start_day, timeline,
                resource_map, sample_pool_map,
                config.skip_weekends, config.start_date,
            )

    # 1b. Clear start_day for non-locked, non-done tasks
    for t in tasks:
        if not t.done and t.id not in locked_ids:
            t.start_day = 0

    # 1c. Sort schedulable tasks by:
    #     higher priority first (lower number) →
    #     longer chain first →
    #     earlier chain index →
    #     longer duration
    schedulable = [t for t in tasks if not t.done and t.id not in locked_ids]
    # Build topo index for sort priority
    topo_index = {t.id: idx for idx, t in enumerate(topo)}

    schedulable.sort(key=lambda t: (
        topo_index.get(t.id, 999),                          # topo order first (deps respected)
        t.priority,
        -(chain_info[t.id][2] if t.id in chain_info else 0),  # longer chain first
        chain_info[t.id][1] if t.id in chain_info else 999,    # earlier chain position first
        -t.duration,                                             # longer duration first
    ))

    # 1d. Greedily place each task
    for task in schedulable:
        earliest = _compute_earliest_from_deps(
            task, dep_map, id_to_task, chains,
            config.skip_weekends, config.start_date,
        )
        slot = find_earliest_slot(
            task, earliest, timeline, resource_map, sample_pool_map,
            config.skip_weekends, config.start_date,
        )
        task.start_day = slot
        place_task(
            task, slot, timeline, resource_map, sample_pool_map,
            config.skip_weekends, config.start_date,
        )

    # ════════════════════════════════════════════════════════════
    # Phase 2 – Compress (left-shift)
    # ════════════════════════════════════════════════════════════
    compress_order = sorted(
        [t for t in tasks if not t.done and t.id not in locked_ids and t.start_day > 0],
        key=lambda t: t.start_day,
    )
    compress_schedule(
        compress_order, timeline, resource_map, sample_pool_map,
        config.skip_weekends, config.start_date, dep_map, locked_ids,
        all_tasks=tasks,
    )

    # ════════════════════════════════════════════════════════════
    # Phase 3 – Report generation
    # ════════════════════════════════════════════════════════════
    active = [t for t in tasks if not t.done and t.start_day > 0]
    new_days = max(
        (t.start_day + t.duration for t in active),
        default=0,
    ) if active else 0

    improvement: float = 0.0
    if original_days > 0 and new_days > 0:
        improvement = round((1.0 - new_days / original_days) * 100, 1)

    # ── Device / pool utilisation ───────────────────────────────
    all_days = sorted(timeline.keys()) if timeline else []
    device_utilization: list[dict] = []

    for r in resources:
        key: str
        if r.type == ResourceType.EQUIPMENT:
            key = f"eq_{r.id}"
        elif r.type == ResourceType.SAMPLE_POOL:
            key = f"pool_{r.id}"
        else:
            continue

        total_avail = 0
        total_used = 0
        for day in all_days:
            total_avail += r.available_qty
            total_used += timeline.get(day, {}).get(key, 0)

        util = round(total_used / total_avail * 100, 1) if total_avail > 0 else 0.0
        device_utilization.append({
            "resource_id": r.id,
            "name": r.name,
            "type": r.type.value,
            "utilization": util,
        })

    # ── Bottlenecks (>80 % utilisation) ────────────────────────
    bottlenecks = [u for u in device_utilization if u["utilization"] > 80]

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
            import logging
            logging.debug("排程截止日期解析失败: deadline=%s, start_date=%s", config.deadline, config.start_date, exc_info=True)

    if improvement > 20:
        suggestions.append(f"✅ 自动排期相比原始方案优化了 {improvement}% 的工期")
    elif improvement < 0:
        suggestions.append(
            "💡 当前排期因资源冲突被延长，建议检查可并行的任务并增加资源"
        )

    return {
        "scheduled_tasks": tasks,
        "report": {
            "total_days": new_days,
            "original_days": original_days,
            "improvement": improvement,
            "device_utilization": device_utilization,
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
        },
        "timeline": timeline,
    }
