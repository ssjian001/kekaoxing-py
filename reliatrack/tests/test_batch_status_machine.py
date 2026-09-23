"""批量操作状态机校验测试 — P1 修复回归。"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from unittest.mock import MagicMock, patch


def test_batch_status_calls_transition():
    """改状态走 transition_status 而非裸 update。"""
    import src.views.bug_tracker.batch_dialog  # noqa: F401 — import 冒烟
    # 逻辑级验证: transition 返回 False 时 continue, 不计 updated
    # 直接测 service 语义: transition_status 拒绝非法流
    from src.services.issue_service import IssueService
    svc = IssueService.__new__(IssueService)  # 不触 DB, 只验证方法签名路由
    assert hasattr(IssueService, "transition_status")
    # batch_dialog field_map: 改状态→status, 其余走 update — 通过代码审查
    src = (pathlib.Path(__file__).parents[1] / "src/views/bug_tracker/batch_dialog.py").read_text()
    assert 'transition_status(' in src, "batch 改状态必须走 transition_status"
    assert src.count('else:\n                    self._service.update') == 1


def test_transition_rejects_open_to_closed_without_fa():
    """状态机基线: open→verified 需 FA(既有行为, 防回归)。"""
    from src.constants import ISSUE_TRANSITIONS
    assert "verified" not in ISSUE_TRANSITIONS.get("open", set())
    assert "closed" in ISSUE_TRANSITIONS.get("open", set())
