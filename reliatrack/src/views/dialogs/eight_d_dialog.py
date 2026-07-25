"""8D 质量报告可视化预览与导出弹窗 (8D Problem Solving Report Dialog)。

以结构化卡片呈现 8D (D1~D8) 完整质量报告内容，
支持交互式预览、一键导出 PDF/Word 报告以及复制纯文本摘要。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QGroupBox,
    QDialogButtonBox,
    QWidget,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

import src.styles.theme as _t
from src.styles.constants import (
    FONT_SIZE_TITLE,
    FONT_SIZE_NORMAL,
    PADDING_MEDIUM,
    PADDING_LARGE,
    SPACING_MEDIUM,
    ISSUE_STATUS_COLORS,
    ISSUE_SEVERITY_COLORS,
)
from src.constants import SEVERITY_LABELS, ISSUE_STATUS_LABELS, RESOLUTION_LABELS
from src.models.issue import Issue, FARecord, CAPARecord

logger = logging.getLogger(__name__)


class _DisciplineCard(QFrame):
    """8D 报告中单步 Discipline (D1~D8) 可视化卡片。"""

    def __init__(
        self,
        code: str,
        title: str,
        content_widget: QWidget,
        accent_color: str = "#1e66f5",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("disciplineCard")
        self.setStyleSheet(
            f"""
            QFrame#disciplineCard {{
                background-color: {_t.SURFACE0};
                border: 1px solid {_t.SURFACE1};
                border-radius: 8px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 头部: 徽章 + 标题
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        badge = QLabel(code)
        badge.setStyleSheet(
            f"""
            background-color: {accent_color};
            color: #ffffff;
            font-weight: bold;
            font-size: 12px;
            border-radius: 4px;
            padding: 3px 8px;
            """
        )
        badge.setFixedHeight(22)
        header_layout.addWidget(badge)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {_t.TEXT};")
        header_layout.addWidget(title_lbl, stretch=1)

        layout.addLayout(header_layout)
        layout.addWidget(content_widget)


