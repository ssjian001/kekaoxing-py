"""Unit test for SearchHistoryChips and chart quick copy/export."""

import pytest
from PySide6.QtWidgets import QApplication

from src.views.widgets.search_history_chips import SearchHistoryChips
from src.views.widgets.dashboard_charts import _DonutChart


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_search_history_chips(qapp):
    chips = SearchHistoryChips("test")
    chips.clear_history()

    chips.save_keyword("高温步进")
    chips.save_keyword("盐雾腐蚀")

    assert chips.isHidden() is False

    chips.clear_history()
    assert chips.isHidden() is True


def test_chart_copy_to_clipboard(qapp):
    chart = _DonutChart()
    chart.setData({"completed": 10, "pending": 5})
    chart.copy_to_clipboard()

    clipboard = qapp.clipboard()
    assert not clipboard.pixmap().isNull()
