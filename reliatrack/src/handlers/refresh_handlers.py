"""Refresh handlers — data refresh and throttling for all views."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MainWindow

    from src.handlers.sample_handlers import SampleHandlers

logger = logging.getLogger(__name__)


class RefreshHandlers:
    """Handles data refresh operations across all views with throttling support."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win
        # Cross-handler references — set by MainWindow after construction
        self._sample_handlers: SampleHandlers | None = None  # type: ignore[name-defined]
        # 全量刷新时的共享数据缓存（避免重复 DB 查询）
        self._cached_projects: list | None = None
        self._cached_samples: list | None = None
        self._need_plan_combo_refresh: bool = False

    def _get_filter_project_id(self):
        """获取当前筛选的项目 ID（None = 全部）。"""
        return self._win.get_project_filter_id()

    def _get_filter_plan_id(self):
        """获取当前筛选的测试计划 ID（None = 全部）。"""
        return self._win.get_plan_filter_id()

    def _refresh_all(self) -> None:
        """全量刷新（项目筛选切换时调用）。"""
        self._win.clear_pending_entities()
        self._do_refresh_all()

    def _schedule_refresh(self, entity_type: str = "all") -> None:
        """节流刷新：合并短时间内的多次变更，100ms 后统一刷新。"""
        self._win.schedule_throttled_refresh(entity_type)

    def _do_refresh_all(self) -> None:
        """执行实际的刷新操作。"""
        pending = self._win.get_pending_entity_types()
        need_all = not pending or "all" in pending

        if need_all:
            pending.clear()
            self._need_plan_combo_refresh = True

        # 全量刷新时预取共享数据，避免重复 DB 查询
        if need_all:
            self._prefetch_shared_data()

        # 根据需要选择刷新范围
        if need_all:
            self._refresh_projects()
            self._refresh_dashboard()
            self._refresh_samples()
            self._refresh_plans()
            self._refresh_issues()
            self._refresh_equipment()
            self._refresh_technicians()
            self._refresh_knowledge()
            self._refresh_todos()
        else:
            _need_dashboard = False
            if "project" in pending:
                self._refresh_projects()
                self._need_plan_combo_refresh = True
                _need_dashboard = True
            if "sample" in pending:
                self._refresh_samples()
                _need_dashboard = True
            if "task" in pending or "plan" in pending:
                self._refresh_plans()
                self._need_plan_combo_refresh = True
                _need_dashboard = True
            if "issue" in pending:
                self._refresh_issues()
                _need_dashboard = True
            if "equipment" in pending:
                self._refresh_equipment()
            if "technician" in pending:
                self._refresh_technicians()
            if "knowledge" in pending:
                self._refresh_knowledge()
            if "todo" in pending:
                self._refresh_todos()
            if _need_dashboard:
                self._refresh_dashboard()

        # 撤销/重做按钮始终更新
        self._refresh_undo_state()

        # 按需刷新顶部计划筛选 combo
        if self._need_plan_combo_refresh:
            self._win.refresh_plan_combo()
            self._need_plan_combo_refresh = False

        pending.clear()
        # 清除缓存
        self._cached_projects = None
        self._cached_samples = None

    def _prefetch_shared_data(self) -> None:
        """全量刷新前预取共享数据。"""
        ctrl = self._win.ctrl
        if not ctrl:
            return
        if ctrl.project_service:
            self._cached_projects = ctrl.project_service.list_all()
        if ctrl.sample_service:
            fpid = self._get_filter_project_id()
            if fpid:
                self._cached_samples = ctrl.sample_service.get_by_project(fpid)
            else:
                self._cached_samples = ctrl.sample_service.list_all()

    def _refresh_projects(self) -> None:
        """刷新项目管理视图 + 筛选 combo。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.project_service:
            return
        all_projects = self._cached_projects if self._cached_projects is not None else ctrl.project_service.list_all()
        self._win.project_view.refresh(all_projects)
        # 更新筛选 combo 选项（通过公共方法，不触发信号）
        self._win.refresh_project_filter(all_projects)

    def _collect_dashboard_data(self, ctrl, filter_project_id, filter_plan_id) -> "DashboardData | None":
        """从 DB 收集仪表盘所需全部数据，返回 DashboardData 或 None。"""
        from src.views.dashboard_view import DashboardData

        # ── 基础数据 ──
        all_projects = self._cached_projects if self._cached_projects is not None else (
            ctrl.project_service.list_all() if ctrl.project_service else []
        )

        current_project_name: str | None = None
        if filter_project_id and ctrl.project_service:
            for p in all_projects:
                if p.id == filter_project_id:
                    current_project_name = p.name
                    break

        sample_count = 0
        if ctrl.sample_service:
            if self._cached_samples is not None:
                all_samples = self._cached_samples
            elif filter_project_id:
                all_samples = ctrl.sample_service.get_by_project(filter_project_id)
            else:
                all_samples = ctrl.sample_service.list_all()
            sample_count = len(all_samples)
        else:
            all_samples = []

        # ── 注入 Issue 弹窗上下文（通过公共方法）──
        self._win.bug_tracker_view.set_context_data(
            projects=all_projects,
            default_project_id=filter_project_id,
            samples=all_samples,
        )
        if ctrl.knowledge_service:
            self._win.bug_tracker_view.set_context_data(
                knowledge=ctrl.knowledge_service.list_all(),
            )

        if not (ctrl.test_tasks and ctrl.issues):
            return None

        # ── 任务状态 ──
        task_status_data = ctrl.test_tasks.count_by_status(
            project_id=filter_project_id, plan_id=filter_plan_id,
        )
        total = sum(task_status_data.values())
        completed = task_status_data.get("completed", 0)
        in_progress = task_status_data.get("in_progress", 0)
        pending_count = task_status_data.get("pending", 0)
        failed_task_count = task_status_data.get("failed", 0) + task_status_data.get("fail", 0)
        skipped_count = task_status_data.get("skipped", 0)
        paused_count = task_status_data.get("paused", 0)

        # ── 任务列表（SQL 过滤） ──
        if filter_plan_id:
            filtered_tasks = ctrl.test_tasks.get_by_plan(filter_plan_id)
        elif filter_project_id and ctrl.test_plan_service:
            filtered_tasks = ctrl.test_plan_service.get_tasks_by_project(filter_project_id, exclude_archived=True)
        else:
            filtered_tasks = ctrl.test_tasks.list_all()
        self._win.bug_tracker_view.set_context_data(tasks=filtered_tasks)

        # ── Issue ──（与 Issue 视图一致：含未分配项目的 Issue）
        if filter_project_id:
            issues_list = ctrl.issues.get_by_project(filter_project_id)
            issues_list += ctrl.issues.get_unassigned()
        else:
            issues_list = ctrl.issues.list_all()
        issues = len(issues_list)
        issue_closed_count = sum(1 for iss in issues_list if iss.status == "closed")
        issue_severity_data = ctrl.issues.count_by_severity(project_id=filter_project_id)

        # ── Bug Tracker 4 指标 ──
        pending_issues = [i for i in issues_list if i.status in ("open", "analyzing")]
        pending_issue_count = len(pending_issues)

        # 本周关闭数（从活动日志查，按项目筛选）
        # 审计 B3：原为 UI 层裸 SQL，收编到 issue_service.count_weekly_closed
        weekly_closed = 0
        if ctrl.issue_service:
            try:
                weekly_closed = ctrl.issue_service.count_weekly_closed(filter_project_id)
            except Exception:
                logger.exception("统计本周关闭 Issue 失败")

        # 平均停留天数
        aging_days_list = [
            ctrl.issue_service.get_aging_days(i.id)
            for i in pending_issues
            if i.id and ctrl.issue_service is not None
        ]
        avg_age_days = sum(aging_days_list) / len(aging_days_list) if aging_days_list else 0

        # Aging 超期警告
        aging_warning_count = sum(1 for d in aging_days_list if d > 7)

        # ── 通过率 ──
        pass_rate: float | None = None
        total_pass = 0
        total_result = 0
        task_ids = [t.id for t in filtered_tasks if t.id is not None]
        if task_ids and ctrl.test_plan_service:
            rm = ctrl.test_plan_service.get_pass_counts_by_tasks(task_ids)
            total_pass = sum(v[0] for v in rm.values())
            total_result = sum(v[1] for v in rm.values())
            if total_result > 0:
                pass_rate = total_pass / total_result * 100

        # ── 失效率 ──
        failure_rate: float | None = None
        if sample_count > 0 and issues > 0:
            failure_rate = issues / sample_count * 100

        # ── CAPA 完成率 ──
        capa_completion_rate: float | None = None
        if ctrl.issue_service:
            total_capa = ctrl.issue_service.count_capa_all(project_id=filter_project_id)
            if total_capa and total_capa > 0:
                done_capa = ctrl.issue_service.count_capa_done(project_id=filter_project_id)
                capa_completion_rate = done_capa / total_capa * 100

        # ── 计划名 ──
        current_plan_name: str | None = None
        if filter_plan_id and ctrl.test_plan_service:
            plan_obj = ctrl.test_plan_service.get_plan(filter_plan_id)
            if plan_obj:
                current_plan_name = plan_obj.name

        # ── 健康评分 ──
        issue_closure_rate = issue_closed_count / issues * 100 if issues else 0
        health_score = (
            (pass_rate or 0) * 0.4
            + issue_closure_rate * 0.3
            + (capa_completion_rate or 0) * 0.3
        )

        # ── 辅助指标 ──
        plan_count = 0
        if ctrl.test_plan_service:
            p_list = (
                ctrl.test_plan_service.get_active_plans_by_project(filter_project_id)
                if filter_project_id
                else ctrl.test_plan_service.list_all_active_plans()
            )
            plan_count = len(p_list) if p_list else 0

        last_update: str | None = None
        if filtered_tasks:
            latest = max(
                (t.updated_at for t in filtered_tasks if getattr(t, "updated_at", None)),
                default=None,
            )
            if latest:
                last_update = str(latest)[:16]

        return DashboardData(
            task_total=total,
            task_completed=completed,
            task_in_progress=in_progress,
            task_pending=pending_count,
            task_skipped=skipped_count,
            task_paused=paused_count,
            issue_count=issues,
            issue_closed_count=issue_closed_count,
            failed_task_count=failed_task_count,
            project_name=current_project_name,
            plan_name=current_plan_name,
            task_status_data=task_status_data,
            issue_severity_data=issue_severity_data,
            pass_rate=pass_rate,
            failure_rate=failure_rate,
            capa_completion_rate=capa_completion_rate,
            health_score=health_score,
            plan_count=plan_count,
            last_update=last_update,
            pass_count=total_pass if task_ids else 0,
            fail_count=max(total_result - total_pass, 0) if task_ids else 0,
            technician_count=ctrl.technicians.count() if ctrl.technicians else 0,
            # Bug Tracker 4 指标
            pending_count=pending_issue_count,
            weekly_closed=weekly_closed,
            avg_age_days=avg_age_days,
            aging_warning_count=aging_warning_count,
        )

    def _refresh_dashboard(self) -> None:
        """刷新 Dashboard A/B 两区 KPI + 图表。"""
        ctrl = self._win.ctrl
        if not ctrl:
            return

        filter_project_id = self._get_filter_project_id()
        filter_plan_id = self._get_filter_plan_id()

        data = self._collect_dashboard_data(ctrl, filter_project_id, filter_plan_id)
        if data is not None:
            self._win.dashboard.refresh(**{
                slot: getattr(data, slot) for slot in data.__slots__
            })

    def _refresh_samples(self) -> None:
        """刷新样品视图。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return
        filter_project_id = self._get_filter_project_id()
        if self._cached_samples is not None:
            all_samples = self._cached_samples
        elif filter_project_id:
            all_samples = ctrl.sample_service.get_by_project(filter_project_id)
        else:
            all_samples = ctrl.sample_service.list_all()
        self._win.sample_view.refresh_ledger(all_samples)
        # 样品池只显示在库样品（也按项目筛选）
        in_stock = [s for s in all_samples if s.status == "in_stock"]
        self._win.sample_view.refresh_pool(in_stock)
        # 出入库记录 — delegate to sample handlers
        if self._sample_handlers is not None:
            self._sample_handlers._refresh_sample_usage()

    def _refresh_plans(self) -> None:
        """刷新测试计划 + 甘特图。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.test_plan_service or not ctrl.test_tasks:
            return
        filter_project_id = self._get_filter_project_id()
        show_archived = getattr(self._win.test_plan_view, 'show_archived', False)
        # 按项目筛选计划（根据归档视图模式过滤）
        if filter_project_id:
            all_plans = ctrl.test_plan_service.get_plans_by_project(
                filter_project_id
            )
        else:
            all_plans = ctrl.test_plan_service.list_all_plans()
        if show_archived:
            # 归档视图：只显示已归档的计划
            all_plans = [p for p in all_plans if p.status == "archived"]
        else:
            # 正常视图：排除归档的计划
            all_plans = [p for p in all_plans if p.status != "archived"]
        # 保存当前选中索引 — 通过公共方法设置 combo 并恢复选中
        current_plan_id = self._win.test_plan_view.get_selected_plan_id()
        plan_names = [p.name for p in all_plans]
        plan_ids = [p.id for p in all_plans]  # type: ignore[misc]

        if not all_plans:
            self._win.test_plan_view.set_plans_and_restore([], [], None)
            self._win.test_plan_view.refresh([], 30)
            return

        # 确定选中的 plan_id
        target_id = self._get_filter_plan_id()
        if target_id is None and current_plan_id and current_plan_id in plan_ids:
            target_id = current_plan_id

        self._win.test_plan_view.set_plans_and_restore(plan_names, plan_ids, target_id)

        selected_plan_id = self._win.test_plan_view.get_selected_plan_id()

        if selected_plan_id is None:
            tasks = []
            for p in all_plans:
                if p.id is not None:
                    tasks.extend(ctrl.test_plan_service.get_tasks(p.id))
            start_date = all_plans[0].start_date if all_plans else ""
            task_prefix = "ALL"
            plan_obj = all_plans[0] if all_plans else None
        else:
            tasks = ctrl.test_plan_service.get_tasks(selected_plan_id)
            plan_obj = ctrl.test_plan_service.get_plan(selected_plan_id)
            start_date = plan_obj.start_date if plan_obj else ""
            task_prefix = plan_obj.task_prefix if plan_obj else ""

        max_day = max(((t.start_day or 0) + t.duration for t in tasks), default=30)

        # 构建技术员映射 {technician_id: name}
        technician_map: dict[int, str] = {}
        if ctrl.technician_service:
            for t in ctrl.technician_service.list_all():
                if t.id is not None:
                    technician_map[t.id] = t.name

        # 批量获取通过率映射 {task_id: (pass_count, total)}
        result_map: dict[int, tuple[int, int]] = {}
        matrix_results: list = []
        task_ids = [t.id for t in tasks if t.id is not None]
        if task_ids and ctrl.test_plan_service:
            result_map = ctrl.test_plan_service.get_pass_counts_by_tasks(task_ids)
            matrix_results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids)

        # 样品映射 {sample_id: sn}
        sample_map: dict[int, str] = {}
        if ctrl.sample_service:
            for s in ctrl.sample_service.list_all():
                if s.id is not None:
                    sample_map[s.id] = s.sn

        # 设备映射 {equipment_id: name} — 甘特图按设备着色
        equipment_map: dict[int, str] = {}
        if ctrl.equipment:
            for eq in ctrl.equipment.list_all():
                if eq.id is not None:
                    equipment_map[eq.id] = eq.name

        # 节假日集合
        holidays: set[str] = set()
        if ctrl.holiday_service:
            holidays = ctrl.holiday_service.get_holidays_set()

        # 关联 Issue（用于失效模式分析）
        plan_issues: list = []
        if ctrl.issue_service:
            if plan_obj and plan_obj.project_id:
                plan_issues = ctrl.issue_service.get_by_project(plan_obj.project_id)
            else:
                plan_issues = ctrl.issue_service.list_all()

        self._win.test_plan_view.refresh(
            tasks, max_day, technician_map, result_map,
            start_date=start_date,
            matrix_results=matrix_results,
            sample_map=sample_map,
            equipment_map=equipment_map,
            issues=plan_issues,
            task_prefix=task_prefix,
            holidays=holidays,
        )


    def _refresh_issues(self) -> None:
        """刷新 Issue 追踪视图 + Bug Tracker 视图。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.issue_service:
            return
        filter_project_id = self._get_filter_project_id()
        if filter_project_id:
            # 项目筛选时：显示属于该项目 + 未关联项目(project_id=NULL)的 Issue
            project_issues = ctrl.issue_service.get_by_project(filter_project_id)
            null_issues = ctrl.issue_service.get_unassigned()
            all_issues = project_issues + null_issues
        else:
            all_issues = ctrl.issue_service.list_all()
        # 注入技术员列表供 CAPA 弹窗使用（通过公共方法）
        if ctrl.technician_service:
            technicians = ctrl.technician_service.list_all()
            self._win.bug_tracker_view.set_context_data(
                technicians=technicians,
            )
            # 构建 technician_map 并注入 Bug Tracker（Fix 1: 看板卡片显示人名）
            tech_map = {t.id: t.name for t in technicians if t.id is not None}
            self._win.bug_tracker_view.set_technician_map(tech_map)
        # 同步刷新 Bug Tracker 视图（注入项目筛选 ID + 刷新数据）
        self._win.bug_tracker_view.set_project_filter(filter_project_id)
        self._win.bug_tracker_view.refresh()

    def _refresh_equipment(self) -> None:
        """刷新设备管理视图。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        all_equipment = ctrl.equipment_service.list_all()
        # 计算设备 → 任务引用数（热力图真实负载数据源）
        task_ref_counts: dict[int, int] = {}
        for eq in all_equipment:
            if eq.id is not None:
                task_ref_counts[eq.id] = ctrl.equipment_service.count_task_references(eq.id)
        self._win.equipment_view.refresh(all_equipment, task_ref_counts)

    def _refresh_technicians(self) -> None:
        """刷新技术员管理视图 + 同步 Bug Tracker 的 technician_map。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.technician_service:
            return
        all_technicians = ctrl.technician_service.list_all()
        self._win.technician_view.refresh(all_technicians)
        # 同步 Bug Tracker 的 technician_map（technician 增刪改名後即時更新）
        bug_tracker = getattr(self._win, '_bug_tracker_view', None)
        if bug_tracker is not None:
            tech_map = {t.id: t.name for t in all_technicians if t.id is not None}
            bug_tracker.set_technician_map(tech_map)

    def _refresh_knowledge(self) -> None:
        """刷新知识库视图。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        all_knowledge = ctrl.knowledge_service.list_all()
        self._win.knowledge_view.refresh(all_knowledge)

    def _refresh_todos(self) -> None:
        """刷新待办事项视图。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.todo_service:
            return
        all_todos = ctrl.todo_service.list_all()
        projects = ctrl.project_service.list_all() if ctrl.project_service else []
        self._win.todo_view.refresh(all_todos, projects)

    def _refresh_undo_state(self) -> None:
        """更新撤销/重做按钮状态。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.undo_manager:
            return
        self._win.update_undo_redo(
            can_undo=ctrl.undo_manager.can_undo(),
            can_redo=ctrl.undo_manager.can_redo(),
            undo_desc=ctrl.undo_manager.undo_description() or "",
            redo_desc=ctrl.undo_manager.redo_description() or "",
        )