class EightDReportDialog(QDialog):
    """8D 质量报告可视化预览弹窗。"""

    def __init__(
        self,
        issue: Issue,
        fa_records: list[FARecord] | None = None,
        capa_records: list[CAPARecord] | None = None,
        technician_name: str = "",
        task=None,
        sample_sn: str = "",
        export_service=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._issue = issue
        self._fa_records = fa_records or []
        self._capa_records = capa_records or []
        self._technician_name = technician_name
        self._task = task
        self._sample_sn = sample_sn
        self._export_service = export_service

        self.setWindowTitle(f"8D 报告可视化预览 — Issue #{issue.id} ({issue.title})")
        self.resize(780, 820)
        self.setMinimumSize(640, 500)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ── 顶栏: 报表标题与元数据信息 ──
        header_frame = QFrame()
        header_frame.setStyleSheet(
            f"background-color: {_t.SURFACE0}; border-radius: 8px; border: 1px solid {_t.SURFACE1};"
        )
        header_box = QVBoxLayout(header_frame)
        header_box.setContentsMargins(16, 12, 16, 12)

        title_lbl = QLabel("8D Problem Solving Report (8D 问题解决报告)")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {_t.BLUE};")
        header_box.addWidget(title_lbl)


        meta_lbl = QLabel(
            f"Issue ID: #{self._issue.id}   |   项目 ID: #{self._issue.project_id or '-'}   |   "
            f"状态: {ISSUE_STATUS_LABELS.get(self._issue.status, self._issue.status)}   |   "
            f"严重度: {SEVERITY_LABELS.get(self._issue.severity, self._issue.severity)}"
        )
        meta_lbl.setStyleSheet(f"font-size: 12px; color: {_t.SUBTEXT0};")
        header_box.addWidget(meta_lbl)


        main_layout.addWidget(header_frame)

        # ── 中间: 可滚动 8D 内容区 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }}")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)

        # D1 ~ D8 卡片构建
        container_layout.addWidget(self._build_d1_card())
        container_layout.addWidget(self._build_d2_card())
        container_layout.addWidget(self._build_d3_card())
        container_layout.addWidget(self._build_d4_card())
        container_layout.addWidget(self._build_d5_card())
        container_layout.addWidget(self._build_d6_card())
        container_layout.addWidget(self._build_d7_card())
        container_layout.addWidget(self._build_d8_card())

        scroll.setWidget(container)
        main_layout.addWidget(scroll, stretch=1)

        # ── 底栏: 操作按钮区域 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_copy = QPushButton("复制文本摘要")
        self._btn_copy.setToolTip("将 D1~D8 文本格式复制到剪贴板")
        self._btn_copy.clicked.connect(self._copy_summary)
        btn_row.addWidget(self._btn_copy)

        btn_row.addStretch()

        self._btn_pdf = QPushButton("导出 PDF 报告")
        self._btn_pdf.setProperty("class", "primary")
        self._btn_pdf.clicked.connect(self._export_pdf)
        btn_row.addWidget(self._btn_pdf)

        self._btn_docx = QPushButton("导出 Word 报告")
        self._btn_docx.clicked.connect(self._export_docx)
        btn_row.addWidget(self._btn_docx)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        main_layout.addLayout(btn_row)

    # ── D1~D8 构建逻辑 ──

    def _build_d1_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        dri_str = self._technician_name or f"DRI ID: {self._issue.assignee_id or '未指定'}"
        lbl = QLabel(f"• 团队负责人 (DRI): {dri_str}\n• 关联试验员: {dri_str}")
        lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(lbl)
        return _DisciplineCard("D1", "Team Assembly (团队成立)", w, accent_color="#89b4fa")

    def _build_d2_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(4)

        task_name = self._task.name if self._task else "-"
        desc = (
            f"<b>问题标题:</b> {self._issue.title}<br>"
            f"<b>问题类别:</b> {self._issue.category or '未分类'}<br>"
            f"<b>样品 S/N:</b> {self._sample_sn or '未绑定'}<br>"
            f"<b>测试任务:</b> {task_name}<br>"
            f"<b>详细描述:</b> {self._issue.description or '无描述'}"
        )
        lbl = QLabel(desc)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(lbl)
        return _DisciplineCard("D2", "Problem Description (问题描述)", w, accent_color="#74c7ec")

    def _build_d3_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        action_text = "• 暂停相关测试项并实施隔离标识\n• 查验在库同批次测试样品"
        if self._issue.status == "closed":
            action_text += "\n• 临时围堵措施已完成确认"
        lbl = QLabel(action_text)
        lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(lbl)
        return _DisciplineCard("D3", "Containment Actions (临时应急措施)", w, accent_color="#94e2d5")

    def _build_d4_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)

        root_cause = self._issue.root_cause or "尚未录入显式根因"
        rc_lbl = QLabel(f"<b>主要根因:</b> {root_cause}")
        rc_lbl.setTextFormat(Qt.TextFormat.RichText)
        rc_lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(rc_lbl)

        if self._fa_records:
            fa_head = QLabel("<b>FA 失效分析步骤:</b>")
            fa_head.setTextFormat(Qt.TextFormat.RichText)
            fa_head.setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 12px;")
            l.addWidget(fa_head)

            for idx, fa in enumerate(self._fa_records, 1):
                s_title = getattr(fa, "step_title", "") or getattr(fa, "step_name", "") or "分析步骤"
                s_finding = getattr(fa, "findings", "") or getattr(fa, "finding", "") or "待分析"
                item_lbl = QLabel(
                    f"  {idx}. [{s_title}] 分析结论: {s_finding} "
                    f"({fa.created_at[:10] if fa.created_at else ''})"
                )
                item_lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 12px;")
                l.addWidget(item_lbl)

        return _DisciplineCard("D4", "Root Cause Analysis (根因分析)", w, accent_color="#f9e2af")

    def _build_d5_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)

        countermeasure = (
            getattr(self._issue, "improvement_measures", "")
            or getattr(self._issue, "countermeasure", "")
            or "尚未录入改善对策"
        )
        cm_lbl = QLabel(f"<b>改善对策方案:</b> {countermeasure}")

        cm_lbl.setTextFormat(Qt.TextFormat.RichText)
        cm_lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(cm_lbl)

        if self._capa_records:
            for idx, c in enumerate(self._capa_records, 1):
                act = getattr(c, "action", "") or getattr(c, "action_plan", "") or "对策项"
                own = getattr(c, "assignee_name", "") or getattr(c, "owner", "") or "未指定"
                c_lbl = QLabel(
                    f"  {idx}. [CAPA] {act} (负责人: {own}, 状态: {c.status})"
                )
                c_lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 12px;")
                l.addWidget(c_lbl)


        return _DisciplineCard("D5", "Corrective Actions (永久纠正措施方案)", w, accent_color="#fab387")

    def _build_d6_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(4)

        if self._capa_records:
            verified_count = sum(1 for c in self._capa_records if c.status == "verified")
            text = f"• CAPA 验证总数: {len(self._capa_records)} 项 (已验证完成: {verified_count} 项)"
        else:
            text = f"• 纠正措施验证状态: {RESOLUTION_LABELS.get(self._issue.resolution, '进行中')}"

        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(lbl)
        return _DisciplineCard("D6", "Implementation & Validation (实施与验证)", w, accent_color="#a6e3a1")

    def _build_d7_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("• 更新可靠性设计规范 / 测试标准作业指导书 (SOP)\n• 标准化经验归档至知识库")
        lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(lbl)
        return _DisciplineCard("D7", "Prevent Recurrence (预防再发生与标准化)", w, accent_color="#cba6f7")

    def _build_d8_card(self) -> _DisciplineCard:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)

        res_str = RESOLUTION_LABELS.get(self._issue.resolution, self._issue.resolution or "未解决")
        close_date = self._issue.updated_at[:10] if self._issue.status == "closed" and self._issue.updated_at else "-"
        lbl = QLabel(f"• 解决状态: {res_str}\n• 结案日期: {close_date}\n• 批准签字: {self._technician_name or 'DRI已审核'}")
        lbl.setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;")
        l.addWidget(lbl)
        return _DisciplineCard("D8", "Team Recognition & Close (团队结案)", w, accent_color="#f38ba8")

    # ── 操作动作 ──

    def _copy_summary(self) -> None:
        """格式化 D1~D8 纯文本并复制到剪贴板。"""
        countermeasure = getattr(self._issue, "improvement_measures", "") or getattr(self._issue, "countermeasure", "") or "详见CAPA记录"
        lines = [
            f"=== 8D Report: Issue #{self._issue.id} ({self._issue.title}) ===",
            f"严重度: {SEVERITY_LABELS.get(self._issue.severity, self._issue.severity)} | 状态: {ISSUE_STATUS_LABELS.get(self._issue.status, self._issue.status)}",
            "",
            f"D1 团队: {self._technician_name or '未指定'}",
            f"D2 问题描述: {self._issue.description or self._issue.title}",
            f"D3 临时措施: 隔离问题样品并通报",
            f"D4 根因分析: {self._issue.root_cause or '详见FA记录'}",
            f"D5 改善对策: {countermeasure}",
            f"D6 验证结果: {RESOLUTION_LABELS.get(self._issue.resolution, '处理中')}",
            f"D7 预防措施: 标准化更新与规范宣贯",
            f"D8 结案签字: {self._technician_name or 'DRI'} (状态: {self._issue.status})",
        ]

        text = "\n".join(lines)
        QApplication.clipboard().setText(text)

        # 反馈 Toast 或更改按钮文字
        self._btn_copy.setText("已复制到剪贴板！")
        self._btn_copy.setEnabled(False)

    def _export_pdf(self) -> None:
        if self._export_service:
            path = self._export_service.export_8d_pdf(
                self._issue, self._fa_records, self._capa_records,
                technician_name=self._technician_name, task=self._task, sample_sn=self._sample_sn,
            )
            self._show_export_success(path, "PDF")

    def _export_docx(self) -> None:
        if self._export_service:
            path = self._export_service.export_8d_docx(
                self._issue, self._fa_records, self._capa_records,
                technician_name=self._technician_name, task=self._task, sample_sn=self._sample_sn,
            )
            self._show_export_success(path, "Word")

    def _show_export_success(self, path: Path | str, fmt: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "导出成功",
            f"8D {fmt} 报告已成功导出至：\n\n{path}",
        )
