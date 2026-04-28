"""导出服务 — Excel (openpyxl) + PDF (fpdf2) + Word (python-docx) 导出。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from src.models.test_plan import TestPlan, TestTask
from src.models.issue import Issue, FARecord
from src.models.sample import Sample


class ExportService:
    """导出服务 — 将数据导出为 Excel / PDF / Word 文件。"""

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
            fa_count = len(fa_map.get(issue.id, [])) if fa_map and issue.id is not None else 0
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

    # 中文字体路径（NotoSansCJK）
    _FONT_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    _FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    _FONT_FAMILY = "NotoSC"

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

        ff = self._FONT_FAMILY
        font_reg = self._FONT_REGULAR
        font_bld = self._FONT_BOLD

        class _ReportPDF(FPDF):
            def header(self) -> None:
                self.set_font(ff, "B", 10)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, "ReliaTrack — 可靠性测试报告", align="R")
                self.ln(8)

            def footer(self) -> None:
                self.set_y(-15)
                self.set_font(ff, "", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 10, f"第 {self.page_no()}/{{nb}} 页", align="C")

        pdf = _ReportPDF()
        # 注册中文字体
        pdf.add_font(ff, fname=font_reg)
        pdf.add_font(ff, fname=font_bld, style="B")
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        # ── 封面 ──
        pdf.add_page()
        pdf.ln(40)
        pdf.set_font(ff, "B", 24)
        pdf.set_text_color(43, 87, 154)
        pdf.cell(0, 15, "可靠性测试报告", align="C")
        pdf.ln(20)
        pdf.set_font(ff, "", 14)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 10, f"计划: {plan.name}", align="C")
        pdf.ln(8)
        pdf.cell(0, 10, f"测试标准: {plan.test_standard or '—'}", align="C")
        pdf.ln(8)
        pdf.set_font(ff, "", 10)
        pdf.cell(0, 10, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")

        # ── 概览 ──
        pdf.add_page()
        pdf.set_font(ff, "B", 16)
        pdf.set_text_color(43, 87, 154)
        pdf.cell(0, 12, "概览统计", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        pending = sum(1 for t in tasks if t.status == "pending")
        total_days = max((t.start_day + t.duration for t in tasks), default=0)
        open_issues = sum(1 for i in issues if i.status in ("open", "analyzing"))
        in_stock = sum(1 for s in samples if s.status == "in_stock")

        pdf.set_font(ff, "", 11)
        pdf.set_text_color(50, 50, 50)
        stats = [
            f"总任务数: {total}",
            f"已完成: {completed}  |  进行中: {in_progress}  |  待开始: {pending}",
            f"总工期: {total_days} 个工作日",
            f"未关闭 Issue: {open_issues} / {len(issues)}",
            f"在库样品: {in_stock} / {len(samples)}",
        ]
        for s in stats:
            pdf.cell(0, 8, s, new_x="LMARGIN", new_y="NEXT")

        # ── 任务列表 ──
        pdf.ln(6)
        pdf.set_font(ff, "B", 14)
        pdf.set_text_color(43, 87, 154)
        pdf.cell(0, 10, "测试任务", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # 表头
        pdf.set_font(ff, "B", 9)
        pdf.set_fill_color(43, 87, 154)
        pdf.set_text_color(255, 255, 255)
        col_widths = [8, 50, 25, 18, 18, 18, 20, 18]
        headers = ["#", "名称", "类别", "工期", "开始", "进度", "状态", "优先级"]
        for i, (w, h) in enumerate(zip(col_widths, headers)):
            pdf.cell(w, 7, h, border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_font(ff, "", 8)
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
            pdf.set_font(ff, "B", 14)
            pdf.set_text_color(192, 80, 77)
            pdf.cell(0, 10, "Issue 追踪", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            pdf.set_font(ff, "B", 9)
            pdf.set_fill_color(192, 80, 77)
            pdf.set_text_color(255, 255, 255)
            issue_cols = [8, 55, 18, 18, 15, 35]
            issue_headers = ["ID", "标题", "严重度", "状态", "优先级", "失效模式"]
            for w, h in zip(issue_cols, issue_headers):
                pdf.cell(w, 7, h, border=1, align="C", fill=True)
            pdf.ln()

            pdf.set_font(ff, "", 8)
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

    # ── Word 导出 ──────────────────────────────────────────────

    def export_to_word(
        self,
        plan: TestPlan,
        tasks: list[TestTask],
        issues: list[Issue],
        samples: list[Sample],
        filepath: str | None = None,
    ) -> str:
        """导出综合测试报告为 Word (.docx)。

        包含：封面标题、项目信息表格、任务列表表格、Issue 列表表格、样品列表表格。
        """
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn, nsdecls
        from docx.oxml import parse_xml

        doc = Document()

        # ── 样式设置（全局一次，子元素自动继承） ──
        style = doc.styles["Normal"]
        font = style.font
        font.name = "微软雅黑"
        font.size = Pt(10)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        pf = style.paragraph_format
        pf.space_after = Pt(4)
        pf.space_before = Pt(2)

        # ── 快速写入单元格（直接操作 lxml 避免 parse_xml 开销） ──
        from lxml import etree
        _ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        _NSMAP = {"w": _ns}

        def _make(tag, **attrib):
            return etree.SubElement(etree.Element("dummy"), f"{{{_ns}}}{tag}").makeelement(
                f"{{{_ns}}}{tag}", {f"{{{_ns}}}{k}": v for k, v in attrib.items()}
            )

        def _fill_cell(ct_tc, text, bold=False, size=9, color=None,
                        shade=None, align=None):
            """直接操作 CT_Tc XML 元素，避免 _Cell 包装开销。"""
            # 清除旧段落
            for p in ct_tc.findall(qn("w:p")):
                ct_tc.remove(p)
            # 构建 <w:p><w:r><w:rPr>...<w:t>xml:space="preserve">text</w:t></w:r></w:p>
            p = etree.SubElement(ct_tc, f"{{{_ns}}}p")
            if align == "center":
                pPr = etree.SubElement(p, f"{{{_ns}}}pPr")
                etree.SubElement(pPr, f"{{{_ns}}}jc", attrib={f"{{{_ns}}}val": "center"})
            r = etree.SubElement(p, f"{{{_ns}}}r")
            rPr = etree.SubElement(r, f"{{{_ns}}}rPr")
            rFonts = etree.SubElement(rPr, f"{{{_ns}}}rFonts")
            rFonts.set(f"{{{_ns}}}ascii", "微软雅黑")
            rFonts.set(f"{{{_ns}}}eastAsia", "微软雅黑")
            rFonts.set(f"{{{_ns}}}hAnsi", "微软雅黑")
            rPr.append(_make("sz", val=str(size * 2)))
            if bold:
                rPr.append(_make("b"))
            if color:
                rPr.append(_make("color", val=color))
            t = etree.SubElement(r, f"{{{_ns}}}t")
            t.text = text
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            if shade:
                tcPr = ct_tc.get_or_add_tcPr()
                tcPr.append(_make("shd", fill=shade, val="clear"))

        def _fill_row_cells(tr, values, bold=False, color=None,
                            shade=None, center_cols=frozenset()):
            """批量填充一行，跳过 _Cell 构造。"""
            tc_elems = tr.findall(qn("w:tc"))
            for j, val in enumerate(values):
                tc = tc_elems[j] if j < len(tc_elems) else None
                if tc is not None:
                    _fill_cell(tc, str(val), bold=bold, color=color,
                               shade=shade if j == 0 or shade else None,
                               align="center" if j in center_cols else None)

        # ── 标题 ──
        title = doc.add_heading(level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("可靠性测试报告")
        run.font.size = Pt(24)
        run.font.color.rgb = RGBColor(0x2B, 0x57, 0x9A)

        # 副标题
        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_run = sub.add_run(f"计划: {plan.name}  |  测试标准: {plan.test_standard or '—'}")
        sub_run.font.size = Pt(12)
        sub_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        # 导出时间
        ts = doc.add_paragraph()
        ts.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ts_run = ts.add_run(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        ts_run.font.size = Pt(10)
        ts_run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        # ── 概览统计 ──
        doc.add_heading("概览统计", level=2)
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        pending = sum(1 for t in tasks if t.status == "pending")
        total_days = max((t.start_day + t.duration for t in tasks), default=0)
        open_issues = sum(1 for i in issues if i.status in ("open", "analyzing"))
        in_stock = sum(1 for s in samples if s.status == "in_stock")

        stats_lines = [
            f"总任务数: {total}    已完成: {completed}    进行中: {in_progress}    待开始: {pending}",
            f"总工期: {total_days} 个工作日",
            f"未关闭 Issue: {open_issues} / {len(issues)}",
            f"在库样品: {in_stock} / {len(samples)}",
        ]
        for line in stats_lines:
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(2)

        # ── 项目信息表格 ──
        doc.add_heading("项目信息", level=2)
        info_table = doc.add_table(rows=5, cols=2, style="Table Grid")
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        info_data = [
            ("计划名称", plan.name),
            ("测试标准", plan.test_standard or "—"),
            ("开始日期", plan.start_date or "—"),
            ("结束日期", plan.end_date or "—"),
            ("计划状态", self.STATUS_MAP.get(plan.status, plan.status)),
        ]
        for i, (label, value) in enumerate(info_data):
            tr = info_table.rows[i]._tr
            tc_elems = tr.findall(qn("w:tc"))
            _fill_cell(tc_elems[0], label, bold=True, size=10, shade="E8EDF5")
            _fill_cell(tc_elems[1], value, size=10)

        # ── 任务列表表格 ──
        doc.add_heading("测试任务", level=2)
        task_headers = ["#", "名称", "类别", "状态", "天数", "设备", "技术员", "进度"]
        task_table = doc.add_table(rows=1 + len(tasks), cols=len(task_headers), style="Table Grid")
        task_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        _fill_row_cells(task_table.rows[0]._tr, task_headers, bold=True,
                        color="FFFFFF", shade="2B579A", center_cols=set(range(len(task_headers))))

        for idx, task in enumerate(tasks, 1):
            equipment_name = f"ID:{task.equipment_id}" if task.equipment_id else "—"
            technician_name = f"ID:{task.technician_id}" if task.technician_id else "—"
            _fill_row_cells(task_table.rows[idx]._tr, [
                idx, task.name,
                self.CATEGORY_MAP.get(task.category, task.category),
                self.STATUS_MAP.get(task.status, task.status),
                task.duration, equipment_name, technician_name,
                f"{task.progress:.0f}%",
            ], center_cols={0})

        # ── Issue 列表表格 ──
        if issues:
            doc.add_heading("Issue 追踪", level=2)
            issue_headers = ["#", "标题", "优先级", "状态", "根因"]
            issue_table = doc.add_table(
                rows=1 + len(issues), cols=len(issue_headers), style="Table Grid"
            )
            issue_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            _fill_row_cells(issue_table.rows[0]._tr, issue_headers, bold=True,
                            color="FFFFFF", shade="C0504D", center_cols=set(range(len(issue_headers))))

            for idx, issue in enumerate(issues, 1):
                _fill_row_cells(issue_table.rows[idx]._tr, [
                    idx, issue.title, issue.priority,
                    self.STATUS_MAP.get(issue.status, issue.status),
                    (issue.root_cause or "")[:80] if issue.root_cause else "",
                ], center_cols={0})

        # ── 样品列表表格 ──
        if samples:
            doc.add_heading("样品台账", level=2)
            sample_headers = ["#", "SN", "批次号", "规格型号", "状态"]
            sample_table = doc.add_table(
                rows=1 + len(samples), cols=len(sample_headers), style="Table Grid"
            )
            sample_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            _fill_row_cells(sample_table.rows[0]._tr, sample_headers, bold=True,
                            color="FFFFFF", shade="4F81BD", center_cols=set(range(len(sample_headers))))

            for idx, s in enumerate(samples, 1):
                _fill_row_cells(sample_table.rows[idx]._tr, [
                    idx, s.sn, s.batch_no, s.spec or "",
                    self.STATUS_MAP.get(s.status, s.status),
                ], center_cols={0})

        # ── 保存 ──
        out = filepath or str(
            self._ensure_dir() / f"测试报告_{plan.name}_{datetime.now():%Y%m%d_%H%M}.docx"
        )
        doc.save(out)
        return os.path.abspath(out)

    # ── 辅助方法 ──

    @staticmethod
    def _set_cell_shading(cell, hex_color: str) -> None:
        """设置 Word 单元格背景色。"""
        from docx.oxml.ns import qn, nsdecls
        from docx.oxml import parse_xml

        shading = parse_xml(
            f'<w:shd {nsdecls("w")} w:fill="{hex_color}" w:val="clear"/>'
        )
        cell._tc.get_or_add_tcPr().append(shading)
