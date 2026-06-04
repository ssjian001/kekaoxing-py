"""导出服务门面 — 保持与原始 ExportService 完全相同的对外接口。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.issue import Issue, FARecord, CAPARecord
    from src.models.sample import Sample
    from src.models.test_plan import TestPlan, TestTask, TestResult

from src.services.export.export_utils import (
    get_cjk_font, _validate_output_path, STATUS_MAP, CATEGORY_MAP,
    excel_styles, excel_save,
)
from src.services.export.excel_exporter import (
    export_tasks_excel, export_issues_excel, export_samples_excel,
)
from src.services.export.pdf_exporter import (
    export_report_pdf, export_dvpr_pdf, export_8d_pdf,
)
from src.services.export.docx_exporter import (
    export_to_word, export_dvpr_docx, export_8d_docx,
    export_dvpr_excel,
)

# 为了向后兼容，重新导出常用名称
__all__ = [
    "ExportService", "get_cjk_font", "STATUS_MAP", "CATEGORY_MAP",
    "excel_styles", "excel_save",
    "export_tasks_excel", "export_issues_excel", "export_samples_excel",
    "export_report_pdf", "export_dvpr_pdf", "export_8d_pdf",
    "export_to_word", "export_dvpr_docx", "export_8d_docx",
    "export_dvpr_excel",
]


class ExportService:
    """导出服务门面 — 兼容旧有调用方式，内部委托给各子导出器。"""

    _CJK_FONT: str | None = None

    def __init__(self, output_dir: str = "exports") -> None:
        self._output_dir = Path(output_dir)

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: str | Path) -> None:
        self._output_dir = Path(value)

    def _ensure_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    def _validate_output_path(self, path: str | Path) -> Path:
        return _validate_output_path(path, self._output_dir)

    # ── 代理到各子导出器 ────────────────────────────────────

    def export_tasks_excel(self, plan, tasks, results=None, technician_names=None, filepath=None):
        return export_tasks_excel(self._output_dir, plan, tasks, results, technician_names, filepath)

    def export_issues_excel(self, issues, fa_map=None, capa_map=None, filepath=None):
        return export_issues_excel(self._output_dir, issues, fa_map, capa_map, filepath)

    def export_samples_excel(self, samples, filepath=None):
        return export_samples_excel(self._output_dir, samples, filepath)

    def export_report_pdf(self, plan, tasks, issues, samples, filepath=None, results=None):
        return export_report_pdf(self._output_dir, plan, tasks, issues, samples, filepath, results)

    def export_dvpr_pdf(self, plan, tasks, results, issues, samples, filepath=None):
        return export_dvpr_pdf(self._output_dir, plan, tasks, results, issues, samples, filepath)

    def export_dvpr_excel(self, plan, tasks, results, issues, samples, filepath=None):
        return export_dvpr_excel(self._output_dir, plan, tasks, results, issues, samples, filepath)

    def export_8d_pdf(self, issue, fa_records=None, capa_records=None, technician_name="", task=None, sample_sn="", filepath=None):
        return export_8d_pdf(self._output_dir, issue, fa_records, capa_records, technician_name, task, sample_sn, filepath)

    def export_to_word(self, plan, tasks, issues, samples, filepath=None, results=None):
        return export_to_word(self._output_dir, plan, tasks, issues, samples, filepath, results)

    def export_dvpr_docx(self, plan, tasks, results, issues, samples, filepath=None):
        return export_dvpr_docx(self._output_dir, plan, tasks, results, issues, samples, filepath)

    def export_8d_docx(self, issue, fa_records=None, capa_records=None, technician_name="", task=None, sample_sn="", filepath=None):
        return export_8d_docx(self._output_dir, issue, fa_records, capa_records, technician_name, task, sample_sn, filepath)

    # ── 类方法兼容 ──────────────────────────────────────────

    @classmethod
    def get_cjk_font(cls) -> str:
        return get_cjk_font()