"""Unit tests for advanced Gantt features in gantt_widget.py and plan_gantt_tab.py."""

import json
import pytest
from PySide6.QtWidgets import QApplication

from src.models.test_plan import TestTask
from src.views.widgets.gantt_widget import _GanttWidget
from src.views.widgets.plan_gantt_tab import PlanGanttTab


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_tasks():
    t1 = TestTask(
        id=1,
        plan_id=10,
        name="跌落前测试",
        category="机械试验",
        start_day=0,
        duration=2,
        equipment_id=100,
        progress=100.0,
        status="completed",
    )
    t2 = TestTask(
        id=2,
        plan_id=10,
        name="跌落试验",
        category="机械试验",
        start_day=2,
        duration=3,
        equipment_id=200,
        dependencies="[1]",  # Depends on Task 1
        progress=50.0,
        status="in_progress",
    )
    # Task 3: Conflict with Task 2 on Equipment 200 at start_day=3 (overlaps days 2..5)
    t3 = TestTask(
        id=3,
        plan_id=10,
        name="震动冲击试验",
        category="机械试验",
        start_day=3,
        duration=4,
        equipment_id=200,  # Equipment conflict with t2
        dependencies="[]",
        progress=0.0,
        status="pending",
    )
    # Task 4: Dependency conflict with Task 1 (starts at D1, but Task 1 finishes at D2)
    t4 = TestTask(
        id=4,
        plan_id=10,
        name="高温老化试验",
        category="环境试验",
        start_day=1,
        duration=5,
        equipment_id=300,
        dependencies="[1]",  # Dep conflict!
        progress=0.0,
        status="pending",
    )
    return [t1, t2, t3, t4]


class TestGanttAdvancedFeatures:
    """Test Gantt chart conflict detection, dependency parsing, and critical path calculation."""

    def test_parse_dependencies(self):
        t = TestTask(dependencies='[10, "20", "invalid"]')
        deps = _GanttWidget._get_task_dep_ids(t)
        assert deps == [10, 20]

    def test_conflict_detection(self, qapp, sample_tasks):
        gantt = _GanttWidget()
        gantt.set_tasks(sample_tasks, total_days=20)
        gantt.set_render_options(show_conflicts=True, show_critical_path=True)

        conflicts, dep_pairs, critical_ids = gantt._detect_conflicts_and_critical_path()

        # Task 2 & Task 3 have equipment conflict on Equipment 200
        assert 2 in conflicts
        assert 3 in conflicts

        # Task 4 has dependency conflict with Task 1 (starts D1 < Task 1 end D2)
        assert 4 in conflicts
        assert (1, 4) in dep_pairs

        # Critical path task ID should include Task 3 (start D3 + dur 4 = finish D7, maximum finish time)
        assert 3 in critical_ids


    def test_gantt_tab_options_toggle(self, qapp, sample_tasks):
        tab = PlanGanttTab()
        tab.gantt.set_tasks(sample_tasks)

        # Verify default toggle states
        assert tab._btn_deps.isChecked() is True
        assert tab._btn_conflicts.isChecked() is True
        assert tab._btn_critical.isChecked() is False

        # Toggle critical path
        tab._btn_critical.setChecked(True)
        assert tab.gantt._show_critical_path is True

        # Toggle conflicts off
        tab._btn_conflicts.setChecked(False)
        assert tab.gantt._show_conflicts is False
