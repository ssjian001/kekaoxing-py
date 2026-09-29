"""KPI 自检 audit_dashboard_data 单元测试。"""
from dataclasses import dataclass, field
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from src.services.kpi_audit import audit_dashboard_data


@dataclass
class FakeDash:
    task_total: int = 10
    task_completed: int = 4
    task_in_progress: int = 2
    task_pending: int = 2
    task_skipped: int = 1
    task_paused: int = 1
    failed_task_count: int = 0
    task_done: int = 4
    pass_count: int = 3
    fail_count: int = 1
    issue_count: int = 5
    issue_closed_count: int = 3
    weekly_closed: int = 2
    pass_rate: float = 75.0
    issue_severity_data: dict = field(default_factory=dict)


def test_ok():
    assert audit_dashboard_data(FakeDash()) == []


def test_sum_mismatch():
    d = FakeDash(task_pending=3)  # 求和 11 != 10
    ps = audit_dashboard_data(d)
    assert any("求和" in p for p in ps), ps


def test_done_mismatch():
    d = FakeDash(task_done=7)  # done != completed+failed
    assert any("task_done" in p for p in audit_dashboard_data(d))


def test_done_gt_total():
    d = FakeDash(task_done=11)
    assert audit_dashboard_data(d)


def test_negative_counts():
    d = FakeDash(pass_count=-1)
    assert any("负" in p for p in audit_dashboard_data(d))


def test_closed_gt_total():
    d = FakeDash(issue_closed_count=6)
    assert any("closed" in p for p in audit_dashboard_data(d))


def test_weekly_gt_closed():
    d = FakeDash(weekly_closed=4)
    assert any("weekly_closed" in p for p in audit_dashboard_data(d))


def test_pass_rate_out_of_range():
    d = FakeDash(pass_rate=150.0)
    assert any("pass_rate" in p for p in audit_dashboard_data(d))


def test_none_safe():
    assert audit_dashboard_data(None) == []
    assert audit_dashboard_data(object()) == []


# ── 回归: 真实生产数据载体必须被检查 ──────────────────────────────
# 历史盲区: 上面的 FakeDash 是 @dataclass, 而生产 DashboardData 是
# __slots__ 普通类。旧守卫 `if not is_dataclass(d): return []` 让哨兵
# 在生产侧永远空转, 而全部单测基于 FakeDash 仍然全绿 → 掩盖了问题。

def test_real_dashboard_data_is_checked():
    """真实 DashboardData(非 dataclass) 必须真正进入检查逻辑。"""
    from src.views.dashboard_view import DashboardData

    # 违规样本: 状态求和 != total, closed > total, pass_rate 出界
    bad = DashboardData(
        task_total=10, task_completed=3, task_in_progress=2, task_pending=1,
        task_skipped=0, task_paused=0, failed_task_count=1,
        issue_count=5, issue_closed_count=9,
        pass_count=4, fail_count=2, pass_rate=150.0,
    )
    problems = audit_dashboard_data(bad)
    assert problems, "真实 DashboardData 未被检查(守卫生效了但对象被拒收)"
    assert any("pass_rate" in p for p in problems)
    assert any("closed" in p for p in problems)


def test_real_dashboard_data_clean_passes():
    """真实 DashboardData 一致时不得误报。"""
    from src.views.dashboard_view import DashboardData

    good = DashboardData(
        task_total=6, task_completed=3, task_in_progress=1, task_pending=2,
        task_skipped=0, task_paused=0, failed_task_count=0,
        issue_count=5, issue_closed_count=2,
        pass_count=4, fail_count=2, pass_rate=66.7,
    )
    assert audit_dashboard_data(good) == []
