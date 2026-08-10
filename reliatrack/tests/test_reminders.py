"""新功能测试 — Issue 关联 UI / 待办提醒 / 校准提醒（2026-08-10 接线）。

运行: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_reminders.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import apsw

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem

# 模块级 QApplication（UI 测试需要）
_app = QApplication.instance() or QApplication(sys.argv)

from src.db.schema import init_schema
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.equipment_repo import EquipmentRepository
from src.db.repositories.todo_repo import TodoRepository
from src.db.repositories.project_repo import ProjectRepository
from src.services.issue_service import IssueService
from src.services.equipment_service import EquipmentService
from src.services.todo_service import TodoService


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
def todo_svc(db_conn) -> TodoService:
    return TodoService(TodoRepository(db_conn))


def _make_issue(issue_svc: IssueService, title: str, status: str = "open") -> int:
    return issue_svc.create(
        title=title, status=status, severity="major", priority=2,
    )


def _get_issue(issue_svc: IssueService, issue_id: int):
    """IssueService 用 get() 查询（无 get_by_id）。"""
    return issue_svc.get(issue_id)


# ═══════════════════════════════════════════════════════════════════
#  1. Issue 关联 — detail_dialog 关联 Tab
# ═══════════════════════════════════════════════════════════════════

class TestIssueLinkDialogTab:
    """IssueDetailDialog 关联 Tab 构建与数据加载。"""

    def _make_dialog(self, issue_svc, issue):
        from src.views.bug_tracker.detail_dialog import IssueDetailDialog
        dlg = IssueDetailDialog(issue, issue_svc, parent=None)
        return dlg

    def test_link_tab_widgets_created(self, issue_svc):
        """关联 Tab 构建：QListWidget + 添加/删除按钮。"""
        iid = _make_issue(issue_svc, "主 Issue")
        issue = _get_issue(issue_svc, iid)
        dlg = self._make_dialog(issue_svc, issue)
        assert hasattr(dlg, "_link_list")
        assert dlg._link_list is not None
        assert dlg._btn_add_link is not None
        assert dlg._btn_del_link is not None
        dlg.deleteLater()

    def test_load_links_empty_placeholder(self, issue_svc):
        """无关联时显示占位 item，且不可选择（NoItemFlags）。"""
        iid = _make_issue(issue_svc, "无关联 Issue")
        issue = _get_issue(issue_svc, iid)
        dlg = self._make_dialog(issue_svc, issue)
        dlg._load_links()
        assert dlg._link_list.count() == 1
        item = dlg._link_list.item(0)
        assert "暂无关联" in item.text()
        assert not (item.flags() & Qt.ItemFlag.ItemIsSelectable)
        dlg.deleteLater()

    def test_load_links_bidirectional_direction(self, issue_svc):
        """双向关联：源侧显示 →，目标侧显示 ←。"""
        id_a = _make_issue(issue_svc, "Issue A")
        id_b = _make_issue(issue_svc, "Issue B")
        issue_svc.add_link(id_a, id_b, "blocks")

        dlg_a = self._make_dialog(issue_svc, _get_issue(issue_svc, id_a))
        dlg_a._load_links()
        assert dlg_a._link_list.count() == 1
        item_a = dlg_a._link_list.item(0)
        assert "→" in item_a.text()
        assert "阻塞" in item_a.text()
        assert "Issue B" in item_a.text()
        link_id = item_a.data(Qt.ItemDataRole.UserRole)
        assert link_id is not None
        dlg_a.deleteLater()

        dlg_b = self._make_dialog(issue_svc, _get_issue(issue_svc, id_b))
        dlg_b._load_links()
        assert dlg_b._link_list.count() == 1
        assert "←" in dlg_b._link_list.item(0).text()
        dlg_b.deleteLater()

    def test_add_link_then_reload_shows_item(self, issue_svc):
        """service.add_link 后 _load_links 显示新条目。"""
        id_a = _make_issue(issue_svc, "源")
        id_b = _make_issue(issue_svc, "目标")
        dlg = self._make_dialog(issue_svc, _get_issue(issue_svc, id_a))
        issue_svc.add_link(id_a, id_b, "relates_to")
        dlg._load_links()
        assert dlg._link_list.count() == 1
        assert "相关" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_delete_link_then_reload_empty(self, issue_svc):
        """service.delete_link 后 _load_links 回到空状态。"""
        id_a = _make_issue(issue_svc, "源")
        id_b = _make_issue(issue_svc, "目标")
        link_id = issue_svc.add_link(id_a, id_b, "duplicates")
        dlg = self._make_dialog(issue_svc, _get_issue(issue_svc, id_a))
        issue_svc.delete_link(link_id)
        dlg._load_links()
        assert dlg._link_list.count() == 1
        assert "暂无关联" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_add_link_self_reference_rejected(self, issue_svc):
        """自引用关联被 DB 约束拒绝。"""
        iid = _make_issue(issue_svc, "自身")
        with pytest.raises(Exception):
            issue_svc.add_link(iid, iid, "relates_to")

    def test_load_links_soft_deleted_shows_title(self, issue_svc):
        """对方软删后仍显示标题（get 不过滤软删，提供上下文）。"""
        id_a = _make_issue(issue_svc, "存活")
        id_b = _make_issue(issue_svc, "已软删")
        issue_svc.add_link(id_a, id_b, "relates_to")
        issue_svc.soft_delete(id_b)

        dlg = self._make_dialog(issue_svc, issue_svc.get(id_a))
        dlg._load_links()
        assert dlg._link_list.count() == 1
        assert "已软删" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_load_links_service_error_returns_empty(self, issue_svc):
        """service.get_links 抛异常 → 空列表占位不崩溃。"""
        iid = _make_issue(issue_svc, "异常测试")
        dlg = self._make_dialog(issue_svc, issue_svc.get(iid))
        dlg._service.get_links = MagicMock(side_effect=RuntimeError("db down"))
        dlg._load_links()
        assert dlg._link_list.count() == 1
        assert "暂无关联" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_on_add_link_dialog_accepted_calls_service(self, issue_svc):
        """添加关联对话框确认后调用 service.add_link 并刷新列表。"""
        from PySide6.QtWidgets import QDialog

        id_a = _make_issue(issue_svc, "源")
        _make_issue(issue_svc, "候选目标")
        dlg = self._make_dialog(issue_svc, issue_svc.get(id_a))

        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            dlg._on_add_link()

        # 添加成功 → 列表出现 1 条关联
        assert dlg._link_list.count() == 1
        assert "候选目标" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_on_add_link_cancel_no_change(self, issue_svc):
        """取消添加关联 → 不产生关联。"""
        from PySide6.QtWidgets import QDialog

        id_a = _make_issue(issue_svc, "源")
        _make_issue(issue_svc, "候选")
        dlg = self._make_dialog(issue_svc, issue_svc.get(id_a))

        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            dlg._on_add_link()

        assert dlg._link_list.count() == 1  # 空占位
        assert "暂无关联" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_on_add_link_service_error_warns(self, issue_svc):
        """add_link 抛异常 → QMessageBox.warning 提示，列表不变。"""
        from PySide6.QtWidgets import QDialog, QMessageBox

        id_a = _make_issue(issue_svc, "源")
        _make_issue(issue_svc, "候选")
        dlg = self._make_dialog(issue_svc, issue_svc.get(id_a))

        real_add = issue_svc.add_link
        issue_svc.add_link = MagicMock(side_effect=Exception("duplicate"))
        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
             patch.object(QMessageBox, "warning") as mock_warn:
            dlg._on_add_link()
        mock_warn.assert_called_once()
        assert "添加失败" in str(mock_warn.call_args[0][2]) or "无法添加关联" in str(mock_warn.call_args[0][2])
        issue_svc.add_link = real_add
        assert dlg._link_list.count() == 1
        dlg.deleteLater()

    def test_on_delete_link_confirmed_calls_service(self, issue_svc):
        """删除确认后调用 service.delete_link 并刷新列表。"""
        from PySide6.QtWidgets import QMessageBox

        id_a = _make_issue(issue_svc, "源")
        id_b = _make_issue(issue_svc, "目标")
        link_id = issue_svc.add_link(id_a, id_b, "blocks")
        dlg = self._make_dialog(issue_svc, issue_svc.get(id_a))
        dlg._load_links()
        assert dlg._link_list.count() == 1
        dlg._link_list.setCurrentRow(0)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dlg._on_delete_link()

        assert issue_svc.get_links(id_a) == []
        assert dlg._link_list.count() == 1
        assert "暂无关联" in dlg._link_list.item(0).text()
        dlg.deleteLater()

    def test_on_delete_link_placeholder_not_deletable(self, issue_svc):
        """空占位 item 不可删除（NoItemFlags 无 ItemIsSelectable）。"""
        from PySide6.QtWidgets import QMessageBox

        iid = _make_issue(issue_svc, "无关联")
        dlg = self._make_dialog(issue_svc, issue_svc.get(iid))
        dlg._load_links()
        dlg._link_list.setCurrentRow(0)

        with patch.object(QMessageBox, "question") as mock_q:
            dlg._on_delete_link()
        mock_q.assert_not_called()
        dlg.deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  2. 待办提醒
# ═══════════════════════════════════════════════════════════════════

class TestTodoReminderService:
    """todo_service 提醒查询/标记（service 层契约）。"""

    def test_list_due_reminders_only_due(self, todo_svc):
        """只返回到期未提醒的待办（remind_at <= now AND reminded=0 AND archived=0）。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        future = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")

        t1 = todo_svc.create(project_id=None, title="到期A", remind_at=past)
        todo_svc.create(project_id=None, title="未来B", remind_at=future)
        t3 = todo_svc.create(project_id=None, title="已提醒C", remind_at=past)
        todo_svc.mark_reminded(t3)
        t4 = todo_svc.create(project_id=None, title="已归档D", remind_at=past)
        todo_svc.archive(t4)

        due = todo_svc.list_due_reminders(now)
        ids = {t.id for t in due}
        assert t1 in ids
        assert t3 not in ids
        assert t4 not in ids
        assert all(t.title != "未来B" for t in due)

    def test_mark_reminded_idempotent(self, todo_svc):
        """mark_reminded 后再次查询不再返回。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        tid = todo_svc.create(project_id=None, title="提醒测试", remind_at=now)
        assert len(todo_svc.list_due_reminders(now)) == 1
        todo_svc.mark_reminded(tid)
        assert len(todo_svc.list_due_reminders(now)) == 0


class TestTodoReminderMainWindow:
    """MainWindow._check_due_reminders 提醒触发逻辑（mock 方式，不构造全窗口）。"""

    def _make_win(self, todo_svc):
        from main import MainWindow
        win = MainWindow.__new__(MainWindow)
        ctrl = MagicMock()
        ctrl.todo_service = todo_svc
        win._ctrl = ctrl
        win.toast = MagicMock()
        win.statusBar = MagicMock()
        return win

    def test_multiple_due_triggers_multiple_toasts(self, todo_svc):
        """多个待办同时到期 → 每个都弹 toast + statusBar。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        todo_svc.create(project_id=None, title="到期1", remind_at=now)
        todo_svc.create(project_id=None, title="到期2", remind_at=now)

        win = self._make_win(todo_svc)
        win._check_due_reminders()

        assert win.toast.call_count == 2
        titles = [c[0][0] for c in win.toast.call_args_list]
        assert any("到期1" in t for t in titles)
        assert any("到期2" in t for t in titles)
        assert win.statusBar().showMessage.call_count == 2

    def test_service_error_swallowed(self, todo_svc):
        """list_due_reminders 抛异常 → 静默返回不崩溃。"""
        win = self._make_win(todo_svc)
        win._ctrl.todo_service = MagicMock()
        win._ctrl.todo_service.list_due_reminders.side_effect = RuntimeError("db down")
        win._check_due_reminders()  # 不抛异常
        win.toast.assert_not_called()

    def test_due_reminder_toasts_and_marks(self, todo_svc):
        """到期待办 → toast + statusBar 提示 + 标记 reminded。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        tid = todo_svc.create(project_id=None, title="启动提醒", remind_at=now)

        win = self._make_win(todo_svc)
        win._check_due_reminders()

        win.toast.assert_called_once()
        assert "启动提醒" in win.toast.call_args[0][0]
        win.statusBar().showMessage.assert_called_once()
        # 已标记 reminded，二次调用不重复
        assert len(todo_svc.list_due_reminders(now)) == 0
        win.toast.reset_mock()
        win._check_due_reminders()
        win.toast.assert_not_called()

    def test_no_due_no_toast(self, todo_svc):
        """无到期待办时不弹提醒。"""
        future = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        todo_svc.create(project_id=None, title="未来事项", remind_at=future)

        win = self._make_win(todo_svc)
        win._check_due_reminders()
        win.toast.assert_not_called()

    def test_archived_excluded(self, todo_svc):
        """已归档待办不提醒。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        tid = todo_svc.create(project_id=None, title="归档项", remind_at=now)
        todo_svc.archive(tid)

        win = self._make_win(todo_svc)
        win._check_due_reminders()
        win.toast.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
