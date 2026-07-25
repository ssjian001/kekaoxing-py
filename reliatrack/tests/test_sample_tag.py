"""测试样品二维码/条形码标签渲染与 SampleTagDialog 对话框。"""

import sys
import pytest
from PySide6.QtWidgets import QApplication
from src.models.sample import Sample
from src.views.dialogs.sample_tag_dialog import (
    render_sample_tag_pixmap,
    _generate_qr_matrix,
    SampleTagDialog,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_qr_matrix_generation():
    """测试二维码矩阵算法的生成维度与非空性。"""
    matrix = _generate_qr_matrix("SN-2026-0001")
    assert len(matrix) == 21
    assert len(matrix[0]) == 21
    # 确认 Finder pattern 的 4 个角块存在点
    assert matrix[0][0] is True
    assert matrix[0][6] is True


def test_render_sample_tag_pixmap(qapp):
    """测试 render_sample_tag_pixmap 绘制 QPixmap。"""
    sample = Sample(
        id=1,
        sn="SN-TEST-9999",
        batch_no="BATCH-2026",
        spec="5G-Module-A",
        status="in_stock",
        project_id=10,
    )
    pixmap = render_sample_tag_pixmap(sample, scale=2.0)
    assert not pixmap.isNull()
    assert pixmap.width() > 0
    assert pixmap.height() > 0


def test_sample_tag_dialog_instantiation(qapp):
    """测试 SampleTagDialog 创建与初始化。"""
    sample = Sample(
        id=2,
        sn="SN-TAG-8888",
        batch_no="BATCH-B",
        spec="Sensors-V2",
        status="in_use",
        project_id=5,
    )
    dialog = SampleTagDialog(sample=sample)
    assert dialog.windowTitle() == "样品标签 — SN-TAG-8888"
