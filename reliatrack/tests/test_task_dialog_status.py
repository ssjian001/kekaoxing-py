"""回归: 编辑"枚举外状态"任务时状态不得被静默降级 (审计 P1-6)。

旧行为: _find_status_label 对枚举外状态回落"待开始", get_data 用
status_map.get(text, "pending") 回写 —— 打开一个 failed / 历史 done 任务、
不改任何东西直接确定, 状态就被写库降级为 pending, 与任务表显示不一致。
"""

import pytest
from PySide6.QtWidgets import QApplication

from src.models.test_plan import TestTask
from src.views.dialogs.task_dialog import TaskEditDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _task(status: str) -> TestTask:
    return TestTask(
        id=7, plan_id=1, name="状态回归任务", category="机械试验",
        duration=1, start_day=0, status=status, progress=0.0,
    )


def _dialog(status: str) -> TaskEditDialog:
    return TaskEditDialog(
        task=_task(status), equipment_list=[], technician_list=[],
        all_tasks=[],
    )


class TestLegacyStatusNotDowngraded:
    @pytest.mark.parametrize("status", ["failed", "done", "fail", "cancelled"])
    def test_out_of_enum_status_passthrough(self, qapp, status):
        """打开枚举外状态任务, 不做任何修改直接保存 → 原值必须原样写回。"""
        dlg = _dialog(status)
        assert dlg.get_data()["status"] == status, f"{status} 被静默降级"

    def test_placeholder_item_is_selected(self, qapp):
        """下拉必须显示原状态(带不可改标记), 而不是回落"待开始"。"""
        dlg = _dialog("failed")
        text = dlg._status_combo.currentText()
        assert "待开始" not in text
        assert "不可改" in text

    @pytest.mark.parametrize("status,label", [
        ("pending", "待开始"),
        ("in_progress", "进行中"),
        ("completed", "已完成"),
        ("skipped", "已跳过"),
    ])
    def test_enum_status_roundtrip(self, qapp, status, label):
        """枚举内状态: 显示标签与写回值都不变(不能引入回归)。"""
        dlg = _dialog(status)
        assert dlg._status_combo.currentText() == label
        assert dlg.get_data()["status"] == status

    def test_user_can_still_change_legacy_status(self, qapp):
        """占位项不影响正常改状态: 用户主动选择后按新值写回。"""
        dlg = _dialog("failed")
        dlg._status_combo.setCurrentText("已完成")
        assert dlg.get_data()["status"] == "completed"

    def test_new_task_defaults_to_pending(self, qapp):
        """新建模式不受占位逻辑影响。"""
        dlg = TaskEditDialog(equipment_list=[], technician_list=[], all_tasks=[])
        assert dlg.get_data()["status"] == "pending"
