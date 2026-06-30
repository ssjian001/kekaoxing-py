"""待办事项 Tab — Todoist 风格列表视图。

布局: 项目筛选 → filter tab → 快速添加栏 → 滚动列表(分组+行)。
每行: 圆形 checkbox + 优先级色点 + 标题 + 日期 + 分类 chip。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QMenu, QScrollArea, QFrame, QComboBox,
    QSizePolicy, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QEvent, QDate, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QPalette, QBrush, QPalette

from src.models.todo import TodoItem
from src.models.project import Project
from src.styles.constants import VIEW_MARGINS
import src.styles.theme as _theme

# ── 常量 ───────────────────────────────────────────────────────

_PRIORITY_COLORS = {
    "high": "#e64553",
    "medium": "#df8e1d",
    "low": "#40a02b",
}
_PRIORITY_CLASS = {
    "high": "pd-h",
    "medium": "pd-m",
    "low": "pd-l",
}
_STATUS_LABELS = {"pending": "待处理", "in_progress": "进行中", "done": "已完成"}

# 分组枚举
GROUP_OVERDUE = "已逾期"
GROUP_TODAY = "今日"
GROUP_WEEK = "本周"
GROUP_LATER = "以后"
GROUP_NODATE = "待排期"
GROUP_DONE = "已完成"

_ALL_FILTERS = ["全部", "今日", "本周", "已逾期", "已完成"]


# ── 工具函数 ──────────────────────────────────────────────────

def _item_date_str(item: TodoItem) -> str:
    """返回待办的日期文本，用于分组判断。"""
    return item.due_date or ""


def _is_overdue(due: str) -> bool:
    """判断是否已逾期（不含今天）。"""
    if not due:
        return False
    today = QDate.currentDate()
    d = QDate.fromString(due, "yyyy-MM-dd")
    if not d.isValid():
        return False
    return d < today


def _is_today(due: str) -> bool:
    if not due:
        return False
    today = QDate.currentDate()
    d = QDate.fromString(due, "yyyy-MM-dd")
    return d.isValid() and d == today


def _is_this_week(due: str) -> bool:
    if not due:
        return False
    today = QDate.currentDate()
    d = QDate.fromString(due, "yyyy-MM-dd")
    if not d.isValid():
        return False
    return today < d <= today.addDays(7)


def _get_group(item: TodoItem) -> str:
    """根据待办项确定分组。"""
    if item.is_done:
        return GROUP_DONE
    due = _item_date_str(item)
    if _is_overdue(due):
        return GROUP_OVERDUE
    if _is_today(due):
        return GROUP_TODAY
    if _is_this_week(due):
        return GROUP_WEEK
    if due:
        return GROUP_LATER
    return GROUP_NODATE


_GROUP_ORDER = [GROUP_OVERDUE, GROUP_TODAY, GROUP_WEEK, GROUP_LATER, GROUP_NODATE, GROUP_DONE]


# ── TodoRow: 单行待办 ─────────────────────────────────────────

class TodoRow(QWidget):
    """待办事项单行 — checkbox + 优先级色点 + 标题 + 日期 + 分类标签。"""

    toggle_clicked = Signal(int)      # 点击 checkbox
    edit_requested = Signal(int)       # 双击行
    selected = Signal(int, object)     # 行被选中 (id, self)

    def __init__(self, todo: TodoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo = todo
        self._selected = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Checkbox
        self._cb = QCheckBox()
        self._cb.setChecked(self._todo.is_done)
        self._cb.setToolTip("点击切换状态")
        self._cb.setProperty("class", "todo-checkbox")
        cb_size = 18
        self._cb.setFixedSize(cb_size, cb_size)
        self._cb.stateChanged.connect(self._on_toggle)
        layout.addWidget(self._cb)

        # 优先级色点
        color = _PRIORITY_COLORS.get(self._todo.priority, _theme.TEXT)
        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background:{color};border-radius:3px;")
        layout.addWidget(dot)

        # 标题
        self._title = QLabel(self._todo.title)
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self._todo.is_done:
            self._title.setStyleSheet(f"color:{_theme.SUBTEXT0};text-decoration:line-through;")
        layout.addWidget(self._title)

        # 元信息
        self._meta_layout = QHBoxLayout()
        self._meta_layout.setSpacing(6)

        # 日期
        if self._todo.due_date:
            date_text = self._todo.due_date
            today = QDate.currentDate()
            d = QDate.fromString(self._todo.due_date, "yyyy-MM-dd")
            if self._todo.is_done:
                date_text = "已完成"
                date_color = _theme.SUBTEXT0
            elif d.isValid() and d < today:
                date_text = f"逾期 {today.daysTo(d)} 天" if today.daysTo(d) < 0 else "逾期"
                date_color = "#e64553"
            elif d.isValid() and d == today:
                date_text = "今天"
                date_color = "#df8e1d"
            else:
                date_color = _theme.SUBTEXT0
            date_lbl = QLabel(f"📅 {date_text}")
            date_lbl.setStyleSheet(f"color:{date_color};font-size:11px;")
            self._meta_layout.addWidget(date_lbl)

        # 分类 tag
        if self._todo.category:
            tag = QLabel(self._todo.category)
            tag.setStyleSheet(
                f"color:{_theme.SUBTEXT0};font-size:10px;"
                f"background:{_theme.SURFACE1};border-radius:8px;padding:1px 6px;"
            )
            self._meta_layout.addWidget(tag)

        layout.addLayout(self._meta_layout)

        # 双击编辑
        self._title.installEventFilter(self)
        self._cb.installEventFilter(self)

    def _on_toggle(self, checked: int) -> None:
        """checkbox 状态变更时发射信号。"""
        if self._todo.id is not None:
            self.toggle_clicked.emit(self._todo.id)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if self._todo.id is not None:
                self.edit_requested.emit(self._todo.id)
            return True
        return super().eventFilter(obj, event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._todo.id is not None:
            self.edit_requested.emit(self._todo.id)

    def mousePressEvent(self, event) -> None:
        """单击选中行。"""
        if self._todo.id is not None:
            self.selected.emit(self._todo.id, self)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        if selected:
            self.setStyleSheet(
                f"background:{_theme.SELECTION_BG};"
                f"border-left:3px solid {_theme.ACCENT};"
                f"padding-left:9px;"  # 12-3=9，补偿左边框占位
            )
        else:
            self.setStyleSheet("background:transparent;border-left:none;padding-left:12px;")


# ── GroupHeader: 分组标题 ─────────────────────────────────────

class GroupHeader(QWidget):
    """分组标题 — 文字 + 计数 + 可折叠。"""

    def __init__(self, name: str, count: int, collapsed: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._count = count
        self._collapsed = collapsed
        self.setFixedHeight(30)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        # 折叠箭头（Unicode 三角，轻量）
        self._arrow = QPushButton("▾" if not collapsed else "▸")
        self._arrow.setFixedSize(14, 14)
        self._arrow.setStyleSheet(
            "QPushButton{background:transparent;border:none;font-size:9px;color:%s;}"
            % _theme.OVERLAY0
        )
        self._arrow.clicked.connect(self._on_toggle)
        layout.addWidget(self._arrow)

        label = QLabel(name)
        label.setStyleSheet(
            f"font-weight:600;font-size:11px;color:{_theme.SUBTEXT0};"
        )
        layout.addWidget(label)

        count_lbl = QLabel(str(count))
        count_lbl.setFixedHeight(16)
        count_lbl.setMinimumWidth(18)
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_lbl.setStyleSheet(
            f"font-size:10px;font-weight:500;color:{_theme.FG_MUTED};"
            f"background:{_theme.SURFACE1};border-radius:8px;padding:0 6px;"
        )
        layout.addWidget(count_lbl)

        layout.addStretch()
        self._collapsed_widget = None

    def _on_toggle(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed_widget:
            self._collapsed_widget.setVisible(not self._collapsed)
        self._arrow.setText("▾" if not self._collapsed else "▸")

    def set_collapsible_target(self, widget: QWidget) -> None:
        self._collapsed_widget = widget


# ── TodoView: 主视图 ──────────────────────────────────────────

class TodoView(QWidget):
    """待办事项视图 — Todoist 风格列表。"""

    todo_changed = Signal()
    toggle_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todo_list: list[TodoItem] = []
        self._all_projects: list[Project] = []
        self._current_filter = "全部"
        self._selected_todo_id: int | None = None
        self._selected_row: TodoRow | None = None
        self._collapse_state: dict[str, bool] = {}
        self._setup_ui()

    # ── UI 构建 ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 顶部工具栏 ──
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(*VIEW_MARGINS)
        toolbar.setSpacing(6)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(160)
        self._project_combo.addItem("全部项目", None)
        self._project_combo.currentIndexChanged.connect(self._on_project_filter_changed)
        proj_label = QLabel("项目")
        proj_label.setStyleSheet(f"color:{_theme.SUBTEXT0};font-size:12px;margin-right:-2px;")
        toolbar.addWidget(proj_label)
        toolbar.addWidget(self._project_combo)

        toolbar.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setFixedHeight(28)
        self.btn_edit.setStyleSheet(
            f"QPushButton{{background:{_theme.BG_INPUT};color:{_theme.ACCENT};"
            f"border:1px solid {_theme.BORDER};border-radius:14px;padding:2px 14px;font-size:12px;}}"
            f"QPushButton:hover{{background:{_theme.BG_HOVER};border-color:{_theme.ACCENT};}}"
        )
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setFixedHeight(28)
        self.btn_delete.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_theme.RED};"
            f"border:1px solid transparent;border-radius:14px;padding:2px 14px;font-size:12px;}}"
            f"QPushButton:hover{{background:{_theme.DANGER_BG};border-color:{_theme.RED};}}"
        )
        toolbar.addWidget(self.btn_delete)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{_theme.SURFACE1};")
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        toolbar.addWidget(sep)

        self.btn_add = QPushButton("＋ 新增")
        self.btn_add.setFixedHeight(28)
        self.btn_add.setStyleSheet(
            f"QPushButton{{background:{_theme.ACCENT};color:white;"
            f"border:none;border-radius:14px;padding:2px 18px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{_theme.BLUE};}}"
        )
        self.btn_add.setToolTip("新增待办事项 (Ctrl+N)")
        toolbar.addWidget(self.btn_add)
        layout.addLayout(toolbar)

        # ── Filter tab bar ──
        self._filter_bar = QHBoxLayout()
        self._filter_bar.setContentsMargins(12, 0, 12, 0)
        self._filter_bar.setSpacing(4)
        self._filter_btns: list[QPushButton] = []
        for i, name in enumerate(_ALL_FILTERS):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setProperty("class", "filter-tab")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked, f=name: self._set_filter(f))
            self._filter_btns.append(btn)
            self._filter_bar.addWidget(btn)
        self._filter_bar.addStretch()
        layout.addLayout(self._filter_bar)

        # ── 快速添加栏 ──
        quick_bar = QHBoxLayout()
        quick_bar.setContentsMargins(12, 6, 12, 10)
        quick_bar.setSpacing(0)

        input_container = QWidget()
        input_container.setStyleSheet(
            f"background:{_theme.BG_INPUT};border:1px solid {_theme.BORDER};"
            f"border-radius:15px;"
        )
        input_container.setFixedHeight(30)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(12, 0, 4, 0)
        input_layout.setSpacing(0)

        self._quick_add = QLineEdit()
        self._quick_add.setPlaceholderText("快速添加待办…")
        self._quick_add.setClearButtonEnabled(True)
        self._quick_add.setFixedHeight(28)
        self._quick_add.setStyleSheet(
            "QLineEdit{background:transparent;border:none;font-size:13px;color:%s;}"
            % _theme.TEXT
        )
        self._quick_add.returnPressed.connect(self._on_quick_add)
        input_layout.addWidget(self._quick_add, stretch=1)

        self._btn_quick_add = QPushButton("添加")
        self._btn_quick_add.setFixedSize(48, 22)
        self._btn_quick_add.setStyleSheet(
            f"QPushButton{{background:{_theme.ACCENT};color:white;"
            f"border:none;border-radius:11px;font-size:11px;}}"
            f"QPushButton:hover{{background:{_theme.BLUE};}}"
        )
        self._btn_quick_add.clicked.connect(self._on_quick_add)
        input_layout.addWidget(self._btn_quick_add)

        quick_bar.addWidget(input_container)
        layout.addLayout(quick_bar)

        # ── 滚动列表区域 ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(0)
        self._scroll_layout.addStretch()  # 撑满空间
        self._scroll.setWidget(self._scroll_content)

        layout.addWidget(self._scroll, stretch=1)

        # ── 空状态 ──
        self._empty_label = QLabel("暂无待办事项")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color:{_theme.SUBTEXT0};font-size:14px;padding:40px;")
        self._empty_label.hide()
        self._scroll_content.layout().addWidget(self._empty_label)

    # ── Filter ────────────────────────────────────────────────

    def _set_filter(self, name: str) -> None:
        self._current_filter = name
        for btn in self._filter_btns:
            btn.setChecked(btn.text() == name)
        self._populate()

    # ── Quick Add ─────────────────────────────────────────────

    def _on_quick_add(self) -> None:
        text = self._quick_add.text().strip()
        if not text:
            return
        self._quick_add.clear()
        self.quick_add_created.emit(text, self._project_combo.currentData())

    quick_add_created = Signal(str, object)  # title, project_id

    # ── 项目筛选 ──────────────────────────────────────────────

    def set_projects(self, projects: list[Project]) -> None:
        self._all_projects = projects
        self._project_combo.blockSignals(True)
        current_id = self._project_combo.currentData()
        self._project_combo.clear()
        self._project_combo.addItem("全部项目", None)
        for p in projects:
            self._project_combo.addItem(p.name, p.id)
        if current_id is not None:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == current_id:
                    self._project_combo.setCurrentIndex(i)
                    break
        self._project_combo.blockSignals(False)

    def get_selected_project_id(self) -> int | None:
        return self._project_combo.currentData()

    def _on_project_filter_changed(self, _index: int) -> None:
        self._populate()

    # ── 数据加载 ──────────────────────────────────────────────

    def refresh(self, todo_list: list[TodoItem], projects: list[Project] | None = None) -> None:
        if projects is not None:
            self.set_projects(projects)
        self._todo_list = todo_list
        self._populate()

    def _populate(self) -> None:
        """按当前 filter + 项目筛选后渲染。"""
        # 清空滚动区域（保留 stretch + empty_label）
        self._clear_scroll()
        self._selected_todo_id = None
        self._selected_row = None

        # 项目筛选
        project_id = self._project_combo.currentData()
        filtered = self._todo_list
        if project_id is not None:
            filtered = [t for t in filtered if t.project_id == project_id]

        # Filter tab 筛选
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        if self._current_filter == "今日":
            filtered = [t for t in filtered if _is_today(_item_date_str(t))]
        elif self._current_filter == "本周":
            filtered = [t for t in filtered if _is_this_week(_item_date_str(t)) or _is_today(_item_date_str(t))]
        elif self._current_filter == "已逾期":
            filtered = [t for t in filtered if _is_overdue(_item_date_str(t))]
        elif self._current_filter == "已完成":
            filtered = [t for t in filtered if t.is_done]

        # 分组
        groups: dict[str, list[TodoItem]] = {g: [] for g in _GROUP_ORDER}
        for item in filtered:
            g = _get_group(item)
            groups[g].append(item)

        # 渲染
        has_items = False
        collapse_state = self._collapse_state

        for group_name in _GROUP_ORDER:
            items = groups.get(group_name, [])
            if not items:
                continue
            if self._current_filter != "全部":
                # 在 filter 模式下，不显示分组标题，直接列出
                for item in items:
                    self._add_row(item)
                    has_items = True
                continue

            has_items = True
            # Group header
            collapsed = collapse_state.get(group_name, False)
            header = GroupHeader(group_name, len(items), collapsed)
            self._scroll_layout.insertWidget(
                self._scroll_layout.count() - 1, header
            )
            # Group items container
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            for item in items:
                row_w = TodoRow(item)
                row_w.toggle_clicked.connect(self._on_row_toggle)
                row_w.edit_requested.connect(self._on_row_edit)
                row_w.selected.connect(self._on_row_selected)
                container_layout.addWidget(row_w)
            if collapsed:
                container.hide()
            header.set_collapsible_target(container)
            self._scroll_layout.insertWidget(
                self._scroll_layout.count() - 1, container
            )
            # 保存折叠状态
            hdr_state = collapse_state
            hdr_name = group_name
            original_toggle = header._on_toggle
            def _new_toggle(h=header, name=hdr_name, state=hdr_state):
                h._collapsed = not h._collapsed
                if h._collapsed_widget:
                    h._collapsed_widget.setVisible(not h._collapsed)
                h._arrow.setText("▾" if not h._collapsed else "▸")
                state[name] = h._collapsed
            header._on_toggle = _new_toggle

        if not has_items:
            self._empty_label.show()

    def _clear_scroll(self) -> None:
        """清空所有行（保留 stretch 和 empty_label）。"""
        self._empty_label.hide()
        layout = self._scroll_layout
        # 移除除最后两个（stretch + empty_label）以外的所有项
        for i in reversed(range(layout.count() - 2)):
            item = layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()

    def _add_row(self, todo: TodoItem) -> None:
        """在非分组模式（filter 已应用）下添加单行。"""
        row = TodoRow(todo)
        row.toggle_clicked.connect(self._on_row_toggle)
        row.edit_requested.connect(self._on_row_edit)
        row.selected.connect(self._on_row_selected)
        self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, row)

    def _on_row_toggle(self, todo_id: int) -> None:
        self.toggle_requested.emit(todo_id)

    def _on_row_edit(self, todo_id: int) -> None:
        self.btn_edit.click()

    def _on_row_selected(self, todo_id: int, row: TodoRow) -> None:
        """选中一行，取消之前的选中。"""
        if self._selected_row and self._selected_row is not row:
            self._selected_row.set_selected(False)
        row.set_selected(True)
        self._selected_row = row
        self._selected_todo_id = todo_id

    # ── 选中支持 ──────────────────────────────────────────────

    def get_selected_todo(self) -> TodoItem | None:
        """获取当前选中的待办。"""
        tid = self._selected_todo_id
        if tid is None:
            return None
        for t in self._todo_list:
            if t.id == tid:
                return t
        return None

    # ── 信号 ──────────────────────────────────────────────────

    def emit_todo_changed(self) -> None:
        self.todo_changed.emit()
