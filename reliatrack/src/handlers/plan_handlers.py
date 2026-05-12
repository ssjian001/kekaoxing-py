"""Test plan & task handlers — scheduling, CRUD, batch import, result recording."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.views.dialogs.schedule_config_dialog import ScheduleConfigDialog
from src.views.dialogs.plan_edit_dialog import PlanEditDialog
from src.views.dialogs.task_dialog import TaskEditDialog
from src.views.dialogs.test_result_dialog import TestResultDialog
from src.views.dialogs.batch_import_dialog import BatchImportDialog
from src.handlers.crud_helpers import exec_crud
from src.services.undo_manager import BatchScheduleCommand, MoveTaskCommand

if TYPE_CHECKING:
    from main import MainWindow

logger = logging.getLogger(__name__)


class PlanHandlers:
    """Handles test plan & task operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win._test_plan_view
        v.btn_schedule.clicked.connect(self._on_auto_schedule)
        v.task_moved.connect(self._on_gantt_task_moved)
        v.btn_add_plan.clicked.connect(self._on_plan_add)
        v.btn_edit_plan.clicked.connect(self._on_plan_edit)
        v._plan_combo.currentIndexChanged.connect(self._on_plan_changed)
        v.btn_import_tasks.clicked.connect(self._on_task_batch_import)
        v.btn_import_from_plan.clicked.connect(self._on_import_from_plan)
        v.btn_record_result.clicked.connect(self._on_record_result)
        v.btn_summary_report.clicked.connect(self._on_summary_report)
        v.setup_task_callbacks(
            on_add=self._on_task_add,
            on_edit=self._on_task_edit,
            on_delete=self._on_task_delete,
            on_status_advance=self._on_task_status_advance,
        )

    def _on_auto_schedule(self) -> None:
        """弹出排程参数配置弹窗 → 预览 → 用户确认后写 DB。

        流程：
        1. ScheduleConfigDialog 配置参数
        2. preview_schedule 预览（不写 DB）
        3. SchedulePreviewDialog 展示预览 + 允许手动调整
        4. 用户确认 → apply_schedule 写 DB + undo
        5. 用户重新排程 → 带 user_locked_days 重跑预览
        """
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.scheduler_service:
            return

        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.statusBar().showMessage("请先创建并选择测试计划", 5000)
            return

        # -- 弹出参数配置弹窗 --
        equipment_list = (
            ctrl.equipment_service.list_all()
            if ctrl.equipment_service
            else []
        )
        dlg = ScheduleConfigDialog(
            equipment_list=equipment_list,
            parent=self._win,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            dlg.deleteLater()
            return
        dlg.deleteLater()

        config = dlg.get_config()
        user_locked_days: dict[int, int] = {}

        # -- 预览循环（支持重新排程） --
        while True:
            self._win.statusBar().showMessage("正在计算排程...", 0)

            try:
                preview_data = ctrl.scheduler_service.preview_schedule(
                    plan_id,
                    skip_weekends=config["skip_weekends"],
                    skip_holidays=config["skip_holidays"],
                    lock_existing=config["lock_existing"],
                    deadline=config["deadline"],
                    equipment_capacity=config["equipment_capacity"],
                    user_locked_days=user_locked_days or None,
                )
            except Exception as e:
                self._win.statusBar().showMessage(f"排程失败: {e}", 10000)
                return

            report = preview_data.get("report", {})
            if report.get("task_count", 0) == 0:
                self._win.statusBar().showMessage("没有待排程的任务", 5000)
                return

            # 弹出预览对话框
            from src.views.dialogs.schedule_preview_dialog import SchedulePreviewDialog
            preview_dlg = SchedulePreviewDialog(
                preview_data, config, parent=self._win,
            )
            result = preview_dlg.exec()
            preview_dlg.deleteLater()

            if result == QDialog.DialogCode.Accepted:
                # 用户确认应用
                changes = preview_dlg.get_changes()
                if changes:
                    # 记录原始 start_day 用于 undo
                    old_start_days: dict[int, int] = {}
                    if ctrl.test_tasks:
                        for task in ctrl.test_tasks.get_by_plan(plan_id):
                            if task.id is not None:
                                old_start_days[task.id] = task.start_day

                    # undo_changes: (task_id, old_start_day, new_start_day)
                    undo_changes = [
                        (tid, old_start_days.get(tid, 0), new_day)
                        for tid, new_day in changes
                    ]
                    if undo_changes and ctrl.test_tasks:
                        # Command.do() 统一写入 DB，不再调 apply_schedule
                        ctrl.undo_manager.execute(
                            BatchScheduleCommand(ctrl.test_tasks, undo_changes)
                        )

                    msg = (
                        f"排程完成：{report['task_count']} 个任务，"
                        f"总工期 {report['total_days']} 天，"
                        f"更新 {len(changes)} 个任务"
                    )
                    self._win.statusBar().showMessage(msg, 10000)
                else:
                    self._win.statusBar().showMessage("排程预览：无变更", 5000)

                # 刷新视图
                self._win._ctrl.notify_data_changed("task")
                return

            elif result == 2:
                # 重新排程 — 获取用户手动锁定
                user_locked_days = preview_dlg.get_user_locked_days()
                continue

            else:
                # 取消
                self._win.statusBar().showMessage("排程已取消", 3000)
                return

    def _on_gantt_task_moved(self, task_id: int, new_start_day: int) -> None:
        """甘特图拖拽移动任务后，写回数据库并注册撤销。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_tasks:
            return
        # 读取旧值
        task = ctrl.test_tasks.get_by_id(task_id)
        if task is None:
            return
        old_day = task.start_day
        if old_day == new_start_day:
            return
        # 用 UndoManager 包装
        ctrl.undo_manager.execute(
            MoveTaskCommand(ctrl.test_tasks, task_id, old_day, new_start_day)
        )
        self._win._ctrl.notify_data_changed("task")

    def _on_import_from_plan(self) -> None:
        """从同项目其他计划导入任务。"""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QInputDialog
        from src.views.dialogs.import_tasks_from_plan_dialog import ImportTasksFromPlanDialog

        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return

        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.statusBar().showMessage("请先创建并选择测试计划", 5000)
            return

        plan = ctrl.test_plan_service.get_plan(plan_id)
        if not plan:
            return

        # 获取同项目下其他计划
        all_plans = ctrl.test_plan_service.get_plans_by_project(plan.project_id)
        other_plans = [p for p in all_plans if p.id != plan_id and p.id is not None]

        if not other_plans:
            self._win.toast("当前项目下没有其他测试计划可导入", "info")
            return

        # 选择来源计划
        plan_names = [p.name for p in other_plans]
        choice, ok = QInputDialog.getItem(
            self._win, "选择来源计划",
            f"从以下计划导入任务到「{plan.name}」：",
            plan_names, 0, False,
        )
        if not ok or not choice:
            return

        source_plan = other_plans[plan_names.index(choice)]
        source_tasks = ctrl.test_plan_service.get_tasks(source_plan.id)

        if not source_tasks:
            self._win.toast(f"计划「{source_plan.name}」没有任务", "info")
            return

        # 勾选任务弹窗
        dlg = ImportTasksFromPlanDialog(
            tasks=source_tasks,
            source_plan_name=source_plan.name,
            parent=self._win,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.get_selected_tasks()
            if not selected:
                dlg.deleteLater()
                return
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                count = ctrl.test_plan_service.import_tasks_from_plan(plan_id, selected)
                self._win.statusBar().showMessage(
                    f"已从「{source_plan.name}」导入 {count} 个任务", 5000
                )
                ctrl.notify_data_changed("task")
            except Exception as e:
                QMessageBox.critical(self._win, "导入失败", str(e))
            finally:
                QApplication.restoreOverrideCursor()
        dlg.deleteLater()

    def _on_task_batch_import(self) -> None:
        """测试任务批量导入。"""
        ctrl = self._win._ctrl
        if ctrl is None or ctrl.test_plan_service is None:
            return

        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.statusBar().showMessage("请先创建并选择测试计划", 5000)
            return

        svc = ctrl.test_plan_service

        def _do_import(task_list: list[dict]) -> tuple[int, int]:
            """执行批量导入，返回 (成功数, 跳过数)。"""
            success = 0
            skip = 0
            for data in task_list:
                name = data.get("name", "").strip()
                if not name:
                    continue
                try:
                    ctrl.test_plan_service.create_task(
                        plan_id=plan_id,
                        name=data.get("name", "").strip(),
                        category=data.get("category", "").strip(),
                        test_standard=data.get("test_standard") or "",
                        duration=int(data.get("duration") or 1),
                        priority=int(data.get("priority") or 3),
                        temperature=data.get("temperature") or "",
                        humidity=data.get("humidity") or "",
                        notes=data.get("notes") or "",
                    )
                    success += 1
                except Exception:
                    task_name = data.get("name", "?")
                    logger.exception("Failed to import task name=%s: data=%s", task_name, data)
                    skip += 1
            return success, skip

        task_field_map = [
            ("任务名称（必填）", "name"),
            ("测试类别", "category"),
            ("测试标准", "test_standard"),
            ("工期(天)", "duration"),
            ("优先级(1-3)", "priority"),
            ("温度范围", "temperature"),
            ("湿度范围", "humidity"),
            ("备注", "notes"),
        ]
        task_guess_keywords = {
            "name": ["name", "名称", "任务", "任务名", "测试项", "测试名称", "test"],
            "category": ["category", "类别", "分类", "测试类别", "类型", "type"],
            "test_standard": ["standard", "标准", "测试标准", "条款", "spec"],
            "duration": ["duration", "工期", "天数", "周期", "day"],
            "priority": ["priority", "优先级", "优先", "pri"],
            "temperature": ["temp", "温度", "temperature"],
            "humidity": ["humidity", "湿度", "rh"],
            "notes": ["notes", "备注", "说明", "remark"],
        }

        dlg = BatchImportDialog(
            parent=self._win,
            on_import=_do_import,
            title="导入测试任务",
            field_map=task_field_map,
            required_fields=["name"],
            guess_keywords=task_guess_keywords,
            result_msg_labels=("成功导入", "导入失败"),
        )
        dlg.exec()
        dlg.deleteLater()
        if dlg.was_imported():
            self._win._ctrl.notify_data_changed("task")
            self._win.statusBar().showMessage("测试任务导入完成", 5000)

    def _on_plan_add(self) -> None:
        """新建测试计划。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service or not ctrl.project_service:
            return
        project_list = ctrl.project_service.list_all()
        default_project_id = self._win.get_project_filter_id()
        dlg = PlanEditDialog(
            plan=None,
            project_list=project_list,
            default_project_id=default_project_id,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            kwargs = {k: v for k, v in data.items() if k != "id"}
            # project_id 为 0 表示未选择项目，弹出提示
            if kwargs.get("project_id") == 0:
                QMessageBox.warning(self._win, "校验失败", "请选择关联项目后再创建计划。")
                dlg.deleteLater()
                return
            exec_crud(
                win=self._win,
                action=ctrl.test_plan_service.create_plan,
                action_kwargs=kwargs,
                toast_msg=f"计划「{data['name']}」已创建",
                entity="plan",
                error_title="创建失败",
            )
        dlg.deleteLater()

    def _on_plan_edit(self) -> None:
        """编辑当前选中的测试计划。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.toast("请先选中一个测试计划", "info")
            return
        plan = ctrl.test_plan_service.get_plan(plan_id)
        if plan is None:
            return
        project_list = ctrl.project_service.list_all() if ctrl.project_service else []
        dlg = PlanEditDialog(
            plan=plan,
            project_list=project_list,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            plan_id_from_data = data.get("id")
            if plan_id_from_data is None:
                dlg.deleteLater()
                return
            update_data = {k: v for k, v in data.items() if k != "id"}
            exec_crud(
                win=self._win,
                action=ctrl.test_plan_service.update_plan,
                action_args=(plan_id_from_data,),
                action_kwargs=update_data,
                toast_msg=f"计划「{data['name']}」已更新",
                entity="plan",
                error_title="更新失败",
            )
        dlg.deleteLater()

    def _on_plan_changed(self, index: int) -> None:
        """切换测试计划时刷新任务列表。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            return
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        max_day = max((t.start_day + t.duration for t in tasks), default=30)

        # 构建技术员映射
        technician_map: dict[int, str] = {}
        if ctrl.technician_service:
            for t in ctrl.technician_service.list_all():
                if t.id is not None:
                    technician_map[t.id] = t.name

        # 批量获取通过率映射
        result_map: dict[int, tuple[int, int]] = {}
        task_ids = [t.id for t in tasks if t.id is not None]
        if task_ids:
            result_map = ctrl.test_plan_service.get_pass_counts_by_tasks(task_ids)

        # 获取结果矩阵数据
        matrix_results = []
        sample_map: dict[int, str] = {}
        if task_ids and ctrl.sample_service:
            matrix_results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids)
            # 从结果和任务中收集 sample_id → sn
            seen_sids: set[int] = set()
            for r in matrix_results:
                if r.sample_id and r.sample_id not in seen_sids:
                    s = ctrl.sample_service.get(r.sample_id)
                    if s:
                        sample_map[r.sample_id] = s.sn
                    seen_sids.add(r.sample_id)

        # 获取 Issue 数据（用于失效模式分析）
        issues = []
        if ctrl.issue_service and plan.project_id:
            issues = [
                iss for iss in ctrl.issue_service.get_by_project(plan.project_id)
                if not iss.is_deleted and iss.plan_id == plan_id
            ]

        self._win._test_plan_view.refresh(
            tasks, max_day, technician_map, result_map,
            start_date=plan.start_date if plan else "",
            matrix_results=matrix_results,
            sample_map=sample_map,
            issues=issues,
        )

    def _get_project_samples(self, ctrl: object) -> list:
        """获取当前项目下的样品列表。"""
        from src.controllers.app_controller import AppController

        if not isinstance(ctrl, AppController):
            return []
        if not ctrl.test_plan_service or not ctrl.sample_service:
            return []
        # 从当前计划获取 project_id
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            return []
        plan = ctrl.test_plan_service.get_plan(plan_id)
        if plan is None:
            return []
        project_id = plan.project_id
        if not project_id:
            return []
        return ctrl.sample_service.get_by_project(project_id)

    def _on_task_add(self) -> None:
        """新建测试任务。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.toast("没有测试计划，请先创建计划", "info")
            return
        current_tasks = ctrl.test_plan_service.get_tasks(plan_id)
        sample_list = self._get_project_samples(ctrl)
        dlg = TaskEditDialog(
            task=None,
            equipment_list=ctrl.equipment.list_all() if ctrl.equipment else [],
            technician_list=ctrl.technicians.list_all() if ctrl.technicians else [],
            all_tasks=current_tasks,
            sample_list=sample_list,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            exec_crud(
                win=self._win,
                action=ctrl.test_plan_service.create_task,
                action_args=(plan_id,),
                action_kwargs=data,
                toast_msg=f"任务「{data['name']}」已创建",
                entity="task",
                error_title="创建失败",
            )
        dlg.deleteLater()

    def _on_task_edit(self, task) -> None:
        """编辑测试任务。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            return
        current_tasks = ctrl.test_plan_service.get_tasks(plan_id)
        sample_list = self._get_project_samples(ctrl)
        dlg = TaskEditDialog(
            task=task,
            equipment_list=ctrl.equipment.list_all() if ctrl.equipment else [],
            technician_list=ctrl.technicians.list_all() if ctrl.technicians else [],
            all_tasks=current_tasks,
            sample_list=sample_list,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            # 自动记录实际日期
            from datetime import date as _date
            today = _date.today().isoformat()
            new_status = data.get("status", "")
            if new_status == "in_progress" and not data.get("actual_start_date"):
                data["actual_start_date"] = today
            if new_status == "completed" and not data.get("actual_end_date"):
                data["actual_end_date"] = today
                data["progress"] = 100.0
            exec_crud(
                win=self._win,
                action=ctrl.test_plan_service.update_task,
                action_args=(task.id,),
                action_kwargs=data,
                toast_msg=f"任务「{data['name']}」已更新",
                entity="task",
                error_title="更新失败",
            )
        dlg.deleteLater()

    def _on_record_result(self) -> None:
        """录入测试结果 — 选中任务后打开结果录入弹窗。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        task = self._win._test_plan_view._task_table.get_task_at_row(
            self._win._test_plan_view._task_table.currentRow()
        )
        if not task or task.id is None:
            QMessageBox.information(self._win, "提示", "请先选中一个测试任务。")
            return

        # 解析任务关联的样品 ID
        sample_ids: list[int] = []
        try:
            sample_ids = json.loads(task.sample_ids)
        except (json.JSONDecodeError, TypeError):
            pass

        # 获取样品列表
        samples: list = []
        if sample_ids and ctrl.sample_service:
            for sid in sample_ids:
                s = ctrl.sample_service.get(sid)
                if s:
                    samples.append(s)

        # 获取已有结果
        existing_results = ctrl.test_plan_service.get_task_results(task.id)

        # 用 QDialog 包装 TestResultDialog
        dlg = QDialog(self._win)
        dlg.setWindowTitle(f"录入结果 — {task.name}")
        dlg.setMinimumSize(480, 400)
        dlg.setSizeGripEnabled(True)
        layout = QVBoxLayout(dlg)
        result_widget = TestResultDialog(
            task=task,
            samples=samples,
            existing_results=existing_results,
            technician_list=ctrl.technicians.list_all() if ctrl.technicians else [],
            parent=dlg,
        )
        layout.addWidget(result_widget)

        # 添加确定/取消按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setProperty("class", "action")
        btn_cancel.clicked.connect(dlg.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton("保存")
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        if dlg.exec():
            all_data = result_widget.get_all_data()
            saved = 0
            deleted_count = 0
            issue_count = 0
            for item in all_data:
                # 已有结果标记删除 → 删除
                if item.get("deleted") and item.get("result_id"):
                    ctrl.test_plan_service.delete_result(item["result_id"])
                    deleted_count += 1
                # 未删除且有效样品 → 保存
                elif item["sample_id"] is not None and not item.get("deleted"):
                    ctrl.test_plan_service.save_result(
                        task_id=task.id,
                        sample_id=item["sample_id"],
                        result=item["result"],
                        test_date=item["test_date"],
                        measured_value=item.get("measured_value", ""),
                        notes=item.get("notes", ""),
                        tester_id=item.get("tester_id"),
                        environment=item.get("environment", "{}"),
                    )
                    saved += 1
                    # 自动创建 Issue
                    if item.get("create_issue") and item.get("result") == "fail":
                        if ctrl.issue_service:
                            try:
                                sample_name = item.get("sample_name", "")
                                title = task.name
                                if sample_name:
                                    title += f" - {sample_name}"
                                ctrl.issue_service.create(
                                    title=title,
                                    project_id=task.project_id if hasattr(task, "project_id") else None,
                                    plan_id=task.plan_id if hasattr(task, "plan_id") else None,
                                    task_id=task.id,
                                    sample_id=item["sample_id"],
                                    failure_mode="不通过",
                                    severity="major",
                                    status="open",
                                    description=f"自动创建：测试任务「{task.name}」样品「{sample_name}」结果不通过",
                                )
                                issue_count += 1
                            except Exception:
                                pass  # 不阻断主流程
            if saved > 0 or deleted_count > 0:
                msg = f"已保存 {saved} 条测试结果（任务: {task.name}）"
                if deleted_count:
                    msg += f"，删除 {deleted_count} 条"
                if issue_count:
                    msg += f"，自动创建 {issue_count} 条 Issue"
                self._win.toast(msg, "success")
                self._win._ctrl.notify_data_changed("task")
                self._win._ctrl.notify_data_changed("issue")
        dlg.deleteLater()

    def _on_summary_report(self) -> None:
        """一键导出当前计划 Word 总结报告。"""
        import os
        from pathlib import Path
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.toast("请先选择测试计划", "info")
            return
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan or not tasks:
            self._win.toast("当前计划无任务", "info")
            return

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            task_ids = [t.id for t in tasks if t.id is not None]
            results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []
            issues = []
            if ctrl.issue_service and plan.project_id:
                issues = [
                    iss for iss in ctrl.issue_service.get_by_project(plan.project_id)
                    if not iss.is_deleted
                ]
            samples = []
            if ctrl.sample_service and plan.project_id:
                samples = ctrl.sample_service.get_by_project(plan.project_id)

            export_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "exports",
            )
            os.makedirs(export_dir, exist_ok=True)

            svc = ctrl.export_service
            if svc is None:
                from src.services.export import ExportService
                svc = ExportService(output_dir=export_dir)
            else:
                svc._output_dir = Path(export_dir)

            path = svc.export_to_word(plan, tasks, issues, samples, results=results)
            self._win.toast(f"总结报告已导出: {path}", "success")
        except Exception as e:
            logger.exception("Summary report export failed")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self._win, "导出失败", f"总结报告导出出错:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _on_task_delete(self, task) -> None:
        """删除测试任务。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        name = task.name
        cmd = ctrl.test_plan_service.create_task_delete_command(task.id)
        exec_crud(
            win=self._win,
            action=ctrl.test_plan_service.delete_task,
            action_args=(task.id,),
            toast_msg=f"任务「{name}」已删除",
            entity="task",
            error_title="删除失败",
            undo_command=cmd,
        )

    def _on_task_status_advance(self, task: object, new_status: str) -> None:
        """一键推进任务状态 — 自动填日期和进度。

        Args:
            task: TestTask 对象。
            new_status: 目标状态 ("in_progress" 或 "completed")。
        """
        from src.models.test_plan import TestTask
        from datetime import date as _date

        if not isinstance(task, TestTask):
            return
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        if task.id is None:
            return

        today = _date.today().isoformat()
        updates: dict = {"status": new_status}

        if new_status == "in_progress":
            if not task.actual_start_date:
                updates["actual_start_date"] = today
            status_label = "进行中"
        elif new_status == "completed":
            if not task.actual_end_date:
                updates["actual_end_date"] = today
            updates["progress"] = 100.0
            status_label = "已完成"
        else:
            status_label = new_status

        exec_crud(
            win=self._win,
            action=ctrl.test_plan_service.update_task,
            action_args=(task.id,),
            action_kwargs=updates,
            toast_msg=f"任务「{task.name}」已标记为{status_label}",
            entity="task",
            error_title="操作失败",
        )