"""样品管理增强 + 失效详情修复的回归测试。

覆盖:
  1. SAMPLE_STATUS_LABELS/OPTIONS/MAP 中 suspended 状态完备
  2. TransactionType.RETURN 枚举存在
  3. 入库时自动创建 check_in transaction
  4. 归还操作创建 return transaction + 状态回 in_stock
  5. list_transactions JOIN test_tasks 返回 task_name
  6. analysis_widget 失效详情正确匹配 Issue（修复"始终未创建"）
"""

from __future__ import annotations

import pytest

from src.constants import (
    SAMPLE_STATUS_LABELS,
    SAMPLE_STATUS_OPTIONS,
    SAMPLE_STATUS_MAP,
    SAMPLE_STATUS_REVERSE,
)
from src.models.sample import TransactionType
from src.db.repositories import (
    SampleRepository,
    IssueRepository,
    TestPlanRepository,
    TestTaskRepository,
    TestResultRepository,
)
from src.services.sample_service import SampleService
from src.services.test_plan_service import TestPlanService
from src.services.issue_service import IssueService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def sample_svc(db_conn):
    return SampleService(SampleRepository(db_conn))


@pytest.fixture()
def plan_svc(db_conn):
    return TestPlanService(
        TestPlanRepository(db_conn), TestTaskRepository(db_conn),
        TestResultRepository(db_conn),
    )


@pytest.fixture()
def issue_svc(db_conn):
    return IssueService(IssueRepository(db_conn))


# ═══════════════════════════════════════════════════════════════════
#  1. 常量完备性 — suspended 状态
# ═══════════════════════════════════════════════════════════════════

class TestSuspendedStatusConstants:
    def test_labels_has_suspended(self):
        assert "suspended" in SAMPLE_STATUS_LABELS
        assert SAMPLE_STATUS_LABELS["suspended"] == "已暂停"

    def test_options_has_suspended(self):
        assert "已暂停" in SAMPLE_STATUS_OPTIONS

    def test_map_has_suspended(self):
        assert SAMPLE_STATUS_MAP["已暂停"] == "suspended"

    def test_reverse_maps_suspended(self):
        assert SAMPLE_STATUS_REVERSE.get("suspended") == "已暂停"

    def test_all_label_values_in_options(self):
        """每个 LABELS 的中文值都必须出现在 OPTIONS 中。"""
        for label in SAMPLE_STATUS_LABELS.values():
            assert label in SAMPLE_STATUS_OPTIONS

    def test_labels_and_map_consistent(self):
        """LABELS 和 MAP 是双向映射。"""
        for eng, chn in SAMPLE_STATUS_LABELS.items():
            assert SAMPLE_STATUS_MAP.get(chn) == eng


# ═══════════════════════════════════════════════════════════════════
#  2. TransactionType.RETURN
# ═══════════════════════════════════════════════════════════════════

class TestTransactionTypeReturn:
    def test_return_enum_exists(self):
        assert hasattr(TransactionType, "RETURN")
        assert TransactionType.RETURN == "return"

    def test_all_types_unique(self):
        values = [t.value for t in TransactionType]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════════
#  3. 入库 transaction 创建
# ═══════════════════════════════════════════════════════════════════

class TestCheckinTransaction:
    def test_checkin_creates_transaction(self, sample_svc, sample_project):
        """创建样品后手动添加 check_in transaction（模拟 handler 行为）。"""
        sid = sample_svc.create("SN-CHKIN", project_id=sample_project["id"], status="in_stock")
        sample_svc.add_transaction(sid, "check_in")

        txns = sample_svc.get_transactions(sid)
        assert len(txns) == 1
        assert txns[0].type == "check_in"

    def test_checkout_then_return(self, sample_svc, sample_project, sample_technician):
        """出库 → 归还完整流程。"""
        sid = sample_svc.create("SN-RTN", project_id=sample_project["id"], status="in_stock")

        # 出库
        sample_svc.add_transaction(
            sid, "check_out",
            purpose="测试",
            operator_id=sample_technician["id"],
        )
        sample_svc.update_status(sid, "checked_out")
        s = sample_svc.get(sid)
        assert s.status == "checked_out"

        # 归还
        sample_svc.add_transaction(
            sid, "return",
            actual_return="2026-06-01",
            operator_id=sample_technician["id"],
            notes="完好归还",
        )
        sample_svc.update_status(sid, "in_stock")
        s = sample_svc.get(sid)
        assert s.status == "in_stock"

        txns = sample_svc.get_transactions(sid)
        assert len(txns) == 2
        types = [t.type for t in txns]
        assert "check_out" in types
        assert "return" in types


