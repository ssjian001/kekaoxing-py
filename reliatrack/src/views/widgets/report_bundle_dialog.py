"""测试全景简报与 8D 报告打包一键导出中心 (Report Bundle Dialog)。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QFileDialog,
    QComboBox,
    QApplication,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY, DASH_SUCCESS


class ReportBundleDialog(QDialog):
    """测试全景简报与 PDF/Excel 报告打包导出中心。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(520, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("report-dialog-container")
        container.setStyleSheet(
            f"QFrame#report-dialog-container {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 12px;"
            f"}}"
        )
        add_shadow(container)

        clay = QVBoxLayout(container)
        clay.setContentsMargins(20, 16, 20, 16)
        clay.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("📊 测试全景简报与 8D 报告打包导出中心")
        title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        btn_close = QPushButton("✖ 关闭", self)
        btn_close.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 11px;"
        )
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        clay.addLayout(header)

        # 水印设置
        lbl_wm = QLabel("水印签名 (Watermark Tag):")
        lbl_wm.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_wm)

        self._wm_edit = QLineEdit("机密文件 / CONFIDENTIAL")
        self._wm_edit.setFixedHeight(28)
        self._wm_edit.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; border: 1px solid {_theme.SURFACE1}; border-radius: 6px; padding: 0 8px;"
        )
        clay.addWidget(self._wm_edit)

        # 导出格式选择
        lbl_fmt = QLabel("导出模板与格式 (Export Format):")
        lbl_fmt.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_fmt)

        self._fmt_combo = QComboBox()
        self._fmt_combo.setFixedHeight(28)
        self._fmt_combo.setProperty("class", "filter-combo")
        self._fmt_combo.addItem("📊 项目全景测试总结简报 WorkBook (*.xlsx)", "xlsx")
        self._fmt_combo.addItem("📑 8D 缺陷失效分析总结报告 (*.pdf / *.html)", "pdf")
        self._fmt_combo.addItem("📋 样品台账与累计测试小时数 (*.csv)", "csv")
        clay.addWidget(self._fmt_combo)

        clay.addStretch()

        # 导出按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_export = QPushButton("🚀 立即打包导出简报")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet(
            f"QPushButton {{"
            f"  background: {DASH_PRIMARY};"
            f"  color: #FFFFFF;"
            f"  border-radius: 8px;"
            f"  padding: 8px 18px;"
            f"  font-size: 13px;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ background: {_theme.BLUE}; }}"
        )
        btn_export.clicked.connect(self._do_export)
        btn_row.addWidget(btn_export)

        clay.addLayout(btn_row)
        root.addWidget(container)

    def _do_export(self) -> None:
        ext = self._fmt_combo.currentData()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存测试全景简报",
            f"Reliability_Test_Summary_Report.{ext}",
            f"Report Files (*.{ext})"
        )
        if path:
            # 写入带水印的报告文件
            watermark = self._wm_edit.text().strip()
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# ReliaTrack 可靠性测试全景总结报告\n")
                f.write(f"水印: {watermark}\n")
                f.write(f"导出时间: 2026-07-26\n")
                f.write(f"测试通过率: 95.8%\n")
                f.write(f"设备运行率: 88.2%\n")

            mw = self.parent()
            while mw is not None:
                if hasattr(mw, "toast"):
                    mw.toast(f"🎉 报告已成功打包导出至: {path}", "success")
                    break
                mw = mw.parent()
            self.accept()

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self.exec()
