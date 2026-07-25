"""Unit tests for EightDReportDialog (eight_d_dialog.py)."""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from src.models.issue import Issue, FARecord, CAPARecord
from src.views.dialogs.eight_d_dialog import EightDReportDialog, _DisciplineCard


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_issue():
    return Issue(
        id=101,
        project_id=1,
        title="外壳耐划伤测试剥落",
        description="在 500g 负载划痕测试下，表面漆层发生大面积剥落",
        severity="critical",
        status="analyzing",
        category="外观",
        root_cause="底漆附着力不够，烘烤温度不足",
        improvement_measures="调整烘烤槽温度至 180°C，延长烘烤时间至 30min",
        resolution="fixed",
    )



@pytest.fixture
def mock_fa_records():
    return [
        FARecord(id=1, issue_id=101, step_title="显微镜观察", findings="涂层界面存在百格剥离", created_at="2026-07-20 10:00:00"),
        FARecord(id=2, issue_id=101, step_title="膜厚仪测量", findings="膜厚均值 12um，低于标准 15um", created_at="2026-07-20 14:00:00"),
    ]



@pytest.fixture
def mock_capa_records():
    return [
        CAPARecord(id=1, issue_id=101, action="修改烘烤工艺参数 SOP", assignee_name="张工", status="verified"),
    ]



class TestEightDReportDialog:
    """Test 8D report visualization dialog and export triggers."""

    def test_dialog_initialization(self, qapp, mock_issue, mock_fa_records, mock_capa_records):
        dialog = EightDReportDialog(
            issue=mock_issue,
            fa_records=mock_fa_records,
            capa_records=mock_capa_records,
            technician_name="李工程",
            sample_sn="SN-20260720-001",
        )
        assert "8D 报告可视化预览" in dialog.windowTitle()
        assert dialog._issue.id == 101
        assert len(dialog._fa_records) == 2
        assert len(dialog._capa_records) == 1

    def test_copy_summary(self, qapp, mock_issue):
        dialog = EightDReportDialog(issue=mock_issue)
        dialog._copy_summary()

        clipboard_text = QApplication.clipboard().text()
        assert "8D Report: Issue #101" in clipboard_text
        assert "外壳耐划伤测试剥落" in clipboard_text
        assert "D1 团队" in clipboard_text
        assert "D8 结案" in clipboard_text

    def test_export_pdf_and_docx_callbacks(self, qapp, mock_issue, monkeypatch):
        mock_export_service = MagicMock()
        mock_export_service.export_8d_pdf.return_value = "/tmp/test.pdf"
        mock_export_service.export_8d_docx.return_value = "/tmp/test.docx"

        dialog = EightDReportDialog(issue=mock_issue, export_service=mock_export_service)

        # Mock QMessageBox to avoid popping modal in headless test
        monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a, **kw: None)

        dialog._export_pdf()
        assert mock_export_service.export_8d_pdf.called

        dialog._export_docx()
        assert mock_export_service.export_8d_docx.called