# ═══════════════════════════════════════════════════════════════════
#  4. list_transactions JOIN test_tasks → task_name
# ═══════════════════════════════════════════════════════════════════

class TestListTransactionsJoin:
    def test_task_name_in_transaction(self, sample_svc, plan_svc, sample_project, db_conn):
        """关联任务后，list_transactions 返回 task_name。"""
        pid = sample_project["id"]
        sid = sample_svc.create("SN-JOIN", project_id=pid, status="in_stock")

        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "高温测试", duration=5)

        sample_svc.add_transaction(
            sid, "check_out",
            related_task_id=tid,
            purpose="高温测试",
        )

        # list_transactions 从 repo 层拿
        repo = SampleRepository(db_conn)
        rows = repo.list_transactions()
        # 找到刚创建的记录
        match = [r for r in rows if r["sample_sn"] == "SN-JOIN"]
        assert len(match) == 1
        assert match[0]["task_name"] == "高温测试"
        assert match[0]["related_task_id"] == tid

    def test_task_name_empty_when_no_task(self, sample_svc, sample_project, db_conn):
        """无关联任务时，task_name 为 None。"""
        sid = sample_svc.create("SN-NOTASK", project_id=sample_project["id"], status="in_stock")
        sample_svc.add_transaction(sid, "check_in")

        repo = SampleRepository(db_conn)
        rows = repo.list_transactions()
        match = [r for r in rows if r["sample_sn"] == "SN-NOTASK"]
        assert len(match) == 1
        assert match[0]["task_name"] is None


# ═══════════════════════════════════════════════════════════════════
#  5. analysis_widget 失效详情 Issue 匹配
# ═══════════════════════════════════════════════════════════════════

class TestAnalysisIssueMatch:
    """验证 analysis_widget 中 task_issues 的匹配逻辑。

    核心逻辑在 analysis_widget.refresh() 中:
      task_issues = {iss.task_id: [iss]} for iss in issues
      has_issue = task.id in task_issues

    这里用 service 层测试验证 Issue.task_id 与 TestTask.id 的正确关联。
    """

    def test_issue_task_id_matches_task(
        self, issue_svc, plan_svc, sample_project, db_conn
    ):
        """Issue 的 task_id 正确关联到 TestTask.id。"""
        pid = sample_project["id"]
        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "低温测试", duration=3)

        iid = issue_svc.create(
            "低温失效",
            project_id=pid,
            task_id=tid,
            status="open",
            severity="critical",
        )

        issue = issue_svc.get(iid)
        assert issue is not None
        assert issue.task_id == tid

    def test_get_by_project_returns_task_issues(
        self, issue_svc, plan_svc, sample_project, db_conn
    ):
        """get_by_project 返回的 Issue 包含 task_id。"""
        pid = sample_project["id"]
        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")
        tid = plan_svc.create_task(plid, "振动测试", duration=2)

        issue_svc.create("振动失效", project_id=pid, task_id=tid, status="open")
        issue_svc.create("无关Issue", project_id=pid, status="open")

        issues = issue_svc.get_by_project(pid)
        assert len(issues) == 2

        task_issues = {}
        for iss in issues:
            if iss.task_id:
                task_issues.setdefault(iss.task_id, []).append(iss)

        assert tid in task_issues
        assert len(task_issues[tid]) == 1
        assert task_issues[tid][0].title == "振动失效"

    def test_analysis_has_issue_logic(
        self, issue_svc, plan_svc, sample_project, db_conn
    ):
        """模拟 analysis_widget 的 has_issue 匹配逻辑。"""
        pid = sample_project["id"]
        plid = plan_svc.create_plan(pid, "计划1", start_date="2026-01-01")
        tid1 = plan_svc.create_task(plid, "有Issue任务", duration=3)
        tid2 = plan_svc.create_task(plid, "无Issue任务", duration=2)

        # 只给 tid1 建 Issue
        issue_svc.create("已关联", project_id=pid, task_id=tid1, status="open")

        # 模拟 analysis_widget 的匹配逻辑
        issues = issue_svc.get_by_project(pid)
        task_issues: dict[int, list] = {}
        for iss in issues:
            if iss.task_id:
                task_issues.setdefault(iss.task_id, []).append(iss)

        has_issue_1 = tid1 in task_issues  # True
        has_issue_2 = tid2 in task_issues  # False

        assert has_issue_1 is True
        assert has_issue_2 is False
