"""Export handler — exports test tasks, issues, samples, and comprehensive reports."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.views.dialogs.export_dialog import ExportDialog

if TYPE_CHECKING:
    from main import MainWindow

# Project root — used to determine the export directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ExportHandlers:
    """Handles data export operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def _on_export(self) -> None:
        """导出数据。"""
        ctrl = self._win._ctrl
        if not ctrl:
            return
        if not ctrl or not ctrl.test_plan_service:
            return
        if not ctrl.issue_service:
            return
        if not ctrl.sample_service:
            return
        dlg = ExportDialog(parent=self._win)
        if not dlg.exec():
            return
        data = dlg.get_data()
        content = data["content"]
        fmt = data["format"]

        # 综合报告默认 PDF，但用户可选 Word
        # word export: 综合报告不再强制 PDF
        if "综合" in content and "Excel" in fmt:
            fmt = "PDF (.pdf)"

        # 确保导出目录
        export_dir = os.path.join(_PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)

        try:
            from src.services.export_service import ExportService

            svc = ExportService(output_dir=export_dir)

            if "测试任务" in content:
                plan_id = self._win._test_plan_view.get_selected_plan_id()
                if plan_id is None:
                    self._win.toast("没有选中测试计划", "info")
                    return
                plan = ctrl.test_plan_service.get_plan(plan_id)
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                if not plan or not tasks:
                    self._win.toast("当前计划没有任务", "info")
                    return
                if "Excel" in fmt:
                    path = svc.export_tasks_excel(plan, tasks)
                # word export: 测试任务也支持 Word 格式（综合报告）
                elif "Word" in fmt:
                    path = svc.export_to_word(
                        plan,
                        tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                else:
                    path = svc.export_report_pdf(
                        plan,
                        tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                self._win.toast(f"已导出: {path}", "success")

            elif "Issue" in content:
                issues = ctrl.issue_service.list_all()
                if not issues:
                    self._win.toast("没有 Issue 数据", "info")
                    return
                # Build fa_map
                fa_map = {}
                for issue in issues:
                    if issue.id is not None:
                        fa_map[issue.id] = ctrl.issue_service.get_fa_records(issue.id)
                path = svc.export_issues_excel(issues, fa_map=fa_map)
                self._win.toast(f"已导出: {path}", "success")

            elif "样品" in content:
                samples = ctrl.sample_service.list_all()
                if not samples:
                    self._win.toast("没有样品数据", "info")
                    return
                path = svc.export_samples_excel(samples)
                self._win.toast(f"已导出: {path}", "success")

            elif "综合" in content:
                plan_id = self._win._test_plan_view.get_selected_plan_id()
                if plan_id is None:
                    self._win.toast("没有选中测试计划", "info")
                    return
                plan = ctrl.test_plan_service.get_plan(plan_id)
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                if not plan:
                    return
                # word export: 综合报告支持 Word 格式
                if "Word" in fmt:
                    path = svc.export_to_word(
                        plan,
                        tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                else:
                    path = svc.export_report_pdf(
                        plan,
                        tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                self._win.toast(f"已导出: {path}", "success")

            elif "DVP&R" in content:
                plan_id = self._win._test_plan_view.get_selected_plan_id()
                if plan_id is None:
                    self._win.toast("没有选中测试计划", "info")
                    return
                plan = ctrl.test_plan_service.get_plan(plan_id)
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                if not plan or not tasks:
                    self._win.toast("当前计划没有任务", "info")
                    return
                task_ids = [t.id for t in tasks if t.id is not None]
                results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []
                issues = ctrl.issue_service.list_all()
                samples = ctrl.sample_service.list_all()
                path = svc.export_dvpr_pdf(plan, tasks, results, issues, samples)
                self._win.toast(f"DVP&R 已导出: {path}", "success")

        except Exception as e:
            import traceback

            traceback.print_exc()
            QMessageBox.critical(self._win, "导出失败", f"导出时发生错误:\n{e}")