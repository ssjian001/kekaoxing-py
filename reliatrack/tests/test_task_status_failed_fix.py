"""測試任務失敗狀態修復 — "fail" vs "failed" 統一 + 狀態枚舉完整性。

覆蓋 2026-08-09 修復：
1. TASK_STATUS_LABELS / TASK_STATUS_COLORS 補 "failed" 條目
2. 表格渲染把歷史 "fail" 規範化為 "failed"（中文標籤 + 紅色）
3. 就地編輯狀態定位兼容歷史 "fail"
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestTaskStatusFailedEnum:
    """TASK_STATUS_LABELS / TASK_STATUS_COLORS 必須包含 failed。"""

    def test_labels_contain_failed(self):
        from src.constants import TASK_STATUS_LABELS
        assert "failed" in TASK_STATUS_LABELS
        assert TASK_STATUS_LABELS["failed"] == "失败"

    def test_colors_contain_failed(self):
        from src.styles.constants import TASK_STATUS_COLORS
        assert "failed" in TASK_STATUS_COLORS


class TestTaskTableFailRender:
    """表格渲染把歷史 "fail" 規範化為 "failed"（行為測試，非源碼匹配）。"""

    def _make_task(self, status: str):
        from src.models.test_plan import TestTask
        return TestTask(id=1, plan_id=1, name="T", category="环境试验",
                        duration=3, status=status, progress=0.0, priority=3)

    def test_fail_status_shows_chinese_label(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        t = _TaskTable()
        t.set_tasks([self._make_task("fail")])
        item = t.item(0, 8)
        assert item is not None
        assert item.text() == "失败"

    def test_failed_status_shows_chinese_label(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        t = _TaskTable()
        t.set_tasks([self._make_task("failed")])
        item = t.item(0, 8)
        assert item is not None
        assert item.text() == "失败"

    def test_fail_status_uses_red_color(self, qapp):
        from src.styles.constants import STATUS_RED
        from src.views.widgets.task_table import _TaskTable
        t = _TaskTable()
        t.set_tasks([self._make_task("fail")])
        item = t.item(0, 8)
        assert item is not None
        assert item.foreground().color().name().upper() == STATUS_RED.upper()

    def test_failed_status_uses_red_color(self, qapp):
        from src.styles.constants import STATUS_RED
        from src.views.widgets.task_table import _TaskTable
        t = _TaskTable()
        t.set_tasks([self._make_task("failed")])
        item = t.item(0, 8)
        assert item is not None
        assert item.foreground().color().name().upper() == STATUS_RED.upper()

    def test_unknown_status_still_renders_raw(self, qapp):
        """未知狀態不崩潰，fallback 顯示原始值。"""
        from src.views.widgets.task_table import _TaskTable
        t = _TaskTable()
        t.set_tasks([self._make_task("blocked")])
        item = t.item(0, 8)
        assert item is not None
        assert item.text() == "blocked"


class TestInlineStatusFailCompat:
    """就地編輯狀態定位兼容歷史 "fail"（行為測試）。"""

    def test_status_combo_positions_to_failed_for_fail(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        from src.models.test_plan import TestTask

        t = _TaskTable()
        task = TestTask(id=1, plan_id=1, name="T", category="环境试验",
                        duration=3, status="fail", progress=0.0, priority=3)
        t._tasks = [task]
        t.setRowCount(1)
        t._edit_inline_status(0, task)

        combo = t.cellWidget(0, 8)
        assert combo is not None
        # 定位循環應把 "fail" 對齊到 "failed" 項，而不是停在 index 0（待开始）
        from src.constants import TASK_STATUS_LABELS
        failed_idx = list(TASK_STATUS_LABELS.keys()).index("failed")
        assert combo.currentIndex() == failed_idx
        assert combo.currentText() == "失败"

    def test_status_combo_positions_to_failed_for_failed(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        from src.models.test_plan import TestTask

        t = _TaskTable()
        task = TestTask(id=1, plan_id=1, name="T", category="环境试验",
                        duration=3, status="failed", progress=0.0, priority=3)
        t._tasks = [task]
        t.setRowCount(1)
        t._edit_inline_status(0, task)

        combo = t.cellWidget(0, 8)
        assert combo is not None
        assert combo.currentText() == "失败"

    def test_status_combo_no_commit_on_unchanged(self, qapp):
        """用戶未改動 combo 時 activated 不寫庫（initial_idx 保護）。"""
        from src.views.widgets.task_table import _TaskTable
        from src.models.test_plan import TestTask

        t = _TaskTable()
        calls: list = []
        t._batch_value_callback = lambda ids, col, val: calls.append((ids, col, val))
        task = TestTask(id=1, plan_id=1, name="T", category="环境试验",
                        duration=3, status="failed", progress=0.0, priority=3)
        t._tasks = [task]
        t.setRowCount(1)
        t._edit_inline_status(0, task)

        combo = t.cellWidget(0, 8)
        assert combo is not None
        # activated.emit 同步觸發 _finish_inline_edit → _commit
        # currentIndex 未變（initial_idx 保護）→ 不調用 _batch_value_callback
        combo.activated.emit(combo.currentIndex())
        assert calls == []

    def test_status_combo_commits_changed_value(self, qapp):
        """用户改了 combo 状态 → activated 提交新值到 DB 回調。"""
        from src.views.widgets.task_table import _TaskTable
        from src.models.test_plan import TestTask
        from src.constants import TASK_STATUS_LABELS

        t = _TaskTable()
        calls: list = []
        t._batch_value_callback = lambda ids, col, val: calls.append((ids, col, val))
        task = TestTask(id=1, plan_id=1, name="T", category="环境试验",
                        duration=3, status="pending", progress=0.0, priority=3)
        t._tasks = [task]
        t.setRowCount(1)
        t._edit_inline_status(0, task)

        combo = t.cellWidget(0, 8)
        assert combo is not None
        failed_idx = list(TASK_STATUS_LABELS.keys()).index("failed")
        combo.setCurrentIndex(failed_idx)  # 選「失败」（與原 pending 不同）
        combo.activated.emit(failed_idx)
        assert calls == [([1], 8, "failed")]

    def test_priority_combo_activated_commits_changed_value(self, qapp):
        """priority 就地編輯：activated 選不同項 → 提交新值到 DB 回調。"""
        from src.views.widgets.task_table import _TaskTable
        from src.models.test_plan import TestTask

        t = _TaskTable()
        calls: list = []
        t._batch_value_callback = lambda ids, col, val: calls.append((ids, col, val))
        task = TestTask(id=1, plan_id=1, name="T", category="环境试验",
                        duration=3, status="pending", progress=0.0, priority=3)
        t._tasks = [task]
        t.setRowCount(1)
        t._edit_inline_priority(0, task)

        combo = t.cellWidget(0, 7)
        assert combo is not None
        # 初始 idx = priority-1 = 2；選 index 0（優先級 1，與原 3 不同）
        combo.setCurrentIndex(0)
        combo.activated.emit(0)
        assert calls == [([1], 7, "1")]


class TestInlineEditorFocusCleanup:
    """就地编辑器 PopupFocusReason 失焦清理（2026-08-10 修复）。

    用户点击 combo popup 外部后编辑器必须立即清理，
    不能残留到下一次点击（PopupFocusReason 无条件跳过导致）。
    """

    def _make_table(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        from src.models.test_plan import TestTask
        t = _TaskTable()
        t.set_tasks([TestTask(id=1, plan_id=1, name="T", duration=3,
                              start_day=0, status="pending")])
        return t

    def test_popup_visible_focusout_keeps_editor(self, qapp):
        """popup 仍可见时失焦（焦点临时去 popup）→ 编辑器保留。"""
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QFocusEvent
        t = self._make_table(qapp)
        t._edit_inline_status(0, t.get_task_at_row(0))
        combo = t.cellWidget(0, 8)
        assert combo is not None
        # 模拟焦点转移去 popup（popup 打开中）
        ev = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.PopupFocusReason)
        t.cellWidget(0, 8)  # noqa
        # 直接对 combo 发事件（popup 仍打开）
        from PySide6.QtWidgets import QApplication
        QApplication.sendEvent(combo, ev)
        assert t.cellWidget(0, 8) is not None

    def test_popup_closed_focusout_cleans_up(self, qapp):
        """popup 已关闭后失焦（用户点击外部）→ 编辑器立即清理。"""
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QFocusEvent
        from PySide6.QtWidgets import QApplication
        t = self._make_table(qapp)
        t._edit_inline_status(0, t.get_task_at_row(0))
        combo = t.cellWidget(0, 8)
        assert combo is not None
        # 用户点击 popup 外部 → popup 关闭
        combo.hidePopup()
        # popup 已关闭后的失焦，reason 仍可能是 PopupFocusReason → 必须清理
        ev = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.PopupFocusReason)
        QApplication.sendEvent(combo, ev)
        QApplication.processEvents()
        assert t.cellWidget(0, 8) is None
