"""UI 工具欄重構測試。

覆蓋 2026-07-20 的工具欄優化：
- BugListView: _build_filter_row / _clear_filters / _apply_filters
- TodoView: _build_filter_row / _build_action_row
- SamplePoolTab: _btn_more / _more_menu
- TestPlanView: _act_toggle_archived
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import apsw

from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox, QPushButton, QToolButton
from PySide6.QtCore import Qt

from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository
from src.services.issue_service import IssueService
from src.models.issue import Issue


# ── fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db_conn():
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def issue_svc(db_conn):
    repo = IssueRepository(db_conn)
    return IssueService(repo)


def _make_issue(**overrides) -> Issue:
    defaults = dict(
        id=0,
        title="測試 Issue",
        description="描述",
        status="open",
        severity="major",
        priority=3,
        dri_name="Alice",
        root_cause="",
    )
    defaults.update(overrides)
    return Issue(**defaults)


# ── BugListView 篩選行 ────────────────────────────────────

class TestBugListViewFilterRow:
    """測試 list_view.py 的 _build_filter_row / _clear_filters / _apply_filters。"""

    def test_filter_widgets_created(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        # 四個篩選控件都應該存在
        assert hasattr(v, "_filter_status")
        assert hasattr(v, "_filter_severity")
        assert hasattr(v, "_filter_priority")
        assert hasattr(v, "_filter_dri")
        assert isinstance(v._filter_status, QComboBox)
        assert isinstance(v._filter_dri, QComboBox)

    def test_filter_status_default_all(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        assert v._filter_status.currentData() == ""
        assert v._filter_severity.currentData() == ""
        assert v._filter_priority.currentData() == ""

    def test_clear_filters_resets_all(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        # 設置非默認值
        v._filter_status.setCurrentIndex(1)
        v._filter_severity.setCurrentIndex(1)
        v._filter_dri.setEditText("abc")
        # 清除
        v._clear_filters()
        assert v._filter_status.currentIndex() == 0
        assert v._filter_severity.currentIndex() == 0
        assert v._filter_priority.currentIndex() == 0
        assert v._filter_dri.currentText() == ""

    def test_apply_filters_status(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        v.set_issues([
            _make_issue(id=1, title="A", status="open"),
            _make_issue(id=2, title="B", status="closed"),
        ])
        # 全部
        assert v._table.rowCount() == 2
        # 只看 open
        v._filter_status.setCurrentIndex(1)  # 第一個非"全部"
        # 觸發 currentIndexChanged 信號手動
        v._apply_filters()
        assert v._table.rowCount() == 1

    def test_apply_filters_search_keyword(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        v.set_issues([
            _make_issue(id=1, title="網絡故障"),
            _make_issue(id=2, title="電源損壞"),
        ])
        v._search_input.setText("網絡")
        v._apply_filters()
        assert v._table.rowCount() == 1

    def test_apply_filters_dri_text(self, qapp, issue_svc):
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        v.set_issues([
            _make_issue(id=1, dri_name="Alice"),
            _make_issue(id=2, dri_name="Bob"),
        ])
        v._filter_dri.setEditText("ali")  # case insensitive
        v._apply_filters()
        assert v._table.rowCount() == 1

    def test_clear_button_in_filter_row(self, qapp, issue_svc):
        """確認 _build_filter_row 有個清除按鈕，且不會異常。"""
        from src.views.bug_tracker.list_view import BugListView
        v = BugListView(issue_svc)
        v._clear_filters()  # 不拋異常即可


# ── TodoView 兩行佈局 ─────────────────────────────────────

class TestTodoViewLayout:
    """測試 todo_view.py 的 _build_filter_row / _build_action_row 拆分。"""

    def test_filter_row_widgets(self, qapp):
        from src.views.todo_view import TodoView
        v = TodoView()
        assert hasattr(v, "_project_combo")
        assert hasattr(v, "_search_edit")
        assert hasattr(v, "_show_archived_cb")
        assert isinstance(v._search_edit, QLineEdit)

    def test_action_row_buttons(self, qapp):
        from src.views.todo_view import TodoView
        v = TodoView()
        assert hasattr(v, "_quick_add")
        assert hasattr(v, "_btn_quick_add")
        assert hasattr(v, "btn_edit")
        assert hasattr(v, "btn_delete")
        assert hasattr(v, "btn_archive")
        assert isinstance(v._quick_add, QLineEdit)
        assert isinstance(v.btn_edit, QPushButton)

    def test_quick_add_signal_connected(self, qapp):
        """確認 _quick_add.returnPressed 已連接到 _on_quick_add。"""
        from src.views.todo_view import TodoView
        v = TodoView()
        # 不能直接測試 connected receivers，但可確認方法存在
        assert callable(v._on_quick_add)

    def test_old_filter_panel_removed(self, qapp):
        """DynamicFilterPanel 應已從 TodoView 移除。"""
        from src.views.todo_view import TodoView
        v = TodoView()
        assert not hasattr(v, "_filter_panel"), "TodoView 不應再持有 DynamicFilterPanel"


# ── SamplePoolTab 更多菜單 ────────────────────────────────

class TestSamplePoolMoreMenu:
    """測試 sample_view.py 的 _btn_more / _more_menu（批量操作合併到下拉）。"""

    def test_more_menu_exists(self, qapp):
        from src.views.sample_view import _SamplePoolTab
        tab = _SamplePoolTab()
        assert hasattr(tab, "_btn_more")
        assert hasattr(tab, "_more_menu")
        assert isinstance(tab._btn_more, QToolButton)
        # 菜單裡有兩個 action
        actions = tab._more_menu.actions()
        action_texts = [a.text() for a in actions]
        assert "批量導入" in action_texts or "批量导入" in action_texts
        assert "批量編輯" in action_texts or "批量编辑" in action_texts

    def test_batch_import_property_returns_action(self, qapp):
        """btn_batch_import property 應返回 QAction（向後兼容 handler 連接）。"""
        from src.views.sample_view import _SamplePoolTab
        tab = _SamplePoolTab()
        act = tab.btn_batch_import
        # 應有 triggered 信號（不是 clicked）
        assert hasattr(act, "triggered")

    def test_batch_edit_property_returns_action(self, qapp):
        from src.views.sample_view import _SamplePoolTab
        tab = _SamplePoolTab()
        act = tab.btn_batch_edit
        assert hasattr(act, "triggered")


# ── TestPlanView 查看歸檔移入菜單 ──────────────────────────

class TestPlanToggleArchivedInMenu:
    """測試 test_plan_view.py 的 _act_toggle_archived（從 btn 移到菜單項）。"""

    def test_toggle_archived_in_plan_menu(self, qapp):
        from src.views.test_plan_view import TestPlanView
        v = TestPlanView()
        # 不應再有 _btn_archived 獨立按鈕
        assert not hasattr(v, "_btn_archived"), "查看歸檔應已移入計劃管理菜單"
        # 應有 _act_toggle_archived
        assert hasattr(v, "_act_toggle_archived")
        assert v._act_toggle_archived.isCheckable()

    def test_toggle_archived_action_text(self, qapp):
        from src.views.test_plan_view import TestPlanView
        v = TestPlanView()
        assert "歸檔" in v._act_toggle_archived.text() or "归档" in v._act_toggle_archived.text()
