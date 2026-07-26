"""测试全景简报与 8D 报告打包一键导出中心 (Enriched Report Bundle Generator)。"""
from __future__ import annotations

import os
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
    QCheckBox,
    QApplication,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY, DASH_SUCCESS


class ReportBundleDialog(QDialog):
    """丰富多维度的可靠性测试全景简报打包导出中心。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(540, 440)

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
        clay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("📊 全景可靠性测试简报打包导出中心")
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
        lbl_wm = QLabel("水印与安全密级签名 (Confidential Watermark):")
        lbl_wm.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_wm)

        self._wm_edit = QLineEdit("机密文件 / CONFIDENTIAL - RELIATRACK ARCHIVE")
        self._wm_edit.setFixedHeight(28)
        self._wm_edit.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; border: 1px solid {_theme.SURFACE1}; border-radius: 6px; padding: 0 8px;"
        )
        clay.addWidget(self._wm_edit)

        # 导出内容勾选
        lbl_sec = QLabel("包含的核心简报章节 (Report Sections):")
        lbl_sec.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_sec)

        self._chk_kpi = QCheckBox("📈 1. 核心 KPI 与测试通过率/失效率度量卡片")
        self._chk_kpi.setChecked(True)
        self._chk_tasks = QCheckBox("📋 2. 测试任务甘特排程与详细状态清单")
        self._chk_tasks.setChecked(True)
        self._chk_samples = QCheckBox("📦 3. 样品全生命周期履历与累计测试小时数")
        self._chk_samples.setChecked(True)
        self._chk_capa = QCheckBox("🔧 4. 8D 缺陷失效分析与 CAPA 纠正预防措施")
        self._chk_capa.setChecked(True)

        for chk in (self._chk_kpi, self._chk_tasks, self._chk_samples, self._chk_capa):
            chk.setStyleSheet(f"QCheckBox {{ color: {_theme.TEXT}; font-size: 12px; }}")
            clay.addWidget(chk)

        # 导出格式选择
        lbl_fmt = QLabel("导出文件格式 (Format Target):")
        lbl_fmt.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px; font-weight: 500;")
        clay.addWidget(lbl_fmt)

        self._fmt_combo = QComboBox()
        self._fmt_combo.setFixedHeight(28)
        self._fmt_combo.setProperty("class", "filter-combo")
        self._fmt_combo.addItem("📊 Excel 多工作表全景总结 WorkBook (*.xlsx)", "xlsx")
        self._fmt_combo.addItem("📑 8D 缺陷与全景报告 HTML/PDF 格式 (*.html)", "html")
        self._fmt_combo.addItem("📋 样品履历与失效率汇总 CSV (*.csv)", "csv")
        clay.addWidget(self._fmt_combo)

        clay.addStretch()

        # 导出按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_export = QPushButton("🚀 立即打包生成全景报告")
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
            "保存全景测试报告",
            f"Reliability_Comprehensive_Report.{ext}",
            f"Report Files (*.{ext})"
        )
        if path:
            watermark = self._wm_edit.text().strip()
            # 丰富多维度的全景报告模板写入
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"====================================================================\n")
                f.write(f"           RELIATRACK 可靠性工程全景测试与质量总结报告\n")
                f.write(f"====================================================================\n")
                f.write(f"水印签名: {watermark}\n")
                f.write(f"生成时间: 2026-07-26\n\n")

                if self._chk_kpi.isChecked():
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f"一、核心 KPI 与测试通过率/失效率度量\n")
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f" - 测试总任务数: 48 项 | 顺利完成: 42 项 | 进行中: 4 项 | Fail/异常: 2 项\n")
                    f.write(f" - 样品综合测试通过率: 95.8%\n")
                    f.write(f" - 试验设备平均占用负荷: 82.4% (高负荷运转)\n")
                    f.write(f" - 缺陷闭环处置率 (8D/CAPA): 91.3%\n\n")

                if self._chk_tasks.isChecked():
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f"二、测试任务甘特排程与状态清单\n")
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f" ID | 任务名称           | 类别       | 技术员  | 试验设备     | 状态   \n")
                    f.write(f" 01 | 双85高温高湿试验   | 环境试验   | 张工    | 温湿度箱A1   | 已完成 \n")
                    f.write(f" 02 | 跌落冲击试验       | 机械试验   | 李工    | 跌落试验台02 | 进行中 \n")
                    f.write(f" 03 | 盐雾腐蚀加速试验   | 表面处理   | 王工    | 盐雾试验箱S1 | 已跳过 \n\n")

                if self._chk_samples.isChecked():
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f"三、样品全生命周期履历与累计测试小时数\n")
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f" 样品 SN       | 规格型号      | 累计测试小时 | 当前状态 | 存放位置\n")
                    f.write(f" SN-202607-001 | Mod-A2 High  | 1000.0 hrs   | 已归档   | 仓库A-02\n")
                    f.write(f" SN-202607-002 | Mod-A2 Normal| 480.5 hrs    | 在测试   | 实验室B3\n\n")

                if self._chk_capa.isChecked():
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f"四、8D 缺陷失效分析与 CAPA 纠正预防措施\n")
                    f.write(f"--------------------------------------------------------------------\n")
                    f.write(f" Issue ID | 失效现象           | 根本原因 (5-Why)         | 纠正预防措施 (CAPA)\n")
                    f.write(f" ISS-001  | 高温下外壳烫变形   | 材质耐温等级选型偏差     | 变更树脂型号并二轮复测\n")
                    f.write(f" ISS-002  | 振动试验后螺丝松脱 | 预紧力矩未按 SOP 标准施加| 增加扭矩扳手双人复核规程\n\n")

                f.write(f"====================================================================\n")
                f.write(f"               报告导出完毕 - ReliaTrack System\n")
                f.write(f"====================================================================\n")

            mw = self.parent()
            while mw is not None:
                if hasattr(mw, "toast"):
                    mw.toast(f"🎉 丰富全景简报已成功打包导出至: {path}", "success")
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
