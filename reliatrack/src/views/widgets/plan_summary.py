from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from src.models.test_plan import TestTask
import src.styles.theme as _t


def compute_summary(
    tasks: list[TestTask],
    result_map: dict[int, tuple[int, int]],
    start_date: str,
) -> tuple[int, int, int]:
    """计算摘要指标: (到期数, 待录入数, 超期数)。

    到期: 预计结束日期 <= 今天且未完成。
    待录入: 有样品但结果数不足。
    超期: 预计结束日期 < 今天且未完成。
    """
    import json as _json

    if not start_date:
        return 0, 0, 0

    try:
        base = date.fromisoformat(start_date)
    except ValueError:
        return 0, 0, 0

    today = date.today()
    due_count = 0
    overdue_count = 0
    pending_result_count = 0

    for task in tasks:
        if task.status in ("completed", "skipped"):
            continue
        end_day = (task.start_day or 0) + task.duration
        end_date = base + timedelta(days=end_day)

        # 超期
        if end_date < today:
            overdue_count += 1
        # 到期（含超期和今天到期）
        elif end_date == today:
            due_count += 1

        # 待录入: sample_ids 有内容但结果数不足
        if task.id is not None:
            try:
                sids = _json.loads(task.sample_ids) if task.sample_ids else []
            except (ValueError, TypeError):
                sids = []
            if sids:
                pass_cnt, total_cnt = result_map.get(task.id, (0, 0))
                if total_cnt < len(sids):
                    pending_result_count += 1

    return due_count, pending_result_count, overdue_count


def format_summary_text(
    tasks: list[TestTask],
    start_date: str,
    existing_summary: str = "",
) -> str:
    """生成摘要栏文本（统计 + 任务状态）。"""
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    pending = total - completed

    today = date.today()
    overdue = 0
    for t in tasks:
        if t.status in ("completed", "done", "skipped", "failed"):
            continue
        if t.start_day is not None:
            plan_start = None
            if start_date:
                try:
                    plan_start = date.fromisoformat(start_date)
                except ValueError:
                    pass
            if plan_start:
                end = plan_start + timedelta(days=t.start_day + t.duration - 1)
                if end < today:
                    overdue += 1

    parts = [f"共 {total} 个任务"]
    has_stats = pending > 0 or completed > 0 or overdue > 0
    if pending > 0:
        parts.append(f"待完成 {pending}")
    if completed > 0:
        parts.append(f"已完成 {completed}")
    if overdue > 0:
        parts.append(f'<span style="color:{_t.RED}">{overdue} 个超期</span>')

    if has_stats:
        sep = "  ·  " if existing_summary else ""
        return existing_summary + sep + "  |  ".join(parts)
    return existing_summary
