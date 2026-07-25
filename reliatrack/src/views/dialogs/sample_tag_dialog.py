"""样品二维码 / 条形码标签生成与打印弹窗。"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QWidget,
    QApplication,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QFont,
    QPen,
    QBrush,
    QImage,
)

import src.styles.theme as _t
from src.styles.constants import FONT_FAMILY
from src.styles.icon import RI_EXPORT, RI_CHECK, set_icon

if TYPE_CHECKING:
    from src.models.sample import Sample


def _generate_qr_matrix(text: str) -> list[list[bool]]:
    """生成确定性 QR 码点阵矩阵 (21x21 标准 1 型伪矩阵，无需第三方库)。"""
    size = 21
    matrix = [[False] * size for _ in range(size)]

    # 1. 绘制 3 个角上的 Position Detection Pattern (7x7)
    def draw_finder(top_row: int, left_col: int):
        for r in range(7):
            for c in range(7):
                if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4):
                    matrix[top_row + r][left_col + c] = True

    draw_finder(0, 0)
    draw_finder(0, size - 7)
    draw_finder(size - 7, 0)

    # 2. 绘制同步线 (Timing patterns)
    for i in range(7, size - 7):
        matrix[6][i] = (i % 2 == 0)
        matrix[i][6] = (i % 2 == 0)

    # 3. 填充基于字符串哈希的随机点阵
    seed = sum(ord(ch) * (idx + 1) for idx, ch in enumerate(text))
    for r in range(size):
        for c in range(size):
            # 避开 finder 区域和 timing pattern
            if (r < 8 and c < 8) or (r < 8 and c >= size - 8) or (r >= size - 8 and c < 8):
                continue
            if r == 6 or c == 6:
                continue
            v = (seed * 1103515245 + r * 31 + c * 17) & 0x7FFFFFFF
            matrix[r][c] = (v % 3 == 0)

    return matrix


def render_sample_tag_pixmap(sample: Sample, scale: float = 2.0) -> QPixmap:
    """用 QPainter 绘制高清晰度样品二维码标签。"""
    w, h = int(360 * scale), int(220 * scale)
    image = QImage(w, h, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF"))

    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 外框边框
    p.setPen(QPen(QColor("#2B579A"), int(3 * scale)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(int(6 * scale), int(6 * scale), int(w - 12 * scale), int(h - 12 * scale), int(8 * scale), int(8 * scale))

    # 顶栏 Header
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#2B579A")))
    p.drawRoundedRect(int(6 * scale), int(6 * scale), int(w - 12 * scale), int(36 * scale), int(6 * scale), int(6 * scale))

    p.setPen(QColor("#FFFFFF"))
    font_header = QFont(FONT_FAMILY, int(11 * scale))
    font_header.setBold(True)
    p.setFont(font_header)
    p.drawText(
        QRectF(12 * scale, 8 * scale, w - 24 * scale, 32 * scale),
        Qt.AlignmentFlag.AlignCenter,
        "Reliability Sample Tag / 可靠性测试样品标签",
    )

    # 左侧 QR 码
    qr_size = int(120 * scale)
    qr_x, qr_y = int(18 * scale), int(60 * scale)
    matrix = _generate_qr_matrix(sample.sn or str(sample.id or "0"))

    grid_n = len(matrix)
    cell_w = qr_size / grid_n

    p.setBrush(QBrush(QColor("#000000")))
    p.setPen(Qt.PenStyle.NoPen)
    for r in range(grid_n):
        for c in range(grid_n):
            if matrix[r][c]:
                rx = qr_x + c * cell_w
                ry = qr_y + r * cell_w
                p.drawRect(QRectF(rx, ry, cell_w + 0.5, cell_w + 0.5))

    # QR 码底部 SN 文字
    font_sn = QFont(FONT_FAMILY, int(8 * scale))
    font_sn.setBold(True)
    p.setFont(font_sn)
    p.setPen(QColor("#333333"))
    p.drawText(
        QRectF(qr_x, qr_y + qr_size + 4 * scale, qr_size, 20 * scale),
        Qt.AlignmentFlag.AlignCenter,
        f"SN: {sample.sn or '-'}",
    )

    # 右侧详细信息
    info_x = qr_x + qr_size + int(16 * scale)
    info_y = int(58 * scale)
    info_w = w - info_x - int(16 * scale)

    p.setPen(QColor("#1E293B"))
    font_label = QFont(FONT_FAMILY, int(9 * scale))
    font_label.setBold(True)
    p.setFont(font_label)

    lines = [
        f"批次号: {sample.batch_no or '—'}",
        f"规格: {sample.spec or '—'}",
        f"状态: {sample.status or '在库'}",
        f"项目ID: #{sample.project_id or 0}",
        f"登记时间: {sample.created_at[:10] if sample.created_at else '—'}",
    ]

    line_h = int(24 * scale)
    for idx, line in enumerate(lines):
        p.drawText(
            QRectF(info_x, info_y + idx * line_h, info_w, line_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            line,
        )

    p.end()
    return QPixmap.fromImage(image)


class SampleTagDialog(QDialog):
    """样品条形码/二维码标签预览与导出对话框。"""

    def __init__(self, sample: Sample, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"样品标签 — {sample.sn}")
        self.setFixedWidth(460)

        self._sample = sample
        self._pixmap = render_sample_tag_pixmap(sample, scale=2.5)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"🏷️ 样品标签: {sample.sn}")
        title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {_t.FG_PRIMARY};")
        layout.addWidget(title)

        # 预览图
        self._lbl_preview = QLabel(self)
        self._lbl_preview.setPixmap(self._pixmap.scaled(
            420, 250,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self._lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_preview.setStyleSheet(f"border: 1px solid {_t.BORDER}; border-radius: 8px; padding: 8px; background-color: #FFFFFF;")
        layout.addWidget(self._lbl_preview)

        # 按钮栏
        btn_box = QHBoxLayout()

        btn_copy = QPushButton("复制到剪贴板")
        btn_copy.setProperty("class", "action")
        btn_copy.clicked.connect(self._on_copy)

        btn_save = QPushButton("保存为图片…")
        btn_save.setProperty("class", "action")
        set_icon(btn_save, RI_EXPORT)
        btn_save.clicked.connect(self._on_save)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)

        btn_box.addWidget(btn_copy)
        btn_box.addWidget(btn_save)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _on_copy(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self._pixmap)
        QMessageBox.information(self, "成功", "标签图片已复制到剪贴板！")

    def _on_save(self) -> None:
        default_name = f"样品标签_{self._sample.sn}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存样品标签", default_name, "PNG 图片 (*.png);;所有文件 (*)"
        )
        if path:
            self._pixmap.save(path, "PNG")
            QMessageBox.information(self, "成功", f"标签已保存至:\n{path}")
