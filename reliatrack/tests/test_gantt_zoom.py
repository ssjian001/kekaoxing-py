"""Unit test for Gantt chart timeline zoomer and view switcher."""

import pytest
from PySide6.QtWidgets import QApplication

from src.views.widgets.gantt_widget import _GanttWidget
from src.views.widgets.plan_gantt_tab import PlanGanttTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_gantt_widget_zoom(qapp):
    widget = _GanttWidget()
    assert widget._day_w == 30.0

    widget.set_day_width(60.0)
    assert widget._day_w == 60.0

    # Minimum bound check
    widget.set_day_width(1.0)
    assert widget._day_w == widget._MIN_DAY_W


def test_plan_gantt_tab_view_mode(qapp):
    tab = PlanGanttTab()
    assert tab._zoom_slider.value() == 30

    tab._view_mode_combo.setCurrentIndex(1)  # 周视图 (12px)
    assert tab._zoom_slider.value() == 12
    assert tab._gantt._day_w == 12.0