#  3. 校准提醒
# ═══════════════════════════════════════════════════════════════════

class TestCalibrationReminderService:
    """equipment_service.get_expiring_calibrations 边界。"""

    def _add_equip(self, equip_svc, name: str, next_cal: str) -> int:
        return equip_svc.create(name=name, next_calibration_date=next_cal)

    def test_boundaries(self, equip_svc):
        """过期/今天/30 天内返回；31 天后/空日期/非法日期不返回。"""
        today = datetime.now().date()
        def iso(days: int) -> str:
            return (today + timedelta(days=days)).isoformat()

        self._add_equip(equip_svc, "已过期", iso(-10))
        self._add_equip(equip_svc, "今天到期", iso(0))
        self._add_equip(equip_svc, "30天内", iso(29))
        self._add_equip(equip_svc, "第30天", iso(30))
        self._add_equip(equip_svc, "31天后", iso(31))
        self._add_equip(equip_svc, "无日期", "")
        self._add_equip(equip_svc, "非法日期", "2026/13/45")

        expiring = equip_svc.get_expiring_calibrations(30)
        names = {e.name for e, _d in expiring}
        assert {"已过期", "今天到期", "30天内", "第30天"} <= names
        assert "31天后" not in names
        assert "无日期" not in names
        assert "非法日期" not in names

    def test_sorted_by_remaining_days(self, equip_svc):
        """结果按剩余天数升序（最紧迫在前）。"""
        today = datetime.now().date()
        self._add_equip(equip_svc, "B-远期", (today + timedelta(days=20)).isoformat())
        self._add_equip(equip_svc, "A-紧迫", (today + timedelta(days=5)).isoformat())
        self._add_equip(equip_svc, "C-逾期", (today - timedelta(days=3)).isoformat())

        expiring = equip_svc.get_expiring_calibrations(30)
        days = [d for _e, d in expiring]
        assert days == sorted(days)
        assert expiring[0][0].name == "C-逾期"

    def test_days_zero_only_overdue_today(self, equip_svc):
        """days=0 只返回已过期和今天的设备。"""
        today = datetime.now().date()
        self._add_equip(equip_svc, "昨天", (today - timedelta(days=1)).isoformat())
        self._add_equip(equip_svc, "今天", today.isoformat())
        self._add_equip(equip_svc, "明天", (today + timedelta(days=1)).isoformat())

        expiring = equip_svc.get_expiring_calibrations(0)
        names = {e.name for e, _d in expiring}
        assert names == {"昨天", "今天"}


