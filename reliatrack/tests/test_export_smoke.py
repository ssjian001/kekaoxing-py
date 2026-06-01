"""导出冒烟测试 — 验证 8 种导出方法在 headless 环境下正常运行。

覆盖要点：
- 文件生成（路径存在、文件非空、扩展名正确）
- CJK 字体不报错（中文标题、中文状态）
- export_service 零 Qt 依赖，纯 Python 测试
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.test_plan import TestPlan, TestTask, TestResult
from src.models.issue import Issue, FARecord, CAPARecord
from src.models.sample import Sample
from src.services.export_service import ExportService


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture()
def svc(tmp_path: Path) -> ExportService:
    """创建以临时目录为输出路径的 ExportService。"""
    return ExportService(output_dir=str(tmp_path))


@pytest.fixture()
def plan() -> TestPlan:
    return TestPlan(id=1, project_id=1, name="中文测试计划", start_date="2026-01-01")


@pytest.fixture()
def tasks() -> list[TestTask]:
    return [
        TestTask(id=1, plan_id=1, name="高温测试", start_day=0, duration=3),
        TestTask(id=2, plan_id=1, name="低温测试", start_day=3, duration=2),
    ]


@pytest.fixture()
def results() -> list[TestResult]:
    return [
        TestResult(id=1, task_id=1, sample_id=1, result="pass"),
        TestResult(id=2, task_id=1, sample_id=2, result="fail"),
    ]


@pytest.fixture()
def samples() -> list[Sample]:
    return [
        Sample(id=1, sn="SN001", project_id=1, status="in_stock"),
        Sample(id=2, sn="SN002", project_id=1, status="checked_out"),
    ]


@pytest.fixture()
def issues() -> list[Issue]:
    return [
        Issue(
            id=1,
            title="中文失效标题",
            project_id=1,
            status="closed",
            severity="major",
            description="描述内容",
        ),
    ]


@pytest.fixture()
def fa_records() -> list[FARecord]:
    return [
        FARecord(id=1, issue_id=1, step_no=1, step_title="外观检查", findings="发现裂纹"),
    ]


@pytest.fixture()
def capa_records() -> list[CAPARecord]:
    return [
        CAPARecord(id=1, issue_id=1, action="纠正措施描述", status="completed"),
    ]


# ═══════════════════════════════════════════════════════════════
#  辅助校验
# ═══════════════════════════════════════════════════════════════

def _assert_valid_file(path: str, ext: str) -> None:
    """断言文件存在、非空、扩展名正确。"""
    p = Path(path)
    assert p.exists(), f"文件不存在: {p}"
    assert p.stat().st_size > 0, f"文件为空: {p}"
    assert p.suffix == ext, f"扩展名不符: 期望 {ext}, 实际 {p.suffix}"


# ═══════════════════════════════════════════════════════════════
#  1. export_tasks_excel → xlsx
# ═══════════════════════════════════════════════════════════════

def test_export_tasks_excel(svc: ExportService, plan: TestPlan, tasks: list[TestTask]):
    path = svc.export_tasks_excel(plan, tasks)
    _assert_valid_file(path, ".xlsx")


# ═══════════════════════════════════════════════════════════════
#  2. export_issues_excel → xlsx
# ═══════════════════════════════════════════════════════════════

def test_export_issues_excel(
    svc: ExportService,
    issues: list[Issue],
    fa_records: list[FARecord],
    capa_records: list[CAPARecord],
):
    fa_map = {1: fa_records}
    capa_map = {1: capa_records}
    path = svc.export_issues_excel(issues, fa_map, capa_map)
    _assert_valid_file(path, ".xlsx")


# ═══════════════════════════════════════════════════════════════
#  3. export_samples_excel → xlsx
# ═══════════════════════════════════════════════════════════════

def test_export_samples_excel(svc: ExportService, samples: list[Sample]):
    path = svc.export_samples_excel(samples)
    _assert_valid_file(path, ".xlsx")


# ═══════════════════════════════════════════════════════════════
#  4. export_report_pdf → pdf
# ═══════════════════════════════════════════════════════════════

def test_export_report_pdf(
    svc: ExportService,
    plan: TestPlan,
    tasks: list[TestTask],
    issues: list[Issue],
    samples: list[Sample],
):
    path = svc.export_report_pdf(plan, tasks, issues, samples)
    _assert_valid_file(path, ".pdf")


# ═══════════════════════════════════════════════════════════════
#  5. export_to_word → docx
# ═══════════════════════════════════════════════════════════════

def test_export_to_word(
    svc: ExportService,
    plan: TestPlan,
    tasks: list[TestTask],
    issues: list[Issue],
    samples: list[Sample],
):
    path = svc.export_to_word(plan, tasks, issues, samples)
    _assert_valid_file(path, ".docx")


# ═══════════════════════════════════════════════════════════════
#  6. export_dvpr_excel → xlsx
# ═══════════════════════════════════════════════════════════════

def test_export_dvpr_excel(
    svc: ExportService,
    plan: TestPlan,
    tasks: list[TestTask],
    results: list[TestResult],
    issues: list[Issue],
    samples: list[Sample],
):
    path = svc.export_dvpr_excel(plan, tasks, results, issues, samples)
    _assert_valid_file(path, ".xlsx")


# ═══════════════════════════════════════════════════════════════
#  7. export_dvpr_pdf → pdf
# ═══════════════════════════════════════════════════════════════

def test_export_dvpr_pdf(
    svc: ExportService,
    plan: TestPlan,
    tasks: list[TestTask],
    results: list[TestResult],
    issues: list[Issue],
    samples: list[Sample],
):
    path = svc.export_dvpr_pdf(plan, tasks, results, issues, samples)
    _assert_valid_file(path, ".pdf")


# ═══════════════════════════════════════════════════════════════
#  8. export_dvpr_docx → docx
# ═══════════════════════════════════════════════════════════════

def test_export_dvpr_docx(
    svc: ExportService,
    plan: TestPlan,
    tasks: list[TestTask],
    results: list[TestResult],
    issues: list[Issue],
    samples: list[Sample],
):
    path = svc.export_dvpr_docx(plan, tasks, results, issues, samples)
    _assert_valid_file(path, ".docx")


# ═══════════════════════════════════════════════════════════════
#  10. export_8d_pdf → pdf
# ═══════════════════════════════════════════════════════════════

def test_export_8d_pdf(
    svc: ExportService,
    issues: list[Issue],
    fa_records: list[FARecord],
    capa_records: list[CAPARecord],
):
    path = svc.export_8d_pdf(
        issues[0],
        fa_records=fa_records,
        capa_records=capa_records,
        technician_name="张工",
        sample_sn="SN001",
    )
    _assert_valid_file(path, ".pdf")


# ═══════════════════════════════════════════════════════════════
#  11. export_8d_docx → docx
# ═══════════════════════════════════════════════════════════════

def test_export_8d_docx(
    svc: ExportService,
    issues: list[Issue],
    fa_records: list[FARecord],
    capa_records: list[CAPARecord],
):
    path = svc.export_8d_docx(
        issues[0],
        fa_records=fa_records,
        capa_records=capa_records,
        technician_name="张工",
        sample_sn="SN001",
    )
    _assert_valid_file(path, ".docx")


# ═══════════════════════════════════════════════════════════════
#  CJK 中文内容边界测试
# ═══════════════════════════════════════════════════════════════

def test_cjk_task_names(svc: ExportService, plan: TestPlan):
    """验证全中文任务名、中文状态标签不报错。"""
    tasks = [
        TestTask(
            id=i,
            plan_id=1,
            name=f"第{i}项：高低温循环试验",
            start_day=i * 3,
            duration=2,
            status="pending",
        )
        for i in range(1, 6)
    ]
    path = svc.export_tasks_excel(plan, tasks)
    _assert_valid_file(path, ".xlsx")


def test_cjk_issue_export(
    svc: ExportService,
    issues: list[Issue],
    fa_records: list[FARecord],
    capa_records: list[CAPARecord],
):
    """验证中文 Issue 标题 + 中文 FA/CAPA 内容导出。"""
    fa_map = {1: fa_records}
    capa_map = {1: capa_records}
    path = svc.export_issues_excel(issues, fa_map, capa_map)
    _assert_valid_file(path, ".xlsx")


def test_empty_data_exports(svc: ExportService, plan: TestPlan):
    """验证空数据集导出不会崩溃。"""
    # 空任务列表
    path1 = svc.export_tasks_excel(plan, [])
    _assert_valid_file(path1, ".xlsx")

    # 空样品列表
    path2 = svc.export_samples_excel([])
    _assert_valid_file(path2, ".xlsx")

    # 空 Issue 列表
    path3 = svc.export_issues_excel([])
    _assert_valid_file(path3, ".xlsx")
