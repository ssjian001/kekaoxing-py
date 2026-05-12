"""Issue Jira-style 工作流测试 — 枚举、状态转换、Resolution/Reporter CRUD、Schema 迁移。"""

from __future__ import annotations

import logging

import pytest

from src.models.issue import Issue, IssueResolution
from src.constants import RESOLUTION_OPTIONS, RESOLUTION_LABELS, ISSUE_TRANSITIONS
from src.db.repositories.issue_repo import IssueRepository
from src.services.issue_service import IssueService


# ── helper ──────────────────────────────────────────────────────────

def _make_service(db_conn):
    """构造 IssueService(IssueRepository(db_conn))。"""
    return IssueService(IssueRepository(db_conn))


def _create_issue(service: IssueService, **overrides) -> int:
    """创建一条 Issue 并返回 id。"""
    defaults = dict(title="测试问题")
    defaults.update(overrides)
    return service.create(**defaults)


# ═══════════════════════════════════════════════════════════════════
#  1. IssueResolution 枚举
# ═══════════════════════════════════════════════════════════════════

class TestIssueResolutionEnum:
    """IssueResolution 枚举值校验。"""

    def test_all_enum_values_valid(self):
        """所有枚举值都在预期集合中。"""
        expected = {"", "fixed", "wont_fix", "duplicate",
                    "cannot_reproduce", "not_an_issue"}
        actual = {m.value for m in IssueResolution}
        assert actual == expected

    def test_invalid_value_not_in_enum(self):
        """无效字符串不属于枚举成员。"""
        valid_values = {m.value for m in IssueResolution}
        assert "bogus_resolution" not in valid_values


# ═══════════════════════════════════════════════════════════════════
#  2. 状态转换校验
# ═══════════════════════════════════════════════════════════════════

class TestStatusTransitions:
    """ISSUE_TRANSITIONS 规则 + IssueService.update() 行为。"""

    def test_legal_transitions(self, db_conn):
        """合法转换链：open → analyzing → verified → closed。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")

        # open → analyzing
        svc.update(iid, status="analyzing")
        assert svc.get(iid).status == "analyzing"

        # analyzing → verified
        svc.update(iid, status="verified")
        assert svc.get(iid).status == "verified"

        # verified → closed
        svc.update(iid, status="closed")
        assert svc.get(iid).status == "closed"

    def test_illegal_transition_logs_warning(self, db_conn, caplog):
        """非法转换 open→verified 不抛异常，但 logger.warning。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")

        with caplog.at_level(logging.WARNING, logger="src.services.issue_service"):
            svc.update(iid, status="verified")

        # 状态仍然被更新（不阻断）
        assert svc.get(iid).status == "verified"
        # 有 warning 日志
        assert any("not in allowed set" in r.message for r in caplog.records)

    def test_reopen_clears_resolution(self, db_conn):
        """closed → open 时 resolution 自动清空。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")

        # 推进到 closed 并设置 resolution
        svc.update(iid, status="analyzing")
        svc.update(iid, status="verified")
        svc.update(iid, status="closed", resolution="fixed")
        assert svc.get(iid).resolution == "fixed"

        # reopen → resolution 清空
        svc.update(iid, status="open")
        issue = svc.get(iid)
        assert issue.status == "open"
        assert issue.resolution == ""

    def test_verified_to_open_clears_resolution(self, db_conn):
        """verified → open 时 resolution 自动清空。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")

        svc.update(iid, status="analyzing")
        svc.update(iid, status="verified", resolution="wont_fix")
        assert svc.get(iid).resolution == "wont_fix"

        svc.update(iid, status="open")
        issue = svc.get(iid)
        assert issue.status == "open"
        assert issue.resolution == ""


# ═══════════════════════════════════════════════════════════════════
#  3. Resolution CRUD
# ═══════════════════════════════════════════════════════════════════

class TestResolutionCRUD:
    """Resolution 字段的创建 / 更新 / 标签映射。"""

    def test_create_with_resolution(self, db_conn):
        """创建 Issue 时可以指定 resolution。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, resolution="fixed")
        assert svc.get(iid).resolution == "fixed"

    def test_update_resolution(self, db_conn):
        """更新 Issue 的 resolution。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc)
        assert svc.get(iid).resolution == ""

        svc.update(iid, resolution="duplicate")
        assert svc.get(iid).resolution == "duplicate"

    def test_resolution_labels_mapping(self):
        """RESOLUTION_LABELS 正确映射英文→中文。"""
        assert RESOLUTION_LABELS == {
            "": "未解决",
            "fixed": "已修复",
            "wont_fix": "不修复",
            "duplicate": "重复",
            "cannot_reproduce": "无法复现",
            "not_an_issue": "非问题",
        }


# ═══════════════════════════════════════════════════════════════════
#  4. Reporter 字段
# ═══════════════════════════════════════════════════════════════════

class TestReporterField:
    """reporter_name 字段的创建与更新。"""

    def test_create_with_reporter(self, db_conn):
        """创建 Issue 时可以指定 reporter_name。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, reporter_name="张三")
        assert svc.get(iid).reporter_name == "张三"

    def test_update_reporter(self, db_conn):
        """更新 Issue 的 reporter_name。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc)
        assert svc.get(iid).reporter_name == ""

        svc.update(iid, reporter_name="李四")
        assert svc.get(iid).reporter_name == "李四"


# ═══════════════════════════════════════════════════════════════════
#  5. Schema v18 迁移
# ═══════════════════════════════════════════════════════════════════

class TestSchemaV18Migration:
    """init_schema 后 issues 表包含 resolution 和 reporter_name 列。"""

    def test_issues_table_has_resolution_and_reporter(self, db_conn):
        """issues 表有 resolution 和 reporter_name 列。"""
        rows = db_conn.execute("PRAGMA table_info(issues)").fetchall()
        col_names = {row[1] for row in rows}  # row[1] 是列名
        assert "resolution" in col_names
        assert "reporter_name" in col_names
