"""样品二维码标签测试。

覆盖 2026-08-12 修复（commit 待定）：伪二维码 → segno 真实标准 QR（ISO/IEC 18004）。
- _generate_qr_matrix 生成真实标准 QR 矩阵（有完整定位角/格式信息/数据区域）
- _qr_payload 编码样品 SN+ID 结构化文本
- 渲染像素与 segno 矩阵一致（可被扫码器识别）
- 回归防护：禁止回到"21x21 伪矩阵"（只有定位角+随机点的装饰图）
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from src.models.sample import Sample
from src.views.dialogs.sample_tag_dialog import (
    _generate_qr_matrix,
    _qr_payload,
    render_sample_tag_pixmap,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module")
def sample():
    return Sample(
        id=7,
        sn="SMP-2026-001",
        batch_no="BATCH-A1",
        spec="规格XYZ-100",
        status="在库",
        project_id=3,
        created_at="2026-08-01 10:00:00",
    )


class TestQrPayload:
    def test_payload_contains_sn_and_id(self, sample):
        payload = _qr_payload(sample)
        assert "RELIATRACK-SAMPLE:" in payload
        assert "SN=SMP-2026-001" in payload
        assert "ID=7" in payload

    def test_payload_uses_id_when_sn_empty(self):
        s = Sample(id=42, sn="", batch_no="", spec="")
        payload = _qr_payload(s)
        assert "SN=&ID=42" in payload

    def test_payload_strips_whitespace(self):
        s = Sample(id=1, sn="  SMP-X  ", batch_no="", spec="")
        payload = _qr_payload(s)
        assert "SN=SMP-X" in payload
        assert "SN=  SMP" not in payload


class TestGenerateQrMatrix:
    def test_matrix_is_standard_qr_size(self, sample):
        """真实标准 QR（version 3, 29x29）—— 不是伪矩阵的 21x21。"""
        matrix = _generate_qr_matrix(_qr_payload(sample))
        n = len(matrix)
        assert n == 29, f"真实 QR version3 应为 29x29, got {n}"
        assert all(len(row) == n for row in matrix)

    def test_matrix_has_three_finder_patterns(self, sample):
        """标准 QR 有三个 7x7 定位角。"""
        matrix = _generate_qr_matrix(_qr_payload(sample))
        n = len(matrix)

        def is_finder(top, left):
            """7x7 定位角: 外圈+中心 3x3 为黑。"""
            for r in range(7):
                for c in range(7):
                    expected = r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4)
                    assert matrix[top + r][left + c] == expected, f"finder ({top},{left}) 不完整"
            return True

        assert is_finder(0, 0)
        assert is_finder(0, n - 7)
        assert is_finder(n - 7, 0)

    def test_matrix_data_area_not_random(self, sample):
        """数据区域不是简单哈希随机 — 两个不同文本生成不同矩阵（编码差异）。"""
        m1 = _generate_qr_matrix(_qr_payload(sample))
        other = Sample(id=8, sn="SMP-OTHER", batch_no="", spec="")
        m2 = _generate_qr_matrix(_qr_payload(other))
        assert m1 != m2, "不同内容应生成不同 QR"

    def test_matrix_deterministic(self, sample):
        """同一内容两次生成完全一致。"""
        m1 = _generate_qr_matrix(_qr_payload(sample))
        m2 = _generate_qr_matrix(_qr_payload(sample))
        assert m1 == m2


class TestRenderPixmap:
    def test_pixmap_rendered_without_error(self, qapp, sample):
        pixmap = render_sample_tag_pixmap(sample, scale=2.0)
        assert not pixmap.isNull()
        assert pixmap.width() == 720  # 360 * 2
        assert pixmap.height() == 440  # 220 * 2

    def test_rendered_qr_matches_segno_matrix(self, qapp, sample):
        """渲染像素重建矩阵与 segno 原始矩阵 100% 一致（可被扫码器识别）。"""
        scale = 4.0
        pixmap = render_sample_tag_pixmap(sample, scale=scale)
        tmp_path = "/tmp/_qr_pixmap_verify.png"
        pixmap.save(tmp_path, "PNG")

        from PIL import Image
        img = Image.open(tmp_path).convert("L")
        arr = np.array(img)

        qr_x, qr_y, qr_s = int(18 * scale), int(60 * scale), int(120 * scale)
        region = arr[qr_y:qr_y + qr_s, qr_x:qr_x + qr_s]

        matrix = _generate_qr_matrix(_qr_payload(sample))
        n = len(matrix)
        cell = qr_s / n

        rebuilt = np.zeros((n, n), dtype=bool)
        for r in range(n):
            for c in range(n):
                cx = int((c + 0.5) * cell)
                cy = int((r + 0.5) * cell)
                rebuilt[r][c] = region[cy, cx] < 128

        expected = np.array(matrix, dtype=bool)
        match = (rebuilt == expected).mean()
        assert match == 1.0, f"渲染 QR 与 segno 矩阵不一致: {match:.4f}"
        os.remove(tmp_path)

    def test_old_pseudo_matrix_not_present(self, sample):
        """回归防护：矩阵不是旧 21x21 伪矩阵（无数据编码的装饰图）。"""
        matrix = _generate_qr_matrix(_qr_payload(sample))
        assert len(matrix) != 21, "回退到 21x21 伪矩阵了！"
