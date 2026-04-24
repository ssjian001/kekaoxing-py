"""Issue 追踪视图 — Issue 列表 + FA 分析记录。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1,
    BLUE, GREEN, YELLOW, RED, PEACH, MAUVE, LAVENDER, PINK,
)
from src.models.issue import Issue, FARecord
from src.views.dialogs.issue_dialog import IssueEditDialog
from src.views.dialogs.fa_record_dialog import FARecordDialog


class _IssueTable(QTableWidget):
    """Issue 列表表格。"""

    COLUMNS = ["ID", "标题", "严重度", "状态", "优先级", "根因", "创建时间"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 50)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self._issues: list[Issue] = []
        self._context_menu: QMenu | None = None

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {BASE}; color: {TEXT};
                gridline-color: {SURFACE1}; border: 1px solid {SURFACE1};
                border-radius: 8px; font-size: 13px;
            }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:alternate {{ background-color: {MANTLE}; }}
            QHeaderView::section {{
                background-color: {SURFACE0}; color: {SUBTEXT0};
                padding: 8px; border: none; font-weight: bold; font-size: 12px;
            }}
        """)

        # 信号
        self.doubleClicked.connect(self._on_double_click)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ── 数据 ───────────────────────────────────────────────────

    def set_issues(self, issues: list[Issue]) -> None:
        self._issues = issues
        self.setRowCount(len(issues))
        severity_colors = {"critical": RED, "major": PEACH, "minor": YELLOW, "cosmetic": SUBTEXT0}
        status_colors = {"open": RED, "analyzing": YELLOW, "verified": BLUE, "closed": GREEN}
        for row, issue in enumerate(issues):
            for col, val in enumerate([
                issue.id,
                issue.title,
                issue.severity,
                issue.status,
                issue.priority,
                (issue.root_cause or "")[:15],
                (issue.created_at or "")[:10],
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 2:  # severity
                    item.setForeground(QColor(severity_colors.get(val, TEXT)))
                elif col == 3:  # status
                    item.setForeground(QColor(status_colors.get(val, TEXT)))
                self.setItem(row, col, item)

    def get_selected_issue_id(self) -> Optional[int]:
        row = self.currentRow()
        if 0 <= row < len(self._issues):
            return self._issues[row].id
        return None

    def get_selected_issue(self) -> Issue | None:
        """返回当前选中的 Issue 对象。"""
        row = self.currentRow()
        if 0 <= row < len(self._issues):
            return self._issues[row]
        return None

    # ── 右键菜单 ──────────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        if self._context_menu is None:
            self._context_menu = QMenu(self)
            self._context_menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {SURFACE0}; color: {TEXT};
                    border: 1px solid {SURFACE1}; padding: 4px;
                }}
                QMenu::item {{ padding: 6px 24px; }}
                QMenu::item:selected {{ background-color: {SURFACE1}; }}
            """)
            self._act_edit = self._context_menu.addAction("✏️ 编辑 Issue")
            self._act_delete = self._context_menu.addAction("🗑️ 删除 Issue")
            self._act_edit.triggered.connect(self._on_edit_action)
            self._act_delete.triggered.connect(self._on_delete_action)

        issue_id = self.get_selected_issue_id()
        self._act_edit.setEnabled(issue_id is not None)
        self._act_delete.setEnabled(issue_id is not None)
        self._context_menu.exec(self.viewport().mapToGlobal(pos))

    def _on_double_click(self) -> None:
        """双击行触发编辑。"""
        issue = self.get_selected_issue()
        if issue:
            self.parent_issue_view()._open_edit_dialog(issue)

    def _on_edit_action(self) -> None:
        issue = self.get_selected_issue()
        if issue:
            self.parent_issue_view()._open_edit_dialog(issue)

    def _on_delete_action(self) -> None:
        issue = self.get_selected_issue()
        if issue:
            self.parent_issue_view()._delete_issue(issue)

    def parent_issue_view(self) -> "IssueView":
        """向上查找到 IssueView 实例。"""
        p = self.parent()
        while p is not None and not isinstance(p, IssueView):
            p = p.parent()
        return p  # type: ignore[return-value]


class _FAPanel(QScrollArea):
    """FA 分析记录面板。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {BASE}; border: 1px solid {SURFACE1};
                border-radius: 8px;
            }}
        """)

    def set_fa_records(self, records: list[FARecord]) -> None:
        # 清空
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not records:
            label = QLabel("选择一个 Issue 查看 FA 分析记录")
            label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 14px; padding: 20px;")
            self._layout.addWidget(label)
            return

        for i, rec in enumerate(records):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {SURFACE0}; border-radius: 8px;
                    border: 1px solid {SURFACE1};
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)

            # 标题行
            header = QHBoxLayout()
            step_label = QLabel(f"Step {rec.step_no}")
            step_label.setStyleSheet(f"color: {BLUE}; font-weight: bold; font-size: 14px;")
            header.addWidget(step_label)

            method_label = QLabel(rec.method or "")
            method_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 12px;")
            header.addWidget(method_label)
            header.addStretch()
            card_layout.addLayout(header)

            # 步骤标题
            title = QLabel(rec.step_title or "")
            title.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: bold;")
            card_layout.addWidget(title)

            # 描述
            desc = QLabel(rec.description or "")
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {SUBTEXT1}; font-size: 13px;")
            card_layout.addWidget(desc)

            # 发现
            if rec.findings:
                findings = QLabel(f"🔍 发现: {rec.findings}")
                findings.setWordWrap(True)
                findings.setStyleSheet(f"color: {PEACH}; font-size: 13px;")
                card_layout.addWidget(findings)

            self._layout.addWidget(card)


class IssueView(QWidget):
    """Issue 追踪视图 — 左侧列表 + 右侧 FA 面板。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        title = QLabel("🐛 Issue 追踪")
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # 工具栏
        toolbar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索 Issue...")
        self._search_input.setFixedWidth(260)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE0}; color: {TEXT};
                border: 1px solid {SURFACE1}; border-radius: 6px; padding: 6px 12px;
            }}
        """)
        toolbar.addWidget(self._search_input)

        self._btn_add = QPushButton("➕ 新建 Issue")
        self._btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {RED}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }}
        """)
        toolbar.addWidget(self._btn_add)

        self._btn_add_fa = QPushButton("➕ 新建 FA 步骤")
        self._btn_add_fa.setStyleSheet(f"""
            QPushButton {{
                background-color: {BLUE}; color: {CRUST}; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }}
        """)
        toolbar.addWidget(self._btn_add_fa)

        toolbar.addStretch()

        # 统计标签
        self._stats_label = QLabel("0 个 Issue")
        self._stats_label.setStyleSheet(f"color: {SUBTEXT0}; font-size: 13px;")
        toolbar.addWidget(self._stats_label)

        layout.addLayout(toolbar)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._issue_table = _IssueTable()
        splitter.addWidget(self._issue_table)

        self._fa_panel = _FAPanel()
        splitter.addWidget(self._fa_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStyleSheet("QSplitter::handle { background-color: #45475a; width: 2px; }")

        layout.addWidget(splitter)

        # ── 信号连接 ──
        self._btn_add.clicked.connect(self._open_create_dialog)
        self._btn_add_fa.clicked.connect(self._open_fa_dialog)
        # 选中 Issue 时自动加载 FA 记录
        self._issue_table.itemSelectionChanged.connect(self._on_issue_selection_changed)

    # ── 数据刷新 ──────────────────────────────────────────────

    def refresh(self, issues: list[Issue]) -> None:
        self._issue_table.set_issues(issues)
        open_count = sum(1 for i in issues if i.status == "open")
        analyzing = sum(1 for i in issues if i.status == "analyzing")
        self._stats_label.setText(f"{len(issues)} 个 Issue（{open_count} 待处理，{analyzing} 分析中）")

    def refresh_fa(self, records: list[FARecord]) -> None:
        self._fa_panel.set_fa_records(records)

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def issue_table(self) -> _IssueTable:
        return self._issue_table

    @property
    def btn_add(self) -> QPushButton:
        return self._btn_add

    @property
    def btn_add_fa(self) -> QPushButton:
        return self._btn_add_fa

    def get_selected_issue_id(self) -> Optional[int]:
        return self._issue_table.get_selected_issue_id()

    # ── Issue 新建/编辑/删除 ──────────────────────────────────

    def _open_create_dialog(self) -> None:
        """打开新建 Issue 弹窗。"""
        dlg = IssueEditDialog(issue=None, parent=self)
        if dlg.exec():
            self._on_issue_saved(dlg.get_data())

    def _open_edit_dialog(self, issue: Issue) -> None:
        """打开编辑 Issue 弹窗。"""
        dlg = IssueEditDialog(issue=issue, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["id"] = issue.id
            self._on_issue_saved(data)

    def _delete_issue(self, issue: Issue) -> None:
        """删除 Issue（带确认）。"""
        reply = QMessageBox.warning(
            self,
            "确认删除",
            f"确定要删除 Issue #{issue.id} 「{issue.title}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_issue_deleted(issue.id)

    # ── FA 步骤 ──────────────────────────────────────────────

    def _open_fa_dialog(self) -> None:
        """打开新建 FA 步骤弹窗。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is None:
            QMessageBox.information(self, "提示", "请先在左侧列表中选中一个 Issue。")
            return
        # 收集已有 step_no 用于自动递增
        existing_nos = [rec.step_no for rec in self._current_fa_records()]
        dlg = FARecordDialog(existing_step_nos=existing_nos, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            data["issue_id"] = issue_id
            self._on_fa_record_added(data)

    def _current_fa_records(self) -> list[FARecord]:
        """返回当前 FA 面板中显示的记录列表（供外部覆盖）。"""
        return []

    # ── 选中变化 ──────────────────────────────────────────────

    def _on_issue_selection_changed(self) -> None:
        """选中 Issue 时触发加载 FA 记录。"""
        issue_id = self.get_selected_issue_id()
        if issue_id is not None:
            self._on_issue_selected(issue_id)

    # ── 钩子方法（由 presenter / controller 连接）───────────

    def _on_issue_saved(self, data: dict) -> None:
        """钩子：Issue 保存后回调。由外部连接。"""
        pass

    def _on_issue_deleted(self, issue_id: int) -> None:
        """钩子：Issue 删除后回调。由外部连接。"""
        pass

    def _on_issue_selected(self, issue_id: int) -> None:
        """钩子：Issue 选中时回调（用于加载 FA 记录）。由外部连接。"""
        pass

    def _on_fa_record_added(self, data: dict) -> None:
        """钩子：FA 记录添加后回调。由外部连接。"""
        pass
