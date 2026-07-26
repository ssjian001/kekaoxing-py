"""Unit test for CommandPaletteDialog (Spotlight command palette)."""

import pytest
from PySide6.QtWidgets import QApplication

from src.views.widgets.command_palette_dialog import CommandPaletteDialog, CommandItem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_command_palette_dialog_filter(qapp):
    dialog = CommandPaletteDialog()
    assert len(dialog._items) > 0

    # Search for "8D"
    dialog._search_input.setText("8D")
    assert len(dialog._filtered_items) >= 1
    assert "8D" in dialog._filtered_items[0].title

    # Search for non-existing string
    dialog._search_input.setText("xyz_not_exist_999")
    assert len(dialog._filtered_items) == 0

    # Reset search
    dialog._search_input.setText("")
    assert len(dialog._filtered_items) == len(dialog._items)
