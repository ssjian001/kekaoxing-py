"""Unit test for EquipmentLoadHeatmapWidget."""

import pytest
from PySide6.QtWidgets import QApplication

from src.models.common import Equipment
from src.views.widgets.equipment_heatmap_widget import EquipmentLoadHeatmapWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_equipment_heatmap_widget(qapp):
    heatmap = EquipmentLoadHeatmapWidget()
    equipments = [
        Equipment(id=1, asset_no="EQ-001", name="高温步进试验箱", status="in_use"),
        Equipment(id=2, asset_no="EQ-002", name="恒温恒湿箱", status="normal"),
        Equipment(id=3, asset_no="EQ-003", name="振动试验台", status="maintenance"),
    ]

    heatmap.refresh(equipments)
    assert len(heatmap._canvas._items) == 3
    assert "高温步进" in heatmap._canvas._items[0][0]
