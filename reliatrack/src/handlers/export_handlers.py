"""Export handler — exports test tasks, issues, samples, and comprehensive reports."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.views.dialogs.export_dialog import ExportDialog

if TYPE_CHECKING:
    from main import MainWindow
    from src.services.export_service import ExportService

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ExportHandlers:
    """Handles data export operations triggered from the UI.

    使用 dispatch table 替代 6×3 的 if-elif 链。
    每个内容类型对应一个 _export_<type> 方法。
    """

    def __init__(self, win: MainWindow) -> None:
        self._win = win
        # 内容类型 → 处理方法 的 dispatch 表
        self._export_dispatch: dict[str, Callable] = {
            "测试任务": self._export_tasks,
            "Issue": self._export_issues,
            "样品": self._export_samples,
            "综合": self._export_comprehensive,
            "DVP&R": self._export_dvpr,
            "8D": self._export_8d,
        }

    # ── 共享辅助 ────────────────────────────────────────────────────

    def _get_svc(self, ctrl, export_dir: str) -> "ExportService":
        """获取或创建导出服务。"""
        svc = ctrl.export_service
        if svc is None:
            from src.services.export import ExportService
            svc = ExportService(output_dir=export_dir)
        else:
            svc._output_dir = Path(export_dir)
        return svc

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

    def _get_export_dir(self) -> str:
        """确保导出目录存在并返回路径。"""
        export_dir = os.path.join(_PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir

    # ── 各内容类型导出方法 ──────────────────────────────────────────

    def _export_tasks(self, ctrl, svc, fmt: str, project_id: int | None) -> str:
        """导出测试任务。"""
        plan_id = self._win.test_plan_view.get_selected_plan_id()
        if plan_id is None:
            raise ValueError("没有选中测试计划")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan or not tasks:
            raise ValueError("当前计划没有任务")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []

        if "Excel" in fmt:
            tech_names = {}
            if ctrl.technicians:
                for tech in ctrl.technicians.list_all():
                    if tech.id is not None:
                        tech_names[tech.id] = tech.name
            return svc.export_tasks_excel(plan, tasks, results=results, technician_names=tech_names)
        elif "Word" in fmt:
            return svc.export_to_word(plan, tasks, self._get_issues(ctrl, project_id),
                                      self._get_samples(ctrl, project_id), results=results)
        else:
            return svc.export_report_pdf(plan, tasks, self._get_issues(ctrl, project_id),
                                         self._get_samples(ctrl, project_id), results=results)

    def _export_issues(self, ctrl, svc, fmt: str, project_id: int | None) -> str:
        """导出 Issue 列表。"""
        if "Excel" not in fmt:
            raise ValueError("Issue 导出暂只支持 Excel 格式")
        issues = self._get_issues(ctrl, project_id)
        if not issues:
            raise ValueError("没有 Issue 数据")
        fa_map = {}
        capa_map = {}
        for issue in issues:
            if issue.id is not None:
                fa_map[issue.id] = ctrl.issue_service.get_fa_records(issue.id)
                capa_map[issue.id] = ctrl.issue_service.get_capa_records(issue.id)
        return svc.export_issues_excel(issues, fa_map=fa_map, capa_map=capa_map)

    def _export_samples(self, ctrl, svc, fmt: str, project_id: int | None) -> str:
        """导出样品台账。"""
        if "Excel" not in fmt:
            raise ValueError("样品导出暂只支持 Excel 格式")
        samples = self._get_samples(ctrl, project_id)
        if not samples:
            raise ValueError("没有样品数据")
        return svc.export_samples_excel(samples)

    def _export_comprehensive(self, ctrl, svc, fmt: str, project_id: int | None) -> str:
        """导出综合报告。"""
        plan_id = self._win.test_plan_view.get_selected_plan_id()
        if plan_id is None:
            raise ValueError("没有选中测试计划")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan:
            raise ValueError("未找到该测试计划")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []

        if "Word" in fmt:
            return svc.export_to_word(plan, tasks, self._get_issues(ctrl, project_id),
                                      self._get_samples(ctrl, project_id), results=results)
        else:
            return svc.export_report_pdf(plan, tasks, self._get_issues(ctrl, project_id),
                                         self._get_samples(ctrl, project_id), results=results)

    def _export_dvpr(self, ctrl, svc, fmt: str, project_id: int | None) -> str:
        """导出 DVP&R 报告。"""
        plan_id = self._win.test_plan_view.get_selected_plan_id()
        if plan_id is None:
            raise ValueError("没有选中测试计划")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan or not tasks:
            raise ValueError("当前计划没有任务")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []
        issues = self._get_issues(ctrl, project_id)
        samples = self._get_samples(ctrl, project_id)

        if "Excel" in fmt:
            return svc.export_dvpr_excel(plan, tasks, results, issues, samples)
        elif "Word" in fmt:
            return svc.export_dvpr_docx(plan, tasks, results, issues, samples)
        else:
            return svc.export_dvpr_pdf(plan, tasks, results, issues, samples)

    def _export_8d(self, ctrl, svc, fmt: str, project_id: int | None) -> str:
        """导出 8D 报告。"""
        issue_id = self._win.issue_view.get_selected_issue_id()
        if issue_id is None:
            raise ValueError("请先选中一个 Issue")
        issue = ctrl.issue_service.get(issue_id)
        if not issue:
            raise ValueError("未找到该 Issue")

        fa_records = ctrl.issue_service.get_fa_records(issue_id)
        capa_records = ctrl.issue_service.get_capa_records(issue_id)

        _task = ctrl.test_plan_service.get_task(issue.task_id) if issue.task_id else None
        _sample_sn = ""
        if issue.sample_id and ctrl.sample_service:
            s = ctrl.sample_service.get(issue.sample_id)
            if s:
                _sample_sn = s.sn or ""
        _tech_name = ""
        if issue.assignee_id and ctrl.technicians:
            for t in ctrl.technicians.list_all():
                if t.id == issue.assignee_id:
                    _tech_name = t.name
                    break

        if "Excel" in fmt:
            raise ValueError("8D 报告暂不支持 Excel 格式，请选 PDF 或 Word")
        elif "Word" in fmt:
            return svc.export_8d_docx(issue, fa_records, capa_records,
                                      technician_name=_tech_name, task=_task, sample_sn=_sample_sn)
        else:
            return svc.export_8d_pdf(issue, fa_records, capa_records,
                                     technician_name=_tech_name, task=_task, sample_sn=_sample_sn)

    # ── 统一入口 ────────────────────────────────────────────────────

    def _on_export(self) -> None:
        """导出数据 — dispatch 到对应内容类型处理方法。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.test_plan_service or not ctrl.issue_service or not ctrl.sample_service:
            return

        # 构建项目列表供筛选
        project_list: list[tuple[int, str]] = []
        if ctrl.project_service:
            try:
                for p in ctrl.project_service.list_all():
                    if p.id is not None:
                        project_list.append((p.id, p.name))
            except Exception:
                logger.exception("Failed to load project list for export dialog")

        dlg = ExportDialog(parent=self._win, projects=project_list)
        if not dlg.exec():
            dlg.deleteLater()
            return
        dlg.deleteLater()

        data = dlg.get_data()
        content = data["content"]
        fmt = data["format"]
        project_id = data.get("project_id")

        # 综合报告降级
        if "综合" in content and "Excel" in fmt:
            fmt = "PDF (.pdf)"
            self._win.toast("综合报告暂不支持 Excel，已自动切换为 PDF", "info")

        # dispatch 到对应处理方法
        handler = self._export_dispatch.get(content)
        if handler is None:
            self._win.toast(f"不支持的导出类型: {content}", "error")
            return

        export_dir = self._get_export_dir()
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            svc = self._get_svc(ctrl, export_dir)
            path = handler(ctrl, svc, fmt, project_id)
            self._win.toast(f"已导出: {path}", "success")
        except ValueError as e:
            self._win.toast(str(e), "info")
        except Exception as e:
            logger.exception("Export failed")
            QMessageBox.critical(self._win, "导出失败", f"导出时发生错误:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()