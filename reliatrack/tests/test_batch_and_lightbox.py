"""Unit test for LightboxViewerDialog and BatchActionBar."""

import pytest
from PySide6.QtWidgets import QApplication

from src.views.widgets.lightbox_viewer_dialog import LightboxViewerDialog
from src.views.widgets.batch_action_bar import BatchActionBar


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_batch_action_bar_visibility(qapp):
    bar = BatchActionBar()
    assert bar.isHidden()

    # Selecting 2 items
    bar.update_selection_count(2)
    assert bar._selected_count == 2

    # Clear items
    bar.update_selection_count(0)
    assert bar._selected_count == 0


def test_lightbox_viewer_init(qapp, tmp_path):
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"dummy")

    dlg = LightboxViewerDialog(str(img_file))
    assert dlg._file_path == str(img_file)
