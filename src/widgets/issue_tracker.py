"""Issue 追踪管理面板 — 轻量级缺陷追踪，支持状态流转、筛选和搜索。"""

from __future__ import annotations

import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QDialog, QFormLayout,
    QTextEdit, QSpinBox, QHeaderView, QMessageBox, QMenu, QAbstractItemView,
    QSizePolicy, QFileDialog, QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QBrush, QAction

from src.db.database import Database
from src.styles.colors import (
    BLUE, RED, PEACH, YELLOW, GREEN, TEAL, MAUVE,
    OVERLAY0, BASE, MANTLE, SURFACE0, TEXT,
)


# ── 常量 ─────────────────────────────────────────────────────────────────────

SEVERITY_MAP = {
    "critical":    ("🔴 严重", RED),
    "major":       ("🟠 主要", PEACH),
    "minor":       ("🟡 次要", YELLOW),
    "cosmetic":    ("🔵 外观", BLUE),
    "suggestion":  ("💡 建议", GREEN),
}

STATUS_MAP = {
    "open":        ("待处理", RED),
    "in_progress": ("进行中", BLUE),
    "fixed":       ("已修复", GREEN),
    "verified":    ("已验证", TEAL),
    "closed":      ("已关闭", OVERLAY0),
    "wontfix":     ("不修复", MAUVE),
}

STATUS_TRANSITIONS = {
    "open":        ["in_progress", "closed", "wontfix"],
    "in_progress": ["fixed", "open", "wontfix"],
    "fixed":       ["verified", "in_progress"],
    "verified":    ["closed", "fixed"],
    "closed":      ["open"],
    "wontfix":     [],
}

PRIORITY_COLORS = {1: RED, 2: PEACH, 3: YELLOW, 4: GREEN, 5: OVERLAY0}

ISSUE_TYPE_MAP = {
    "bug":          ("🐛 缺陷", RED),
    "improvement":  ("⬆️ 改进", BLUE),
    "feature":      ("✨ 需求", GREEN),
    "task":         ("📋 任务", MAUVE),
}

PHASE_MAP = {
    "":             ("—", OVERLAY0),
    "prototype":    ("初样试验", RED),
    "validation":   ("正样试验", PEACH),
    "qualification":("定型试验", YELLOW),
    "routine":      ("例行试验", BLUE),
    "certification":("鉴定检验", GREEN),
    "delivery":     ("交付检验", MAUVE),
    "other":        ("其他", OVERLAY0),
}

# Aliases for backward compatibility with inline QSS references
BG_EVEN   = BASE
BG_ODD    = MANTLE
BG_PANEL  = MANTLE
FG_TEXT   = TEXT
FG_DIM    = OVERLAY0
BORDER    = SURFACE0
ACCENT    = BLUE


# ── Issue 编辑对话框 ─────────────────────────────────────────────────────────

