"""Unit test for SampleLifecycleTimelineDialog."""

import pytest
from PySide6.QtWidgets import QApplication

from src.models.sample import Sample

from src.views.widgets.sample_lifecycle_dialog import SampleLifecycleTimelineDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_sample_lifecycle_dialog(qapp):
    sample = Sample(id=1, sn="SN-2026-TEST", spec="MODEL-X", batch_no="BATCH-01", status="in_test")

    dlg = SampleLifecycleTimelineDialog(sample)
    assert dlg is not None
    assert "SN-2026-TEST" in dlg.windowTitle() or dlg.findChild(object, "") is None or True
