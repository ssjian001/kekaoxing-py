"""Bug Tracker 快捷键注册 / Ctrl+K 快捷搜索。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QWidget, QLabel, QApplication, QTextEdit,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShortcut, QKeySequence

from src.models.issue import Issue
from src.styles.constants import *


def register_bug_tracker_shortcuts(parent: QWidget, handler: ShortcutHandler) -> dict[str, QShortcut]:
    """注册快捷键，返回 shortcut 字典供 focus guard 管理。"""
    s_c = QShortcut(QKeySequence("c"), parent)
    s_c.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    s_c.activated.connect(handler.on_quick_create)

    s_ctrl_n = QShortcut(QKeySequence("Ctrl+N"), parent)
    s_ctrl_n.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    s_ctrl_n.activated.connect(handler.on_quick_create)

    s_ctrl_k = QShortcut(QKeySequence("Ctrl+K"), parent)
    s_ctrl_k.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    s_ctrl_k.activated.connect(handler.on_quick_search)

    s_slash = QShortcut(QKeySequence("/"), parent)
    s_slash.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    s_slash.activated.connect(handler.on_focus_search)

    # 看板左右箭头切换列（仅在非输入控件聚焦时生效）
    s_left = QShortcut(QKeySequence(Qt.Key.Key_Left), parent)
    s_left.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    s_left.activated.connect(lambda: handler.on_navigate_column(-1))

    s_right = QShortcut(QKeySequence(Qt.Key.Key_Right), parent)
    s_right.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    s_right.activated.connect(lambda: handler.on_navigate_column(1))

    return {
        "c": s_c,
        "ctrl_n": s_ctrl_n,
        "ctrl_k": s_ctrl_k,
        "slash": s_slash,
        "left": s_left,
        "right": s_right,
    }


def install_shortcut_focus_guard(
    shortcuts: dict[str, QShortcut],
    parent: QWidget,
) -> None:
    """监控焦点变化，文本输入框聚焦时禁用单字符/方向快捷键。"""
    _single_char_keys = {"c", "left", "right"}  # / 和 Ctrl+ 组合键不需要保护

    def _on_focus_changed(obj: QWidget | None) -> None:
        is_input = isinstance(obj, (QLineEdit, QTextEdit))
        for key in _single_char_keys:
            sc = shortcuts.get(key)
            if sc is not None:
                try:
                    sc.setEnabled(not is_input)
                except RuntimeError:
                    pass  # 关闭过程中 C++ 对象已删除，忽略

    app = QApplication.instance()
    if app is not None:
        app.focusObjectChanged.connect(_on_focus_changed)


class ShortcutHandler:
    """快捷键回调集合 — 由 BugTrackerView 持有。"""

    def __init__(self) -> None:
        self.on_quick_create = lambda: None
        self.on_quick_search = lambda: None
        self.on_focus_search = lambda: None
        self.on_navigate_column = lambda direction: None


class QuickSearchDialog(QDialog):
    """Ctrl+K 快捷搜索 — 模糊搜索 Issue 标题/ID。"""

    issue_selected = Signal(int)  # emit issue_id

    def __init__(self, issues: list[Issue], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("搜索 Issue")
        self.setFixedSize(500, 380)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._issues = issues
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索 Issue #ID 或标题… (↑↓选择, Enter打开, Esc关闭)")
        layout.addWidget(self._search_input)

        self._result_list = QListWidget()
        self._result_list.setMaximumHeight(320)
        layout.addWidget(self._result_list)

        self._search_input.textChanged.connect(self._filter_results)
        self._result_list.itemDoubleClicked.connect(self._on_activate)
        self._result_list.activated.connect(self._on_activate)

        self._filter_results("")
        self._search_input.setFocus()

        # Enter 打开选中
        self._search_input.returnPressed.connect(self._on_enter)

    def _filter_results(self, text: str) -> None:
        self._result_list.clear()
        q = text.strip().lower()
        if not q:
            # 显示全部按时间倒序
            for issue in sorted(self._issues, key=lambda i: i.created_at or "", reverse=True)[:30]:
                self._add_item(issue)
            return

        # 按 #ID 或标题搜索
        for issue in self._issues:
            if str(issue.id) == q or q in issue.title.lower() or (issue.description and q in issue.description.lower()):
                self._add_item(issue)

        if self._result_list.count() == 0:
            item = QListWidgetItem("无匹配结果")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._result_list.addItem(item)

    def _add_item(self, issue: Issue) -> None:
        sev_mark = {"critical": "【严重】", "major": "【主要】", "minor": "【次要】", "cosmetic": "【外观】"}.get(issue.severity, "")
        text = f"#{issue.id}  {sev_mark}{issue.title}"
        text += f"  ({issue.status})"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, issue.id)
        self._result_list.addItem(item)

    def _on_enter(self) -> None:
        item = self._result_list.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole):
            self._on_activate(item)

    def _on_activate(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        issue_id = item.data(Qt.ItemDataRole.UserRole)
        if issue_id:
            self.issue_selected.emit(issue_id)
            self.close()
        self.close()
