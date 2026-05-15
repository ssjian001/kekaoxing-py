"""排程 Service — 封装 scheduler 引擎，连接 Repository 层。

提供从数据库读取任务/设备 → 执行排程 → 写回数据库的完整流程。
支持预览模式（不写 DB）和直接应用模式。
"""

from __future__ import annotations

import copy
import logging
from copy import deepcopy
from dataclasses import replace
from typing import Optional

from src.db.repositories import TestTaskRepository, EquipmentRepository, TestPlanRepository
from src.models.test_plan import TestTask, TestPlan
from src.models.common import Equipment
from src.services.scheduler import (
    ScheduleConfig,
    run_auto_schedule,
)

logger = logging.getLogger(__name__)


class SchedulerService:
    """排程业务逻辑 — 读取 DB 数据，执行排程，写回结果。"""

    def __init__(
        self,
        task_repo: TestTaskRepository,
        equipment_repo: EquipmentRepository,
        plan_repo: TestPlanRepository,
        holiday_service: object | None = None,
    ) -> None:
        self._task_repo = task_repo
        self._equipment_repo = equipment_repo
        self._plan_repo = plan_repo
        self._holiday_service = holiday_service

    # ── 预览排程（不写 DB）──────────────────────────────────

    def preview_schedule(
        self,
        plan_id: int,
        skip_weekends: bool = True,
        skip_holidays: bool = True,
        lock_existing: bool = False,
        deadline: str = "",
        equipment_capacity: dict[int, int] | None = None,
        user_locked_days: dict[int, int] | None = None,
        daily_start_limit: int = 0,
    ) -> dict:
        """执行排程但不写回 DB，返回预览数据。

        Parameters
        ----------
        plan_id : int
            测试计划 ID。
        user_locked_days : dict[int, int] | None
            用户手动锁定的 {task_id: start_day}，这些任务不参与自动排程。

        Returns
        -------
        dict with keys:
            ``original_start_days`` – {task_id: old_start_day}
            ``tasks`` – list[TestTask] 排程后的任务副本（start_day 已更新）
            ``report`` – 排程报告 dict
            ``start_date`` – 计划起始日期
            ``equipment`` – 设备列表
        """
        plan = self._plan_repo.get_by_id(plan_id)
        start_date = plan.start_date if plan else ""

        tasks = self._task_repo.get_by_plan(plan_id)
        if not tasks:
            return self._empty_preview(start_date)

        equipment = self._equipment_repo.list_all()

        holidays: set[str] = set()
        if self._holiday_service:
            holidays = self._holiday_service.get_holidays_set()

        # ── 深拷贝任务，不污染 DB 读出的原始对象 ──
        tasks_copy = [replace(t) for t in tasks]

        # ── 应用用户手动锁定 ──
        locked_ids: set[int] = set()
        if user_locked_days:
            for t in tasks_copy:
                if t.id in user_locked_days:
                    t.start_day = user_locked_days[t.id]
                    locked_ids.add(t.id)  # type: ignore[arg-type]

        config = ScheduleConfig(
            start_date=start_date,
            skip_weekends=skip_weekends,
            skip_holidays=skip_holidays,
            lock_existing=lock_existing or bool(user_locked_days),
            deadline=deadline,
            equipment_capacity=equipment_capacity or {},
            holidays=holidays,
            daily_start_limit=daily_start_limit,
        )

        # 记录原始 start_day
        original_start_days = {t.id: t.start_day for t in tasks if t.id is not None}

        # 执行排程（在副本上）
        result = run_auto_schedule(tasks_copy, equipment, config)
        report = result["report"]

        # 附加统计
        changes = [
            (t.id, t.start_day)
            for t in tasks_copy
            if t.id is not None and t.start_day != original_start_days.get(t.id)
        ]
        report["task_count"] = len(tasks_copy)
        report["updated_count"] = len(changes)

        return {
            "original_start_days": original_start_days,
            "tasks": tasks_copy,
            "report": report,
            "start_date": start_date,
            "equipment": equipment,
        }

    # ── 应用排程（写 DB）──────────────────────────────────

    def apply_schedule(
        self,
        plan_id: int,
        changes: list[tuple[int, int]],
    ) -> int:
        """将用户确认后的排程结果写入 DB。

        Parameters
        ----------
        plan_id : int
            测试计划 ID。
        changes : list[tuple[int, int]]
            [(task_id, new_start_day), ...]

        Returns
        -------
        int : 更新的任务数
        """
        if not changes:
            return 0
        self._task_repo.bulk_update_start_day(changes)
        logger.info(
            "Applied schedule for plan %d: %d tasks updated",
            plan_id, len(changes),
        )
        return len(changes)

    # ── 向后兼容：一键排程（预览+应用）──────────────────────

    def auto_schedule(
        self,
        plan_id: int,
        skip_weekends: bool = True,
        skip_holidays: bool = True,
        lock_existing: bool = False,
        deadline: str = "",
        equipment_capacity: dict[int, int] | None = None,
        daily_start_limit: int = 0,
    ) -> dict:
        """对指定测试计划执行自动排程并直接写回 DB（向后兼容）。

        内部调用 preview_schedule + apply_schedule。
        """
        # 读取计划获取 start_date
        plan = self._plan_repo.get_by_id(plan_id)
        start_date = plan.start_date if plan else ""

        tasks = self._task_repo.get_by_plan(plan_id)
        if not tasks:
            logger.info("Plan %d has no tasks, skipping schedule", plan_id)
            return self._empty_report()

        equipment = self._equipment_repo.list_all()

        holidays: set[str] = set()
        if self._holiday_service:
            holidays = self._holiday_service.get_holidays_set()
        config = ScheduleConfig(
            start_date=start_date,
            skip_weekends=skip_weekends,
            skip_holidays=skip_holidays,
            lock_existing=lock_existing,
            deadline=deadline,
            equipment_capacity=equipment_capacity or {},
            holidays=holidays,
            daily_start_limit=daily_start_limit,
        )

        # 记录排程前的 start_day 用于对比
        original_start_days = {t.id: t.start_day for t in tasks if t.id is not None}

        # 深拷贝任务列表，防止 run_auto_schedule 污染原始对象
        import copy
        tasks_copy = copy.deepcopy(tasks)

        # 执行排程
        result = run_auto_schedule(tasks_copy, equipment, config)
        report = result["report"]

        # 写回 start_day 到数据库（用拷贝后的结果）
        updates = [
            (t.id, t.start_day)
            for t in tasks_copy
            if t.id is not None and t.start_day != original_start_days.get(t.id)
        ]
        if updates:
            self._task_repo.bulk_update_start_day(updates)

        # 附加统计信息
        report["task_count"] = len(tasks)
        report["updated_count"] = len(updates)

        logger.info(
            "Schedule complete for plan %d: %d tasks, %d days total, %d updated",
            plan_id, len(tasks), report["total_days"], len(updates),
        )
        return report

    # ── 内部辅助 ──

    def _empty_report(self) -> dict:
        return {
            "total_days": 0,
            "original_days": 0,
            "improvement": 0.0,
            "equipment_utilization": [],
            "bottlenecks": [],
            "suggestions": ["没有待排程的任务"],
            "task_count": 0,
            "updated_count": 0,
        }

    def _empty_preview(self, start_date: str = "") -> dict:
        return {
            "original_start_days": {},
            "tasks": [],
            "report": self._empty_report(),
            "start_date": start_date,
            "equipment": [],
        }
