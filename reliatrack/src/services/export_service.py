"""导出服务 — Excel (openpyxl) + PDF (fpdf2) 导出。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from src.models.test_plan import TestPlan, TestTask
from src.models.issue import Issue, FARecord
from src.models.sample import Sample


class ExportService:
    """导出服务 — 将数据导出为 Excel / PDF 文件。"""

    # ── 类别中文映射 ──
    CATEGORY_MAP = {
        "环境试验": "env",
        "env": "环境试验",
        "机械试验": "mech",
        "mech": "机械试验",
        "表面处理": "surf",
        "surf": "表面处理",
        "包装": "pack",
        "pack": "包装",
        "其他": "other",
        "other": "其他",
    }

    STATUS_MAP = {
        "pending": "待开始",
        "in_progress": "进行中",
        "completed": "已完成",
        "skipped": "已跳过",
        "open": "待处理",
        "analyzing": "分析中",
        "verified": "已验证",
        "closed": "已关闭",
        "in_stock": "在库",
        "checked_out": "已出库",
        "in_test": "测试中",
        "scrapped": "已报废",
        "returned": "已归还",
    }

    def __init__(self, output_dir: str = "exports") -> None:
        self._output_dir = Path(output_dir)

    def _ensure_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    # ── Excel 导出 ──────────────────────────────────────────────

    def export_tasks_excel(
        self,
        plan: TestPlan,
        tasks: list[TestTask],
        filepath: str | None = None,
    ) -> str:
        """导出测试任务列表为 Excel。

        Returns:
            导出文件的绝对路径。
        """
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = Workbook()
        ws = wb.active
        ws.title = "测试任务"

        # 样式
        header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2B579A", end_color="2B579A", fill_type="solid")
        cell_font = Font(name="微软雅黑", size=10)
        center = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # 标题行
        ws.merge_cells("A1:I1")
        title_cell = ws["A1"]
        title_cell.value = f"测试计划: {plan.name}"
        title_cell.font = Font(name="微软雅黑", size=14, bold=True, color="2B579A")
        title_cell.alignment = Alignment(horizontal="center")
        ws.row_dimensions[1].height = 30

        # 副标题
        ws.merge_cells("A2:I2")
        sub = ws["A2"]
        sub.value = f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  测试标准: {plan.test_standard or '—'}"
        sub.font = Font(name="微软雅黑", size=9, color="666666")
        sub.alignment = Alignment(horizontal="center")

        # 表头
        headers = ["#", "名称", "类别", "工期(天)", "开始天", "进度", "状态", "优先级", "环境条件"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border

        # 数据行
        for row_idx, task in enumerate(tasks, 5):
            values = [
                row_idx - 4,
                task.name,
                self.CATEGORY_MAP.get(task.category, task.category),
                task.duration,
                task.start_day,
                f"{task.progress:.0f}%",
                self.STATUS_MAP.get(task.status, task.status),
                task.priority,
                task.environment,
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)
                cell.font = cell_font
                cell.alignment = center
                cell.border = thin_border

        # 列宽
        widths = [5, 30, 10, 10, 10, 8, 10, 8, 25]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w

        # 保存
        out = filepath or str(self._ensure_dir() / f"测试任务_{plan.name}_{datetime.now():%Y%m%d_%H%M}.xlsx")
        wb.save(out)
        return os.path.abspath(out)

    def export_issues_excel(
        self,
        issues: list[Issue],
        fa_map: dict[int, list[FARecord]] | None = None,
        filepath: str | None = None,
    ) -> str:
        """导出 Issue 列表为 Excel。

        Args:
            fa_map: {issue_id: [FARecord, ...]} 可选。
        """
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = Workbook()
        ws = wb.active
        ws.title = "Issue 追踪"

        header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="C0504D", end_color="C0504D", fill_type="solid")
        cell_font = Font(name="微软雅黑", size=10)
        center = Alignment(horizontal="center", vertical="center")
        wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # 标题
        ws.merge_cells("A1:H1")
        title_cell = ws["A1"]
        title_cell.value = "Issue 追踪报告"
        title_cell.font = Font(name="微软雅黑", size=14, bold=True, color="C0504D")
        title_cell.alignment = Alignment(horizontal="center")
        ws.row_dimensions[1].height = 30

        ws.merge_cells("A2:H2")
        sub = ws["A2"]
        sub.value = f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  共 {len(issues)} 个 Issue"
        sub.font = Font(name="微软雅黑", size=9, color="666666")
        sub.alignment = Alignment(horizontal="center")

        headers = ["ID", "标题", "严重度", "状态", "优先级", "失效模式", "根因分析", "FA 步骤数"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border

        for row_idx, issue in enumerate(issues, 5):
            fa_count = len(fa_map.get(issue.id, [])) if fa_map else 0
            values = [
                issue.id,
                issue.title,
                issue.severity,
                self.STATUS_MAP.get(issue.status, issue.status),
                issue.priority,
                issue.failure_mode or "",
                (issue.root_cause or "")[:100],
                fa_count,
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)
                cell.font = cell_font
                cell.alignment = wrap if col in (2, 6, 7) else center
                cell.border = thin_border

        widths = [5, 25, 10, 10, 8, 15, 35, 10]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w

        out = filepath or str(self._ensure_dir() / f"Issue追踪_{datetime.now():%Y%m%d_%H%M}.xlsx")
        wb.save(out)
        return os.path.abspath(out)

    def export_samples_excel(
        self,
        samples: list[Sample],
        filepath: str | None = None,
    ) -> str:
        """导出样品台账为 Excel。"""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = Workbook()
        ws = wb.active
        ws.title = "样品台账"

        header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        cell_font = Font(name="微软雅黑", size=10)
        center = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        ws.merge_cells("A1:F1")
        title_cell = ws["A1"]
        title_cell.value = "样品台账"
        title_cell.font = Font(name="微软雅黑", size=14, bold=True, color="4F81BD")
        title_cell.alignment = Alignment(horizontal="center")
        ws.row_dimensions[1].height = 30

        ws.merge_cells("A2:F2")
        sub = ws["A2"]
        sub.value = f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  共 {len(samples)} 个样品"
        sub.font = Font(name="微软雅黑", size=9, color="666666")
        sub.alignment = Alignment(horizontal="center")

        headers = ["ID", "SN", "批次号", "规格型号", "状态", "存放位置"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border

        for row_idx, s in enumerate(samples, 5):
            values = [s.id, s.sn, s.batch_no, s.spec or "", self.STATUS_MAP.get(s.status, s.status), s.location or ""]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)
                cell.font = cell_font
                cell.alignment = center
                cell.border = thin_border

        widths = [5, 20, 15, 20, 10, 15]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w

        out = filepath or str(self._ensure_dir() / f"样品台账_{datetime.now():%Y%m%d_%H%M}.xlsx")
        wb.save(out)
        return os.path.abspath(out)

    # ── PDF 导出 ──────────────────────────────────────────────

    def export_report_pdf(
        self,
        plan: TestPlan,
        tasks: list[TestTask],
        issues: list[Issue],
        samples: list[Sample],
        filepath: str | None = None,
    ) -> str:
        """导出综合测试报告为 PDF。

        包含：概览统计、任务列表、Issue 列表、样品状态。
        """
        from fpdf import FPDF

        class _ReportPDF(FPDF):
            def header(self) -> None:
                self.set_font("Helvetica", "B", 10)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, "ReliaTrack - Reliability Test Report", align="R")
                self.ln(8)

            def footer(self) -> None:
                self.set_y(-15)
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

        pdf = _ReportPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        # ── 封面 ──
        pdf.add_page()
        pdf.ln(40)
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(43, 87, 154)
        pdf.cell(0, 15, "Reliability Test Report", align="C")
        pdf.ln(20)
        pdf.set_font("Helvetica", "", 14)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 10, f"Plan: {plan.name}", align="C")
        pdf.ln(8)
        pdf.cell(0, 10, f"Standard: {plan.test_standard or 'N/A'}", align="C")
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")

        # ── 概览 ──
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(43, 87, 154)
        pdf.cell(0, 12, "Overview", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        pending = sum(1 for t in tasks if t.status == "pending")
        total_days = max((t.start_day + t.duration for t in tasks), default=0)
        open_issues = sum(1 for i in issues if i.status in ("open", "analyzing"))
        in_stock = sum(1 for s in samples if s.status == "in_stock")

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(50, 50, 50)
        stats = [
            f"Total Tasks: {total}",
            f"Completed: {completed}  |  In Progress: {in_progress}  |  Pending: {pending}",
            f"Total Duration: {total_days} working days",
            f"Open Issues: {open_issues} / {len(issues)}",
            f"Samples In Stock: {in_stock} / {len(samples)}",
        ]
        for s in stats:
            pdf.cell(0, 8, s, new_x="LMARGIN", new_y="NEXT")

        # ── 任务列表 ──
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(43, 87, 154)
        pdf.cell(0, 10, "Test Tasks", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # 表头
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(43, 87, 154)
        pdf.set_text_color(255, 255, 255)
        col_widths = [8, 50, 25, 18, 18, 18, 20, 18]
        headers = ["#", "Name", "Category", "Days", "Start", "Progress", "Status", "Priority"]
        for i, (w, h) in enumerate(zip(col_widths, headers)):
            pdf.cell(w, 7, h, border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(50, 50, 50)
        for idx, task in enumerate(tasks, 1):
            cat = self.CATEGORY_MAP.get(task.category, task.category)
            status = self.STATUS_MAP.get(task.status, task.status)
            vals = [
                str(idx),
                task.name[:25],
                cat,
                str(task.duration),
                f"D{task.start_day}",
                f"{task.progress:.0f}%",
                status,
                str(task.priority),
            ]
            for w, v in zip(col_widths, vals):
                pdf.cell(w, 6, v, border=1, align="C")
            pdf.ln()

        # ── Issue 列表 ──
        if issues:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(192, 80, 77)
            pdf.cell(0, 10, "Issue Tracking", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(192, 80, 77)
            pdf.set_text_color(255, 255, 255)
            issue_cols = [8, 55, 18, 18, 15, 35]
            issue_headers = ["ID", "Title", "Severity", "Status", "Priority", "Failure Mode"]
            for w, h in zip(issue_cols, issue_headers):
                pdf.cell(w, 7, h, border=1, align="C", fill=True)
            pdf.ln()

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(50, 50, 50)
            for issue in issues:
                sev = issue.severity
                status = self.STATUS_MAP.get(issue.status, issue.status)
                vals = [
                    str(issue.id),
                    issue.title[:30],
                    sev,
                    status,
                    str(issue.priority),
                    (issue.failure_mode or "")[:20],
                ]
                for w, v in zip(issue_cols, vals):
                    pdf.cell(w, 6, v, border=1, align="C")
                pdf.ln()

        out = filepath or str(self._ensure_dir() / f"测试报告_{plan.name}_{datetime.now():%Y%m%d_%H%M}.pdf")
        pdf.output(out)
        return os.path.abspath(out)
