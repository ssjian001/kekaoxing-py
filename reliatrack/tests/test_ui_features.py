"""UI 功能特性测试 — 视觉布局 / 搜索交互 / 数据列与字段（2026-08-10 深挖批次）。

覆盖：Issue 详情 6 Tab 布局、添加关联搜索过滤、设备 location 列、
排程技术员容量配置、编辑弹窗新字段（location / remind_at）。

运行: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_features.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import apsw

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QLineEdit

# 模块级 QApplication（UI 测试需要）
_app = QApplication.instance() or QApplication(sys.argv)

from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.equipment_repo import EquipmentRepository
from src.db.repositories.technician_repo import TechnicianRepository
from src.services.issue_service import IssueService
from src.services.equipment_service import EquipmentService
from src.services.technician_service import TechnicianService


@pytest.fixture()
def db_conn() -> apsw.Connection:
    conn = apsw.Connection(":memory:")
    init_schema(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    yield conn


@pytest.fixture()
def issue_svc(db_conn) -> IssueService:
    return IssueService(IssueRepository(db_conn), db_conn)


@pytest.fixture()
def equip_svc(db_conn) -> EquipmentService:
    return EquipmentService(EquipmentRepository(db_conn))


@pytest.fixture()
def tech_svc(db_conn) -> TechnicianService:
    return TechnicianService(TechnicianRepository(db_conn))


# ═══════════════════════════════════════════════════════════════════
#  1. Issue 详情弹窗 — 6 Tab 布局（视觉/可访问性）
# ═══════════════════════════════════════════════════════════════════

class TestDetailDialogLayout:
    """IssueDetailDialog 6 Tab 布局：所有 segment 构建且可见。"""

    def _make_dialog(self, issue_svc):
        from src.views.bug_tracker.detail_dialog import IssueDetailDialog
        iid = issue_svc.create(title="布局测试", status="open", severity="major", priority=2)
        return IssueDetailDialog(issue_svc.get(iid), issue_svc, parent=None)

    def test_six_segments_created(self, issue_svc):
        """6 个 segment 按钮全部创建且可见。"""
        dlg = self._make_dialog(issue_svc)
        dlg.show()
        _app.processEvents()
        from src.views.widgets.segmented_widget import SegmentedWidget
        seg = dlg.findChild(SegmentedWidget)
        assert seg is not None
        assert len(seg._buttons) == 6
        labels = [b.text() for b in seg._buttons]
        assert labels == ["详情", "评论", "活动", "FA", "CAPA", "关联"]
        for btn in seg._buttons:
            assert btn.isVisible()
        dlg.deleteLater()

    def test_link_tab_widgets_visible(self, issue_svc):
        """切到关联 Tab 后列表 + 按钮均可见。"""
        dlg = self._make_dialog(issue_svc)
        from src.views.widgets.segmented_widget import SegmentedWidget
        seg = dlg.findChild(SegmentedWidget)
        seg.setCurrentIndex(5)  # 关联 Tab
        dlg.show()
        _app.processEvents()
        assert dlg._link_list.isVisible()
        assert dlg._btn_add_link.isVisible()
        assert dlg._btn_del_link.isVisible()
        assert dlg._link_list.count() == 1  # 空占位已加载
        dlg.deleteLater()

    def test_dialog_created_without_crash_all_tabs(self, issue_svc):
        """构造后切到每个 segment 不崩溃。"""
        dlg = self._make_dialog(issue_svc)
        from src.views.widgets.segmented_widget import SegmentedWidget
        seg = dlg.findChild(SegmentedWidget)
        for idx in range(6):
            seg.setCurrentIndex(idx)
            _app.processEvents()
        dlg.deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  2. 添加关联对话框 — 搜索过滤交互
# ═══════════════════════════════════════════════════════════════════

class TestAddLinkSearch:
    """添加关联对话框的搜索过滤交互。"""

    def _open_dialog_widgets(self, issue_svc):
        """patch exec 不阻塞，从对话框控件树定位搜索框与目标下拉。"""
        from src.views.bug_tracker.detail_dialog import IssueDetailDialog
        id_src = issue_svc.create(title="源 Issue", status="open", severity="major", priority=2)
        issue_svc.create(title="Alpha 压力测试", status="open", severity="major", priority=2)
        issue_svc.create(title="Beta 温湿度", status="open", severity="major", priority=2)
        dlg = IssueDetailDialog(issue_svc.get(id_src), issue_svc, parent=None)
        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            dlg._on_add_link()
        # 添加对话框以 self 为 parent，控件仍在 Qt 对象树（pending delete）
        search_edit = dlg.findChild(QLineEdit)
        combos = dlg.findChildren(QComboBox)
        target_combo = combos[-1]  # type_combo 在前，target_combo 最后
        return dlg, search_edit, target_combo

    def test_search_filters_options(self, issue_svc):
        """输入关键词 → 下拉只保留匹配项。"""
        dlg, search_edit, target_combo = self._open_dialog_widgets(issue_svc)
        assert target_combo.count() == 2

        search_edit.setText("alpha")
        assert target_combo.count() == 1
        assert "Alpha" in target_combo.itemText(0)

        search_edit.setText("温湿度")
        assert target_combo.count() == 1
        assert "Beta" in target_combo.itemText(0)

        dlg.deleteLater()

    def test_search_no_match_placeholder(self, issue_svc):
        """无匹配 → 显示（无匹配）占位且 data=None。"""
        dlg, search_edit, target_combo = self._open_dialog_widgets(issue_svc)

        search_edit.setText("不存在的关键词xyz")
        assert target_combo.count() == 1
        assert "无匹配" in target_combo.itemText(0)
        assert target_combo.currentData() is None
        dlg.deleteLater()

    def test_clear_search_restores_all(self, issue_svc):
        """清空搜索 → 恢复全部候选。"""
        dlg, search_edit, target_combo = self._open_dialog_widgets(issue_svc)

        search_edit.setText("alpha")
        assert target_combo.count() == 1
        search_edit.clear()
        assert target_combo.count() == 2
        dlg.deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  3. 设备 — location 列显示 + 编辑字段
# ═══════════════════════════════════════════════════════════════════

class TestEquipmentLocation:
    """设备 location 数据链路：编辑字段 → DB → 表格列。"""

    def test_edit_dialog_has_location_field(self, equip_svc):
        """设备编辑弹窗含"存放位置"字段且 get_data 带出。"""
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog
        eid = equip_svc.create(name="示波器", asset_no="EQ-001")
        eq = equip_svc.get(eid)
        dlg = EquipmentEditDialog(eq, parent=None)
        data = dlg.get_data()
        assert "location" in data
        dlg.deleteLater()

    def test_edit_dialog_location_roundtrip(self, equip_svc):
        """编辑时预填 location，get_data 返回新值。"""
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog
        eid = equip_svc.create(name="万用表", asset_no="EQ-002", location="A栋3楼")
        eq = equip_svc.get(eid)
        dlg = EquipmentEditDialog(eq, parent=None)
        assert "A栋3楼" in dlg.get_data()["location"]
        dlg._location_edit.setText("B栋1楼")
        assert dlg.get_data()["location"] == "B栋1楼"
        dlg.deleteLater()

    def test_view_columns_include_location(self, equip_svc):
        """设备表格 _COLUMNS 含存放位置列 + 字段映射。"""
        from src.views.equipment_view import EquipmentView
        view = EquipmentView()
        cols = view._COLUMNS
        assert any(c[0] == "存放位置" for c in cols)
        assert ("存放位置", "location") in cols
        view.deleteLater()

    def test_populate_table_shows_location(self, equip_svc):
        """填充表格后 location 值出现在存放位置列。"""
        from src.views.equipment_view import EquipmentView
        eid = equip_svc.create(name="频谱仪", asset_no="EQ-003", location="实验室C")
        view = EquipmentView()
        items = equip_svc.list_all()
        view._populate_table(items)
        # 找到存放位置列索引 + 名称列（索引 3）定位行
        col_idx = next(i for i, (name, _attr) in enumerate(view._COLUMNS) if name == "存放位置")
        row_idx = next(r for r in range(view._table.rowCount())
                       if view._table.item(r, 3) and view._table.item(r, 3).text() == "频谱仪")
        assert view._table.item(row_idx, col_idx).text() == "实验室C"
        view.deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  4. 排程配置 — 技术员容量配置区
# ═══════════════════════════════════════════════════════════════════

class TestScheduleConfigTechnicianCapacity:
    """ScheduleConfigDialog 技术员容量配置区。"""

    def test_with_technicians_creates_rows(self, tech_svc):
        """带 technician_list 构造 → 生成容量行。"""
        from src.views.dialogs.schedule_config_dialog import ScheduleConfigDialog
        t1 = tech_svc.create(name="张工")
        t2 = tech_svc.create(name="李工")
        dlg = ScheduleConfigDialog(
            equipment_list=[],
            technician_list=tech_svc.list_all(),
            parent=None,
        )
        assert len(dlg._technician_rows) == 2
        tech_ids = {r.technician_id for r in dlg._technician_rows}
        assert tech_ids == {t1, t2}
        dlg.deleteLater()

    def test_without_technicians_no_rows(self, tech_svc):
        """无技术员 → 不生成容量区。"""
        from src.views.dialogs.schedule_config_dialog import ScheduleConfigDialog
        dlg = ScheduleConfigDialog(equipment_list=[], technician_list=[], parent=None)
        assert dlg._technician_rows == []
        dlg.deleteLater()

    def test_get_config_returns_technician_capacity(self, tech_svc):
        """get_config() 返回 technician_capacity 映射（默认 1）。"""
        from src.views.dialogs.schedule_config_dialog import ScheduleConfigDialog
        tech_svc.create(name="张工")
        dlg = ScheduleConfigDialog(
            equipment_list=[],
            technician_list=tech_svc.list_all(),
            parent=None,
        )
        cfg = dlg.get_config()
        assert "technician_capacity" in cfg
        assert cfg["technician_capacity"] == {tech_svc.list_all()[0].id: 1}
        dlg.deleteLater()

    def test_spin_adjusts_capacity(self, tech_svc):
        """调整 spin 值 → get_config 反映新容量。"""
        from src.views.dialogs.schedule_config_dialog import ScheduleConfigDialog
        tid = tech_svc.create(name="张工")
        dlg = ScheduleConfigDialog(
            equipment_list=[],
            technician_list=tech_svc.list_all(),
            parent=None,
        )
        row = next(r for r in dlg._technician_rows if r.technician_id == tid)
        row._spin.setValue(3)
        assert dlg.get_config()["technician_capacity"][tid] == 3
        dlg.deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  5. 待办编辑弹窗 — remind_at 字段
# ═══════════════════════════════════════════════════════════════════

class TestTodoEditRemindAt:
    """TodoEditDialog 提醒时间字段。"""

    def test_get_data_contains_remind_at(self):
        """get_data 带出 remind_at（新建时为空字符串）。"""
        from src.views.dialogs.todo_edit_dialog import TodoEditDialog
        dlg = TodoEditDialog(todo=None, parent=None)
        data = dlg.get_data()
        assert "remind_at" in data
        dlg.deleteLater()

    def test_remind_at_roundtrip(self):
        """编辑时预填 remind_at，修改后 get_data 返回新值。"""
        from src.models.todo import TodoItem
        from src.views.dialogs.todo_edit_dialog import TodoEditDialog
        past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        todo = TodoItem(id=1, title="带提醒", remind_at=past)
        dlg = TodoEditDialog(todo=todo, parent=None)
        assert dlg.get_data()["remind_at"] == past
        future = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        dlg._remind_at_edit.setText(future)
        assert dlg.get_data()["remind_at"] == future
        dlg.deleteLater()
