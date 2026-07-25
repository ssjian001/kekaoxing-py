"""测试 Ctrl+K 全局 CommandPaletteDialog 组件。"""

import sys
import pytest
from PySide6.QtWidgets import QApplication
from src.views.dialogs.command_palette_dialog import CommandPaletteDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_command_palette_dialog_filtering(qapp):
    """测试命令面板的列表筛选功能。"""
    sample_data = [
        {"category": "项目", "category_key": "project", "id": 1, "name": "5G手机高温测试", "detail": "PRJ-001"},
        {"category": "设备", "category_key": "equipment", "id": 2, "name": "恒温恒湿箱 A1", "detail": "TH-01"},
    ]

    def dummy_fetcher(query: str):
        if not query:
            return sample_data
        return [item for item in sample_data if query.lower() in item["name"].lower()]

    dialog = CommandPaletteDialog(fetcher=dummy_fetcher)

    # 初始状态：包含 2 条数据
    assert dialog._list_widget.count() == 2

    # 搜索 "高温"
    dialog._search_input.setText("高温")
    assert dialog._list_widget.count() == 1
    assert "5G手机高温测试" in dialog._list_widget.item(0).text()

    # 搜索不存在项
    dialog._search_input.setText("不存在的项目")
    assert dialog._list_widget.count() == 1
    assert "未找到相关数据" in dialog._list_widget.item(0).text()
