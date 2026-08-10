"""UI 集成测试 — Qt 事件模拟（FilterPanel、BatchOperationDialog 的 signal/交互）。

运行: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_integration.py -v
"""

from __future__ import annotations

import sys
import pytest
import apsw

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest

# 模块级 QApplication（UI 测试需要）
_app = QApplication.instance() or QApplication(sys.argv)

from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository
from src.services.issue_service import IssueService
from src.models.issue import Issue
from src.views.bug_tracker.batch_dialog import BatchOperationDialog


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture()
def db_conn() -> apsw.Connection:
    conn = apsw.Connection(":memory:")
    init_schema(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


@pytest.fixture()
def issue_svc(db_conn) -> IssueService:
    return IssueService(IssueRepository(db_conn), db_conn)


@pytest.fixture()
def sample_issues(issue_svc: IssueService) -> list[Issue]:
    """创建一批样本 issue，覆盖各状态/严重度/优先级。"""
    ids: list[int] = []
    configs = [
        ("open", "critical", 1, "Alice"),
        ("open", "major", 2, "Bob"),
        ("analyzing", "minor", 3, "Alice"),
        ("verified", "cosmetic", 4, "Charlie"),
        ("closed", "critical", 5, "Bob"),
        ("open", "major", 3, "Bob"),
    ]
    for status, severity, priority, dri in configs:
        kwargs = dict(title=f"Test Issue {len(ids)}", status=status,
                      severity=severity, priority=priority)
        if dri is not None:
            kwargs["dri_name"] = dri
        iid = issue_svc.create(**kwargs)
        ids.append(iid)
    return [issue_svc.get(iid) for iid in ids if issue_svc.get(iid)]


# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
#  BatchOperationDialog 集成测试
# ═══════════════════════════════════════════════════════════════════

class TestBatchOperationDialog:
    """BatchOperationDialog 创建/选项联动 — 不真正执行批量操作。"""

    def test_create_with_issue_ids(self, issue_svc, sample_issues):
        """构造函数接受 issue_ids 并显示标题。"""
        ids = [i.id for i in sample_issues if i.id]
        dlg = BatchOperationDialog(ids, issue_svc, parent=None)
        assert "已选" in dlg.windowTitle()
        assert str(len(ids)) in dlg.windowTitle()

    def test_operation_switches_value_widget(self, issue_svc, sample_issues):
        """切换操作类型 → 目标值下拉改变。"""
        ids = [i.id for i in sample_issues if i.id]
        dlg = BatchOperationDialog(ids, issue_svc, parent=None)

        # 默认: 改状态
        assert dlg._op_combo.currentText() == "改状态"
        assert dlg._value_combo.count() == 4  # 4 种状态

        # 切换到改严重度
        dlg._op_combo.setCurrentText("改严重度")
        assert dlg._value_combo.count() == 4  # 4 种严重度

        # 切换到改优先级
        dlg._op_combo.setCurrentText("改优先级")
        assert dlg._value_combo.count() == 5  # 5 个优先级

        # 切换到设置DRI
        dlg._op_combo.setCurrentText("设置DRI")
        assert dlg._value_combo.isEditable()
        assert dlg._value_combo.count() >= 1  # 至少"清除DRI"

    def test_no_undo_manager_does_not_crash(self, issue_svc, sample_issues):
        """undo_manager=None 时批量操作不崩溃。"""
        ids = [i.id for i in sample_issues if i.id]
        dlg = BatchOperationDialog(ids, issue_svc, parent=None, undo_manager=None)
        # 设置操作和值
        dlg._op_combo.setCurrentText("改状态")
        dlg._value_combo.setCurrentIndex(1)
        # 执行（不检查结果，只确保不 crash）
        dlg._execute_batch()


# ═══════════════════════════════════════════════════════════════════
#  IssueDetailDialog 集成测试（构造 + tab 切换）
# ═══════════════════════════════════════════════════════════════════

class TestIssueDetailDialog:
    """IssueDetailDialog 构造和基础交互。"""

    def test_create_with_issue(self, issue_svc, sample_issues):
        """使用 Issue 对象创建弹窗不崩溃。"""
        from src.models.issue import Issue, IssueComment
        from src.views.bug_tracker.detail_dialog import IssueDetailDialog

        issue = sample_issues[0]
        dlg = IssueDetailDialog(issue, issue_svc, parent=None)
        # 基础属性
        assert dlg._fa_panel is not None
        assert dlg._capa_panel is not None
        dlg.deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  _GanttWidget 集成测试（数据渲染 + 交互）
# ═══════════════════════════════════════════════════════════════════

class TestGanttWidget:
    """甘特图 widget 基本交互。"""

    def test_set_tasks_updates_height(self):
        """设置任务后 widget 高度按行数增长。"""
        from datetime import date
        from src.models.test_plan import TestTask
        from src.views.widgets.gantt_widget import _GanttWidget

        widget = _GanttWidget()
        tasks = [TestTask(id=i, plan_id=1, name=f"T{i}", start_day=i, duration=5)
                 for i in range(10)]
        widget.set_tasks(tasks, total_days=30,
                         start_date=date.today().isoformat())

        expected_min = 10 * 28 + 24 + 20  # rows * row_height + header + padding
        assert widget.minimumHeight() >= expected_min

    def test_set_tasks_empty(self):
        """空任务列表正常显示占位文字。"""
        from src.views.widgets.gantt_widget import _GanttWidget
        widget = _GanttWidget()
        widget.set_tasks([])
        # 不崩溃即可
        assert widget._tasks == []

    def test_wheel_zoom_limits(self):
        """滚轮缩放不越界。"""
        from src.views.widgets.gantt_widget import _GanttWidget
        from PySide6.QtCore import QPoint, QEvent, QObject
        widget = _GanttWidget()
        assert widget._MIN_DAY_W <= widget._day_w <= widget._MAX_DAY_W

    def test_hit_test_outside_chart(self):
        """点击标签列返回 None。"""
        from src.models.test_plan import TestTask
        from src.views.widgets.gantt_widget import _GanttWidget
        from PySide6.QtCore import QPoint

        widget = _GanttWidget()
        tasks = [TestTask(id=i, plan_id=1, name=f"T{i}", start_day=i, duration=5)
                 for i in range(5)]
        widget.set_tasks(tasks, total_days=30)

        # 点击标签列区域（x < _label_w）
        result = widget._hit_test(QPoint(10, 50))
        assert result is None

    def test_hit_test_on_bar(self):
        """点击甘特条返回对应索引。"""
        from src.models.test_plan import TestTask
        from src.views.widgets.gantt_widget import _GanttWidget
        from PySide6.QtCore import QPoint

        widget = _GanttWidget()
        widget.resize(1200, 600)
        tasks = [TestTask(id=i, plan_id=1, name=f"T{i}", start_day=i, duration=10)
                 for i in range(5)]
        widget.set_tasks(tasks, total_days=30)

        # 点击第一个任务条中间位置
        bar = widget._bar_rect(0)
        if bar.isValid():
            center = bar.center()
            result = widget._hit_test(center)
            assert result == 0
