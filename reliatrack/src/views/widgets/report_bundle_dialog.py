"""测试全景简报与 8D 报告打包一键导出中心 (Enriched Report Bundle Generator)。"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QFileDialog,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY

if TYPE_CHECKING:
    from src.controllers.app_controller import AppController

logger = logging.getLogger(__name__)


class ReportBundleDialog(QDialog):
    """丰富多维度的可靠性测试全景简报打包导出中心。

    接入真实 ExportService 引擎，根据用户勾选的章节和格式，
    从数据库读取实际数据生成报告。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        controller: "AppController | None" = None,
        get_plan_id: Callable[[], int | None] | None = None,
        get_project_id: Callable[[], int | None] | None = None,
    ):
        super().__init__(parent)
        self._ctrl = controller
        self._get_plan_id = get_plan_id or (lambda: None)
        self._get_project_id = get_project_id or (lambda: None)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(540, 440)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("report-dialog-container")
        container.setStyleSheet(
            f"QFrame#report-dialog-container {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 12px;"
            f"}}"
        )
        add_shadow(container)

        clay = QVBoxLayout(container)
        clay.setContentsMargins(20, 16, 20, 16)
        clay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("📊 全景可靠性测试简报打包导出中心")
        title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        btn_close = QPushButton("✖ 关闭", self)
        btn_close.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 11px;"
        )
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        clay.addLayout(header)

        # 水印设置
        lbl_wm = QLabel("水印与安全密级签名 (Confidential Watermark):")
        lbl_wm.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_wm)

        self._wm_edit = QLineEdit("机密文件 / CONFIDENTIAL - RELIATRACK ARCHIVE")
        self._wm_edit.setFixedHeight(28)
        self._wm_edit.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; border: 1px solid {_theme.SURFACE1}; border-radius: 6px; padding: 0 8px;"
        )
        clay.addWidget(self._wm_edit)

        # 导出内容勾选
        lbl_sec = QLabel("包含的核心简报章节 (Report Sections):")
        lbl_sec.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_sec)

        self._chk_kpi = QCheckBox("📈 1. 核心 KPI 与测试通过率/失效率度量卡片")
        self._chk_kpi.setChecked(True)
        self._chk_tasks = QCheckBox("📋 2. 测试任务甘特排程与详细状态清单")
        self._chk_tasks.setChecked(True)
        self._chk_samples = QCheckBox("📦 3. 样品全生命周期履历与累计测试小时数")
        self._chk_samples.setChecked(True)
        self._chk_capa = QCheckBox("🔧 4. 8D 缺陷失效分析与 CAPA 纠正预防措施")
        self._chk_capa.setChecked(True)
        # 审计 #29：KPI/任务/样品勾选对产物无实际影响（Word/PDF 综合报告
        # 无条件内置这些章节），可勾选状态是 UX 陷阱。改为禁用 + 说明。
        self._chk_kpi.setEnabled(False)
        self._chk_kpi.setToolTip("综合报告固定包含 KPI 章节，此勾选不可更改")
        self._chk_tasks.setEnabled(False)
        self._chk_tasks.setToolTip("综合报告固定包含任务清单，此勾选不可更改")
        self._chk_samples.setEnabled(False)
        self._chk_samples.setToolTip("综合报告固定包含样品章节，此勾选不可更改")

        for chk in (self._chk_kpi, self._chk_tasks, self._chk_samples, self._chk_capa):
            chk.setStyleSheet(f"QCheckBox {{ color: {_theme.TEXT}; font-size: 12px; }}")
            clay.addWidget(chk)

        # 导出格式选择
        lbl_fmt = QLabel("导出文件格式 (Format Target):")
        lbl_fmt.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_fmt)

        self._fmt_combo = QComboBox()
        self._fmt_combo.setFixedHeight(28)
        self._fmt_combo.setProperty("class", "filter-combo")
        self._fmt_combo.addItem("📊 Excel 多工作表全景总结 Workbook (*.xlsx)", "xlsx")
        self._fmt_combo.addItem("📄 Word 综合可靠性报告 Docx (*.docx)", "docx")
        self._fmt_combo.addItem("📑 PDF 综合可靠性报告 (*.pdf)", "pdf")
        clay.addWidget(self._fmt_combo)

        clay.addStretch()

        # 导出按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_export = QPushButton("🚀 立即打包生成全景报告")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet(
            f"QPushButton {{"
            f"  background: {DASH_PRIMARY};"
            f"  color: #FFFFFF;"
            f"  border-radius: 8px;"
            f"  padding: 8px 18px;"
            f"  font-size: 13px;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ background: {_theme.BLUE}; }}"
        )
        btn_export.clicked.connect(self._do_export)
        btn_row.addWidget(btn_export)

        clay.addLayout(btn_row)
        root.addWidget(container)

    def _do_export(self) -> None:
        """接入真实 ExportService 引擎导出。

        根据勾选的章节组合和格式，调用对应导出方法。
        所有数据从数据库实时读取，不使用硬编码假数据。
        """
        if not self._ctrl:
            QMessageBox.warning(self, "无法导出", "控制器未初始化，无法读取数据。")
            return

        ext = self._fmt_combo.currentData()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存全景测试报告",
            f"Reliability_Comprehensive_Report.{ext}",
            f"Report Files (*.{ext})",
        )
        if not path:
            return

        try:
            result_path = self._dispatch_export(ext, path)
        except ValueError as e:
            QMessageBox.warning(self, "导出取消", str(e))
            return
        except Exception as e:
            logger.exception("Report bundle export failed")
            QMessageBox.critical(self, "导出失败", f"生成报告时出错：\n{e}")
            return

        # 成功反馈
        mw = self.parent()
        while mw is not None:
            if hasattr(mw, "toast"):
                mw.toast(f"📊 全景报告已导出至: {result_path}", "success")
                break
            mw = mw.parent()
        self.accept()

    def _dispatch_export(self, ext: str, filepath: str) -> str:
        """根据章节勾选 + 格式分派到 ExportService 方法。

        返回最终生成的文件路径。
        抛 ValueError 表示用户数据不足（如未选计划），由调用方提示。
        """
        from src.services.export import ExportService

        ctrl = self._ctrl
        svc = ExportService(output_dir=os.path.dirname(filepath) or ".")

        # 判断导出内容组合
        # KPI 章节只在 Word/PDF 综合报告中有意义（由 exporter 内部生成），
        # Excel 模式下无独立 KPI 导出引擎，KPI 勾选被忽略。
        want_kpi = self._chk_kpi.isChecked()
        want_tasks = self._chk_tasks.isChecked()
        want_samples = self._chk_samples.isChecked()
        want_capa = self._chk_capa.isChecked()

        # Word / PDF 走综合报告引擎（综合报告内置 KPI，忽略单章节勾选）
        if ext in ("docx", "pdf"):
            return self._export_comprehensive(svc, ctrl, filepath, fmt=ext, include_capa=want_capa)

        # Excel: 按勾选章节分 sheet 导出
        return self._export_excel_sections(svc, ctrl, filepath, want_tasks, want_samples, want_capa)

    # -- 综合报告（Word / PDF）--------------------------------------

    def _export_comprehensive(self, svc, ctrl, filepath: str, fmt: str, include_capa: bool) -> str:
        """综合报告 — KPI + 任务 + 样品 +（可选）Issue。

        fmt: "docx" → export_to_word; "pdf" → export_report_pdf。
        """
        plan_id = self._get_plan_id()
        if plan_id is None:
            raise ValueError("综合报告需要选中一个测试计划。\n请先在测试计划视图中选中计划，再导出。")
        plan = ctrl.test_plan_service.get_plan(plan_id)
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        if not plan:
            raise ValueError("未找到选中的测试计划")

        task_ids = [t.id for t in tasks if t.id is not None]
        results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []

        # Issue 按 project_id 精确筛选；无关联 Issue 则不导出而非 fallback 全库
        project_id = plan.project_id or self._get_project_id()
        issues: list = []
        if include_capa and project_id:
            issues = ctrl.issue_service.get_by_project(project_id) or []

        samples: list = []
        if project_id and ctrl.sample_service:
            samples = ctrl.sample_service.get_by_project(project_id) or []

        if fmt == "docx":
            return svc.export_to_word(plan, tasks, issues, samples, filepath=filepath, results=results)
        return svc.export_report_pdf(plan, tasks, issues, samples, filepath=filepath, results=results)

    # -- Excel 分章节导出 ------------------------------------------

    def _export_excel_sections(self, svc, ctrl, filepath: str, want_tasks: bool, want_samples: bool, want_capa: bool) -> str:
        """按勾选章节导出为单个 Excel 文件（多 sheet 由底层 exporter 处理）。

        至少需要勾选一个章节，否则抛 ValueError。
        优先级：tasks > samples > issues（单选时）；多选时 tasks 为主 sheet。
        """
        if not any([want_tasks, want_samples, want_capa]):
            raise ValueError("请至少勾选一个导出章节")

        if want_tasks:
            # 以任务为主导（需要计划上下文），附加样品/issue 作为额外信息
            # 简化处理：单 sheet 任务导出（ExportService 当前不支持多 sheet 合并）
            plan_id = self._get_plan_id()
            if plan_id and ctrl.test_plan_service:
                plan = ctrl.test_plan_service.get_plan(plan_id)
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                if plan and tasks:
                    task_ids = [t.id for t in tasks if t.id is not None]
                    results = ctrl.test_plan_service.get_all_results_by_tasks(task_ids) if task_ids else []
                    tech_names = {}
                    if ctrl.technicians:
                        for tech in ctrl.technicians.list_all():
                            if tech.id is not None:
                                tech_names[tech.id] = tech.name
                    return svc.export_tasks_excel(plan, tasks, results=results, technician_names=tech_names, filepath=filepath)

        # 无计划或未勾选任务 → 按样品/issue 单独导出
        if want_samples and not want_capa:
            samples = ctrl.sample_service.list_all() if ctrl.sample_service else []
            if not samples:
                raise ValueError("没有样品数据可导出")
            return svc.export_samples_excel(samples, filepath=filepath)

        if want_capa and not want_samples:
            issues = ctrl.issue_service.list_all() if ctrl.issue_service else []
            if not issues:
                raise ValueError("没有 Issue 数据可导出")
            issue_ids = [i.id for i in issues if i.id is not None]
            fa_map = ctrl.issue_service.get_fa_records_batch(issue_ids) if issue_ids else {}
            capa_map = ctrl.issue_service.get_capa_records_batch(issue_ids) if issue_ids else {}
            return svc.export_issues_excel(issues, fa_map=fa_map, capa_map=capa_map, filepath=filepath)

        # 多章节但无计划上下文 → 退化为 issue 导出（信息密度最高）
        raise ValueError("Excel 分章导出需要选中测试计划（任务章节）。\n请选中计划，或只勾选样品/Issue 单章节。")

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self.exec()
