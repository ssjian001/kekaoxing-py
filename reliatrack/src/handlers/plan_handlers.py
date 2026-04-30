"""Test plan & task handlers — scheduling, CRUD, batch import, result recording."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
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
from src.services.undo_manager import BatchScheduleCommand, MoveTaskCommand

if TYPE_CHECKING:
    from main import MainWindow


class PlanHandlers:
    """Handles test plan & task operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def _on_auto_schedule(self) -> None:
        """弹出排程参数配置弹窗，然后执行自动排程。"""
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
            return

        config = dlg.get_config()

        self._win.statusBar().showMessage("正在排程...", 0)

        try:
            # 排程前记录所有任务的 start_day
            old_start_days: dict[int, int] = {}
            if ctrl.test_tasks:
                for task in ctrl.test_tasks.get_by_plan(plan_id):
                    if task.id is not None:
                        old_start_days[task.id] = task.start_day

            # 执行排程（内部会写回 DB）
            report = ctrl.scheduler_service.auto_schedule(
                plan_id,
                skip_weekends=config["skip_weekends"],
                lock_existing=config["lock_existing"],
                deadline=config["deadline"],
                equipment_capacity=config["equipment_capacity"],
            )

            # 排程后重新读取，计算 diff
            changes: list[tuple[int, int, int]] = []
            if ctrl.test_tasks:
                for task in ctrl.test_tasks.get_by_plan(plan_id):
                    if task.id is not None:
                        old_day = old_start_days.get(task.id, 0)
                        new_day = task.start_day
                        if old_day != new_day:
                            changes.append((task.id, old_day, new_day))

            # 用 BatchScheduleCommand 包装写回操作（支持撤销/重做）
            if changes and ctrl.test_tasks:
                ctrl.undo_manager.execute(
                    BatchScheduleCommand(ctrl.test_tasks, changes)
                )

            msg = (
                f"排程完成：{report['task_count']} 个任务，"
                f"总工期 {report['total_days']} 天，"
                f"更新 {report['updated_count']} 个任务"
            )
            self._win.statusBar().showMessage(msg, 10000)
            if report.get("suggestions"):
                for s in report["suggestions"][:2]:
                    print(f"[Schedule] {s}")
        except Exception as e:
            self._win.statusBar().showMessage(f"排程失败: {e}", 10000)

        # 刷新视图
        self._win._ctrl.notify_data_changed("task")

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
                    svc.create_task(
                        plan_id=plan_id,
                        name=name,
                        category=data.get("category") or "",
                        test_standard=data.get("test_standard") or "",
                        duration=int(data.get("duration") or 1),
                        priority=int(data.get("priority") or 3),
                        temperature=data.get("temperature") or "",
                        humidity=data.get("humidity") or "",
                        notes=data.get("notes") or "",
                    )
                    success += 1
                except Exception:
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
        if dlg.was_imported():
            self._win._ctrl.notify_data_changed("task")
            self._win.statusBar().showMessage("测试任务导入完成", 5000)

    def _on_plan_add(self) -> None:
        """新建测试计划。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service or not ctrl.project_service:
            return
        project_list = ctrl.project_service.list_all()
        default_project_id = self._win._project_filter_combo.currentData()
        dlg = PlanEditDialog(
            plan=None,
            project_list=project_list,
            default_project_id=default_project_id,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                # 从 data 中提取用于 create_plan 的参数
                kwargs = {k: v for k, v in data.items() if k != "id"}
                # project_id 为 0 表示未选择项目，弹出提示
                if kwargs.get("project_id") == 0:
                    QMessageBox.warning(self._win, "校验失败", "请选择关联项目后再创建计划。")
                    return
                ctrl.test_plan_service.create_plan(**kwargs)
                self._win.statusBar().showMessage(
                    f"✅ 计划「{data['name']}」已创建", 5000
                )
                self._win._ctrl.notify_data_changed("plan")
            except Exception as e:
                QMessageBox.critical(self._win, "创建失败", f"保存失败: {e}")

    def _on_plan_edit(self) -> None:
        """编辑当前选中的测试计划。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self._win.statusBar().showMessage("⚠️ 请先选中一个测试计划", 5000)
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
            plan_id_from_data = data.pop("id", None)
            if plan_id_from_data is None:
                return
            try:
                ctrl.test_plan_service.update_plan(plan_id_from_data, **data)
                self._win.statusBar().showMessage(
                    f"✅ 计划「{data['name']}」已更新", 5000
                )
                self._win._ctrl.notify_data_changed("plan")
            except Exception as e:
                QMessageBox.critical(self._win, "更新失败", f"保存失败: {e}")

    def _on_plan_changed(self, index: int) -> None:
        """切换测试计划时刷新任务列表。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._win._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            return
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        max_day = max((t.start_day + t.duration for t in tasks), default=30)

        # 构建技术员映射
        technician_map: dict[int, str] = {}
        if ctrl.technicians:
            for t in ctrl.technicians.list_all():
                if t.id is not None:
                    technician_map[t.id] = t.name

        # 构建通过率映射
        result_map: dict[int, tuple[int, int]] = {}
        if ctrl.test_results:
            for task in tasks:
                if task.id is not None:
                    results = ctrl.test_plan_service.get_task_results(task.id)
                    total = len(results)
                    pass_count = sum(1 for r in results if r.result == "pass")
                    if total > 0:
                        result_map[task.id] = (pass_count, total)

        self._win._test_plan_view.refresh(tasks, max_day, technician_map, result_map)

    def _get_project_samples(self, ctrl: object) -> list:
        """获取当前项目下的样品列表。"""
        from src.controllers.app_controller import AppController

        assert isinstance(ctrl, AppController)
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
            self._win.statusBar().showMessage("⚠️ 没有测试计划，请先创建计划", 5000)
            return
        current_tasks = ctrl.test_plan_service.get_tasks(plan_id)
        sample_list = self._get_project_samples(ctrl)
        dlg = TaskEditDialog(
            task=None,
            equipment_list=ctrl.equipment.list_all() if ctrl.equipment else [],
            technician_list=[],
            all_tasks=current_tasks,
            sample_list=sample_list,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            ctrl.test_plan_service.create_task(plan_id, **data)
            self._win.statusBar().showMessage(
                f"✅ 任务「{data['name']}」已创建", 5000
            )
            self._win._ctrl.notify_data_changed("task")

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
            technician_list=[],
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
            ctrl.test_plan_service.update_task(task.id, **data)
            self._win.statusBar().showMessage(
                f"✅ 任务「{data['name']}」已更新", 5000
            )
            self._win._ctrl.notify_data_changed("task")

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
        dlg.setMinimumSize(560, 400)
        dlg.setSizeGripEnabled(True)
        layout = QVBoxLayout(dlg)
        result_widget = TestResultDialog(
            task=task,
            samples=samples,
            existing_results=existing_results,
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
            for item in all_data:
                if item["sample_id"] is not None:
                    ctrl.test_plan_service.save_result(
                        task_id=task.id,
                        sample_id=item["sample_id"],
                        result=item["result"],
                        test_date=item["test_date"],
                        notes=item.get("notes", ""),
                    )
                    saved += 1
            self._win.statusBar().showMessage(
                f"✅ 已保存 {saved} 条测试结果（任务: {task.name}）", 5000
            )
            self._win._ctrl.notify_data_changed("task")

    def _on_task_delete(self, task) -> None:
        """删除测试任务。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        name = task.name
        ctrl.test_plan_service.delete_task(task.id)
        self._win.statusBar().showMessage(f"✅ 任务「{name}」已删除", 5000)
        self._win._ctrl.notify_data_changed("task")

    def _on_task_status_advance(self, task: object, new_status: str) -> None:
        """一键推进任务状态 — 自动填日期和进度。

        Args:
            task: TestTask 对象。
            new_status: 目标状态 ("in_progress" 或 "completed")。
        """
        from src.models.test_plan import TestTask
        from datetime import date as _date

        assert isinstance(task, TestTask)
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

        try:
            ctrl.test_plan_service.update_task(task.id, **updates)
            self._win.statusBar().showMessage(
                f"✅ 任务「{task.name}」已标记为{status_label}", 5000
            )
            self._win._ctrl.notify_data_changed("task")
        except Exception as e:
            QMessageBox.critical(self._win, "操作失败", f"状态更新失败: {e}")
