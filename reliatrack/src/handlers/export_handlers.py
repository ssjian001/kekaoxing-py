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

    def _get_issues(self, ctrl, project_id: int | None):
        """按项目获取 Issue，None 或 0 则返回全部。"""
        if project_id:
            return ctrl.issue_service.get_by_project(project_id)
        return ctrl.issue_service.list_all()

    def _get_samples(self, ctrl, project_id: int | None):
        """按项目获取样品，None 或 0 则返回全部。"""
        if project_id:
            return ctrl.sample_service.get_by_project(project_id)
        return ctrl.sample_service.list_all()

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
        # 构建项目列表供筛选
        project_list: list[tuple[int, str]] = []
        if ctrl.project_service:
            try:
                for p in ctrl.project_service.list_all():
                    if p.id is not None:
                        project_list.append((p.id, p.name))
            except Exception:
                pass
        dlg = ExportDialog(parent=self._win, projects=project_list)
        if not dlg.exec():
            return
        data = dlg.get_data()
        content = data["content"]
        fmt = data["format"]
        project_id = data.get("project_id")  # None = 全部

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
                        self._get_issues(ctrl, project_id),
                        self._get_samples(ctrl, project_id),
                    )
                else:
                    path = svc.export_report_pdf(
                        plan,
                        tasks,
                        self._get_issues(ctrl, project_id),
                        self._get_samples(ctrl, project_id),
                    )
                self._win.toast(f"已导出: {path}", "success")

            elif "Issue" in content:
                issues = self._get_issues(ctrl, project_id)
                if not issues:
                    self._win.toast("没有 Issue 数据", "info")
                    return
                # Build fa_map and capa_map
                fa_map = {}
                capa_map = {}
                for issue in issues:
                    if issue.id is not None:
                        fa_map[issue.id] = ctrl.issue_service.get_fa_records(issue.id)
                        capa_map[issue.id] = ctrl.issue_service.get_capa_records(issue.id)
                path = svc.export_issues_excel(issues, fa_map=fa_map, capa_map=capa_map)
                self._win.toast(f"已导出: {path}", "success")

            elif "样品" in content:
                samples = self._get_samples(ctrl, project_id)
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
                        self._get_issues(ctrl, project_id),
                        self._get_samples(ctrl, project_id),
                    )
                else:
                    path = svc.export_report_pdf(
                        plan,
                        tasks,
                        self._get_issues(ctrl, project_id),
                        self._get_samples(ctrl, project_id),
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
                issues = self._get_issues(ctrl, project_id)
                samples = self._get_samples(ctrl, project_id)
                if "Excel" in fmt:
                    path = svc.export_dvpr_excel(plan, tasks, results, issues, samples)
                elif "Word" in fmt:
                    path = svc.export_dvpr_docx(plan, tasks, results, issues, samples)
                else:
                    path = svc.export_dvpr_pdf(plan, tasks, results, issues, samples)
                self._win.toast(f"DVP&R 已导出: {path}", "success")

            elif "8D" in content:
                issue_id = self._win._issue_view.get_selected_issue_id()
                if issue_id is None:
                    self._win.toast("请先选中一个 Issue", "info")
                    return
                issue = ctrl.issue_service.get(issue_id)
                if not issue:
                    self._win.toast("未找到该 Issue", "info")
                    return

                # 格式选择
                fmt = QMessageBox.question(
                    self._win, "导出格式",
                    "选择导出格式：\n\n"
                    "「是」= PDF\n「否」= Word (.docx)\n「取消」= 放弃",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                )
                if fmt == QMessageBox.StandardButton.Cancel:
                    return

                fa_records = ctrl.issue_service.get_fa_records(issue_id)
                capa_records = ctrl.issue_service.get_capa_records(issue_id)
                if fmt == QMessageBox.StandardButton.Yes:
                    path = svc.export_8d_pdf(issue, fa_records, capa_records)
                else:
                    path = svc.export_8d_docx(issue, fa_records, capa_records)
                self._win.toast(f"8D 报告已导出: {path}", "success")

        except Exception as e:
            import traceback

            traceback.print_exc()
            QMessageBox.critical(self._win, "导出失败", f"导出时发生错误:\n{e}")