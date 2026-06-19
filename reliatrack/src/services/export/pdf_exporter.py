"""导出服务 — PDF 导出器。

包含：综合报告 PDF、DVP&R PDF、8D Report PDF（reportlab）。
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.issue import Issue, FARecord, CAPARecord
    from src.models.sample import Sample
    from src.models.test_plan import TestPlan, TestTask, TestResult

from src.services.export.export_utils import (
    CATEGORY_MAP, STATUS_MAP, get_cjk_font, _judge_conclusion,
    _validate_output_path, logger,
)
from src.constants import RESOLUTION_LABELS

if TYPE_CHECKING:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas as _Canvas
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
else:
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


def _find_cjk_font() -> tuple[str, str, int | None, int | None]:
    """跨平台查找可用的中文字体（reportlab 用）。

    Returns:
        (regular_path, bold_path, regular_subfont, bold_subfont)
        subfont 为 None 表示纯 TTF 文件，无需指定索引。
    """
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        fd = os.path.join(windir, "Fonts")
        candidates: list[tuple[str, str, int | None, int | None]] = [
            (os.path.join(fd, "msyh.ttc"), os.path.join(fd, "msyhbd.ttc"), 0, 0),
            (os.path.join(fd, "msyh.ttc"), os.path.join(fd, "msyh.ttc"), 0, 1),
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
            ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
             "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
             None, None),
            ("/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
             "/usr/share/fonts-droid-fallback/truetype/DroidSansFallback.ttf",
             None, None),
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

    logger.warning(
        "未找到系统 CJK 字体，使用 reportlab 内置 STSong-Light 作为 fallback"
    )
    return ("", "", -1, -1)


def _register_cjk_fonts():
    """注册中文字体，返回正文字体和粗体字体名称。"""
    reg_path, bld_path, reg_sub, bld_sub = _find_cjk_font()
    _FN = "CJK"
    _FN_B = "CJK-Bold"

    if reg_sub == -1:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        if _FN not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _FN = "STSong-Light"
        _FN_B = "STSong-Light"
    else:
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

    return _FN, _FN_B


def _build_header_footer(canvas: _Canvas, doc: object, title_text: str = "ReliaTrack",
                         font_name: str = "CJK") -> None:
    """页眉页脚回调。"""
    canvas.saveState()
    canvas.setFont(font_name, 8)
    canvas.setFillColor(HexColor("#969696"))
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm,
                           f"{title_text} — 可靠性测试报告")
    canvas.drawCentredString(A4[0] / 2, 12 * mm,
                             f"第 {canvas.getPageNumber()} 页")
    canvas.restoreState()


def export_report_pdf(
    output_dir: Path,
    plan: TestPlan,
    tasks: list[TestTask],
    issues: list[Issue],
    samples: list[Sample],
    filepath: str | None = None,
    results: list | None = None,
) -> str:
    """导出综合测试报告为 PDF。"""
    _FN, _FN_B = _register_cjk_fonts()

    _BLUE = HexColor("#2B579A")
    _RED = HexColor("#C0504D")
    _GRAY = HexColor("#646464")
    _LIGHT_GRAY = HexColor("#969696")
    _DARK = HexColor("#323232")

    style_title = ParagraphStyle("Title", fontName=_FN_B, fontSize=24,
                                  textColor=_BLUE, alignment=TA_CENTER, spaceAfter=8 * mm)
    style_subtitle = ParagraphStyle("Subtitle", fontName=_FN, fontSize=14,
                                     textColor=_GRAY, alignment=TA_CENTER, spaceAfter=4 * mm)
    style_ts = ParagraphStyle("Timestamp", fontName=_FN, fontSize=10,
                               textColor=_LIGHT_GRAY, alignment=TA_CENTER)
    style_section = ParagraphStyle("Section", fontName=_FN_B, fontSize=16,
                                    textColor=_BLUE, spaceAfter=3 * mm, spaceBefore=6 * mm)
    style_section_red = ParagraphStyle("SectionRed", fontName=_FN_B, fontSize=14,
                                        textColor=_RED, spaceAfter=2 * mm, spaceBefore=4 * mm)
    style_stat = ParagraphStyle("Stat", fontName=_FN, fontSize=11,
                                 textColor=_DARK, spaceAfter=1 * mm)
    style_header = ParagraphStyle("Header", fontName=_FN, fontSize=8,
                                   textColor=_LIGHT_GRAY, alignment=TA_CENTER)
    cell_style = ParagraphStyle("Cell", fontName=_FN, fontSize=8,
                                 textColor=_DARK, alignment=TA_CENTER)

    out = filepath or str(
        output_dir / f"测试报告_{plan.name}_{datetime.now():%Y%m%d_%H%M}.pdf"
    )
    doc_obj = SimpleDocTemplate(
        out, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
    )

    story: list[object] = []

    # ── 封面 ──
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph("可靠性测试报告", style_title))
    story.append(Paragraph(f"计划: {plan.name}", style_subtitle))
    story.append(Paragraph(f"测试标准: {plan.test_standard or '—'}", style_subtitle))
    story.append(Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", style_ts))

    # ── 概览 ──
    story.append(PageBreak())
    story.append(Paragraph("概览统计", style_section))

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    in_progress = sum(1 for t in tasks if t.status == "in_progress")
    pending = sum(1 for t in tasks if t.status == "pending")
    total_days = max(((t.start_day or 0) + t.duration for t in tasks), default=0)
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

    task_headers = ["序号", "名称", "类别", "天数", "开始", "进度", "状态", "优先级", "设备", "技术员"]
    task_col_widths = [18, 100, 45, 30, 30, 35, 42, 35, 45, 45]
    header_row = [Paragraph(h, ParagraphStyle("TH", fontName=_FN_B, fontSize=9,
                                               textColor=HexColor("#FFFFFF"), alignment=TA_CENTER))
                  for h in task_headers]

    prefix = getattr(plan, 'task_prefix', '') or ''
    # 预构建技术员名称映射
    tech_name_map: dict[int, str] = {}
    task_data_rows: list[list[object]] = []
    for idx, task in enumerate(tasks, 1):
        task_id_display = f"{prefix}-{idx:03d}" if prefix else str(idx)
        cat = CATEGORY_MAP.get(task.category, task.category)
        status = STATUS_MAP.get(task.status, task.status)
        equip = f"ID:{task.equipment_id}" if task.equipment_id else "—"
        tech = tech_name_map.get(task.technician_id, f"ID:{task.technician_id}") if task.technician_id else "—"
        task_data_rows.append([
            Paragraph(task_id_display, cell_style),
            Paragraph(task.name[:25], cell_style),
            Paragraph(cat, cell_style),
            Paragraph(str(task.duration), cell_style),
            Paragraph(f"D{task.start_day}", cell_style),
            Paragraph(f"{task.progress:.0f}%", cell_style),
            Paragraph(status, cell_style),
            Paragraph(str(task.priority), cell_style),
            Paragraph(equip, cell_style),
            Paragraph(tech, cell_style),
        ])

    if not task_data_rows:
        task_data_rows = [[Paragraph("—", cell_style)] * len(task_headers)]

    task_table = Table([header_row] + task_data_rows, colWidths=task_col_widths)
    task_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F5F7FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(task_table)

    # ── Issue 列表 ──
    if issues:
        story.append(PageBreak())
        story.append(Paragraph("Issue 追踪", style_section_red))

        issue_headers = ["ID", "Issue描述", "严重度", "状态", "优先级", "DRI", "报告人", "解决结果", "根因", "改善对策"]
        issue_header_row = [Paragraph(h, ParagraphStyle("IH", fontName=_FN_B, fontSize=9,
                                                         textColor=HexColor("#FFFFFF"), alignment=TA_CENTER))
                            for h in issue_headers]

        issue_data = [issue_header_row]
        for issue in issues:
            sev = issue.severity
            status = STATUS_MAP.get(issue.status, issue.status)
            resolution_text = RESOLUTION_LABELS.get(issue.resolution, issue.resolution) or ""
            issue_data.append([
                Paragraph(str(issue.id), cell_style),
                Paragraph(issue.title[:30], cell_style),
                Paragraph(sev, cell_style),
                Paragraph(status, cell_style),
                Paragraph(str(issue.priority), cell_style),
                Paragraph((issue.dri_name or "")[:15], cell_style),
                Paragraph((issue.reporter_name or "")[:15], cell_style),
                Paragraph(resolution_text, cell_style),
                Paragraph((issue.root_cause or "")[:50], cell_style),
                Paragraph((issue.improvement_measures or "")[:60], cell_style),
            ])

        issue_table = Table(issue_data, colWidths=[18, 100, 40, 40, 30, 45, 45, 50, 65, 65])
        issue_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#FFF5F5")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(issue_table)

    # ── 测试结果汇总 ──
    _results = results or []
    if _results:
        story.append(PageBreak())
        story.append(Paragraph("测试结果汇总", style_section))

        sample_map = {s.id: s.sn for s in samples if s.id is not None}
        task_map = {t.id: t for t in tasks if t.id is not None}

        total_pass = sum(1 for r in _results if r.result == "pass")
        total_fail = sum(1 for r in _results if r.result == "fail")
        total_conditional = sum(1 for r in _results if r.result == "conditional")
        total_results = len(_results)
        pass_rate = f"{total_pass / total_results * 100:.1f}%" if total_results else "—"

        stat_lines = [
            f"测试结果总数: {total_results}  |  通过: {total_pass}  |  失败: {total_fail}  |  条件通过: {total_conditional}  |  通过率: {pass_rate}",
        ]
        overall_conclusion = _judge_conclusion(
            total_pass, total_fail, total_conditional,
            accept_criteria="",
        )
        stat_lines.append(f"总体判定结论: {overall_conclusion}")
        for s in stat_lines:
            story.append(Paragraph(s, style_stat))

        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("结果明细", ParagraphStyle(
            "SubSection", fontName=_FN_B, fontSize=12,
            textColor=_BLUE, spaceAfter=2 * mm, spaceBefore=3 * mm,
        )))

        res_headers = ["序号", "任务名", "样品SN", "结果", "判定"]
        res_col_widths = [18, 120, 100, 50, 50]
        res_header_row = [Paragraph(h, ParagraphStyle("RH", fontName=_FN_B, fontSize=9,
                                                       textColor=HexColor("#FFFFFF"), alignment=TA_CENTER))
                          for h in res_headers]

        res_data = [res_header_row]
        # 预计算每个 task 的结论（O(N)），避免每行重复遍历
        _task_conclusions: dict[int, str] = {}
        for tid in {x.task_id for x in _results if x.task_id}:
            tp = sum(1 for x in _results if x.task_id == tid and x.result == "pass")
            tf = sum(1 for x in _results if x.task_id == tid and x.result == "fail")
            tc = sum(1 for x in _results if x.task_id == tid and x.result == "conditional")
            t_obj = task_map.get(tid)
            _task_conclusions[tid] = _judge_conclusion(
                tp, tf, tc,
                accept_criteria=(t_obj.accept_criteria or "") if t_obj else "",
            )

        for idx, r in enumerate(_results, 1):
            task_name = (task_map[r.task_id].name or "")[:25] if r.task_id and r.task_id in task_map else ""
            sample_sn = sample_map.get(r.sample_id, f"#{r.sample_id}") if r.sample_id else "—"
            result_text = r.result.upper() if r.result else "—"

            conclusion = _task_conclusions.get(r.task_id, "")
            if idx > 1 and _results[idx - 2].task_id == r.task_id:
                conclusion = ""

            res_data.append([
                Paragraph(str(idx), cell_style),
                Paragraph(task_name, cell_style),
                Paragraph(sample_sn, cell_style),
                Paragraph(result_text, cell_style),
                Paragraph(conclusion, cell_style),
            ])

        res_table = Table(res_data, colWidths=res_col_widths)
        _GREEN = HexColor("#339933")
        res_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F0FFF0")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(res_table)

    output_dir.mkdir(parents=True, exist_ok=True)
    _validate_output_path(out, output_dir)
    # 闭包捕获实际字体名，避免 fallback 路径下字体名不一致
    _hf = lambda c, d: _build_header_footer(c, d, font_name=_FN)
    try:
        doc_obj.build(story, onFirstPage=_hf, onLaterPages=_hf)
    except (OSError, PermissionError) as e:
        logger.error("PDF build failed: %s → %s", out, e)
        if os.path.exists(out):
            try:
                os.unlink(out)
            except OSError:
                pass
        raise
    return os.path.abspath(out)


# ---------------------------------------------------------------------------
# DVP&R PDF 导出
# ---------------------------------------------------------------------------

def export_dvpr_pdf(
    output_dir: Path,
    plan: TestPlan,
    tasks: list[TestTask],
    results: list[TestResult],
    issues: list[Issue],
    samples: list[Sample],
    filepath: str | None = None,
) -> str:
    """导出 DVP&R (Design Verification Plan & Report) 格式 PDF。

    DVP&R = 设计验证计划与报告，汽车行业标准格式。
    包含：封面、概览统计、DVP&R 矩阵（任务×样品+判定）、
    Issue/FA/CAPA 汇总、校准状态汇总。
    """
    from reportlab.lib.pagesizes import A4, landscape

    _FN, _FN_B = _register_cjk_fonts()

    _BLUE = HexColor("#2B579A")
    _RED = HexColor("#C0504D")
    _GREEN = HexColor("#339933")
    _GRAY = HexColor("#646464")
    _LIGHT_GRAY = HexColor("#969696")
    _DARK = HexColor("#323232")
    _PASS_BG = HexColor("#E8F5E9")
    _FAIL_BG = HexColor("#FFEBEE")

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
        "Section", fontName=_FN_B, fontSize=14,
        textColor=_BLUE, spaceAfter=3 * mm, spaceBefore=6 * mm,
    )
    style_stat = ParagraphStyle(
        "Stat", fontName=_FN, fontSize=11,
        textColor=_DARK, spaceAfter=1 * mm,
    )
    cell_style = ParagraphStyle(
        "Cell", fontName=_FN, fontSize=7,
        textColor=_DARK, alignment=TA_CENTER,
    )
    cell_left = ParagraphStyle(
        "CellL", fontName=_FN, fontSize=7,
        textColor=_DARK, alignment=TA_LEFT,
    )
    th_style = ParagraphStyle(
        "TH", fontName=_FN_B, fontSize=7,
        textColor=HexColor("#FFFFFF"), alignment=TA_CENTER,
    )

    def _header_footer(canvas: _Canvas, doc: object) -> None:
        canvas.saveState()
        canvas.setFont(_FN, 7)
        canvas.setFillColor(_LIGHT_GRAY)
        canvas.drawRightString(
            landscape(A4)[0] - 20 * mm, landscape(A4)[1] - 12 * mm,
            "ReliaTrack — DVP&R Report",
        )
        canvas.drawCentredString(
            landscape(A4)[0] / 2, 10 * mm,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    output_dir.mkdir(parents=True, exist_ok=True)
    out = filepath or str(
        output_dir / f"DVP&R_{plan.name}_{datetime.now():%Y%m%d_%H%M}.pdf"
    )
    doc = SimpleDocTemplate(
        out, pagesize=landscape(A4),
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=12 * mm, rightMargin=12 * mm,
    )

    story: list[object] = []

    # ── 封面 ──
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("DVP&R", style_title))
    story.append(Paragraph("Design Verification Plan & Report", style_subtitle))
    story.append(Paragraph(f"计划: {plan.name}", style_subtitle))
    story.append(Paragraph(f"测试标准: {plan.test_standard or '—'}", style_subtitle))
    story.append(Paragraph(
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", style_ts))

    # ── 版本号与日期 ──
    style_version = ParagraphStyle(
        "Version", fontName=_FN, fontSize=11,
        textColor=_DARK, alignment=TA_CENTER, spaceAfter=2 * mm,
    )
    version_line = (
        f"版本: V1.0　　　日期: {datetime.now().strftime('%Y-%m-%d')}"
    )
    story.append(Paragraph(version_line, style_version))

    # ── 概览 ──
    story.append(PageBreak())
    story.append(Paragraph("概览统计", style_section))

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    total_pass = sum(1 for r in results if r.result == "pass")
    total_fail = sum(1 for r in results if r.result == "fail")
    total_results = len(results)
    pass_rate = f"{total_pass / total_results * 100:.1f}%" if total_results else "—"

    for s in [
        f"总任务数: {total}  |  已完成: {completed}",
        f"测试结果: {total_results}  |  通过: {total_pass}  |  失败: {total_fail}  |  通过率: {pass_rate}",
        f"Issue 数: {len(issues)}",
        f"样品数: {len(samples)}",
    ]:
        story.append(Paragraph(s, style_stat))

    # ── DVP&R 矩阵 ──
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("DVP&R 矩阵", style_section))

    # 收集所有涉及样品
    sample_ids = sorted({r.sample_id for r in results if r.sample_id})
    sample_map = {s.id: s.sn for s in samples if s.id is not None}

    # 构建 lookup: (task_id, sample_id) → result
    lookup: dict[tuple[int, int], str] = {}
    for r in results:
        if r.task_id and r.sample_id:
            lookup[(r.task_id, r.sample_id)] = r.result

    # 表头
    dvpr_headers = ["序号", "测试项", "判定准则", "样品 SN"]
    for sid in sample_ids:
        dvpr_headers.append(sample_map.get(sid, f"#{sid}"))
    dvpr_headers.append("结论")

    header_row = [Paragraph(h, th_style) for h in dvpr_headers]
    dvpr_data = [header_row]

    prefix = getattr(plan, 'task_prefix', '') or ''
    for idx, task in enumerate(tasks, 1):
        row = [
            Paragraph(f"{prefix}-{idx:03d}" if prefix else str(idx), cell_style),
            Paragraph((task.name or "")[:20], cell_left),
            Paragraph((task.accept_criteria or "")[:20], cell_left),
        ]
        # 样品 SN 列 — 列出本任务关联的样品编号
        task_sample_ids = sorted({
            r.sample_id for r in results
            if r.task_id == task.id and r.sample_id
        })
        task_sns = ", ".join(
            sample_map.get(sid, f"#{sid}") for sid in task_sample_ids
        )
        row.append(Paragraph((task_sns or "—")[:25], cell_left))
        task_pass = 0
        task_fail = 0
        task_conditional = 0
        for sid in sample_ids:
            res = lookup.get((task.id, sid), "")
            if res == "pass":
                row.append(Paragraph("P", cell_style))
                task_pass += 1
            elif res == "fail":
                row.append(Paragraph("F", cell_style))
                task_fail += 1
            elif res == "conditional":
                row.append(Paragraph("C", cell_style))
                task_conditional += 1
            elif res == "skip":
                row.append(Paragraph("S", cell_style))
            else:
                row.append(Paragraph("—", cell_style))
        # 结论
        conclusion = _judge_conclusion(
            task_pass, task_fail, task_conditional,
            accept_criteria=task.accept_criteria or "",
        )
        row.append(Paragraph(conclusion, cell_style))
        dvpr_data.append(row)

    # 列宽
    n_samples = len(sample_ids)
    page_w = landscape(A4)[0] - 24 * mm
    fixed_cols = 18 + 80 + 65 + 60 + 35  # # + name + criteria + SN + conclusion
    sample_col_w = max(35, (page_w - fixed_cols) / max(n_samples, 1))
    dvpr_widths = [18, 80, 65, 60] + [sample_col_w] * n_samples + [35]

    dvpr_table = Table(dvpr_data, colWidths=dvpr_widths)
    table_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [HexColor("#FFFFFF"), HexColor("#F5F7FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    # 着色 pass/fail 单元格
    for row_idx, task in enumerate(tasks, 1):
        for col_idx, sid in enumerate(sample_ids):
            res = lookup.get((task.id, sid), "")
            if res == "fail":
                table_styles.append(("BACKGROUND", (col_idx + 4, row_idx), (col_idx + 4, row_idx), _FAIL_BG))
            elif res == "pass":
                table_styles.append(("BACKGROUND", (col_idx + 4, row_idx), (col_idx + 4, row_idx), _PASS_BG))

    dvpr_table.setStyle(TableStyle(table_styles))
    story.append(dvpr_table)

    # ── Issue 汇总 ──
    if issues:
        story.append(PageBreak())
        story.append(Paragraph("Issue 追踪汇总", style_section))
        issue_headers = ["ID", "Issue描述", "严重度", "状态", "DRI", "报告人", "解决结果", "改善对策"]
        issue_data = [[Paragraph(h, th_style) for h in issue_headers]]
        for issue in issues:
            resolution_text = RESOLUTION_LABELS.get(issue.resolution, issue.resolution) or ""
            issue_data.append([
                Paragraph(str(issue.id), cell_style),
                Paragraph((issue.title or "")[:30], cell_left),
                Paragraph(issue.severity, cell_style),
                Paragraph(STATUS_MAP.get(issue.status, issue.status), cell_style),
                Paragraph((issue.dri_name or "")[:15], cell_style),
                Paragraph((issue.reporter_name or "")[:15], cell_style),
                Paragraph(resolution_text, cell_style),
                Paragraph((issue.improvement_measures or "")[:80], cell_left),
            ])
        issue_table = Table(issue_data, colWidths=[25, 120, 50, 50, 55, 55, 60, 80])
        issue_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(issue_table)

    # ── 签字栏 ──
    story.append(Spacer(1, 12 * mm))
    sig_label_style = ParagraphStyle(
        "SigLabel", fontName=_FN_B, fontSize=9,
        textColor=_DARK, alignment=TA_CENTER,
    )
    sig_line_style = ParagraphStyle(
        "SigLine", fontName=_FN, fontSize=9,
        textColor=_LIGHT_GRAY, alignment=TA_CENTER,
    )
    sig_roles = ["编制", "审核", "批准"]
    sig_cells = []
    for role in sig_roles:
        sig_cells.append([
            Paragraph(role, sig_label_style),
            Spacer(1, 10 * mm),
            Paragraph("________________________", sig_line_style),
        ])
    sig_table = Table(
        [sig_cells],
        colWidths=[page_w / 3] * 3,
    )
    sig_table.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.5, _GRAY),
        ("BOX", (1, 0), (1, 0), 0.5, _GRAY),
        ("BOX", (2, 0), (2, 0), 0.5, _GRAY),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    _validate_output_path(out, output_dir)
    try:
        doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    except (OSError, PermissionError) as e:
        logger.error("PDF build failed: %s → %s", out, e)
        raise
    return os.path.abspath(out)


# ---------------------------------------------------------------------------
# 8D Report PDF 导出 — 辅助函数
# ---------------------------------------------------------------------------

def _build_d4_content(issue: Issue, fa_records: list[FARecord] | None) -> str:
    """构建 D4 根因分析内容。"""
    parts: list[str] = []
    if issue.root_cause:
        parts.append(f"根因: {issue.root_cause}")
    if issue.failure_mode:
        parts.append(f"失效模式: {issue.failure_mode}")
    if fa_records:
        parts.append("\nFA 分析记录摘要:")
        for rec in fa_records:
            confirmed_labels = {0: "待定", 1: "确认", 2: "排除"}
            status = confirmed_labels.get(rec.confirmed, "待定")
            parts.append(
                f"  Step {rec.step_no}: {rec.step_title or ''}"
                f" — {rec.method or ''}"
                f" — 发现: {rec.findings or '—'}"
                f" — 可能原因: {rec.possible_cause or '—'}"
                f" [{status}]"
            )
    return "\n".join(parts) if parts else ""


def _build_d6_content(capa_records: list[CAPARecord] | None) -> str:
    """构建 D6 实施验证内容。"""
    if not capa_records:
        return ""
    parts: list[str] = []
    for rec in capa_records:
        status_labels = {
            "pending": "待执行", "in_progress": "进行中",
            "completed": "已完成", "verified": "已验证",
        }
        status = status_labels.get(rec.status, rec.status)
        parts.append(f"措施: {rec.action}")
        assignee_name = getattr(rec, 'assignee_name', '') or ''
        if assignee_name:
            parts.append(f"  负责人: {assignee_name}")
        parts.append(f"  状态: {status}")
        if rec.verification_result:
            parts.append(f"  验证结果: {rec.verification_result}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 8D Report PDF 导出
# ---------------------------------------------------------------------------

def export_8d_pdf(
    output_dir: Path,
    issue: Issue,
    fa_records: list[FARecord] | None = None,
    capa_records: list[CAPARecord] | None = None,
    technician_name: str = "",
    task: TestTask | None = None,
    sample_sn: str = "",
    filepath: str | None = None,
) -> str:
    """导出 8D Problem Solving Report 为 PDF。

    包含：基本信息表、D1-D8 八个章节、底部签字栏。
    用 Issue 已有数据填充可匹配的部分，其余留空供用户手写。

    Args:
        output_dir: 输出目录。
        issue: Issue 对象。
        fa_records: FA 分析记录列表。
        capa_records: CAPA 记录列表。
        technician_name: Issue 负责人姓名（用于 D1 团队）。
        task: 关联的测试任务（用于 D2 测试条件）。
        sample_sn: 关联的样品 SN（用于 D2 问题描述）。
        filepath: 输出文件路径（可选）。
    """
    _FN, _FN_B = _register_cjk_fonts()

    _BLUE = HexColor("#2B579A")
    _RED = HexColor("#C0504D")
    _GRAY = HexColor("#646464")
    _LIGHT_GRAY = HexColor("#969696")
    _DARK = HexColor("#323232")
    _SECTION_BG = HexColor("#E8EDF5")

    style_title = ParagraphStyle(
        "Title8D", fontName=_FN_B, fontSize=22,
        textColor=_BLUE, alignment=TA_CENTER, spaceAfter=6 * mm,
    )
    style_subtitle = ParagraphStyle(
        "Sub8D", fontName=_FN, fontSize=12,
        textColor=_GRAY, alignment=TA_CENTER, spaceAfter=4 * mm,
    )
    style_section_label = ParagraphStyle(
        "SecL", fontName=_FN_B, fontSize=11,
        textColor=_BLUE, spaceAfter=1 * mm, spaceBefore=2 * mm,
    )
    style_body = ParagraphStyle(
        "Body8D", fontName=_FN, fontSize=9,
        textColor=_DARK, alignment=TA_LEFT, leading=14,
    )
    style_cell = ParagraphStyle(
        "Cell8D", fontName=_FN, fontSize=9,
        textColor=_DARK, alignment=TA_LEFT, leading=13,
    )
    style_cell_center = ParagraphStyle(
        "CellC8D", fontName=_FN, fontSize=9,
        textColor=_DARK, alignment=TA_CENTER, leading=13,
    )
    style_cell_bold = ParagraphStyle(
        "CellB8D", fontName=_FN_B, fontSize=9,
        textColor=_BLUE, alignment=TA_CENTER, leading=13,
    )
    style_blank = ParagraphStyle(
        "Blank8D", fontName=_FN, fontSize=9,
        textColor=_LIGHT_GRAY, alignment=TA_LEFT, leading=13,
    )
    style_sig_label = ParagraphStyle(
        "SigL8D", fontName=_FN_B, fontSize=9,
        textColor=_DARK, alignment=TA_CENTER,
    )
    style_sig_line = ParagraphStyle(
        "SigLine8D", fontName=_FN, fontSize=9,
        textColor=_LIGHT_GRAY, alignment=TA_CENTER,
    )

    def _header_footer(canvas: _Canvas, doc: object) -> None:
        canvas.saveState()
        canvas.setFont(_FN, 8)
        canvas.setFillColor(_LIGHT_GRAY)
        canvas.drawRightString(
            A4[0] - 20 * mm, A4[1] - 12 * mm,
            "ReliaTrack — 8D Problem Solving Report",
        )
        canvas.drawCentredString(
            A4[0] / 2, 12 * mm,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    output_dir.mkdir(parents=True, exist_ok=True)
    out = filepath or str(
        output_dir / f"8D_Report_Issue{issue.id}_{datetime.now():%Y%m%d_%H%M}.pdf"
    )
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
    )

    page_w = A4[0] - 30 * mm  # usable width

    story: list[object] = []

    # ── 标题 ──
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("8D Problem Solving Report", style_title))
    story.append(Paragraph(
        f"Issue #{issue.id} — {issue.title}", style_subtitle))
    story.append(Paragraph(
        f"报告日期: {datetime.now().strftime('%Y-%m-%d')}", style_subtitle))

    # ── 基本信息表 ──
    severity_labels = {
        "critical": "Critical (致命)",
        "major": "Major (严重)",
        "minor": "Minor (一般)",
        "cosmetic": "Cosmetic (外观)",
    }
    sev_text = severity_labels.get(issue.severity, issue.severity)
    status_text = STATUS_MAP.get(issue.status, issue.status)

    info_data = [
        [
            Paragraph("Issue 编号", style_cell_bold),
            Paragraph(str(issue.id), style_cell_center),
            Paragraph("严重度", style_cell_bold),
            Paragraph(sev_text, style_cell_center),
        ],
        [
            Paragraph("Issue描述", style_cell_bold),
            Paragraph(issue.title, style_cell),
            Paragraph("状态", style_cell_bold),
            Paragraph(status_text, style_cell_center),
        ],
        [
            Paragraph("报告日期", style_cell_bold),
            Paragraph(datetime.now().strftime("%Y-%m-%d"), style_cell_center),
            Paragraph("优先级", style_cell_bold),
            Paragraph(str(issue.priority), style_cell_center),
        ],
        [
            Paragraph("DRI", style_cell_bold),
            Paragraph(issue.dri_name or "", style_cell_center),
            Paragraph("报告人", style_cell_bold),
            Paragraph(issue.reporter_name or "", style_cell_center),
        ],
        [
            Paragraph("失效模式", style_cell_bold),
            Paragraph(issue.failure_mode or "", style_cell),
            Paragraph("解决结果", style_cell_bold),
            Paragraph(RESOLUTION_LABELS.get(issue.resolution, issue.resolution) or "", style_cell_center),
        ],
    ]
    info_table = Table(info_data, colWidths=[page_w * 0.15, page_w * 0.35, page_w * 0.15, page_w * 0.35])
    info_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, _GRAY),
        ("BACKGROUND", (0, 0), (0, -1), _SECTION_BG),
        ("BACKGROUND", (2, 0), (2, -1), _SECTION_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)

    # ── D1-D8 章节 ──
    # D1: 自动填充团队信息
    team_lines: list[str] = []
    if technician_name:
        team_lines.append(f"负责人: {technician_name}")
    d1_content = "\n".join(team_lines) if team_lines else "(手写区)"

    # D2: 问题描述 — 补充测试条件和样品信息
    d2_parts: list[str] = []
    if issue.description:
        d2_parts.append(issue.description)
    if task:
        tc_parts: list[str] = []
        if task.name:
            tc_parts.append(f"测试项: {task.name}")
        if task.temperature:
            tc_parts.append(f"温度: {task.temperature}")
        if task.humidity:
            tc_parts.append(f"湿度: {task.humidity}")
        if task.accept_criteria:
            tc_parts.append(f"判定准则: {task.accept_criteria}")
        if tc_parts:
            d2_parts.append("测试条件: " + " | ".join(tc_parts))
    if sample_sn:
        d2_parts.append(f"样品: {sample_sn}")
    if issue.failure_stage:
        d2_parts.append(f"失效阶段: {issue.failure_stage}")
    d2_content = "\n".join(d2_parts) if d2_parts else ""

    # D3: 临时遏制 — 列出 pending/in_progress 的 CAPA
    capa_pending: list[str] = []
    if capa_records:
        for _c in capa_records:
            if _c.status in ("pending", "in_progress"):
                capa_pending.append(f"• {_c.action} (状态: {_c.status})")
    d3_content = "\n".join(capa_pending) if capa_pending else "(手写区)"

    # D7: 预防再发 — 提示知识库
    d7_parts: list[str] = ["(手写区 — 建议归档至知识库)"]
    if issue.failure_mode:
        d7_parts.append(f"失效模式: {issue.failure_mode} → 建议同步至知识库")
    d7_content = "\n".join(d7_parts)

    d_sections: list[tuple[str, str, str]] = [
        ("D1", "团队组建 (Establish the Team)", d1_content),
        ("D2", "问题描述 (Describe the Problem)", d2_content),
        ("D3", "临时遏制措施 (Interim Containment Actions)", d3_content),
        ("D4", "根因分析 (Root Cause Analysis)", _build_d4_content(issue, fa_records)),
        ("D5", "纠正措施 (Corrective Actions)", (issue.improvement_measures or "") or RESOLUTION_LABELS.get(issue.resolution, issue.resolution) or ""),
        ("D6", "实施验证 (Implement & Validate)", _build_d6_content(capa_records)),
        ("D7", "预防再发 (Prevent Recurrence)", d7_content),
        ("D8", "结论与签字 (Congratulate the Team)", "(签字区)"),
    ]

    for d_label, d_title, d_content in d_sections:
        story.append(Spacer(1, 3 * mm))

        # D 章节标题行
        header_data = [[
            Paragraph(f"<b>{d_label}</b>", ParagraphStyle(
                "DH", fontName=_FN_B, fontSize=10,
                textColor=HexColor("#FFFFFF"), alignment=TA_CENTER,
            )),
            Paragraph(f"<b>{d_title}</b>", ParagraphStyle(
                "DT", fontName=_FN_B, fontSize=10,
                textColor=HexColor("#FFFFFF"), alignment=TA_LEFT,
            )),
        ]]
        header_table = Table(header_data, colWidths=[page_w * 0.12, page_w * 0.88])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)

        # D 内容行
        content_text = d_content if d_content else ""
        content_style = style_blank if content_text.startswith("(") else style_cell
        content_data = [[
            Paragraph("", style_cell),
            Paragraph(content_text or "", content_style),
        ]]
        content_table = Table(content_data, colWidths=[page_w * 0.12, page_w * 0.88])
        min_h = 50 if content_text.startswith("(") else max(30, len(content_text) // 2)
        content_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, _GRAY),
            ("LINEAFTER", (0, 0), (0, -1), 0.5, _GRAY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("ROWHEIGHTS", (0, 0), (-1, -1), min_h),
        ]))
        story.append(content_table)

    # ── 底部签字栏 ──
    story.append(Spacer(1, 8 * mm))
    sig_roles = ["编制 (Prepared)", "审核 (Reviewed)", "批准 (Approved)"]
    sig_cells = []
    for role in sig_roles:
        sig_cells.append([
            Paragraph(f"<b>{role}</b>", style_sig_label),
            Spacer(1, 10 * mm),
            Paragraph("________________________", style_sig_line),
        ])
    sig_table = Table(
        [sig_cells],
        colWidths=[page_w / 3] * 3,
    )
    sig_table.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.5, _GRAY),
        ("BOX", (1, 0), (1, 0), 0.5, _GRAY),
        ("BOX", (2, 0), (2, 0), 0.5, _GRAY),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    _validate_output_path(out, output_dir)
    try:
        doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    except (OSError, PermissionError) as e:
        logger.error("PDF build failed: %s → %s", out, e)
        raise
    return os.path.abspath(out)