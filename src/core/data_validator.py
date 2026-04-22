"""数据校验规则引擎 — 在任务保存/更新/排程后自动检测潜在问题并生成警告。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import Resource, Task


# ── 公共数据结构 ──────────────────────────────────────────────


@dataclass
class ValidationIssue:
    severity: str        # "error" | "warning" | "info"
    category: str        # "冲突" | "超载" | "异常" | "孤立" | "样品池"
    message: str
    task_id: int | None = None
    day: int | None = None
    resource_name: str = ""


# ── 校验器 ────────────────────────────────────────────────────


class DataValidator:
    """对一组 Task / Resource 执行五类校验，返回 ValidationIssue 列表。"""

    def __init__(self, tasks: list[Task], resources: list[Resource]) -> None:
        self.tasks = tasks
        self.resources = resources
        self._task_map: dict[int, Task] = {t.id: t for t in tasks}
        self._num_map: dict[str, Task] = {t.num: t for t in tasks}
        self._resource_map: dict[int, Resource] = {r.id: r for r in resources}

    # ── 总入口 ────────────────────────────────────────────────

    def validate_all(self) -> list[ValidationIssue]:
        """运行所有校验，返回按 category 分组的问题列表。"""
        issues: list[ValidationIssue] = []
        issues.extend(self._check_dependency_conflicts())
        issues.extend(self._check_resource_overload())
        issues.extend(self._check_duration_anomalies())
        issues.extend(self._check_orphan_tasks())
        issues.extend(self._check_sample_pool())
        return issues

    # ── 1. 工期冲突检测 ─────────────────────────────────────

    def _check_dependency_conflicts(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for task in self.tasks:
            for dep_num in task.dependencies:
                dep_task = self._num_map.get(dep_num)
                if dep_task is None:
                    # 引用不存在的任务编号 → 归入孤立任务检测
                    continue
                dep_end = dep_task.start_day + dep_task.duration
                if dep_end > task.start_day:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="冲突",
                            message=(
                                f"任务 {task.num} 依赖任务 {dep_num}，"
                                f"但 {dep_num} 的结束日(D{dep_end})"
                                f"晚于 {task.num} 的开始日(D{task.start_day})"
                            ),
                            task_id=task.id,
                        )
                    )
        return issues

    # ── 2. 资源超载检测 ─────────────────────────────────────

    def _check_resource_overload(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not self.tasks or not self.resources:
            return issues

        # 1) 找到全局时间范围
        max_day = max((t.start_day + t.duration for t in self.tasks), default=0)
        min_day = min((t.start_day for t in self.tasks), default=0)

        # 2) 仅收集设备类资源
        equip_resources = {
            r.id: r
            for r in self.resources
            if r.type.value == "equipment" and r.available_qty > 0
        }
        if not equip_resources:
            return issues

        # 3) 构建需求矩阵: demand[resource_id][day] += quantity
        demand: dict[int, dict[int, int]] = {rid: {} for rid in equip_resources}

        for task in self.tasks:
            for req in task.requirements:
                if req.resource_id not in demand:
                    continue
                day_demand = demand[req.resource_id]
                for d in range(task.start_day, task.start_day + task.duration):
                    day_demand[d] = day_demand.get(d, 0) + req.quantity

        # 4) 检测超载
        for rid, day_map in demand.items():
            res = equip_resources[rid]
            avail = res.available_qty
            for day in range(min_day, max_day + 1):
                needed = day_map.get(day, 0)
                if needed > avail:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="超载",
                            message=(
                                f"D{day}: {res.name} 需求{needed}台 "
                                f"超出可用{avail}台"
                            ),
                            day=day,
                            resource_name=res.name,
                        )
                    )
        return issues

    # ── 3. 工期异常检测 ─────────────────────────────────────

    def _check_duration_anomalies(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for t in self.tasks:
            if t.duration <= 0:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="异常",
                        message=f"任务 {t.num}({t.name_cn}) 工期 ≤ 0（当前值: {t.duration}天）",
                        task_id=t.id,
                    )
                )
            elif t.duration > 365:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="异常",
                        message=f"任务 {t.num}({t.name_cn}) 工期超过 365 天（当前值: {t.duration}天）",
                        task_id=t.id,
                    )
                )
            if t.start_day < 0:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="异常",
                        message=f"任务 {t.num}({t.name_cn}) 开始日 < 0（当前值: D{t.start_day}）",
                        task_id=t.id,
                    )
                )
            if t.progress < 0:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="异常",
                        message=f"任务 {t.num}({t.name_cn}) 进度 < 0（当前值: {t.progress}%）",
                        task_id=t.id,
                    )
                )
            elif t.progress > 100:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="异常",
                        message=f"任务 {t.num}({t.name_cn}) 进度 > 100（当前值: {t.progress}%）",
                        task_id=t.id,
                    )
                )
        return issues

    # ── 4. 孤立任务检测 ─────────────────────────────────────

    def _check_orphan_tasks(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        # 收集被依赖的任务编号集合
        downstream_nums: set[str] = set()
        for t in self.tasks:
            downstream_nums.update(t.dependencies)

        for t in self.tasks:
            # 引用不存在的任务编号
            for dep_num in t.dependencies:
                if dep_num not in self._num_map:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="孤立",
                            message=f"任务 {t.num} 依赖的任务编号 '{dep_num}' 不存在",
                            task_id=t.id,
                        )
                    )

            # 没有上游依赖 且 没有下游任务 → 孤立
            has_deps = bool(t.dependencies)
            is_downstream = t.num in downstream_nums
            if not has_deps and not is_downstream:
                # 首层任务（没有上游但有下游）不算孤立
                issues.append(
                    ValidationIssue(
                        severity="info",
                        category="孤立",
                        message=f"任务 {t.num}({t.name_cn}) 既无依赖也无下游任务",
                        task_id=t.id,
                    )
                )
        return issues

    # ── 5. 样品池不一致检测 ─────────────────────────────────

    def _check_sample_pool(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        # 收集样品池类型的资源名称（大小写不敏感匹配）
        pool_names: set[str] = {
            r.name.lower()
            for r in self.resources
            if r.type.value == "sample_pool"
        }
        if not pool_names:
            # 数据库中没有任何样品池资源 → 无法校验，跳过
            return issues

        seen: set[str] = set()  # 避免同一 pool 值重复报告
        for t in self.tasks:
            sp = t.sample_pool.strip()
            if not sp:
                continue
            if sp in seen:
                continue
            if sp.lower() not in pool_names:
                seen.add(sp)
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="样品池",
                        message=f"样品池 '{sp}' 不在资源列表中",
                        task_id=t.id,
                    )
                )
        return issues
