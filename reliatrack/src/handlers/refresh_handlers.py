"""Refresh handlers — data refresh and throttling for all views."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MainWindow

    from src.handlers.sample_handlers import SampleHandlers


class RefreshHandlers:
    """Handles data refresh operations across all views with throttling support."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win
        # Cross-handler references — set by MainWindow after construction
        self._sample_handlers: SampleHandlers | None = None  # type: ignore[name-defined]
        # 全量刷新时的共享数据缓存（避免重复 DB 查询）
        self._cached_projects: list | None = None
        self._cached_samples: list | None = None

    def _get_filter_project_id(self):
        """获取当前筛选的项目 ID（None = 全部）。"""
        return self._win._project_filter_combo.currentData()

    def _refresh_all(self) -> None:
        """全量刷新（项目筛选切换时调用）。"""
        self._win._pending_entity_types.clear()
        self._do_refresh_all()

    def _schedule_refresh(self, entity_type: str = "all") -> None:
        """节流刷新：合并短时间内的多次变更，100ms 后统一刷新。"""
        if entity_type == "all":
            self._win._pending_entity_types.clear()
        else:
            self._win._pending_entity_types.add(entity_type)
            # plan 变更也影响 dashboard
            self._win._pending_entity_types.add("plan")
        self._win._refresh_timer.start()

    def _do_refresh_all(self) -> None:
        """执行实际的刷新操作。"""
        pending = self._win._pending_entity_types
        need_all = not pending or "all" in pending

        if need_all:
            pending.clear()

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
        else:
            _need_dashboard = False
            if "project" in pending:
                self._refresh_projects()
                _need_dashboard = True
            if "sample" in pending:
                self._refresh_samples()
                _need_dashboard = True
            if "task" in pending or "plan" in pending:
                self._refresh_plans()
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
            if _need_dashboard:
                self._refresh_dashboard()

        # 撤销/重做按钮始终更新
        self._refresh_undo_state()

        pending.clear()
        # 清除缓存
        self._cached_projects = None
        self._cached_samples = None

    def _prefetch_shared_data(self) -> None:
        """全量刷新前预取共享数据。"""
        ctrl = self._win._ctrl
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
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.project_service:
            return
        all_projects = self._cached_projects if self._cached_projects is not None else ctrl.project_service.list_all()
        self._win._project_view.refresh(all_projects)
        # 更新筛选 combo 选项（不触发信号）
        self._win._project_filter_combo.blockSignals(True)
        current_filter = self._win._project_filter_combo.currentData()
        self._win._project_filter_combo.clear()
        self._win._project_filter_combo.addItem("📋 全部项目", None)
        for p in all_projects:
            self._win._project_filter_combo.addItem(f"📁 {p.name}", p.id)
        # 恢复之前选中的筛选项
        for i in range(self._win._project_filter_combo.count()):
            if self._win._project_filter_combo.itemData(i) == current_filter:
                self._win._project_filter_combo.setCurrentIndex(i)
                break
        self._win._project_filter_combo.blockSignals(False)

    def _refresh_dashboard(self) -> None:
        """刷新 Dashboard KPI + 图表 + 样品图表。"""
        ctrl = self._win._ctrl
        if not ctrl:
            return

        filter_project_id = self._get_filter_project_id()

        # 获取项目列表和名称
        all_projects = self._cached_projects if self._cached_projects is not None else (ctrl.project_service.list_all() if ctrl.project_service else [])
        self._win._issue_view._project_list = all_projects
        self._win._issue_view._default_project_id = filter_project_id

        current_project_name: str | None = None
        if filter_project_id and ctrl.project_service:
            for p in all_projects:
                if p.id == filter_project_id:
                    current_project_name = p.name
                    break

        task_status_data: dict[str, int] = {}
        sample_status_data: dict[str, int] = {}
        issue_severity_data: dict[str, int] = {}
        sample_count = 0

        # 样品（优先使用缓存）
        if ctrl.sample_service:
            if self._cached_samples is not None:
                all_samples = self._cached_samples
            elif filter_project_id:
                all_samples = ctrl.sample_service.get_by_project(filter_project_id)
            else:
                all_samples = ctrl.sample_service.list_all()
            sample_count = len(all_samples)
            # SQL 聚合替代 Counter
            if ctrl.sample_service._repo:
                sample_status_data = ctrl.sample_service._repo.count_by_status(
                    project_id=filter_project_id
                )
            else:
                sample_status_data = dict(Counter(s.status for s in all_samples))
        else:
            all_samples = []

        # 注入任务列表和样品列表给 Issue 弹窗
        self._win._issue_view._sample_list = all_samples

        # 注入知识库条目给 Issue 弹窗（失效模式自动推荐）
        if ctrl.knowledge_service:
            self._win._issue_view._knowledge_list = ctrl.knowledge_service.list_all()
        if ctrl.test_tasks and ctrl.issues and ctrl.equipment:
            # ── 任务状态：SQL 聚合 ──
            task_status_data = ctrl.test_tasks.count_by_status(
                project_id=filter_project_id
            )
            total = sum(task_status_data.values())
            completed = task_status_data.get("completed", 0)
            in_progress = task_status_data.get("in_progress", 0)
            pending_count = task_status_data.get("pending", 0)

            # 仍需任务列表供 Issue 弹窗 & 通过率计算
            all_tasks = ctrl.test_tasks.list_all()
            if filter_project_id and ctrl.test_plan_service:
                filtered_plans = ctrl.test_plan_service.get_plans_by_project(
                    filter_project_id
                )
                plan_ids = {p.id for p in filtered_plans}
                filtered_tasks = [t for t in all_tasks if t.plan_id in plan_ids]
            else:
                filtered_tasks = all_tasks

            # 注入给 Issue 弹窗
            self._win._issue_view._task_list = filtered_tasks

            # 按项目筛选 issues
            if filter_project_id:
                issues_list = ctrl.issues.get_by_project(filter_project_id)
            else:
                issues_list = ctrl.issues.list_all()
            issues = len(issues_list)
            equipment = len(ctrl.equipment.list_all())

            # Issue 严重度分布 — SQL 聚合替代 Counter
            issue_severity_data = ctrl.issues.count_by_severity(
                project_id=filter_project_id
            )

            # ── 专业 KPI 计算 ──
            # 1. 测试通过率
            pass_rate: float | None = None
            task_ids = [t.id for t in filtered_tasks if t.id is not None]
            if task_ids and ctrl.test_plan_service:
                rm = ctrl.test_plan_service.get_pass_counts_by_tasks(task_ids)
                total_pass = sum(v[0] for v in rm.values())
                total_result = sum(v[1] for v in rm.values())
                if total_result > 0:
                    pass_rate = total_pass / total_result * 100

            # 2. Issue 闭环率 — SQL 聚合替代 sum(1 for ...)
            issue_close_rate: float | None = None
            if issues > 0:
                status_counts = ctrl.issues.count_by_status(
                    project_id=filter_project_id
                )
                closed_count = status_counts.get("closed", 0)
                issue_close_rate = closed_count / issues * 100

            # 3. 校准预警（30天内到期）— SQL 聚合
            cal_warning = 0
            if ctrl.equipment:
                threshold = (date.today() + timedelta(days=30)).isoformat()
                cal_warning = ctrl.equipment.count_calibration_due(threshold)

            self._win._dashboard.refresh(
                task_total=total,
                task_completed=completed,
                task_in_progress=in_progress,
                task_pending=pending_count,
                issue_count=issues,
                equipment_count=equipment,
                sample_count=sample_count,
                project_name=current_project_name,
                task_status_data=task_status_data,
                sample_status_data=sample_status_data,
                issue_severity_data=issue_severity_data,
                pass_rate=pass_rate,
                issue_close_rate=issue_close_rate,
                calibration_warning_count=cal_warning,
            )

    def _refresh_samples(self) -> None:
        """刷新样品视图。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        filter_project_id = self._get_filter_project_id()
        if self._cached_samples is not None:
            all_samples = self._cached_samples
        elif filter_project_id:
            all_samples = ctrl.sample_service.get_by_project(filter_project_id)
        else:
            all_samples = ctrl.sample_service.list_all()
        self._win._sample_view.refresh_ledger(all_samples)
        # 样品池只显示在库样品（也按项目筛选）
        in_stock = [s for s in all_samples if s.status == "in_stock"]
        self._win._sample_view.refresh_pool(in_stock)
        # 出入库记录 — delegate to sample handlers
        if self._sample_handlers is not None:
            self._sample_handlers._refresh_sample_usage()

    def _refresh_plans(self) -> None:
        """刷新测试计划 + 甘特图。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service or not ctrl.test_tasks:
            return
        filter_project_id = self._get_filter_project_id()
        # 按项目筛选计划
        if filter_project_id:
            all_plans = ctrl.test_plan_service.get_plans_by_project(
                filter_project_id
            )
        else:
            all_plans = ctrl.test_plan_service.list_all_plans()
        # 保存当前选中索引
        current_plan_id = self._win._test_plan_view.get_selected_plan_id()
        self._win._test_plan_view._plan_combo.blockSignals(True)
        self._win._test_plan_view.set_plans(
            [p.name for p in all_plans],
            [p.id for p in all_plans],  # type: ignore[misc]
        )
        restore_idx = 0
        if all_plans:
            # 尝试恢复之前选中的计划
            target_id = current_plan_id if current_plan_id else all_plans[0].id
            # 在新 plan_ids 中找到对应索引
            new_ids = [p.id for p in all_plans]
            restore_idx = new_ids.index(target_id) if target_id in new_ids else 0
            self._win._test_plan_view._plan_combo.setCurrentIndex(restore_idx)
        self._win._test_plan_view._plan_combo.blockSignals(False)
        # 手动加载选中计划的任务
        if all_plans:
            plan_id = all_plans[restore_idx].id
            if plan_id is None:
                return
            tasks = ctrl.test_plan_service.get_tasks(plan_id)
            max_day = max((t.start_day + t.duration for t in tasks), default=30)

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

            self._win._test_plan_view.refresh(
                tasks, max_day, technician_map, result_map,
                start_date=all_plans[restore_idx].start_date,
                matrix_results=matrix_results,
                sample_map=sample_map,
            )

    def _refresh_issues(self) -> None:
        """刷新 Issue 追踪视图。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        filter_project_id = self._get_filter_project_id()
        if filter_project_id:
            all_issues = ctrl.issue_service.get_by_project(filter_project_id)
        else:
            all_issues = ctrl.issue_service.list_all()
        self._win._issue_view.refresh(all_issues)

    def _refresh_equipment(self) -> None:
        """刷新设备管理视图。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        all_equipment = ctrl.equipment_service.list_all()
        self._win._equipment_view.refresh(all_equipment)

    def _refresh_technicians(self) -> None:
        """刷新技术员管理视图。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.technician_service:
            return
        all_technicians = ctrl.technician_service.list_all()
        self._win._technician_view.refresh(all_technicians)

    def _refresh_knowledge(self) -> None:
        """刷新知识库视图。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        all_knowledge = ctrl.knowledge_service.list_all()
        self._win._knowledge_view.refresh(all_knowledge)

    def _refresh_undo_state(self) -> None:
        """更新撤销/重做按钮状态。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.undo_manager:
            return
        self._win._act_undo.setEnabled(ctrl.undo_manager.can_undo())
        self._win._act_redo.setEnabled(ctrl.undo_manager.can_redo())
        if ctrl.undo_manager.undo_description():
            self._win._act_undo.setText(f"↩ {ctrl.undo_manager.undo_description()}")
        if ctrl.undo_manager.redo_description():
            self._win._act_redo.setText(f"↪ {ctrl.undo_manager.redo_description()}")
