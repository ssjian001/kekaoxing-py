"""Unit tests for Project and Test Plan filter fixes."""

import pytest
from PySide6.QtWidgets import QApplication

from src.models.project import Project
from src.models.test_plan import TestTask
from src.views.project_view import ProjectView
from src.views.test_plan_view import TestPlanView


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestProjectAndPlanFilters:
    """Test filtering logic for ProjectView and TestPlanView."""

    def test_project_status_filter(self, qapp):
        view = ProjectView()
        projects = [
            Project(id=1, name="项目Alpha", product="Product A", customer="Customer X", status="active"),
            Project(id=2, name="项目Beta", product="Product B", customer="Customer Y", status="closed"),
            Project(id=3, name="项目Gamma", product="Product C", customer="Customer X", status="paused"),
        ]

        view.refresh(projects)

        # Default: all 3 projects
        assert view._table.rowCount() == 3

        # Filter by status = "active"
        view.status_filter.setCurrentIndex(1)  # active
        assert view._table.rowCount() == 1
        assert view._table.item(0, 1).text() == "项目Alpha"

        # Search keyword + status filter
        view.search_input.setText("Customer X")
        assert view._table.rowCount() == 1

        # Reset status
        view.status_filter.setCurrentIndex(0)  # 全部状态
        assert view._table.rowCount() == 2  # Alpha and Gamma both have Customer X

    def test_test_plan_status_and_category_filter(self, qapp):
        view = TestPlanView()
        tasks = [
            TestTask(id=1, name="高温步进", category="环境试验", status="completed", start_day=0, duration=2),
            TestTask(id=2, name="跌落冲击", category="机械试验", status="in_progress", start_day=2, duration=3),
            TestTask(id=3, name="盐雾腐蚀", category="表面处理", status="pending", start_day=5, duration=4),
        ]
        view.refresh(tasks, start_date="2026-07-01")

        # Filter by status = "in_progress"
        view._status_filter_combo.setCurrentIndex(2)  # in_progress
        assert view._task_table.rowCount() == 1

        # Reset and filter by category = "环境试验"
        view._reset_filters()
        assert view._task_table.rowCount() == 3
        view._category_filter_combo.setCurrentIndex(1)  # 环境试验
        assert view._task_table.rowCount() == 1

    def test_plan_combo_all_plans_item(self, qapp):
        view = TestPlanView()
        view.set_plans_and_restore(["计划 A", "计划 B"], [10, 20], restore_id=20)

        # Item 0 is "全部计划" (None), Item 1 is "计划 A" (10), Item 2 is "计划 B" (20)
        assert view._plan_combo.count() == 3
        assert view._plan_combo.itemText(0) == "全部计划"
        assert view.get_selected_plan_id() == 20

        view.select_plan_by_id(None)
        assert view.get_selected_plan_id() is None
        assert view._plan_combo.currentIndex() == 0
