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
