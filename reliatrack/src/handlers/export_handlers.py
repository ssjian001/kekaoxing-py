"""Export handler — exports test tasks, issues, samples, and comprehensive reports.

线程安全说明：
  ExportWorker 在 QThread 中运行，handler 函数通过 WorkerDataProvider 访问
  独立 DB 连接（与主线程无关），不再访问 Qt widget。UI 状态（plan_id/issue_id）
  在主线程预取后传入 Worker。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QApplication

from src.views.dialogs.export_dialog import ExportDialog

if TYPE_CHECKING:
    from main import MainWindow
    from src.services.export_service import ExportService

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WorkerDataProvider:
    """Worker 线程的数据提供者 — 使用独立 DB 连接。

    提供与 AppController 相同的方法签名（仅导出所需的子集），
    避免 Worker 线程访问主线程的 apsw.Connection。
    """

    def __init__(self, db_path: str) -> None:
        import apsw
        from src.db.repositories import (
            TestPlanRepository, TestTaskRepository, TestResultRepository,
            IssueRepository, SampleRepository, TechnicianRepository,
        )
        from src.services import (
            TestPlanService, IssueService, SampleService,
        )

        conn = apsw.Connection(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")

        # 确保 schema 已初始化（Worker 使用独立连接）
        from src.db.schema import init_schema
        init_schema(conn)

        tp = TestPlanRepository(conn)
        tt = TestTaskRepository(conn)
        tr = TestResultRepository(conn)
        issues = IssueRepository(conn)
        samples = SampleRepository(conn)
        techs = TechnicianRepository(conn)

        self.test_plans = tp
        self.test_tasks = tt
        self.test_results = tr
        self.issues = issues
        self.samples = samples
        self.technicians = techs  # handler 中用到 ctrl.technicians.list_all()

        self.test_plan_service = TestPlanService(tp, tt, tr)
        self.issue_service = IssueService(issues, conn=conn)
        self.sample_service = SampleService(samples, tr, issues)

        self._conn = conn

    def close(self) -> None:
        """关闭 Worker 的独立 DB 连接。"""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                logger.exception("Worker connection close failed")
            self._conn = None


class ExportWorker(QThread):
    """后台导出线程，使用独立 DB 连接，不访问 Qt widget。"""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, handler_fn: Callable, db_path: str, svc, fmt: str,
                 project_id: int | None, plan_id: int | None,
                 issue_id: int | None, parent=None) -> None:
        super().__init__(parent)
        self._handler_fn = handler_fn
        self._db_path = db_path
        self._svc = svc
        self._fmt = fmt
        self._project_id = project_id
        self._plan_id = plan_id
        self._issue_id = issue_id

    def run(self) -> None:
        provider: WorkerDataProvider | None = None
        try:
            provider = WorkerDataProvider(self._db_path)
            path = self._handler_fn(provider, self._svc, self._fmt,
                                    self._project_id, self._plan_id, self._issue_id)
            self.finished.emit(str(path) if path else "")
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            logger.exception("Export worker failed")
            self.error.emit(f"导出失败: {e}")
        finally:
            if provider:
                provider.close()


class ExportHandlers:
    """Handles data export operations triggered from the UI.

    使用 dispatch table 替代 6x3 的 if-elif 链。
    每个内容类型对应一个 _export_<type> 方法。
    """

    def __init__(self, win: MainWindow) -> None:
        self._win = win
        # 内容类型 -> 处理方法 的 dispatch 表
        self._export_dispatch: dict[str, Callable] = {
            "测试任务": self._export_tasks,
            "Issue": self._export_issues,
            "样品": self._export_samples,
            "综合": self._export_comprehensive,
            "DVP&R": self._export_dvpr,
            "8D": self._export_8d,
        }

    # -- 共享辅助 ---------------------------------------------------

    @staticmethod
    def _get_issues(ctrl, project_id: int | None):
        """按项目获取 Issue，None 或 0 则返回全部。"""
        if project_id:
            return ctrl.issue_service.get_by_project(project_id)
        return ctrl.issue_service.list_all()

    @staticmethod
    def _get_samples(ctrl, project_id: int | None):
        """按项目获取样品，None 或 0 则返回全部。"""
        if project_id:
            return ctrl.sample_service.get_by_project(project_id)
        return ctrl.sample_service.list_all()

    @staticmethod
    def _get_export_dir() -> str:
        """确保导出目录存在并返回路径。"""
        export_dir = os.path.join(_PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir

    # -- 各内容类型导出方法 ------------------------------------------

    @staticmethod
    def _export_tasks(ctrl, svc, fmt: str, project_id: int | None,
                      plan_id: int | None, *args) -> str:
        """导出测试任务。"""
        if plan_id is None:
            raise ValueError("没有选中测试计划")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan or not tasks:
            raise ValueError("当前计划没有任务")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []

        plan_pid = plan.project_id or project_id

        if "Excel" in fmt:
            tech_names = {}
            if ctrl.technicians:
                for tech in ctrl.technicians.list_all():
                    if tech.id is not None:
                        tech_names[tech.id] = tech.name
            return svc.export_tasks_excel(plan, tasks, results=results, technician_names=tech_names)
        elif "Word" in fmt:
            return svc.export_to_word(plan, tasks, ExportHandlers._get_issues(ctrl, plan_pid),
                                      ExportHandlers._get_samples(ctrl, plan_pid), results=results)
        else:
            return svc.export_report_pdf(plan, tasks, ExportHandlers._get_issues(ctrl, plan_pid),
                                         ExportHandlers._get_samples(ctrl, plan_pid), results=results)

    @staticmethod
    def _export_issues(ctrl, svc, fmt: str, project_id: int | None,
                       *args) -> str:
        """导出 Issue 列表（含 FA/CAPA，使用批量查询避免 N+1）。"""
        if "Excel" not in fmt:
            raise ValueError("Issue 导出暂只支持 Excel 格式")
        issues = ExportHandlers._get_issues(ctrl, project_id)
        if not issues:
            raise ValueError("没有 Issue 数据")
        issue_ids = [i.id for i in issues if i.id is not None]
        if issue_ids:
            fa_map = ctrl.issue_service.get_fa_records_batch(issue_ids)
            capa_map = ctrl.issue_service.get_capa_records_batch(issue_ids)
        else:
            fa_map, capa_map = {}, {}
        return svc.export_issues_excel(issues, fa_map=fa_map, capa_map=capa_map)

    @staticmethod
    def _export_samples(ctrl, svc, fmt: str, project_id: int | None,
                        *args) -> str:
        """导出样品台账。"""
        if "Excel" not in fmt:
            raise ValueError("样品导出暂只支持 Excel 格式")
        samples = ExportHandlers._get_samples(ctrl, project_id)
        if not samples:
            raise ValueError("没有样品数据")
        return svc.export_samples_excel(samples)

    @staticmethod
    def _export_comprehensive(ctrl, svc, fmt: str, project_id: int | None,
                               plan_id: int | None, *args) -> str:
        """导出综合报告。"""
        if plan_id is None:
            raise ValueError("没有选中测试计划")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan:
            raise ValueError("未找到该测试计划")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []

        plan_pid = plan.project_id or project_id

        if "Word" in fmt:
            return svc.export_to_word(plan, tasks, ExportHandlers._get_issues(ctrl, plan_pid),
                                      ExportHandlers._get_samples(ctrl, plan_pid), results=results)
        else:
            return svc.export_report_pdf(plan, tasks, ExportHandlers._get_issues(ctrl, plan_pid),
                                         ExportHandlers._get_samples(ctrl, plan_pid), results=results)

    @staticmethod
    def _export_dvpr(ctrl, svc, fmt: str, project_id: int | None,
                      plan_id: int | None, *args) -> str:
        """导出 DVP&R 报告。"""
        if plan_id is None:
            raise ValueError("没有选中测试计划")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan or not tasks:
            raise ValueError("当前计划没有任务")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []

        plan_pid = plan.project_id or project_id
        issues = ExportHandlers._get_issues(ctrl, plan_pid)
        samples = ExportHandlers._get_samples(ctrl, plan_pid)

        if "Excel" in fmt:
            return svc.export_dvpr_excel(plan, tasks, results, issues, samples)
        elif "Word" in fmt:
            return svc.export_dvpr_docx(plan, tasks, results, issues, samples)
        else:
            return svc.export_dvpr_pdf(plan, tasks, results, issues, samples)

    @staticmethod
    def _export_8d(ctrl, svc, fmt: str, project_id: int | None,
                    issue_id: int | None, *args) -> str:
        """导出 8D 报告。"""
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

    # -- 统一入口 ---------------------------------------------------

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
        handler = None
        for key, fn in self._export_dispatch.items():
            if key in content:
                handler = fn
                break
        if handler is None:
            self._win.toast(f"不支持的导出类型: {content}", "error")
            return

        # 在主线程预取 UI 状态（不传递给 QThread）
        plan_id: int | None = None
        issue_id: int | None = None
        if hasattr(self._win, 'test_plan_view'):
            plan_id = self._win.test_plan_view.get_selected_plan_id()
        if hasattr(self._win, 'issue_view'):
            issue_id = self._win.issue_view.get_selected_issue_id()

        export_dir = os.path.join(_PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)

        from src.services.export import ExportService
        svc = ExportService(output_dir=export_dir)

        # 进度对话框（不确定进度模式）
        progress = QProgressDialog("正在导出...", "取消", 0, 0, self._win)
        progress.setWindowTitle("导出中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        worker = ExportWorker(handler, ctrl._db_path if hasattr(ctrl, '_db_path') else '',
                              svc, fmt, project_id, plan_id, issue_id, parent=self._win)
        _generated_path: Path | None = None

        def _on_finished(path: str) -> None:
            nonlocal _generated_path
            _generated_path = Path(path) if path else None
            progress.close()
            self._win.toast(f"已导出: {path}", "success")

        def _on_error(msg: str) -> None:
            progress.close()
            if _generated_path and _generated_path.exists():
                try:
                    _generated_path.unlink()
                except OSError:
                    logger.warning("Failed to clean partial export: %s", _generated_path)
            QMessageBox.critical(self._win, "导出失败", msg)

        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        progress.canceled.connect(worker.terminate)
        worker.start()
