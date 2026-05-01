"""导出服务 — Excel (openpyxl) + PDF (reportlab) + Word (python-docx) 导出。"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from src.constants import (
    TASK_STATUS_LABELS,
    ISSUE_STATUS_LABELS,
    SAMPLE_STATUS_LABELS,
)
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

    # Merged status → Chinese label map (task + issue + sample)
    STATUS_MAP: dict[str, str] = {
        **TASK_STATUS_LABELS,
        **ISSUE_STATUS_LABELS,
        **SAMPLE_STATUS_LABELS,
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

    @staticmethod
    def _find_cjk_font() -> tuple[str, str, int | None, int | None]:
        """跨平台查找可用的中文字体。

        Returns:
            (regular_path, bold_path, regular_subfont, bold_subfont)
            subfont 为 None 表示纯 TTF 文件，无需指定索引。
        """
        if sys.platform == "win32":
            windir = os.environ.get("WINDIR", r"C:\Windows")
            fd = os.path.join(windir, "Fonts")
            candidates: list[tuple[str, str, int | None, int | None]] = [
                # 微软雅黑: msyh.ttc(reg) + msyhbd.ttc(bold)
                (os.path.join(fd, "msyh.ttc"), os.path.join(fd, "msyhbd.ttc"), 0, 0),
                # msyh.ttc 单文件（部分版本 bold 在同一 ttc 内）
                (os.path.join(fd, "msyh.ttc"), os.path.join(fd, "msyh.ttc"), 0, 1),
                # 黑体
                (os.path.join(fd, "simhei.ttf"), os.path.join(fd, "simhei.ttf"), None, None),
            ]
        elif sys.platform == "darwin":
            candidates = [
                ("/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/PingFang.ttc", 1, 3),
            ]
        else:
            # Linux
            candidates = [
                # DroidSansFallback (纯 TrueType，reportlab 兼容最好)
                ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                 "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                 None, None),
                ("/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
                 "/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
                 None, None),
                # Noto Sans CJK (TTC, 需要 subfontIndex)
                ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                 0, 0),
                ("/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
                 0, 1),
            ]

        for reg, bld, r_sub, b_sub in candidates:
            if os.path.isfile(reg) and (reg == bld or os.path.isfile(bld)):
                return reg, bld, r_sub, b_sub

        raise FileNotFoundError(
            "未找到可用的中文字体。请安装微软雅黑 (Windows) 或 "
            "DroidSansFallback (Linux) 字体。"
        )

    def export_report_pdf(
        self,
        plan: TestPlan,
        tasks: list[TestTask],
        issues: list[Issue],
        samples: list[Sample],
        filepath: str | None = None,
    ) -> str:
        """导出综合测试报告为 PDF (reportlab)。

        包含：概览统计、任务列表、Issue 列表、样品状态。
        自动检测系统中可用的中文字体（Windows/macOS/Linux）。
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak,
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        from reportlab.pdfgen.canvas import Canvas as _Canvas

        # 跨平台字体检测
        reg_path, bld_path, reg_sub, bld_sub = self._find_cjk_font()
        _FN = "CJK"   # 内部注册名（固定）
        _FN_B = "CJK-Bold"

        # 注册字体（已注册则跳过）
        if _FN not in pdfmetrics.getRegisteredFontNames():
            kw: dict[str, object] = {}
            if reg_sub is not None:
                kw["subfontIndex"] = reg_sub
            pdfmetrics.registerFont(TTFont(_FN, reg_path, **kw))

        if _FN_B not in pdfmetrics.getRegisteredFontNames():
            kw = {}
            if bld_sub is not None:
                kw["subfontIndex"] = bld_sub
            pdfmetrics.registerFont(TTFont(_FN_B, bld_path, **kw))

        pdfmetrics.registerFontFamily(_FN, normal=_FN, bold=_FN_B)

        # 颜色
        _BLUE = HexColor("#2B579A")
        _RED = HexColor("#C0504D")
        _GRAY = HexColor("#646464")
        _LIGHT_GRAY = HexColor("#969696")
        _DARK = HexColor("#323232")

        # 样式
        style_title = ParagraphStyle(
            "Title", fontName=_FN_B, fontSize=24,
            textColor=_BLUE, alignment=TA_CENTER, spaceAfter=8 * mm,
        )
        style_subtitle = ParagraphStyle(
            "Subtitle", fontName=_FN, fontSize=14,
            textColor=_GRAY, alignment=TA_CENTER, spaceAfter=4 * mm,
        )
        style_ts = ParagraphStyle(
            "Timestamp", fontName=_FN, fontSize=10,
            textColor=_LIGHT_GRAY, alignment=TA_CENTER,
        )
        style_section = ParagraphStyle(
            "Section", fontName=_FN_B, fontSize=16,
            textColor=_BLUE, spaceAfter=3 * mm, spaceBefore=6 * mm,
        )
        style_section_red = ParagraphStyle(
            "SectionRed", fontName=_FN_B, fontSize=14,
            textColor=_RED, spaceAfter=2 * mm, spaceBefore=4 * mm,
        )
        style_stat = ParagraphStyle(
            "Stat", fontName=_FN, fontSize=11,
            textColor=_DARK, spaceAfter=1 * mm,
        )
        style_header = ParagraphStyle(
            "Header", fontName=_FN, fontSize=8,
            textColor=_LIGHT_GRAY, alignment=TA_CENTER,
        )

        # 页眉页脚回调
        def _header_footer(canvas: _Canvas, doc: object) -> None:  # noqa: ANN001
            canvas.saveState()
            canvas.setFont(_FN, 8)
            canvas.setFillColor(_LIGHT_GRAY)
            canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm,
                                   "ReliaTrack — 可靠性测试报告")
            canvas.drawCentredString(A4[0] / 2, 12 * mm,
                                     f"第 {canvas.getPageNumber()} 页")
            canvas.restoreState()

        out = filepath or str(
            self._ensure_dir() / f"测试报告_{plan.name}_{datetime.now():%Y%m%d_%H%M}.pdf"
        )
        doc = SimpleDocTemplate(
            out, pagesize=A4,
            topMargin=18 * mm, bottomMargin=18 * mm,
            leftMargin=15 * mm, rightMargin=15 * mm,
        )

        story: list[object] = []

        # ── 封面 ──
        story.append(Spacer(1, 40 * mm))
        story.append(Paragraph("可靠性测试报告", style_title))
        story.append(Paragraph(
            f"计划: {plan.name}", style_subtitle))
        story.append(Paragraph(
            f"测试标准: {plan.test_standard or '—'}", style_subtitle))
        story.append(Paragraph(
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", style_ts))

        # ── 概览 ──
        story.append(PageBreak())
        story.append(Paragraph("概览统计", style_section))

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        pending = sum(1 for t in tasks if t.status == "pending")
        total_days = max((t.start_day + t.duration for t in tasks), default=0)
        open_issues = sum(1 for i in issues if i.status in ("open", "analyzing"))
        in_stock = sum(1 for s in samples if s.status == "in_stock")

        stats = [
            f"总任务数: {total}",
            f"已完成: {completed}  |  进行中: {in_progress}  |  待开始: {pending}",
            f"总工期: {total_days} 个工作日",
            f"未关闭 Issue: {open_issues} / {len(issues)}",
            f"在库样品: {in_stock} / {len(samples)}",
        ]
        for s in stats:
            story.append(Paragraph(s, style_stat))

        # ── 任务列表 ──
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("测试任务", style_section))

        # 表头
        task_headers = ["#", "名称", "类别", "工期", "开始", "进度", "状态", "优先级"]
        task_col_widths = [18, 130, 55, 40, 40, 40, 50, 40]
        header_row = [Paragraph(h, ParagraphStyle(
            "TH", fontName=_FN_B, fontSize=9,
            textColor=HexColor("#FFFFFF"), alignment=TA_CENTER,
        )) for h in task_headers]

        cell_style = ParagraphStyle(
            "Cell", fontName=_FN, fontSize=8,
            textColor=_DARK, alignment=TA_CENTER,
        )

        task_data = [header_row]
        for idx, task in enumerate(tasks, 1):
            cat = self.CATEGORY_MAP.get(task.category, task.category)
            status = self.STATUS_MAP.get(task.status, task.status)
            task_data.append([
                Paragraph(str(idx), cell_style),
                Paragraph(task.name[:25], cell_style),
                Paragraph(cat, cell_style),
                Paragraph(str(task.duration), cell_style),
                Paragraph(f"D{task.start_day}", cell_style),
                Paragraph(f"{task.progress:.0f}%", cell_style),
                Paragraph(status, cell_style),
                Paragraph(str(task.priority), cell_style),
            ])

        task_table = Table(task_data, colWidths=task_col_widths)
        task_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor("#FFFFFF"), HexColor("#F5F7FA")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(task_table)

        # ── Issue 列表 ──
        if issues:
            story.append(PageBreak())
            story.append(Paragraph("Issue 追踪", style_section_red))

            issue_headers = ["ID", "标题", "严重度", "状态", "优先级", "失效模式"]
            issue_col_widths = [18, 140, 45, 45, 40, 100]
            issue_header_row = [Paragraph(h, ParagraphStyle(
                "IH", fontName=_FN_B, fontSize=9,
                textColor=HexColor("#FFFFFF"), alignment=TA_CENTER,
            )) for h in issue_headers]

            issue_data = [issue_header_row]
            for issue in issues:
                sev = issue.severity
                status = self.STATUS_MAP.get(issue.status, issue.status)
                issue_data.append([
                    Paragraph(str(issue.id), cell_style),
                    Paragraph(issue.title[:30], cell_style),
                    Paragraph(sev, cell_style),
                    Paragraph(status, cell_style),
                    Paragraph(str(issue.priority), cell_style),
                    Paragraph((issue.failure_mode or "")[:20], cell_style),
                ])

            issue_table = Table(issue_data, colWidths=issue_col_widths)
            issue_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _RED),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [HexColor("#FFFFFF"), HexColor("#FFF5F5")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(issue_table)

        # ── 生成 PDF ──
        doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
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
