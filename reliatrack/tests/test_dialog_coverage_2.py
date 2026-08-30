"""补充第二批低覆盖 Dialog 测试。

目标模块（覆盖率提升目标 40%+）：
- src/views/dialogs/task_dialog.py            (7%  → 构造/编辑预填/预计日期三向联动/
                                                    get_data/accept 校验/依赖与样品选择)
- src/views/dialogs/test_result_dialog.py     (10% → _ResultRow 行逻辑/统计/批量操作/环境预填)
- src/views/dialogs/schedule_preview_dialog.py (11% → 日期换算辅助/表格填充/冲突检测/
                                                    get_changes/on_apply 分支)
- src/views/dialogs/attachment_dialog.py      (14% → 大小格式化/加载/添加/删除/双击打开)

约定与 test_dialog_coverage.py 保持一致：QApplication session fixture、
offscreen 平台、monkeypatch QMessageBox/QFileDialog/QDialog.exec 防止模态阻塞、
临时目录承载附件复制。service 依赖使用 :memory: apsw + init_schema 构造真依赖。

跳过的路径（必须在模态 exec 内才能测）：
- SchedulePreviewDialog._on_cell_double_click 的 Accepted 分支（内部 dlg.exec()
  弹出 _StartDayEditDialog）——改为直接测 _StartDayEditDialog 本体。
- TaskEditDialog._open_dep_selector 内部搜索过滤分支——搜索框为函数局部变量，
  无法在不弹窗的情况下触达（列表填充逻辑已通过 exec 补丁覆盖主路径）。
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import pytest
import apsw

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QDate, Qt

from src.db.schema import init_schema
from src.models.common import Equipment, Technician
from src.models.sample import Sample
from src.models.test_plan import TestTask, TestResult


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ═══════════════════════════════════════════════════════════════════
#  TaskEditDialog
# ═══════════════════════════════════════════════════════════════════

def _make_task(**kw) -> TestTask:
    defaults = dict(
        id=1, plan_id=1, name="高温老化", category="环境试验",
        test_standard="GB/T 2423.3", duration=3, start_day=2,
        progress=40.0, status="in_progress", priority=4,
        environment='{"temp":"85C"}', temperature="-40~85C",
        humidity="85%RH", accept_criteria="C=0",
        sample_ids='[11]', dependencies='[2]',
        notes="原备注", log_file="/tmp/a.log",
        actual_start_date="2026-01-06", actual_end_date="2026-01-08",
    )
    defaults.update(kw)
    return TestTask(**defaults)


class TestTaskEditDialog:
    """任务编辑弹窗 — 构造 / 预填 / 联动 / get_data / accept 校验。"""

    # ── 构造 ──

    def test_create_mode_no_plan_date(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog()
        assert dlg.windowTitle() == "新建测试任务"
        # 无计划开始日期 → 预计日期控件禁用并提示
        assert not dlg._planned_start_edit.isEnabled()
        assert not dlg._planned_end_edit.isEnabled()
        assert "请先" in dlg._planned_hint.text()

    def test_create_mode_with_plan_date(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="2026-01-05")
        assert dlg._planned_start_edit.isEnabled()
        assert dlg._planned_start_edit.date() == QDate(2026, 1, 5)
        # 新任务 start_day=0, duration=1 → end = base
        assert dlg._planned_end_edit.date() == QDate(2026, 1, 5)

    def test_create_mode_invalid_plan_date(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="not-a-date")
        assert not dlg._planned_start_edit.isEnabled()
        assert "无效" in dlg._planned_hint.text()

    def test_edit_mode_prefill(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        task = _make_task()
        equips = [Equipment(id=7, name="温箱-01"), Equipment(id=9, name="振动台")]
        techs = [Technician(id=5, name="张工")]
        dlg = TaskEditDialog(
            task=task, equipment_list=equips, technician_list=techs,
            plan_start_date="2026-01-05",
        )
        assert dlg.windowTitle() == "编辑测试任务"
        assert dlg._name_edit.text() == "高温老化"
        assert dlg._temp_edit.text() == "-40~85C"
        assert dlg._humidity_edit.text() == "85%RH"
        assert dlg._log_file_edit.text() == "/tmp/a.log"
        # 已选样品/依赖从 JSON 解析
        assert dlg._selected_sample_ids == [11]
        assert dlg._selected_dep_ids == [2]
        # 实际日期已填 → 未设置 checkbox 未勾选
        assert not dlg._actual_start_unset.isChecked()
        assert dlg._actual_start_edit.isEnabled()
        assert dlg._actual_start_edit.date() == QDate(2026, 1, 6)

    def test_edit_mode_corrupt_json(self, qapp):
        """sample_ids/dependencies 为非法 JSON 或非 list 时应回退为空。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        task = _make_task(sample_ids="not-json", dependencies='{"a":1}')
        dlg = TaskEditDialog(task=task)
        assert dlg._selected_sample_ids == []
        assert dlg._selected_dep_ids == []

    def test_edit_mode_all_tasks_exclude_self(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        t1 = _make_task(id=1)
        t2 = _make_task(id=2, name="低温试验")
        dlg = TaskEditDialog(task=t1, all_tasks=[t1, t2])
        assert [t.id for t in dlg._all_tasks] == [2]

    # ── get_data ──

    def test_get_data_create_mode(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="2026-01-05")
        dlg._name_edit.setText("新任务")
        dlg._env_edit.setText('{"humidity":"60%RH"}')
        data = dlg.get_data()
        assert data["name"] == "新任务"
        assert data["duration"] == 1
        assert data["priority"] == 3
        assert data["status"] == "pending"
        assert data["progress"] == 0.0
        assert data["sample_ids"] == "[]"
        assert data["dependencies"] == "[]"
        assert data["equipment_id"] is None
        assert data["technician_id"] is None
        # 实际日期未设置 → 空串
        assert data["actual_start_date"] == ""
        assert data["actual_end_date"] == ""
        # 计划有起始日期 → start_day=0 且 manual_scheduled=1
        assert data["start_day"] == 0
        assert data["manual_scheduled"] == 1
        assert data["environment"] == '{"humidity":"60%RH"}'

    def test_get_data_edit_roundtrip(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        task = _make_task(equipment_id=7, technician_id=5)
        dlg = TaskEditDialog(
            task=task,
            equipment_list=[Equipment(id=7, name="温箱-01")],
            technician_list=[Technician(id=5, name="张工")],
        )
        # 预填的设备/技术员标签应解析回 ID
        assert dlg._equipment_combo.currentText() == "7 — 温箱-01"
        assert dlg._technician_combo.currentText() == "5 — 张工"
        data = dlg.get_data()
        assert data["equipment_id"] == 7
        assert data["technician_id"] == 5
        assert data["status"] == "in_progress"
        assert data["progress"] == 40.0
        assert json.loads(data["sample_ids"]) == [11]
        assert json.loads(data["dependencies"]) == [2]
        assert data["temperature"] == "-40~85C"
        assert data["humidity"] == "85%RH"
        assert data["accept_criteria"] == "C=0"
        assert data["notes"] == "原备注"
        assert data["log_file"] == "/tmp/a.log"
        assert data["actual_start_date"] == "2026-01-06"
        assert data["actual_end_date"] == "2026-01-08"

    def test_get_data_equip_tech_labels(self, qapp):
        """设备/技术员组合框文本解析："（无）"与非法文本 → None。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(
            equipment_list=[Equipment(id=7, name="温箱-01")],
            technician_list=[Technician(id=5, name="张工")],
        )
        dlg._equipment_combo.setCurrentText("（无）")
        dlg._technician_combo.setCurrentText("garbage")
        data = dlg.get_data()
        assert data["equipment_id"] is None
        assert data["technician_id"] is None

    def test_get_data_status_mapping(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog()
        dlg._name_edit.setText("X")
        dlg._status_combo.setCurrentText("已完成")
        assert dlg.get_data()["status"] == "completed"
        dlg._status_combo.setCurrentText("已跳过")
        assert dlg.get_data()["status"] == "skipped"

    # ── 预计日期三向联动 ──

    def test_planned_end_change_updates_duration(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="2026-01-05")
        dlg._planned_end_edit.setDate(QDate(2026, 1, 14))  # start+9 → 10 天
        assert dlg._duration_spin.value() == 10

    def test_planned_start_change_extends_end(self, qapp):
        """预计开始晚于预计结束 → 结束自动拉齐并提示。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="2026-01-05")
        dlg._planned_start_edit.setDate(QDate(2026, 1, 8))
        assert dlg._planned_end_edit.date() == QDate(2026, 1, 8)
        assert "自动调整" in dlg._planned_hint.text()

    def test_planned_start_change_recalc_duration(self, qapp):
        """开始日期前移（结束不变）→ 工期重算。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="2026-01-05")
        dlg._planned_end_edit.setDate(QDate(2026, 1, 14))   # 工期 10
        dlg._planned_start_edit.setDate(QDate(2026, 1, 7))  # 1/7~1/14 → 8 天
        assert dlg._duration_spin.value() == 8
        assert dlg._planned_end_edit.date() == QDate(2026, 1, 14)

    def test_duration_change_updates_planned_end(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(plan_start_date="2026-01-05")
        dlg._duration_spin.setValue(5)
        assert dlg._planned_end_edit.date() == QDate(2026, 1, 9)

    def test_duration_change_no_plan_date_noop(self, qapp):
        """无计划开始日期时改工期不应崩溃也不改日期。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog()
        dlg._duration_spin.setValue(5)
        assert not dlg._planned_start_edit.isEnabled()

    # ── 测试类型模板自动填充 ──

    def test_test_type_template_autofill_create(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        from src.configs.test_type_templates import get_template_names, get_template_by_name
        name = get_template_names()[1]
        tpl = get_template_by_name(name)
        dlg = TaskEditDialog()
        dlg._test_type_combo.setCurrentText(name)
        assert dlg._name_edit.text() == tpl.name
        assert dlg._category_combo.currentText() == tpl.category
        assert dlg._standard_edit.text() == tpl.test_standard
        assert dlg._duration_spin.value() == tpl.duration
        assert dlg._temp_edit.text() == tpl.temperature
        assert dlg._humidity_edit.text() == tpl.humidity
        if tpl.accept_criteria:
            assert tpl.accept_criteria in dlg._criteria_edit.text()

    def test_test_type_custom_noop(self, qapp):
        """切回"（自定义）"不应改动任何字段。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog()
        dlg._name_edit.setText("手动填写")
        dlg._test_type_combo.setCurrentText("（自定义）")
        assert dlg._name_edit.text() == "手动填写"

    def test_test_type_edit_mode_keeps_name(self, qapp):
        """编辑模式下已有名称不被模板覆盖。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        from src.configs.test_type_templates import get_template_names
        dlg = TaskEditDialog(task=_make_task(id=1))
        dlg._test_type_combo.setCurrentText(get_template_names()[1])
        assert dlg._name_edit.text() == "高温老化"

    # ── 样品 / 依赖选择 ──

    def test_format_sample_count(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        samples = [Sample(id=i, sn=f"SN-{i:03d}") for i in range(1, 8)]
        dlg = TaskEditDialog(sample_list=samples)
        assert dlg._sample_count_label.text() == "未选择（共 7 个可选）"
        dlg._selected_sample_ids = [1, 2]
        dlg._sample_count_label.setText(dlg._format_sample_count())
        assert dlg._sample_count_label.text() == "已选 2 个: SN-001, SN-002"
        dlg._selected_sample_ids = list(range(1, 8))
        dlg._sample_count_label.setText(dlg._format_sample_count())
        text = dlg._sample_count_label.text()
        assert text.startswith("已选 7 个:")
        assert "等 7 个" in text

    def test_open_sample_select_accepted(self, qapp, monkeypatch):
        """弹窗 exec 被 monkeypatch 为 Accepted — 验证预选回读与标签刷新。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        samples = [Sample(id=11, sn="SN-011"), Sample(id=12, sn="SN-012")]
        dlg = TaskEditDialog(sample_list=samples)
        dlg._selected_sample_ids = [11]
        monkeypatch.setattr(
            QDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )
        dlg._open_sample_select()
        assert dlg._selected_sample_ids == [11]
        assert "SN-011" in dlg._sample_count_label.text()

    def test_open_sample_select_rejected(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(sample_list=[Sample(id=11, sn="SN-011")])
        dlg._selected_sample_ids = [11]
        monkeypatch.setattr(
            QDialog, "exec", lambda self: QDialog.DialogCode.Rejected,
        )
        dlg._open_sample_select()
        assert dlg._selected_sample_ids == [11]

    def test_open_dep_selector_accepted(self, qapp, monkeypatch):
        """依赖选择弹窗 exec 补丁 — 预选依赖保持，摘要刷新。"""
        from src.views.dialogs.task_dialog import TaskEditDialog
        tasks = [_make_task(id=i, name=f"任务{i}") for i in (1, 2, 3)]
        dlg = TaskEditDialog(task=_make_task(id=10), all_tasks=tasks)
        dlg._selected_dep_ids = [2]
        monkeypatch.setattr(
            QDialog, "exec", lambda self: QDialog.DialogCode.Accepted,
        )
        dlg._open_dep_selector()
        assert dlg._selected_dep_ids == [2]
        assert "#2 任务2" in dlg._dep_summary.text()

    def test_open_dep_selector_rejected(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog(task=_make_task(id=10),
                             all_tasks=[_make_task(id=2)])
        dlg._selected_dep_ids = [2]
        monkeypatch.setattr(
            QDialog, "exec", lambda self: QDialog.DialogCode.Rejected,
        )
        dlg._open_dep_selector()
        assert dlg._selected_dep_ids == [2]

    def test_format_dep_summary_unknown_id(self, qapp):
        from src.views.dialogs.task_dialog import TaskEditDialog
        dlg = TaskEditDialog()
        dlg._selected_dep_ids = [99]
        assert dlg._format_dep_summary() == "#99 ?"
        dlg._selected_dep_ids = []
        assert dlg._format_dep_summary() == "（无）"

    # ── 测试日志浏览 ──

    def test_browse_log_file(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        from PySide6.QtWidgets import QFileDialog
        dlg = TaskEditDialog()
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **kw: ("/tmp/run.log", "")),
        )
        dlg._browse_log_file()
        assert dlg._log_file_edit.text() == "/tmp/run.log"

    def test_browse_log_file_cancel(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        from PySide6.QtWidgets import QFileDialog
        dlg = TaskEditDialog()
        dlg._log_file_edit.setText("/keep.log")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **kw: ("", "")),
        )
        dlg._browse_log_file()
        assert dlg._log_file_edit.text() == "/keep.log"

    # ── accept() 校验分支 ──

    def test_accept_valid(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        warnings = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: warnings.append(a),
        )
        dlg = TaskEditDialog()
        dlg._name_edit.setText("合法任务")
        dlg.accept()
        assert not warnings
        assert dlg.result() == QDialog.DialogCode.Accepted

    def test_accept_missing_name(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        warnings = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: warnings.append(a[2]),
        )
        dlg = TaskEditDialog()
        dlg._name_edit.setText("   ")
        dlg.accept()
        assert len(warnings) == 1
        assert "必填" in warnings[0]
        assert dlg.result() != QDialog.DialogCode.Accepted

    def test_accept_self_dependency(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        warnings = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: warnings.append(a[2]),
        )
        task = _make_task(id=1, dependencies="[1]")
        dlg = TaskEditDialog(task=task)
        dlg.accept()
        assert any("依赖自身" in w for w in warnings)
        assert dlg.result() != QDialog.DialogCode.Accepted

    def test_accept_invalid_dependency(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        warnings = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: warnings.append(a[2]),
        )
        task = _make_task(id=1, dependencies="[999]")
        dlg = TaskEditDialog(task=task, all_tasks=[_make_task(id=2)])
        dlg.accept()
        assert any("999" in w for w in warnings)
        assert dlg.result() != QDialog.DialogCode.Accepted

    def test_accept_bad_env_json(self, qapp, monkeypatch):
        from src.views.dialogs.task_dialog import TaskEditDialog
        warnings = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: warnings.append(a[2]),
        )
        dlg = TaskEditDialog()
        dlg._name_edit.setText("X")
        dlg._env_edit.setText("{not-json")
        dlg.accept()
        assert any("JSON" in w for w in warnings)
        assert dlg.result() != QDialog.DialogCode.Accepted


# ═══════════════════════════════════════════════════════════════════
#  TestResultDialog / _ResultRow
# ═══════════════════════════════════════════════════════════════════

def _make_row(sample=None, existing=None, techs=None, on_change=None):
    from src.views.dialogs.test_result_dialog import _ResultRow
    return _ResultRow(sample, existing, technician_list=techs,
                      on_change=on_change)


class TestResultRow:
    """单行结果录入控件。"""

    def test_row_with_sample_and_existing(self, qapp):
        s = Sample(id=11, sn="SN-011", batch_no="B1", spec="SPX")
        existing = TestResult(
            id=5, task_id=1, sample_id=11, result="fail",
            test_date="2026-01-10", tester_id=3,
            environment='{"temperature":"85C","humidity":"85%RH"}',
            notes="引脚氧化", measured_value="0.8V",
        )
        row = _make_row(s, existing, techs=[Technician(id=3, name="张工")])
        assert row.result_id == 5
        assert "SN-011" in row._sample_lbl.text()
        assert "B1" in row._sample_lbl.text()
        data = row.get_data()
        assert data["sample_id"] == 11
        assert data["result"] == "fail"
        assert data["test_date"] == "2026-01-10"
        assert data["notes"] == "引脚氧化"
        assert data["measured_value"] == "0.8V"
        assert json.loads(data["environment"]) == {
            "temperature": "85C", "humidity": "85%RH",
        }
        assert data["tester_id"] == 3
        assert data["result_id"] == 5
        assert data["deleted"] is False

    def test_row_env_corrupt_json(self, qapp):
        existing = TestResult(id=5, task_id=1, sample_id=11,
                              environment="not-json")
        row = _make_row(Sample(id=11, sn="S"), existing)
        assert row.get_env_values() == ("", "")

    def test_row_no_sample(self, qapp):
        row = _make_row(None)
        assert "整体结论" in row._sample_lbl.text()
        data = row.get_data()
        assert data["sample_id"] is None
        assert data["sample_name"] == ""

    def test_row_needs_attention_cleared(self, qapp):
        """新增行初始 needs_attention，选非 pending 结果后清除。

        注：结果下拉默认选中第一项 pass（RESULT_OPTIONS[0]），因此改回
        pass 不触发信号，用 conditional 验证清除逻辑。
        """
        row = _make_row(Sample(id=1, sn="S1"))
        assert row._needs_attention is True
        row._combo.setCurrentIndex(row._combo.findData("conditional"))
        assert row._needs_attention is False
        assert row.get_data()["result"] == "conditional"

    def test_row_fail_auto_checks_issue(self, qapp):
        """初始非 fail → 设为 fail 自动勾选「创建Issue」；已勾选不重复触发。"""
        row = _make_row(Sample(id=1, sn="S1"))
        assert not row._create_issue_cb.isChecked()
        row._combo.setCurrentIndex(row._combo.findData("fail"))
        assert row._create_issue_cb.isChecked()
        # 取消后再次切到 fail（initial 已记录为 None）→ 仍勾选
        row._create_issue_cb.setChecked(False)
        row._combo.setCurrentIndex(row._combo.findData("conditional"))
        row._combo.setCurrentIndex(row._combo.findData("fail"))
        assert row._create_issue_cb.isChecked()

    def test_row_toggle_delete(self, qapp):
        calls = []
        row = _make_row(Sample(id=1, sn="S1"), on_change=lambda: calls.append(1))
        row._on_toggle_delete()
        assert row._deleted is True
        assert row._toggle_btn.text() == "撤销"
        assert not row._combo.isEnabled()
        assert not row._notes_edit.isEnabled()
        assert row.get_data()["deleted"] is True
        assert len(calls) == 1
        row._on_toggle_delete()
        assert row._deleted is False
        assert row._toggle_btn.text() == "删除"
        assert row._combo.isEnabled()

    def test_row_set_env_if_empty(self, qapp):
        row = _make_row(Sample(id=1, sn="S1"))
        row.set_env_if_empty("85C", "85%RH")
        assert row.get_env_values() == ("85C", "85%RH")
        # 已有值不覆盖
        row.set_env_if_empty("60C", "30%RH")
        assert row.get_env_values() == ("85C", "85%RH")
        # 空源不覆盖
        row2 = _make_row(Sample(id=2, sn="S2"))
        row2.set_env_if_empty("", "")
        assert row2.get_env_values() == ("", "")

    def test_row_refresh_theme(self, qapp):
        row = _make_row(Sample(id=1, sn="S1"))
        row.refresh_theme()  # 不抛异常即可
        assert row._indicator.styleSheet()  # 指示器有背景色


class TestResultDialog:
    """结果录入容器 — 行构建 / 统计 / 批量操作。"""

    def _dialog(self, samples, existing=None, task_kw=None):
        from src.views.dialogs.test_result_dialog import TestResultDialog
        task = TestTask(id=1, name="高温老化", accept_criteria="C=0",
                        temperature="85C", humidity="85%RH", **(task_kw or {}))
        return TestResultDialog(task=task, samples=samples,
                                existing_results=existing,
                                technician_list=[Technician(id=3, name="张工")])

    def test_with_samples_prefills_env(self, qapp):
        samples = [Sample(id=1, sn="SN-001"), Sample(id=2, sn="SN-002")]
        dlg = self._dialog(samples)
        assert len(dlg._rows) == 2
        assert dlg._has_samples is True
        # 未录入的行从 task 预填温湿度
        for row in dlg._rows:
            assert row.get_env_values() == ("85C", "85%RH")
        # 统计行（结果下拉默认选中 pass → 初始统计为通过）
        text = dlg._stats_label.text()
        assert "共 2 个样品" in text
        assert "通过 2" in text

    def test_existing_results_map(self, qapp):
        samples = [Sample(id=1, sn="SN-001"), Sample(id=2, sn="SN-002")]
        existing = [TestResult(id=9, task_id=1, sample_id=1, result="fail")]
        dlg = self._dialog(samples, existing)
        assert dlg._rows[0].result_id == 9
        assert dlg._rows[0].get_data()["result"] == "fail"
        # 未录入行回退到下拉默认项 pass
        assert dlg._rows[1].result_id is None
        assert dlg._rows[1].get_data()["result"] == "pass"
        assert "不通过 1" in dlg._stats_label.text()
        assert "通过 1" in dlg._stats_label.text()

    def test_no_samples_overall_row(self, qapp):
        dlg = self._dialog([])
        assert len(dlg._rows) == 1
        assert dlg._rows[0]._sample is None
        assert dlg._has_samples is False
        assert "整体结果" in dlg._stats_label.text()

    def test_pass_all_fail_all(self, qapp):
        samples = [Sample(id=1, sn="S1"), Sample(id=2, sn="S2")]
        dlg = self._dialog(samples)
        # 初始即 pass → _pass_all 无变化，先 fail 全部
        dlg._pass_all()
        assert "全部通过" in dlg._btn_pass_all.text()
        dlg._fail_all()
        assert all(r.get_data()["result"] == "fail" for r in dlg._rows)
        assert "全部不通过 (2)" in dlg._btn_fail_all.text()
        dlg._pass_all()
        assert all(r.get_data()["result"] == "pass" for r in dlg._rows)
        assert "全部通过 (2)" in dlg._btn_pass_all.text()
        # 再点一次无变化 → 计数不变
        dlg._pass_all()
        assert "全部通过 (2)" in dlg._btn_pass_all.text()
        # 注：源码中 _on_result_changed 不回调 on_change（仅删除切换回
        # 调），批量按钮后统计标签不自动刷新 — 显式调 _update_stats
        # 验证其计数逻辑本身。
        dlg._update_stats()
        assert "通过 2" in dlg._stats_label.text()

    def test_apply_env_to_all_from_task(self, qapp):
        samples = [Sample(id=1, sn="S1"), Sample(id=2, sn="S2")]
        dlg = self._dialog(samples)
        dlg._rows[0]._temp_edit.setText("")  # 清空一行再统一应用
        dlg._rows[0]._humidity_edit.setText("")
        dlg._apply_env_to_all()
        assert dlg._rows[0].get_env_values() == ("85C", "85%RH")
        assert "已应用 (1)" in dlg._btn_apply_env.text()

    def test_apply_env_to_all_fallback_first_row(self, qapp):
        """task 无默认温湿度 → 回退到首个非空行。"""
        from src.views.dialogs.test_result_dialog import TestResultDialog
        task = TestTask(id=1, name="T")
        samples = [Sample(id=1, sn="S1"), Sample(id=2, sn="S2")]
        dlg = TestResultDialog(task=task, samples=samples)
        dlg._rows[0]._temp_edit.setText("60C")
        dlg._rows[0]._humidity_edit.setText("40%RH")
        dlg._apply_env_to_all()
        assert dlg._rows[1].get_env_values() == ("60C", "40%RH")

    def test_stats_exclude_deleted(self, qapp):
        samples = [Sample(id=1, sn="S1"), Sample(id=2, sn="S2")]
        dlg = self._dialog(samples)
        dlg._pass_all()
        dlg._rows[0]._on_toggle_delete()
        text = dlg._stats_label.text()
        assert "共 1 个样品" in text
        assert "已标记删除 1" in text
        # 全部删除 → 统计清空
        dlg._rows[1]._on_toggle_delete()
        assert dlg._stats_label.text() == ""

    def test_get_all_data(self, qapp):
        samples = [Sample(id=1, sn="S1"), Sample(id=2, sn="S2")]
        dlg = self._dialog(samples)
        all_data = dlg.get_all_data()
        assert [d["sample_id"] for d in all_data] == [1, 2]
        assert all(d["create_issue"] is False for d in all_data)


# ═══════════════════════════════════════════════════════════════════
#  SchedulePreviewDialog
# ═══════════════════════════════════════════════════════════════════

CFG = {"skip_weekends": False, "skip_holidays": False, "lock_existing": False}


def _make_preview(tasks, original=None, report=None, equipment=None,
                  config=None):
    from src.views.dialogs.schedule_preview_dialog import SchedulePreviewDialog
    data = {
        "start_date": "2026-01-05",
        "tasks": tasks,
        "original_start_days": original or {},
        "report": report or {},
        "equipment": equipment or [],
    }
    return SchedulePreviewDialog(data, config or dict(CFG))


class TestScheduleHelpers:
    """模块级日期换算辅助函数。"""

    def test_day_to_date(self):
        from src.views.dialogs.schedule_preview_dialog import (
            _day_to_date,
        )
        assert _day_to_date("2026-01-05", 0) == "—"
        assert _day_to_date("2026-01-05", 2) == "2026-01-07"
        assert _day_to_date("", 3) == "—"
        assert _day_to_date("bad", 3) == "—"

    def test_day_label(self):
        from src.views.dialogs.schedule_preview_dialog import _day_label
        assert _day_label("2026-01-05", 0) == "未排"
        assert _day_label("2026-01-05", 1) == "Day 1 (2026-01-06)"


class TestSchedulePreviewDialog:
    """排程预览对话框 — 表格填充 / 冲突检测 / 变更导出。"""

    def test_construct_and_fill(self, qapp):
        from src.views.dialogs.schedule_preview_dialog import (
            SchedulePreviewDialog,
        )
        tasks = [
            TestTask(id=1, name="高温", duration=3, start_day=1,
                     equipment_id=1, status="pending"),
            TestTask(id=2, name="低温", duration=2, start_day=5,
                     equipment_id=1, status="pending"),
        ]
        dlg = _make_preview(
            tasks,
            original={1: 1, 2: 2},
            report={"total_days": 10, "original_days": 12,
                    "improvement": 16.7, "task_count": 2,
                    "updated_count": 2, "skipped_cycle_tasks": ["T9"]},
            equipment=[Equipment(id=1, name="温箱A")],
            config={**CFG, "skip_weekends": True, "deadline": "2026-02-01"},
        )
        assert dlg.windowTitle() == "排程预览"
        assert dlg._table.rowCount() == 2
        assert dlg._table.item(0, SchedulePreviewDialog._COL_NAME).text() == "高温"
        assert dlg._table.item(0, SchedulePreviewDialog._COL_EQUIPMENT).text() == "温箱A"
        # 行0：old day=1、new start_day=1 → 未变化；行1：old 2 → new 5
        assert "Day 1 (2026-01-06)" in dlg._table.item(0, 3).text()
        assert "Day 1 (2026-01-06)" in dlg._table.item(0, 4).text()
        assert dlg._table.item(0, 5).text() == "—"
        assert "Day 2 (2026-01-07)" in dlg._table.item(1, 3).text()
        assert "Day 5 (2026-01-10)" in dlg._table.item(1, 4).text()
        assert dlg._table.item(1, 5).text() == "+3天"
        # 无冲突初始 + 参数提示
        assert dlg._table.item(0, 6).text() == "无冲突"
        assert "跳过周末" in dlg._build_params_label().text()
        assert "截止 2026-02-01" in dlg._build_params_label().text()

    def test_params_label_variants(self, qapp):
        tasks = [TestTask(id=1, name="T", duration=1, start_day=1)]
        # CFG 无开关 → 无特殊参数
        dlg = _make_preview(tasks)
        assert dlg._build_params_label().text() == "无特殊参数"
        # 全开关 + 截止日期
        dlg2 = _make_preview(tasks, config={
            **CFG, "skip_weekends": True, "skip_holidays": True,
            "lock_existing": True, "deadline": "2026-03-01",
        })
        text = dlg2._build_params_label().text()
        for part in ("跳过周末", "跳过节假日", "锁定已有排期", "截止 2026-03-01"):
            assert part in text

    def test_detect_equipment_conflict(self, qapp):
        tasks = [
            TestTask(id=1, name="A", duration=5, start_day=1, equipment_id=1),
            TestTask(id=2, name="B", duration=3, start_day=2, equipment_id=1),
        ]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1")])
        assert dlg._has_conflicts is True
        texts = [dlg._table.item(r, 6).text() for r in range(2)]
        assert all("! 设备冲突" == t for t in texts)

    def test_detect_dependency_conflict(self, qapp):
        tasks = [
            TestTask(id=1, name="A", duration=5, start_day=1, equipment_id=1),
            TestTask(id=2, name="B", duration=2, start_day=2,
                     equipment_id=2, dependencies="[1]"),
        ]
        dlg = _make_preview(tasks, equipment=[
            Equipment(id=1, name="E1"), Equipment(id=2, name="E2")])
        # B 依赖 A 且 B.start_day(2) < A 工作日结束(6) → 依赖冲突；A 无冲突
        assert dlg._table.item(0, 6).text() == "无冲突"
        assert dlg._table.item(1, 6).text() == "! 依赖冲突"
        assert dlg._has_conflicts is True

    def test_detect_start_limit_and_tech_conflict(self, qapp):
        tasks = [
            TestTask(id=1, name="A", duration=2, start_day=1,
                     equipment_id=1, technician_id=7),
            TestTask(id=2, name="B", duration=2, start_day=1,
                     equipment_id=2, technician_id=7),
        ]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1"),
                                              Equipment(id=2, name="E2")],
                            config={**CFG, "daily_start_limit": 1})
        # 同日启动 2 个 > 上限 1；同一技术员并行 2 > 容量 1
        for r in range(2):
            text = dlg._table.item(r, 6).text()
            assert text in ("! 启动数超限", "! 技术员冲突")
        assert dlg._has_conflicts is True

    def test_detect_non_working_day(self, qapp):
        # 2026-01-05 是周一 → day 5 = 周六
        tasks = [TestTask(id=1, name="A", duration=1, start_day=5,
                          equipment_id=1)]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1")],
                            config={**CFG, "skip_weekends": True})
        assert dlg._table.item(0, 6).text() == "! 非工作日"

    def test_completed_task_excluded(self, qapp):
        tasks = [
            TestTask(id=1, name="done", duration=2, start_day=1,
                     equipment_id=1, status="completed"),
            TestTask(id=2, name="B", duration=2, start_day=1,
                     equipment_id=1),
        ]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1")])
        # 已完成行置灰禁用，不参与冲突检测
        assert not (dlg._table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEnabled)
        assert dlg._table.item(0, 6).text() == "无冲突"
        assert dlg._table.item(1, 6).text() == "无冲突"
        assert dlg._has_conflicts is False

    def test_get_changes_and_locked_days(self, qapp):
        tasks = [
            TestTask(id=1, name="A", duration=2, start_day=3),
            TestTask(id=2, name="B", duration=2, start_day=2, status="completed"),
        ]
        dlg = _make_preview(tasks, original={1: 1, 2: 2})
        # B 已完成、无变化的任务不导出
        assert dlg.get_changes() == [(1, 3)]
        assert dlg.get_user_locked_days() == {}
        # 手动改 start_day 后 _update_row 刷新显示
        tasks[0].start_day = 6
        dlg._update_row(0)
        assert "Day 6 (2026-01-11)" in dlg._table.item(0, 4).text()
        assert dlg._table.item(0, 5).text() == "+5天"
        dlg._user_locked_days[1] = 6
        assert dlg.get_user_locked_days() == {1: 6}
        assert dlg.get_changes() == [(1, 6)]

    def test_update_row_no_change(self, qapp):
        tasks = [TestTask(id=1, name="A", duration=2, start_day=1)]
        dlg = _make_preview(tasks, original={1: 1})
        tasks[0].start_day = 1
        dlg._update_row(0)
        assert dlg._table.item(0, 5).text() == "—"

    # ── on_apply / on_reschedule ──

    def test_on_apply_no_conflict_accepts(self, qapp):
        tasks = [TestTask(id=1, name="A", duration=1, start_day=1,
                          equipment_id=1)]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1")])
        dlg._on_apply()
        assert dlg.result() == QDialog.DialogCode.Accepted

    def test_on_apply_conflict_user_rejects(self, qapp, monkeypatch):
        import src.views.dialogs.schedule_preview_dialog as m
        tasks = [
            TestTask(id=1, name="A", duration=5, start_day=1, equipment_id=1),
            TestTask(id=2, name="B", duration=3, start_day=2, equipment_id=1),
        ]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1")])
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **kw: m.QMessageBox.StandardButton.No,
        )
        dlg._on_apply()
        assert dlg.result() != QDialog.DialogCode.Accepted

    def test_on_apply_conflict_user_confirms(self, qapp, monkeypatch):
        import src.views.dialogs.schedule_preview_dialog as m
        tasks = [
            TestTask(id=1, name="A", duration=5, start_day=1, equipment_id=1),
            TestTask(id=2, name="B", duration=3, start_day=2, equipment_id=1),
        ]
        dlg = _make_preview(tasks, equipment=[Equipment(id=1, name="E1")])
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **kw: m.QMessageBox.StandardButton.Yes,
        )
        dlg._on_apply()
        assert dlg.result() == QDialog.DialogCode.Accepted

    def test_on_reschedule_done_2(self, qapp):
        tasks = [TestTask(id=1, name="A", duration=1, start_day=1)]
        dlg = _make_preview(tasks)
        dlg._on_reschedule()
        assert dlg.result() == 2

    def test_double_click_completed_noop(self, qapp):
        """已完成行双击直接返回，不弹编辑框。"""
        tasks = [TestTask(id=1, name="A", duration=1, start_day=1,
                          status="completed")]
        dlg = _make_preview(tasks)
        dlg._on_cell_double_click(0, 4)
        dlg._on_cell_double_click(99, 0)  # 越界
        assert dlg.get_user_locked_days() == {}


class TestStartDayEditDialog:
    """start_day 手动编辑小弹窗。"""

    def test_construct_and_change(self, qapp):
        from src.views.dialogs.schedule_preview_dialog import _StartDayEditDialog
        dlg = _StartDayEditDialog("高温老化", 3, "2026-01-05")
        assert "高温老化" in dlg.windowTitle()
        assert dlg.get_start_day() == 3
        assert "Day 3 (2026-01-08)" in dlg._date_preview.text()
        dlg._spin.setValue(7)
        assert dlg.get_start_day() == 7
        assert "Day 7 (2026-01-12)" in dlg._date_preview.text()
        assert "Day 0" not in dlg._date_preview.text()


# ═══════════════════════════════════════════════════════════════════
#  AttachmentDialog
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def issue_svc(db_conn):
    from src.db.repositories.issue_repo import IssueRepository
    from src.services.issue_service import IssueService
    svc = IssueService(IssueRepository(db_conn), db_conn)
    issue_id = svc.create(title="附件测试Issue", severity="critical")
    return svc, issue_id


class TestAttachmentHelpers:
    def test_format_file_size(self):
        from src.views.dialogs.attachment_dialog import _format_file_size
        assert _format_file_size(512) == "512 B"
        assert _format_file_size(2048) == "2.0 KB"
        assert _format_file_size(5 * 1024 * 1024) == "5.0 MB"
        assert _format_file_size(2 * 1024 * 1024 * 1024) == "2.0 GB"


class TestAttachmentDialog:
    """附件管理弹窗 — 加载 / 添加 / 删除 / 双击打开。"""

    def test_construct_empty(self, qapp, issue_svc):
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        svc, issue_id = issue_svc
        dlg = AttachmentDialog(issue_id, svc)
        assert dlg.windowTitle() == "管理附件"
        assert dlg._list_widget.count() == 0
        assert not dlg._btn_delete.isEnabled()
        assert dlg._btn_ok.isHidden() and dlg._btn_cancel.isHidden()
        # 空状态提示可见
        assert not dlg._empty_label.isHidden()

    def test_load_existing_with_size(self, qapp, issue_svc, tmp_path):
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        svc, issue_id = issue_svc
        f = tmp_path / "report.pdf"
        f.write_bytes(b"x" * 3000)
        svc.add_attachment(issue_id, file_path=str(f), file_type="document",
                           description="测试报告")
        dlg = AttachmentDialog(issue_id, svc)
        assert dlg._list_widget.count() == 1
        text = dlg._list_widget.item(0).text()
        assert "report.pdf" in text
        assert "2.9 KB" in text
        assert "测试报告" in text
        assert dlg._empty_label.isHidden()

    def test_add_attachments(self, qapp, issue_svc, tmp_path, monkeypatch):
        from src.views.dialogs import attachment_dialog as m
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        from PySide6.QtWidgets import QFileDialog
        svc, issue_id = issue_svc
        # 附件目录重定向到临时目录，避免污染用户目录
        attach_dir = tmp_path / "attachments"
        monkeypatch.setattr(m, "DEFAULT_ATTACHMENTS_DIR", attach_dir)
        f1 = tmp_path / "a.png"
        f1.write_bytes(b"img")
        f2 = tmp_path / "b.txt"
        f2.write_bytes(b"text")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames",
            staticmethod(lambda *a, **kw: ([str(f1), str(f2)], "")),
        )
        dlg = AttachmentDialog(issue_id, svc)
        dlg._on_add_attachments()
        assert dlg._list_widget.count() == 2
        atts = svc.get_attachments(issue_id)
        assert len(atts) == 2
        types = {a.file_path.split("/")[-1]: a.file_type for a in atts}
        assert types["a.png"] == "image"
        assert types["b.txt"] == "document"
        # 文件确实被复制到安全目录
        assert (attach_dir / str(issue_id) / "a.png").is_file()

    def test_add_duplicate_name(self, qapp, issue_svc, tmp_path, monkeypatch):
        from src.views.dialogs import attachment_dialog as m
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        from PySide6.QtWidgets import QFileDialog
        svc, issue_id = issue_svc
        monkeypatch.setattr(m, "DEFAULT_ATTACHMENTS_DIR", tmp_path / "att")
        f = tmp_path / "same.log"
        f.write_bytes(b"log")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames",
            staticmethod(lambda *a, **kw: ([str(f)], "")),
        )
        dlg = AttachmentDialog(issue_id, svc)
        dlg._on_add_attachments()
        dlg._on_add_attachments()  # 同名 → 自动重命名
        names = sorted(
            a.file_path for a in svc.get_attachments(issue_id))
        assert len(names) == 2
        assert names[0].endswith("same.log")
        assert names[1].endswith("same_1.log")

    def test_add_skips_nonexistent_and_cancel(self, qapp, issue_svc,
                                              tmp_path, monkeypatch):
        from src.views.dialogs import attachment_dialog as m
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        from PySide6.QtWidgets import QFileDialog
        svc, issue_id = issue_svc
        monkeypatch.setattr(m, "DEFAULT_ATTACHMENTS_DIR", tmp_path / "att")
        real = tmp_path / "ok.csv"
        real.write_bytes(b"1,2")
        dlg = AttachmentDialog(issue_id, svc)
        # 含不存在文件 → 跳过
        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames",
            staticmethod(lambda *a, **kw: ([str(real), "/no/such.bin"], "")),
        )
        dlg._on_add_attachments()
        assert dlg._list_widget.count() == 1
        # 用户取消（空列表）→ 无新增
        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames",
            staticmethod(lambda *a, **kw: ([], "")),
        )
        dlg._on_add_attachments()
        assert dlg._list_widget.count() == 1

    def test_delete_attachment(self, qapp, issue_svc, tmp_path, monkeypatch):
        import src.views.dialogs.attachment_dialog as m
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        svc, issue_id = issue_svc
        f = tmp_path / "x.dat"
        f.write_bytes(b"d")
        svc.add_attachment(issue_id, file_path=str(f), file_type="other")
        dlg = AttachmentDialog(issue_id, svc)
        dlg._list_widget.setCurrentRow(0)
        assert dlg._btn_delete.isEnabled()
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **kw: m.QMessageBox.StandardButton.Yes,
        )
        dlg._on_delete_attachment()
        assert dlg._list_widget.count() == 0
        assert svc.get_attachments(issue_id) == []

    def test_delete_cancelled(self, qapp, issue_svc, tmp_path, monkeypatch):
        import src.views.dialogs.attachment_dialog as m
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        svc, issue_id = issue_svc
        f = tmp_path / "y.dat"
        f.write_bytes(b"d")
        svc.add_attachment(issue_id, file_path=str(f), file_type="other")
        dlg = AttachmentDialog(issue_id, svc)
        dlg._list_widget.setCurrentRow(0)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **kw: m.QMessageBox.StandardButton.No,
        )
        dlg._on_delete_attachment()
        assert dlg._list_widget.count() == 1

    def test_delete_no_selection_noop(self, qapp, issue_svc):
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        svc, issue_id = issue_svc
        dlg = AttachmentDialog(issue_id, svc)
        dlg._on_delete_attachment()  # 无选中项 → 直接返回
        assert dlg._list_widget.count() == 0

    def test_double_click_opens_file(self, qapp, issue_svc, tmp_path,
                                     monkeypatch):
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        from PySide6.QtGui import QDesktopServices
        svc, issue_id = issue_svc
        f = tmp_path / "open.txt"
        f.write_bytes(b"hi")
        svc.add_attachment(issue_id, file_path=str(f), file_type="document")
        opened = []
        monkeypatch.setattr(
            QDesktopServices, "openUrl",
            staticmethod(lambda url: opened.append(url.toString())),
        )
        dlg = AttachmentDialog(issue_id, svc)
        dlg._on_item_double_clicked(dlg._list_widget.item(0))
        assert len(opened) == 1
        assert opened[0].endswith("open.txt")

    def test_double_click_missing_file_warns(self, qapp, issue_svc,
                                             monkeypatch):
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        svc, issue_id = issue_svc
        svc.add_attachment(issue_id, file_path="/no/such/file.bin",
                           file_type="other")
        warns = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: warns.append(a[2]),
        )
        dlg = AttachmentDialog(issue_id, svc)
        dlg._on_item_double_clicked(dlg._list_widget.item(0))
        assert any("不存在" in w for w in warns)

    def test_double_click_invalid_id_noop(self, qapp, issue_svc):
        from src.views.dialogs.attachment_dialog import AttachmentDialog
        from PySide6.QtWidgets import QListWidgetItem
        svc, issue_id = issue_svc
        dlg = AttachmentDialog(issue_id, svc)
        item = QListWidgetItem("无 id 项")
        item.setData(Qt.ItemDataRole.UserRole, None)
        dlg._on_item_double_clicked(item)  # id 为 None → 返回
