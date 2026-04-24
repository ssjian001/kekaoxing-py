"""排程 Service — 封装 scheduler 引擎，连接 Repository 层。

提供从数据库读取任务/设备 → 执行排程 → 写回数据库的完整流程。
"""

from __future__ import annotations

import logging

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
    ) -> None:
        self._task_repo = task_repo
        self._equipment_repo = equipment_repo
        self._plan_repo = plan_repo

    def auto_schedule(
        self,
        plan_id: int,
        skip_weekends: bool = True,
        lock_existing: bool = False,
        deadline: str = "",
        equipment_capacity: dict[int, int] | None = None,
    ) -> dict:
        """对指定测试计划执行自动排程。

        Parameters
        ----------
        plan_id : int
            测试计划 ID。
        skip_weekends : bool
            是否跳过周末。
        lock_existing : bool
            是否锁定已有排期的任务。
        deadline : str
            截止日期 "YYYY-MM-DD"（可选，用于报告）。
        equipment_capacity : dict[int, int]
            设备并行数覆盖 {equipment_id: max_parallel}。

        Returns
        -------
        dict : 排程报告 {
            "total_days", "original_days", "improvement",
            "equipment_utilization", "bottlenecks", "suggestions",
            "task_count", "updated_count"
        }
        """
        # 读取计划获取 start_date
        plan = self._plan_repo.get_by_id(plan_id)
        start_date = plan.start_date if plan else ""

        # 读取所有任务
        tasks = self._task_repo.get_by_plan(plan_id)
        if not tasks:
            logger.info("Plan %d has no tasks, skipping schedule", plan_id)
            return self._empty_report()

        # 读取所有设备
        equipment = self._equipment_repo.list_all()

        # 构建配置
        config = ScheduleConfig(
            start_date=start_date,
            skip_weekends=skip_weekends,
            lock_existing=lock_existing,
            deadline=deadline,
            equipment_capacity=equipment_capacity or {},
        )

        # 记录排程前的 start_day 用于对比
        original_start_days = {t.id: t.start_day for t in tasks if t.id is not None}

        # 执行排程
        result = run_auto_schedule(tasks, equipment, config)
        report = result["report"]

        # 写回 start_day 到数据库
        updates = [
            (t.id, t.start_day)
            for t in tasks
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

    def _empty_report(self) -> dict:
        return {
            "total_days": 0,
            "original_days": 0,
            "improvement": 0.0,
            "equipment_utilization": [],
            "bottlenecks": [],
            "suggestions": ["💡 没有待排程的任务"],
            "task_count": 0,
            "updated_count": 0,
        }
