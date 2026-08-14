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


def test_batch_action_bar_status_options_populate_menu(qapp):
    """set_status_options 填充批量变更状态菜单。"""
    bar = BatchActionBar()
    bar.set_status_options([("已完成", "completed"), ("进行中", "in_progress")])
    assert len(bar._status_menu.actions()) == 2
    assert bar._status_menu.actions()[0].text() == "已完成"


def test_batch_action_bar_technician_options_populate_menu(qapp):
    """set_technician_options 填充批量指派技术员菜单（2026-08-14 修复空菜单）。"""
    bar = BatchActionBar()
    bar.set_technician_options([("陈工", 1), ("李工", 2)])
    assert len(bar._tech_menu.actions()) == 2
    assert bar._tech_menu.actions()[0].text() == "陈工"


def test_lightbox_viewer_init(qapp, tmp_path):
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"dummy")

    dlg = LightboxViewerDialog(str(img_file))
    assert dlg._file_path == str(img_file)
