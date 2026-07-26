"""Unit test for ColumnVisibilityMenu."""

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget

from src.views.widgets.column_visibility_menu import ColumnVisibilityMenu, create_column_visibility_button


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_column_visibility_menu(qapp):
    table = QTableWidget(2, 3)
    table.setHorizontalHeaderLabels(["列A", "列B", "列C"])

    menu = ColumnVisibilityMenu(table, "test_table")
    assert menu is not None
    assert len(menu.actions()) == 3

    btn = create_column_visibility_button(table, "test_table")
    assert btn is not None
