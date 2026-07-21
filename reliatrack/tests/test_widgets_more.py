"""補充測試 — 覆蓋低覆蓋率模塊。

- src/styles/column_persistence.py (26% → 目標 80%+)
- src/views/dialogs/import_tasks_from_plan_dialog.py (0%)
- src/views/widgets/task_table.py (22%) — smoke + API
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import apsw

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView,
)

from src.db.schema import init_schema


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db_conn():
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


# ── column_persistence ────────────────────────────────────

class TestColumnPersistence:
    """測試列寬持久化（save/restore/debounce/sort）。"""

    def test_save_and_restore_widths(self, qapp):
        from src.styles.column_persistence import (
            save_column_widths, restore_column_widths,
        )
        table = QTableWidget(2, 2)
        # 設第一列為 Interactive 並自定義寬度
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 200)

        key = "test_col_table_1"
        save_column_widths(table, key)
        # 重置寬度
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 60)
        # 恢復
        restore_column_widths(table, key)
        assert table.columnWidth(0) == 150
        assert table.columnWidth(1) == 200

    def test_restore_with_no_saved_data_does_nothing(self, qapp):
        from src.styles.column_persistence import restore_column_widths
        table = QTableWidget(2, 2)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 80)
        # 不存在的 key
        restore_column_widths(table, "non_existent_key_xyz")
        assert table.columnWidth(0) == 80  # 沒變化

    def test_save_ignores_non_interactive_columns(self, qapp):
        """Fixed/Stretch 列寬不持久化（-1 標記）。"""
        from src.styles.column_persistence import save_column_widths
        table = QTableWidget(2, 2)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        key = "test_mixed_mode"
        save_column_widths(table, key)
        settings = QSettings()
        widths = settings.value(f"ReliaTrack/column_widths/{key}")
        assert widths[0] > 0  # Interactive
        assert widths[1] == -1  # Stretch

    def test_save_and_restore_sort_state(self, qapp):
        from src.styles.column_persistence import save_sort_state, restore_sort_state
        table = QTableWidget(3, 2)
        table.setItem(0, 0, QTableWidgetItem("c"))
        table.setItem(1, 0, QTableWidgetItem("a"))
        table.setItem(2, 0, QTableWidgetItem("b"))
        # 按第 0 列降序排序
        table.sortItems(0, Qt.SortOrder.DescendingOrder)
        key = "test_sort_key"
        save_sort_state(table, key)
        # 改變排序
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        # 恢復
        restore_sort_state(table, key)
        header = table.horizontalHeader()
        assert header.sortIndicatorSection() == 0
        assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder

    def test_debounced_save(self, qapp):
        """debounce 版可調用不崩潰。"""
        from src.styles.column_persistence import save_column_widths_debounced
        table = QTableWidget(2, 2)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        key = "test_debounce"
        save_column_widths_debounced(table, key)
        save_column_widths_debounced(table, key)  # 重複調用
        # 不拋異常即可


# ── import_tasks_from_plan_dialog ─────────────────────────

class TestImportTasksFromPlanDialog:
    """構造 + 基本方法測試。"""

    def test_construct(self, qapp, db_conn):
        from src.models.test_plan import TestTask
        from src.views.dialogs.import_tasks_from_plan_dialog import (
            ImportTasksFromPlanDialog,
        )
        tasks = [
            TestTask(id=1, name="Task1", plan_id=1, start_day=1, duration=5),
            TestTask(id=2, name="Task2", plan_id=1, start_day=3, duration=2),
        ]
        dlg = ImportTasksFromPlanDialog(tasks, "Plan1")
        assert dlg is not None

    def test_empty_tasks_does_not_crash(self, qapp, db_conn):
        from src.views.dialogs.import_tasks_from_plan_dialog import (
            ImportTasksFromPlanDialog,
        )
        dlg = ImportTasksFromPlanDialog([], "EmptyPlan")
        assert dlg is not None


# ── task_table smoke ──────────────────────────────────────

class TestTaskTableSmoke:
    """_TaskTable 構造 + API smoke。"""

    def test_construct(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        # _TaskTable 可能需要參數，先試簡單構造
        try:
            table = _TaskTable()
            assert table is not None
        except TypeError:
            # 嘗試帶 columns 參數
            table = _TaskTable(["任務", "開始", "工期"])
            assert table is not None


# ── theme.py QSS 構造 ─────────────────────────────────────

class TestThemeBuildQss:
    """測試 theme.py 的 QSS 生成（目前 34%）。"""

    def test_build_qss_returns_string(self, qapp):
        import src.styles.theme as _t
        qss = _t._build_qss()
        assert isinstance(qss, str)
        assert "QPushButton" in qss  # 至少有 QPushButton 樣式

    def test_theme_constants_exist(self, qapp):
        import src.styles.theme as _t
        # 確認核心色板變量（globaals().update 注入）
        color_names = [
            name for name in dir(_t)
            if name.startswith("BG_") or name.startswith("FG_")
               or name.startswith("ACCENT")
        ]
        assert len(color_names) >= 5


# ── undo_manager ──────────────────────────────────────────

class TestUndoManager:
    """undo_manager.py 的 UndoManager 測試。"""

    def test_construct(self, qapp):
        from src.services.undo_manager import UndoManager
        um = UndoManager()
        assert um is not None

    def test_empty_undo_returns_none(self, qapp):
        from src.services.undo_manager import UndoManager
        um = UndoManager()
        result = um.undo()
        assert result is None

    def test_execute_and_undo(self, qapp):
        """用一個簡單 Command 驗證 undo/redo 流程。"""
        from src.services.undo_manager import UndoManager, UpdateFieldCommand

        # 需要一個 mock repo（UpdateFieldCommand 調用 repo.update()）
        class _MockRepo:
            def __init__(self):
                self.value = "old"
            def update(self, entity_id, **kwargs):
                if "name" in kwargs:
                    self.value = kwargs["name"]

        repo = _MockRepo()
        cmd = UpdateFieldCommand(repo, 1, "name", "old", "new", "Task")
        um = UndoManager()
        um.execute(cmd)
        assert repo.value == "new"
        um.undo()
        assert repo.value == "old"