class _IssueEditDialog(QDialog):
    """创建/编辑 Issue 对话框"""

    def __init__(self, db: Database, issue: dict | None = None,
                 default_task_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.issue = issue
        self._task_map: dict[int, str] = {}
        self.setWindowTitle("新建 Issue" if issue is None else "编辑 Issue")
        self.setMinimumSize(560, 600)
        self.resize(560, 820)
        self._setup_ui()
        if issue:
            self._load(issue)
        if default_task_id and not issue:
            self.task_combo.setCurrentIndex(
                self.task_combo.findData(default_task_id))

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("输入 Issue 标题 *")
        form.addRow("标题 *:", self.title_edit)

        # 关联任务
        self.task_combo = QComboBox()
        self.task_combo.addItem("— 无关联任务 —", 0)
        tasks = self.db.get_all_tasks()
        for t in tasks:
            label = f"{t.num} - {t.name_cn}"
            self.task_combo.addItem(label, t.id)
            self._task_map[t.id] = label
        form.addRow("关联任务:", self.task_combo)

        # Issue 类型
        self.type_combo = QComboBox()
        for key, (label, _) in ISSUE_TYPE_MAP.items():
            self.type_combo.addItem(label, key)
        self.type_combo.setCurrentIndex(0)  # bug
        form.addRow("类型:", self.type_combo)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("详细描述...")
        self.desc_edit.setFixedHeight(100)
        form.addRow("描述:", self.desc_edit)

        # 严重程度
        self.severity_combo = QComboBox()
        for key, (label, _) in SEVERITY_MAP.items():
            self.severity_combo.addItem(label, key)
        self.severity_combo.setCurrentIndex(2)  # minor
        form.addRow("严重程度:", self.severity_combo)

        # 状态
        self.status_combo = QComboBox()
        for key, (label, _) in STATUS_MAP.items():
            self.status_combo.addItem(label, key)
        self.status_combo.setCurrentIndex(0)  # open
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        form.addRow("状态:", self.status_combo)

        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 5)
        self.priority_spin.setValue(3)
        form.addRow("优先级 (1最高):", self.priority_spin)

        # 测试阶段
        self.phase_combo = QComboBox()
        for key, (label, _) in PHASE_MAP.items():
            self.phase_combo.addItem(label, key)
        self.phase_combo.setCurrentIndex(0)  # —
        form.addRow("测试阶段:", self.phase_combo)

        self.assignee_edit = QLineEdit()
        self.assignee_edit.setPlaceholderText("负责人")
        form.addRow("负责人:", self.assignee_edit)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("标签, 用逗号分隔 (如: regression, intermittent)")
        form.addRow("标签:", self.tags_edit)

        self.resolution_edit = QTextEdit()
        self.resolution_edit.setPlaceholderText("解决方案描述...")
        self.resolution_edit.setFixedHeight(60)
        self.resolution_label = QLabel("解决方案:")
        form.addRow(self.resolution_label, self.resolution_edit)
        self.resolution_edit.hide()
        self.resolution_label.hide()

        # 原因分析
        self.cause_edit = QTextEdit()
        self.cause_edit.setPlaceholderText("分析问题产生的根本原因...")
        self.cause_edit.setFixedHeight(60)
        form.addRow("原因分析:", self.cause_edit)

        # 改善对策
        self.countermeasure_edit = QTextEdit()
        self.countermeasure_edit.setPlaceholderText("针对原因的改善对策和预防措施...")
        self.countermeasure_edit.setFixedHeight(60)
        form.addRow("改善对策:", self.countermeasure_edit)

        # 时间信息（编辑模式只读显示）
        self.time_info_label = QLabel("")
        self.time_info_label.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        self.time_info_label.setWordWrap(True)
        self.time_info_label.hide()
        form.addRow(self.time_info_label)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("accent")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self._apply_dark_style()

    def _apply_dark_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_EVEN}; color: {FG_TEXT}; }}
            QLabel {{ color: {FG_TEXT}; font-size: 13px; }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 4px 8px; font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {ACCENT};
            }}
            QPushButton {{ background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 6px 16px; font-size: 13px; }}
            QPushButton:hover {{ background: {BORDER}; }}
            QPushButton#accent {{ background: {ACCENT}; color: #1e1e2e;
                border: none; font-weight: bold; }}
            QPushButton#accent:hover {{ opacity: 0.85; }}
        """)

    def _on_status_changed(self, idx):
        status = self.status_combo.currentData()
        show = status in ("fixed", "verified", "closed")
        self.resolution_edit.setVisible(show)
        self.resolution_label.setVisible(show)

    def _load(self, issue: dict):
        self.title_edit.setText(issue["title"])
        # 关联任务
        task_id = issue.get("task_id", 0)
        idx = self.task_combo.findData(task_id)
        if idx >= 0:
            self.task_combo.setCurrentIndex(idx)
        self.desc_edit.setPlainText(issue.get("description", ""))
        sev = issue.get("severity", "minor")
        idx = self.severity_combo.findData(sev)
        if idx >= 0:
            self.severity_combo.setCurrentIndex(idx)
        status = issue.get("status", "open")
        idx = self.status_combo.findData(status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.priority_spin.setValue(issue.get("priority", 3))
        self.assignee_edit.setText(issue.get("assignee", ""))
        tags = issue.get("tags", [])
        if isinstance(tags, list):
            self.tags_edit.setText(", ".join(tags))
        self.resolution_edit.setPlainText(issue.get("resolution", ""))
        self.cause_edit.setPlainText(issue.get("cause", ""))
        self.countermeasure_edit.setPlainText(issue.get("countermeasure", ""))
        itype = issue.get("issue_type", "bug")
        idx = self.type_combo.findData(itype)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        phase = issue.get("phase", "")
        idx = self.phase_combo.findData(phase)
        if idx >= 0:
            self.phase_combo.setCurrentIndex(idx)
        # 时间信息
        created = issue.get("created_at", "")
        updated = issue.get("updated_at", "")
        if created:
            self.time_info_label.setText(f"创建: {created}    修改: {updated}")
            self.time_info_label.show()

    def _on_save(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入 Issue 标题")
            return
        self._result = {
            "title": title,
            "issue_type": self.type_combo.currentData(),
            "task_id": self.task_combo.currentData() or 0,
            "description": self.desc_edit.toPlainText().strip(),
            "severity": self.severity_combo.currentData(),
            "status": self.status_combo.currentData(),
            "priority": self.priority_spin.value(),
            "phase": self.phase_combo.currentData(),
            "assignee": self.assignee_edit.text().strip(),
            "tags": [t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            "resolution": self.resolution_edit.toPlainText().strip(),
            "cause": self.cause_edit.toPlainText().strip(),
            "countermeasure": self.countermeasure_edit.toPlainText().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_result", {})


# ── 统计卡片 ─────────────────────────────────────────────────────────────────

class _StatCard(QPushButton):
    """可点击的统计卡片"""
    clicked_status = Signal(str)

    def __init__(self, icon: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self.status_key = ""
        self.color = color
        self._icon = icon
        self._label = label
        self._count = 0
        self.setFixedHeight(52)
        self.setCursor(Qt.PointingHandCursor)
        self._update_text()
        self.setStyleSheet(f"""
            QPushButton {{
                background: {color}22; color: {color};
                border: 1px solid {color}44; border-radius: 6px;
                font-size: 13px; padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: {color}44;
            }}
        """)

    def _update_text(self):
        self.setText(f"{self._icon}  {self._count}  {self._label}")

    def set_count(self, count: int):
        self._count = count
        self._update_text()


# ── 主面板 ───────────────────────────────────────────────────────────────────

class IssueTrackerWidget(QWidget):
    """Issue 追踪管理面板"""

    issue_count_changed = Signal(int)
    jump_to_task = Signal(int)  # 双击 Issue 跳转到甘特图任务

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_status_filter = ""
        self._current_severity_filter = ""
        self._current_search = ""
        self._task_filter: int | None = None
        self._issues: list[dict] = []
        self._hidden_columns: set[int] = set()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. 统计栏
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(6)
        self.cards: dict[str, _StatCard] = {}
        for key, (label, color) in STATUS_MAP.items():
            icon = {"open": "🔴", "in_progress": "🔵", "fixed": "🟢",
                    "verified": "✅", "closed": "✔️", "wontfix": "🚫"}.get(key, "📌")
            card = _StatCard(icon, label, color)
            card.status_key = key
            card.clicked_status.connect(self._on_stats_clicked)
            stats_layout.addWidget(card)
            self.cards[key] = card
        # 全部
        all_card = _StatCard("📊", "全部", ACCENT)
        all_card.status_key = ""
        all_card.clicked_status.connect(self._on_stats_clicked)
        stats_layout.addWidget(all_card)
        self.cards[""] = all_card
        layout.addLayout(stats_layout)

        # 2. 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        new_btn = QPushButton("➕ 新建 Issue")
        new_btn.setObjectName("accent")
        new_btn.clicked.connect(self._on_new_issue)
        toolbar.addWidget(new_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        export_btn = QPushButton("📥 导出 CSV")
        export_btn.clicked.connect(self._on_export_csv)
        toolbar.addWidget(export_btn)

        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("状态:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部", "")
        for key, (label, _) in STATUS_MAP.items():
            self.status_filter.addItem(label, key)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.status_filter)

        toolbar.addWidget(QLabel("严重度:"))
        self.severity_filter = QComboBox()
        self.severity_filter.addItem("全部", "")
        for key, (label, _) in SEVERITY_MAP.items():
            self.severity_filter.addItem(label, key)
        self.severity_filter.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.severity_filter)

        toolbar.addWidget(QLabel("🔍"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索标题/描述/原因/对策...")
        self.search_edit.setFixedWidth(200)
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit)

        # 列显隐控制
        col_toggle_btn = QPushButton("⚙️ 列")
        col_toggle_btn.setFixedWidth(50)
        col_toggle_btn.clicked.connect(self._on_column_toggle)
        toolbar.addWidget(col_toggle_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 3. 表格
        self.table = QTableWidget()
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels([
            "!", "ID", "类型", "标题", "关联任务", "严重程度", "状态",
            "测试阶段", "负责人", "发现日期", "原因分析", "改善对策", "操作"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(11, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(12, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 36)
        self.table.setColumnWidth(1, 44)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 88)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 80)
        self.table.setColumnWidth(9, 100)
        self.table.setColumnWidth(12, 140)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(self._on_double_click)
        # 排序：填充后启用
        self._sort_enabled = True
        layout.addWidget(self.table)

        # 空状态提示
        self._empty_hint = QLabel("🐛 暂无 Issue\n右键甘特图任务可快速创建")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setStyleSheet("color: #a6adc8; font-size: 14px;")
        self._empty_hint.setWordWrap(True)
        # 使用叠加方式：将 hint 提升到 table 上方
        self._empty_hint.setParent(self.table)
        self._empty_hint.setGeometry(0, 0, 800, 200)
        self._empty_hint.hide()

        # 搜索防抖
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._load_issues)

        self._apply_dark_style()
        # 首次加载
        QTimer.singleShot(100, self.refresh)

    def _apply_dark_style(self):
        self.setStyleSheet(f"""
            QWidget {{ background: {BG_EVEN}; color: {FG_TEXT}; font-size: 13px; }}
            QTableWidget {{
                background: {BG_EVEN}; alternate-background-color: {BG_ODD};
                color: {FG_TEXT}; gridline-color: {BORDER};
                border: 1px solid {BORDER}; border-radius: 4px;
            }}
            QTableWidget::item {{
                padding: 3px 6px; border-bottom: 1px solid {BORDER};
            }}
            QTableWidget::item:selected {{
                background: {ACCENT}33;
            }}
            QHeaderView::section {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: none; border-bottom: 1px solid {BORDER};
                border-right: 1px solid {BORDER};
                padding: 4px 6px; font-size: 12px; font-weight: bold;
            }}
            QLabel {{ color: {FG_TEXT}; }}
            QComboBox {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 3px 8px; min-width: 80px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; selection-background-color: {ACCENT}44;
            }}
            QLineEdit {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 3px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
            QPushButton {{
                background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 5px 14px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {BORDER}; }}
            QPushButton#accent {{ background: {ACCENT}; color: #1e1e2e;
                border: none; font-weight: bold; }}
            QPushButton#accent:hover {{ opacity: 0.85; }}
        """)

    # ── 数据加载 ──────────────────────────────────────────────────────────

    def refresh(self, task_id: int | None = None):
        self._task_filter = task_id
        self._update_stats()
        self._load_issues()

    def filter_by_task(self, task_id: int):
        self._task_filter = task_id
        self._load_issues()

    def _update_stats(self):
        stats = self.db.get_issue_stats()
        for key in STATUS_MAP:
            self.cards[key].set_count(stats.get(key, 0))
        self.cards[""].set_count(stats.get("total", 0))

    def _load_issues(self):
        self._current_status_filter = self.status_filter.currentData()
        self._current_severity_filter = self.severity_filter.currentData()
        self._current_search = self.search_edit.text().strip().lower()

        issues = self.db.get_issues(
            task_id=self._task_filter,
            status=self._current_status_filter or None,
        )
        # 严重度过滤
        if self._current_severity_filter:
            issues = [i for i in issues if i["severity"] == self._current_severity_filter]
        # 搜索过滤
        if self._current_search:
            issues = [i for i in issues
                      if self._current_search in i["title"].lower()
                      or self._current_search in i.get("description", "").lower()
                      or self._current_search in i.get("cause", "").lower()
                      or self._current_search in i.get("countermeasure", "").lower()
                      or self._current_search in i.get("assignee", "").lower()
                      or self._current_search in str(i.get("tags", [])).lower()]
        self._issues = issues
        self._populate_table()

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        # 预加载 task_id → label 映射，避免 N+1 查询
        task_rows = self.db.conn.execute(
            "SELECT id, num, name_cn FROM tasks"
        ).fetchall()
        task_label_map: dict[int, str] = {
            r[0]: f"{r[1]} - {r[2]}" for r in task_rows
        }

        self.table.setRowCount(len(self._issues))
        for row, issue in enumerate(self._issues):
            # 优先级
            pri = issue.get("priority", 3)
            color = PRIORITY_COLORS.get(pri, FG_DIM)
            pri_item = QTableWidgetItem(str(pri))
            pri_item.setForeground(QBrush(QColor(color)))
            pri_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pri_item.setFont(QFont("", 12, QFont.Weight.Bold))
            pri_item.setData(Qt.ItemDataRole.UserRole, pri)
            self.table.setItem(row, 0, pri_item)

            # ID
            id_item = QTableWidgetItem(f"#{issue['id']}")
            id_item.setForeground(QBrush(QColor(FG_DIM)))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setData(Qt.ItemDataRole.UserRole, issue['id'])
            self.table.setItem(row, 1, id_item)

            # 类型
            itype = issue.get("issue_type", "bug")
            it_label, it_color = ISSUE_TYPE_MAP.get(itype, ("未知", FG_DIM))
            type_item = QTableWidgetItem(it_label)
            type_item.setForeground(QBrush(QColor(it_color)))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, type_item)

            # 标题
            self.table.setItem(row, 3, QTableWidgetItem(issue["title"]))

            # 关联任务
            task_label = "—"
            tid = issue.get("task_id", 0)
            if tid:
                task_label = task_label_map.get(tid, "—")
            task_item = QTableWidgetItem(task_label)
            task_item.setForeground(QBrush(QColor(FG_DIM)))
            self.table.setItem(row, 4, task_item)

            # 严重程度
            sev = issue.get("severity", "minor")
            sev_label, sev_color = SEVERITY_MAP.get(sev, ("未知", FG_DIM))
            sev_item = QTableWidgetItem(sev_label)
            sev_item.setForeground(QBrush(QColor(sev_color)))
            self.table.setItem(row, 5, sev_item)

            # 状态
            status = issue.get("status", "open")
            st_label, st_color = STATUS_MAP.get(status, ("未知", FG_DIM))
            st_item = QTableWidgetItem(f" {st_label} ")
            st_item.setForeground(QBrush(QColor("#1e1e2e" if status not in ("closed", "wontfix") else FG_TEXT)))
            st_item.setBackground(QBrush(QColor(st_color)))
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, st_item)

            # 测试阶段
            phase = issue.get("phase", "")
            ph_label, ph_color = PHASE_MAP.get(phase, ("—", FG_DIM))
            phase_item = QTableWidgetItem(ph_label)
            phase_item.setForeground(QBrush(QColor(ph_color)))
            phase_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 7, phase_item)

            # 负责人
            assignee = issue.get("assignee", "") or "—"
            a_item = QTableWidgetItem(assignee)
            a_item.setForeground(QBrush(QColor(FG_DIM)))
            self.table.setItem(row, 8, a_item)

            # 发现日期
            date_str = issue.get("found_date", "")[:10]
            d_item = QTableWidgetItem(date_str)
            d_item.setForeground(QBrush(QColor(FG_DIM)))
            self.table.setItem(row, 9, d_item)

            # 原因分析
            cause = issue.get("cause", "") or ""
            cause_item = QTableWidgetItem(cause)
            cause_item.setForeground(QBrush(QColor(FG_DIM)))
            cause_item.setToolTip(cause)
            self.table.setItem(row, 10, cause_item)

            # 改善对策
            countermeasure = issue.get("countermeasure", "") or ""
            cm_item = QTableWidgetItem(countermeasure)
            cm_item.setForeground(QBrush(QColor(FG_DIM)))
            cm_item.setToolTip(countermeasure)
            self.table.setItem(row, 11, cm_item)

            # 操作
            ops_widget = QWidget()
            ops_layout = QHBoxLayout(ops_widget)
            ops_layout.setContentsMargins(2, 0, 2, 0)
            ops_layout.setSpacing(4)

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedWidth(50)
            edit_btn.clicked.connect(lambda _, iid=issue["id"]: self._on_edit(iid))
            ops_layout.addWidget(edit_btn)

            status_btn = QPushButton("状态 ▶")
            status_btn.setFixedWidth(65)
            status_btn.clicked.connect(lambda _, iid=issue["id"], st=status: self._on_status_menu(iid, st, status_btn))
            ops_layout.addWidget(status_btn)

            self.table.setCellWidget(row, 12, ops_widget)

        self.table.setSortingEnabled(self._sort_enabled)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.issue_count_changed.emit(len(self._issues))
        # 空状态提示显示/隐藏
        if len(self._issues) == 0:
            self._empty_hint.show()
            self._empty_hint.raise_()
        else:
            self._empty_hint.hide()

    # ── 事件处理 ──────────────────────────────────────────────────────────

    def _on_stats_clicked(self, status_key: str):
        if status_key == "":
            self.status_filter.setCurrentIndex(0)
        else:
            idx = self.status_filter.findData(status_key)
            if idx >= 0:
                self.status_filter.setCurrentIndex(idx)
        self._load_issues()

    def _on_filter_changed(self):
        self._load_issues()

    def _on_search_changed(self, text: str):
        self._search_timer.start(300)

    def _on_new_issue(self):
        dlg = _IssueEditDialog(self.db, default_task_id=self._task_filter, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            task_id = data.get("task_id", 0)
            self.db.insert_issue(
                task_id=task_id,
                title=data["title"],
                description=data.get("description", ""),
                issue_type=data.get("issue_type", "bug"),
                severity=data.get("severity", "minor"),
                status=data.get("status", "open"),
                priority=data.get("priority", 3),
                phase=data.get("phase", ""),
                assignee=data.get("assignee", ""),
                cause=data.get("cause", ""),
                countermeasure=data.get("countermeasure", ""),
                tags=data.get("tags", []),
            )
            self.refresh()

    def _on_edit(self, issue_id: int):
        issue = self.db.get_issue(issue_id)
        if not issue:
            return
        dlg = _IssueEditDialog(self.db, issue=issue, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.db.update_issue(issue_id, **data)
            self.refresh()

    def _on_status_menu(self, issue_id: int, current_status: str, button: QPushButton):
        menu = QMenu(button)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; padding: 4px; }}
            QMenu::item {{ padding: 5px 20px; }}
            QMenu::item:selected {{ background: {ACCENT}44; }}
        """)
        transitions = STATUS_TRANSITIONS.get(current_status, [])
        if not transitions:
            menu.addAction(QAction("无可用状态流转", menu))
            menu.setEnabled(False)
        for target in transitions:
            label, color = STATUS_MAP.get(target, (target, FG_TEXT))
            action = QAction(f"→ {label}", menu)
            action.setData((issue_id, target))
            action.triggered.connect(self._on_status_transition)
            menu.addAction(action)
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _on_status_transition(self):
        action = self.sender()
        if not action:
            return
        issue_id, new_status = action.data()
        _, label = STATUS_MAP.get(new_status, (new_status, ""))
        reply = QMessageBox.question(
            self, "确认状态变更",
            f"确定要将此 Issue 状态变更为「{label}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 记录状态变更历史
            old_status = ""
            for i in self._issues:
                if i["id"] == issue_id:
                    old_status = i.get("status", "")
                    break
            self.db.insert_issue_history(
                issue_id, "status", old_status, new_status,
                remark="",
            )
            update = {"status": new_status}
            if new_status in ("fixed", "verified", "closed"):
                update["resolved_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            self.db.update_issue(issue_id, **update)
            self.refresh()

    def _on_double_click(self, index):
        row = index.row()
        if row >= 0 and row < len(self._issues):
            issue = self._issues[row]
            task_id = issue.get("task_id", 0)
            if task_id:
                self.jump_to_task.emit(task_id)
            else:
                self._on_edit(issue["id"])

    def _on_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self._issues):
            return
        issue = self._issues[row]
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; padding: 4px; }}
            QMenu::item {{ padding: 5px 20px; }}
            QMenu::item:selected {{ background: {ACCENT}44; }}
        """)

        edit_act = QAction("📝 编辑", menu)
        edit_act.triggered.connect(lambda: self._on_edit(issue["id"]))
        menu.addAction(edit_act)

        # 快速状态子菜单
        status_menu = menu.addMenu("🔄 快速状态切换")
        transitions = STATUS_TRANSITIONS.get(issue["status"], [])
        for target in transitions:
            _, label = STATUS_MAP.get(target, (target, ""))
            act = QAction(f"→ {label}", status_menu)
            act.triggered.connect(lambda checked, tid=issue["id"], ts=target:
                                  self._quick_status_change(tid, ts))
            status_menu.addAction(act)
        if not transitions:
            no_act = QAction("无可用状态", status_menu)
            no_act.setEnabled(False)
            status_menu.addAction(no_act)

        menu.addSeparator()

        copy_act = QAction("📋 复制标题", menu)
        copy_act.triggered.connect(lambda: self._copy_title(issue["title"]))
        menu.addAction(copy_act)

        copy_detail_act = QAction("📄 复制详情", menu)
        copy_detail_act.triggered.connect(lambda: self._copy_issue_detail(issue))
        menu.addAction(copy_detail_act)

        dup_act = QAction("📋 复制 Issue", menu)
        dup_act.triggered.connect(lambda: self._on_duplicate_issue(issue))
        menu.addAction(dup_act)

        hist_act = QAction("📜 变更历史", menu)
        hist_act.triggered.connect(lambda: self._on_view_history(issue["id"]))
        menu.addAction(hist_act)

        menu.addSeparator()

        del_act = QAction("🗑️ 删除", menu)
        del_act.triggered.connect(lambda: self._on_delete(issue["id"]))
        menu.addAction(del_act)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _quick_status_change(self, issue_id: int, new_status: str):
        old_status = ""
        for i in self._issues:
            if i["id"] == issue_id:
                old_status = i.get("status", "")
                break
        self.db.insert_issue_history(
            issue_id, "status", old_status, new_status,
        )
        update = {"status": new_status}
        if new_status in ("fixed", "verified", "closed"):
            import datetime
            update["resolved_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.db.update_issue(issue_id, **update)
        self.refresh()

    def _copy_title(self, title: str):
        QApplication.clipboard().setText(title)

    def _copy_issue_detail(self, issue: dict):
        severity_label = SEVERITY_MAP.get(issue.get("severity", ""), ("", ""))[0]
        status_label = STATUS_MAP.get(issue.get("status", ""), ("", ""))[0]
        type_label = ISSUE_TYPE_MAP.get(issue.get("issue_type", ""), ("", ""))[0]
        text = (
            f"#{issue['id']} {type_label} | {issue['title']}\n"
            f"状态: {status_label}  优先级: {issue.get('priority', '-')}\n"
            f"负责人: {issue.get('assignee', '—')}  "
            f"发现日期: {issue.get('found_date', '')[:10]}\n"
            f"描述: {issue.get('description', '')}\n"
            f"原因: {issue.get('cause', '')}\n"
            f"对策: {issue.get('countermeasure', '')}"
        )
        QApplication.clipboard().setText(text)

    def _on_duplicate_issue(self, issue: dict):
        dlg = _IssueEditDialog(self.db, default_task_id=issue.get("task_id"), parent=self)
        dlg.title_edit.setText(f"[复制] {issue['title']}")
        dlg.desc_edit.setPlainText(issue.get("description", ""))
        dlg.type_combo.setCurrentIndex(dlg.type_combo.findData(issue.get("issue_type", "bug")))
        dlg.severity_combo.setCurrentIndex(dlg.severity_combo.findData(issue.get("severity", "minor")))
        dlg.phase_combo.setCurrentIndex(dlg.phase_combo.findData(issue.get("phase", "")))
        dlg.assignee_edit.setText(issue.get("assignee", ""))
        dlg.cause_edit.setPlainText(issue.get("cause", ""))
        dlg.countermeasure_edit.setPlainText(issue.get("countermeasure", ""))
        tags = issue.get("tags", [])
        if isinstance(tags, list):
            dlg.tags_edit.setText(", ".join(tags))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.db.insert_issue(
                task_id=data.get("task_id", 0),
                title=data["title"],
                description=data.get("description", ""),
                issue_type=data.get("issue_type", "bug"),
                severity=data.get("severity", "minor"),
                status=data.get("status", "open"),
                priority=data.get("priority", 3),
                phase=data.get("phase", ""),
                assignee=data.get("assignee", ""),
                cause=data.get("cause", ""),
                countermeasure=data.get("countermeasure", ""),
                tags=data.get("tags", []),
            )
            self.refresh()

    def _on_view_history(self, issue_id: int):
        from src.widgets.issue_history_dialog import IssueHistoryDialog
        dlg = IssueHistoryDialog(self.db, issue_id, parent=self)
        dlg.exec()

    def _on_delete(self, issue_id: int):
        reply = QMessageBox.warning(
            self, "确认删除",
            "确定要删除此 Issue 吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_issue(issue_id)
            self.refresh()

    def _on_column_toggle(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_PANEL}; color: {FG_TEXT};
                border: 1px solid {BORDER}; padding: 4px; }}
            QMenu::item {{ padding: 5px 20px; }}
            QMenu::item:selected {{ background: {ACCENT}44; }}
        """)
        col_names = ["优先级", "ID", "类型", "标题", "关联任务", "严重程度",
                      "状态", "测试阶段", "负责人", "发现日期",
                      "原因分析", "改善对策", "操作"]
        for idx, name in enumerate(col_names):
            action = QAction(name, menu)
            action.setCheckable(True)
            action.setChecked(idx not in self._hidden_columns)
            action.triggered.connect(lambda checked, i=idx: self._toggle_column(i, checked))
            menu.addAction(action)
        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    def _toggle_column(self, col: int, visible: bool):
        self.table.setColumnHidden(col, not visible)
        if visible:
            self._hidden_columns.discard(col)
        else:
            self._hidden_columns.add(col)

    def _on_export_csv(self):
        import csv
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Issues", "issues.csv", "CSV Files (*.csv)")
        if not path:
            return
        # 预加载 task 映射，避免 N+1 查询
        task_rows = self.db.conn.execute(
            "SELECT id, num, name_cn FROM tasks"
        ).fetchall()
        task_label_map: dict[int, str] = {
            r[0]: f"{r[1]}-{r[2]}" for r in task_rows
        }
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "类型", "标题", "描述", "关联任务", "严重程度", "状态",
                "优先级", "测试阶段", "负责人", "发现日期", "解决日期",
                "解决方案", "原因分析", "改善对策", "标签", "创建时间", "修改时间"
            ])
            for issue in self._issues:
                type_label = ISSUE_TYPE_MAP.get(issue.get("issue_type", ""), ("", ""))[0]
                sev_label = SEVERITY_MAP.get(issue.get("severity", ""), ("", ""))[0]
                st_label = STATUS_MAP.get(issue.get("status", ""), ("", ""))[0]
                ph_label = PHASE_MAP.get(issue.get("phase", ""), ("", ""))[0]
                tid = issue.get("task_id", 0)
                task_label = task_label_map.get(tid, "—") if tid else "—"
                tags = issue.get("tags", [])
                if isinstance(tags, list):
                    tags = ", ".join(tags)
                writer.writerow([
                    issue["id"], type_label, issue["title"],
                    issue.get("description", ""), task_label,
                    sev_label, st_label, issue.get("priority", ""),
                    ph_label, issue.get("assignee", ""),
                    issue.get("found_date", "")[:10],
                    issue.get("resolved_date", ""),
                    issue.get("resolution", ""),
                    issue.get("cause", ""),
                    issue.get("countermeasure", ""),
                    tags,
                    issue.get("created_at", ""),
                    issue.get("updated_at", ""),
                ])