class TestCalibrationReminderMainWindow:
    """MainWindow._check_calibration_reminders 触发逻辑（mock 方式）。"""

    def _make_win(self, equip_svc):
        from main import MainWindow
        win = MainWindow.__new__(MainWindow)
        ctrl = MagicMock()
        ctrl.equipment_service = equip_svc
        win._ctrl = ctrl
        win.toast = MagicMock()
        win.statusBar = MagicMock()
        return win

    def test_overdue_triggers_toast(self, equip_svc):
        """有过期设备 → toast + statusBar 提示。"""
        today = datetime.now().date()
        equip_svc.create(name="压机-1", next_calibration_date=(today - timedelta(days=5)).isoformat())

        win = self._make_win(equip_svc)
        with patch("PySide6.QtCore.QSettings") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.value.return_value = None  # 当天未提醒过
            mock_cls.return_value = mock_settings
            win._check_calibration_reminders()

        win.toast.assert_called_once()
        assert "压机-1" in win.toast.call_args[0][0]
        win.statusBar().showMessage.assert_called_once()
        mock_settings.setValue.assert_called_once()

    def test_once_per_day(self, equip_svc):
        """同一天重复调用不重复提醒（QSettings 记录日期）。"""
        today = datetime.now().date()
        equip_svc.create(name="恒温箱", next_calibration_date=(today - timedelta(days=1)).isoformat())

        win = self._make_win(equip_svc)
        with patch("PySide6.QtCore.QSettings") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.value.return_value = today.isoformat()  # 今天已提醒过
            mock_cls.return_value = mock_settings
            win._check_calibration_reminders()

        win.toast.assert_not_called()
        mock_settings.setValue.assert_not_called()

    def test_toast_text_classification_and_truncation(self, equip_svc):
        """toast 文案：已过期/30天内分类 + 超过 3 台截断。"""
        today = datetime.now().date()
        equip_svc.create(name="压机-过期", next_calibration_date=(today - timedelta(days=5)).isoformat())
        equip_svc.create(name="恒温箱-到期", next_calibration_date=(today + timedelta(days=10)).isoformat())
        equip_svc.create(name="振动机-3", next_calibration_date=(today + timedelta(days=15)).isoformat())
        equip_svc.create(name="盐雾箱-4", next_calibration_date=(today + timedelta(days=20)).isoformat())

        win = self._make_win(equip_svc)
        with patch("PySide6.QtCore.QSettings") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.value.return_value = None
            mock_cls.return_value = mock_settings
            win._check_calibration_reminders()

        msg = win.toast.call_args[0][0]
        assert "1 台已过期" in msg
        assert "3 台 30 天内到期" in msg
        assert "等 4 台" in msg  # 4 台截断显示前 3

    def test_no_expiring_no_toast(self, equip_svc):
        """无到期设备不提示。"""
        today = datetime.now().date()
        equip_svc.create(name="远期设备", next_calibration_date=(today + timedelta(days=90)).isoformat())

        win = self._make_win(equip_svc)
        with patch("PySide6.QtCore.QSettings") as mock_cls:
            win._check_calibration_reminders()

        win.toast.assert_not_called()
