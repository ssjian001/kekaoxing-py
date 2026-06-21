"""Issue 详情弹窗 — 5个 Tab（详情/评论/活动/FA/CAPA）。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

import src.styles.theme as _t
from src.styles.constants import (
    ISSUE_STATUS_COLORS,
    ISSUE_SEVERITY_COLORS,
    FONT_SIZE_TITLE,
    FONT_SIZE_NORMAL,
    PADDING_MEDIUM,
    PADDING_LARGE,
    SPACING_MEDIUM,
)
from src.constants import SEVERITY_LABELS, ISSUE_STATUS_LABELS
from src.models.issue import Issue, IssueComment
from src.views.issue_view import _FAPanel, _CAPAPanel


class IssueDetailDialog(QDialog):
    """Issue 详情弹窗 — 5个 Tab 浏览 Issue 完整信息。"""

    def __init__(
        self,
        issue: Issue,
        issue_service,
        parent: QWidget | None = None,
        technician_map: dict[int, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._issue = issue
        self._service = issue_service
        self._technician_map = technician_map or {}

        self.setWindowTitle(f"Issue #{issue.id} 详情")
        self.setFixedSize(640, 520)
        self.setModal(True)

        self._build_ui()
        self._load_data()

    # ── UI 构建 ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE)
        root.setSpacing(SPACING_MEDIUM)

        # ── 顶部：标题 + 徽标 ──
        root.addLayout(self._build_header())

        # ── 中间：TabWidget ──
        self._tab = self._build_tabs()
        root.addWidget(self._tab, stretch=1)

        # ── 底部：关闭按钮 ──
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _build_header(self) -> QHBoxLayout:
        """构建标题行：大号标题 + 严重度徽标 + 状态徽标。"""
        header = QHBoxLayout()
        header.setSpacing(SPACING_MEDIUM)

        title_lbl = QLabel(self._issue.title or "(无标题)")
        title_lbl.setProperty("class", "header-title")
        title_lbl.setStyleSheet(f"font-size: {FONT_SIZE_TITLE}px; font-weight: bold;")
        title_lbl.setWordWrap(True)
        header.addWidget(title_lbl, stretch=1)

        # 严重度徽标
        severity_label = SEVERITY_LABELS.get(self._issue.severity, self._issue.severity)
        sev_color = ISSUE_SEVERITY_COLORS.get(self._issue.severity, _t.SUBTEXT0)
        sev_badge = QLabel(severity_label)
        sev_badge.setProperty("class", "badge")
        sev_badge.setStyleSheet(
            f"background-color: {sev_color}22; color: {sev_color};"
            f" padding: 2px 8px; border-radius: 4px; font-weight: bold;"
            f" font-size: {FONT_SIZE_NORMAL}px;"
        )
        header.addWidget(sev_badge)

        # 状态徽标
        status_label = ISSUE_STATUS_LABELS.get(self._issue.status, self._issue.status)
        st_color = ISSUE_STATUS_COLORS.get(self._issue.status, _t.SUBTEXT0)
        st_badge = QLabel(status_label)
        st_badge.setProperty("class", "badge")
        st_badge.setStyleSheet(
            f"background-color: {st_color}18; color: {st_color};"
            f" padding: 2px 8px; border-radius: 4px; font-weight: bold;"
            f" font-size: {FONT_SIZE_NORMAL}px;"
        )
        header.addWidget(st_badge)

        return header

    def _build_tabs(self):
        """构建 5 个 Tab。"""
        from PySide6.QtWidgets import QTabWidget

        tab = QTabWidget()
        tab.setProperty("class", "detail-tabs")

        tab.addTab(self._build_detail_tab(), "详情")
        tab.addTab(self._build_comment_tab(), "评论")
        tab.addTab(self._build_activity_tab(), "活动")
        tab.addTab(self._build_fa_tab(), "FA")
        tab.addTab(self._build_capa_tab(), "CAPA")

        return tab

    # ── Tab 1: 详情 ────────────────────────────────────────────────

    def _build_detail_tab(self) -> QWidget:
        """Tab1 详情 — QFormLayout 展示所有只读字段 + 附件。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        form = QFormLayout(container)
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(0, 0, 0, 0)

        issue = self._issue

        # 字段定义: (标签, 值)
        fields = [
            ("项目", str(issue.project_id or "")),
            ("计划", str(issue.plan_id or "")),
            ("任务", str(issue.task_id or "")),
            ("样品", str(issue.sample_id or "")),
            ("描述", issue.description or ""),
            ("根因", issue.root_cause or ""),
            ("解决方案", issue.resolution or ""),
            ("改善对策", issue.improvement_measures or ""),
            ("DRI", issue.dri_name or ""),
            ("失效代码", issue.failure_code or ""),
            ("创建时间", issue.created_at or ""),
            ("Aging", self._get_aging_text()),
        ]

        for label_text, value_text in fields:
            lbl = QLabel(value_text if value_text else "-")
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(f"{label_text}:", lbl)

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # 附件区域
        attach_frame = QFrame()
        attach_frame.setProperty("class", "attach-section")
        attach_layout = QVBoxLayout(attach_frame)
        attach_layout.setContentsMargins(0, PADDING_MEDIUM, 0, 0)

        attach_title = QLabel("附件")
        attach_title.setProperty("class", "section-label")
        attach_title.setStyleSheet(f"font-weight: bold; font-size: {FONT_SIZE_NORMAL}px;")
        attach_layout.addWidget(attach_title)

        self._attach_list = QLabel("加载中...")
        self._attach_list.setProperty("class", "subtext")
        self._attach_list.setWordWrap(True)
        attach_layout.addWidget(self._attach_list)

        layout.addWidget(attach_frame)

        return page

    # ── Tab 2: 评论 ────────────────────────────────────────────────

    def _build_comment_tab(self) -> QWidget:
        """Tab2 评论 — 评论列表 + 输入区。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE)

        # 评论列表滚动区
        self._comment_scroll = QScrollArea()
        self._comment_scroll.setWidgetResizable(True)
        self._comment_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._comment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._comment_container = QWidget()
        self._comment_list_layout = QVBoxLayout(self._comment_container)
        self._comment_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._comment_list_layout.setSpacing(SPACING_MEDIUM)
        self._comment_scroll.setWidget(self._comment_container)

        layout.addWidget(self._comment_scroll, stretch=1)

        # 空状态
        self._comment_empty = QLabel("暂无评论，写下第一条")
        self._comment_empty.setProperty("class", "subtext")
        self._comment_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._comment_list_layout.addWidget(self._comment_empty)

        # 输入区域
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, PADDING_MEDIUM, 0, 0)

        self._comment_input = QTextEdit()
        self._comment_input.setPlaceholderText("输入评论...")
        self._comment_input.setMaximumHeight(60)
        input_layout.addWidget(self._comment_input, stretch=1)

        self._comment_send = QPushButton("发送")
        self._comment_send.setProperty("class", "primary")
        self._comment_send.setFixedWidth(60)
        self._comment_send.clicked.connect(self._on_send_comment)
        input_layout.addWidget(self._comment_send)

        layout.addLayout(input_layout)

        return page

    # ── Tab 3: 活动 ────────────────────────────────────────────────

    def _build_activity_tab(self) -> QWidget:
        """Tab3 活动 — 时间线布局。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE)

        self._activity_scroll = QScrollArea()
        self._activity_scroll.setWidgetResizable(True)
        self._activity_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._activity_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._activity_container = QWidget()
        self._activity_layout = QVBoxLayout(self._activity_container)
        self._activity_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._activity_layout.setSpacing(SPACING_MEDIUM)
        self._activity_scroll.setWidget(self._activity_container)

        layout.addWidget(self._activity_scroll, stretch=1)

        return page

    # ── Tab 4: FA ──────────────────────────────────────────────────

    def _build_fa_tab(self) -> QWidget:
        """Tab4 FA — 复用 _FAPanel。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fa_panel = _FAPanel()
        layout.addWidget(self._fa_panel)

        return page

    # ── Tab 5: CAPA ────────────────────────────────────────────────

    def _build_capa_tab(self) -> QWidget:
        """Tab5 CAPA — 复用 _CAPAPanel。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self._capa_panel = _CAPAPanel()
        layout.addWidget(self._capa_panel)

        return page

    # ── 数据加载 ────────────────────────────────────────────────────

    def _load_data(self) -> None:
        """加载所有 tab 数据。"""
        self._load_attachments()
        self._load_comments()
        self._load_activity()
        self._load_fa_records()
        self._load_capa_records()

    def _load_attachments(self) -> None:
        """加载附件列表。"""
        try:
            attachments = self._service.get_attachments(self._issue.id)
            if attachments:
                lines = []
                for att in attachments:
                    desc = att.description or att.file_path or ""
                    lines.append(f"• {desc}")
                self._attach_list.setText("\n".join(lines))
            else:
                self._attach_list.setText("无附件")
        except Exception:
            logger.exception("_load_attachments() failed")
            self._attach_list.setText("加载附件失败")

    def _load_comments(self) -> None:
        """加载评论列表（从新到旧）。"""
        try:
            comments = self._service.get_comments(self._issue.id)
        except Exception:
            logger.exception("_load_comments() failed")
            comments = []

        # 清空评论区域
        self._clear_layout(self._comment_list_layout)

        if not comments:
            self._comment_list_layout.addWidget(self._comment_empty)
            return

        # 从新到旧显示
        for c in reversed(comments):
            self._comment_list_layout.addWidget(self._build_comment_card(c))

    def _build_comment_card(self, comment: IssueComment) -> QFrame:
        """构建单条评论卡片。"""
        card = QFrame()
        card.setProperty("class", "comment-card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM)
        card_layout.setSpacing(4)

        # 头部：头像占位 + 作者 + 时间 + 删除按钮
        header = QHBoxLayout()
        header.setSpacing(SPACING_MEDIUM)

        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        avatar.setProperty("class", "avatar-placeholder")
        avatar.setStyleSheet(
            f"background-color: {_t.SURFACE1}; border-radius: 14px;"
            f" font-weight: bold; font-size: 12px;"
            f" color: {_t.FG_PRIMARY};"
        )
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setText((comment.author_name or "?")[0])
        header.addWidget(avatar)

        author_lbl = QLabel(comment.author_name or "未知")
        author_lbl.setProperty("class", "comment-author")
        author_lbl.setStyleSheet("font-weight: bold;")
        header.addWidget(author_lbl)

        time_lbl = QLabel(comment.created_at or "")
        time_lbl.setProperty("class", "subtext")
        time_lbl.setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 11px;")
        header.addWidget(time_lbl)

        header.addStretch()

        # 删除按钮
        btn_del = QPushButton("删除")
        btn_del.setProperty("class", "danger")
        btn_del.setFixedSize(40, 22)
        btn_del.setStyleSheet("font-size: 11px; padding: 0 4px;")
        cid = comment.id
        btn_del.clicked.connect(lambda cid=cid: self._on_delete_comment(cid) if cid is not None else None)
        header.addWidget(btn_del)

        card_layout.addLayout(header)

        # 内容
        content_lbl = QLabel(comment.content)
        content_lbl.setWordWrap(True)
        content_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(content_lbl)

        return card

    def _load_activity(self) -> None:
        """加载活动日志时间线。"""
        try:
            activities = self._service.get_activity_with_duration(self._issue.id)
        except Exception:
            logger.exception("_load_activity() failed")
            activities = []

        self._clear_layout(self._activity_layout)

        if not activities:
            empty = QLabel("暂无活动记录")
            empty.setProperty("class", "subtext")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._activity_layout.addWidget(empty)
            return

        for act in activities:
            self._activity_layout.addWidget(self._build_activity_card(act))

    def _build_activity_card(self, act: dict) -> QFrame:
        """构建单条活动日志卡片。"""
        card = QFrame()
        card.setProperty("class", "activity-card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM)

        # 时间
        time_lbl = QLabel((act.get("created_at") or "")[:16])
        time_lbl.setFixedWidth(130)
        time_lbl.setProperty("class", "subtext")
        time_lbl.setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 11px;")
        card_layout.addWidget(time_lbl)

        # 详情列
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(2)

        # 操作者 + 变更描述
        field = act.get("field", "")
        old_val = act.get("old_value", "")
        new_val = act.get("new_value", "")
        operator = act.get("operator", "")

        if field == "status":
            old_label = ISSUE_STATUS_LABELS.get(old_val, old_val)
            new_label = ISSUE_STATUS_LABELS.get(new_val, new_val)
            change_text = f"状态: {old_label} → {new_label}"
        elif field == "severity":
            old_label = SEVERITY_LABELS.get(old_val, old_val)
            new_label = SEVERITY_LABELS.get(new_val, new_val)
            change_text = f"严重度: {old_label} → {new_label}"
        else:
            map_label = {"assignee_id": "负责人", "dri_name": "DRI", "priority": "优先级",
                         "resolution": "处理结果", "category": "类别"}
            field_label = map_label.get(field, field)
            # assignee_id 翻译成人名
            if field == "assignee_id":
                def _translate_assignee(val: str) -> str:
                    if not val or val == "None":
                        return "（无）"
                    try:
                        tid = int(val)
                        return self._technician_map.get(tid, f"#{tid}")
                    except (ValueError, TypeError):
                        return val
                old_val = _translate_assignee(old_val)
                new_val = _translate_assignee(new_val)
            change_text = f"{field_label}: {old_val} → {new_val}"

        if operator:
            change_text = f"[{operator}] {change_text}"

        change_lbl = QLabel(change_text)
        change_lbl.setProperty("class", "activity-change")
        detail_layout.addWidget(change_lbl)

        # 停留时长
        duration = act.get("stay_duration", "")
        if duration:
            dur_lbl = QLabel(f"停留时长: {duration}")
            dur_lbl.setProperty("class", "subtext")
            dur_lbl.setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 11px;")
            detail_layout.addWidget(dur_lbl)

        card_layout.addLayout(detail_layout, stretch=1)

        return card

    def _load_fa_records(self) -> None:
        """加载 FA 记录到 _FAPanel。"""
        try:
            records = self._service.get_fa_records(self._issue.id)
        except Exception:
            logger.exception("_load_fa_records() failed")
            records = []
        self._fa_panel.set_fa_records(records)

    def _load_capa_records(self) -> None:
        """加载 CAPA 记录到 _CAPAPanel。"""
        try:
            records = self._service.get_capa_records(self._issue.id)
        except Exception:
            logger.exception("_load_capa_records() failed")
            records = []
        self._capa_panel.set_capa_records(records)

    # ── 操作回调 ────────────────────────────────────────────────────

    def _on_send_comment(self) -> None:
        """发送评论。"""
        content = self._comment_input.toPlainText().strip()
        if not content:
            return

        try:
            self._service.add_comment(
                self._issue.id, content, author_name="",
            )
            self._comment_input.clear()
            self._load_comments()
        except Exception:
            logger.exception("_on_send_comment() failed")
            pass

    def _on_delete_comment(self, comment_id: int) -> None:
        """删除评论 — 确认后软删除。"""
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这条评论吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._service.delete_comment(comment_id)
            self._load_comments()
        except Exception:
            logger.exception("_on_delete_comment() failed")
            pass

    # ── 辅助 ────────────────────────────────────────────────────────

    def _get_aging_text(self) -> str:
        """获取 Aging 天数文本。"""
        try:
            days = self._service.get_aging_days(self._issue.id)
            return f"{days} 天"
        except Exception:
            logger.exception("_get_aging_text() failed")
            return "-"

    @staticmethod
    def _clear_layout(layout) -> None:
        """清空布局内所有子控件。"""
        while layout.count():
            child = layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()
