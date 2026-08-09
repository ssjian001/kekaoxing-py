"""測試任務失敗狀態修復 — "fail" vs "failed" 統一 + 狀態枚舉完整性。

覆蓋 2026-08-09 修復：
1. TASK_STATUS_LABELS / TASK_STATUS_COLORS 補 "failed" 條目
2. refresh_handlers 的 failed 統計合併 "fail" + "failed"
3. 就地編輯狀態定位兼容歷史 "fail"（_edit_inline_status 的 key 匹配）
4. 表格渲染把歷史 "fail" 規範化為 "failed"（中文標籤 + 紅色）
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


class TestDashboardFailMerge:
    """refresh_handlers 的 failed 統計合併邏輯。"""

    def test_merge_expression_matches_implementation(self):
        # 驗證 refresh_handlers 中 failed_task_count = get("failed") + get("fail")
        import inspect
        import re
        from src.handlers import refresh_handlers
        src = inspect.getsource(refresh_handlers)
        assert re.search(
            r'failed_task_count = task_status_data\.get\("failed", 0\) \+ task_status_data\.get\("fail", 0\)',
            src,
        )


class TestInlineStatusFailCompat:
    """就地編輯狀態定位 + 表格渲染兼容歷史 "fail"。"""

    def test_status_key_normalization_used(self, qapp):
        import inspect
        from src.views.widgets import task_table as tt
        src = inspect.getsource(tt._TaskTable._edit_inline_status)
        # 定位循環必須兼容 task.status == "fail" → key == "failed"
        assert 'task.status == "fail" and key == "failed"' in src

    def test_status_render_normalizes_fail(self, qapp):
        import inspect
        from src.views.widgets import task_table as tt
        src = inspect.getsource(tt._TaskTable.set_tasks)
        assert '_status_key = "failed" if task.status == "fail" else task.status' in src

    def test_status_color_normalizes_fail(self, qapp):
        import inspect
        from src.views.widgets import task_table as tt
        src = inspect.getsource(tt._TaskTable.set_tasks)
        assert '_color_key = "failed" if task.status == "fail" else task.status' in src
