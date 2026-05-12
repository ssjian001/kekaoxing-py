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


# ═══════════════════════════════════════════════════════════════════
#  6. 全路径状态转换覆盖
# ═══════════════════════════════════════════════════════════════════

class TestAllTransitionPaths:
    """参数化测试 ISSUE_TRANSITIONS 中所有合法路径。"""

    @pytest.mark.parametrize("from_status,to_status", [
        ("open", "analyzing"),
        ("open", "closed"),
        ("analyzing", "open"),
        ("analyzing", "verified"),
        ("analyzing", "closed"),
        ("verified", "open"),
        ("verified", "closed"),
        ("closed", "open"),
    ])
    def test_legal_transition(self, db_conn, from_status, to_status):
        """合法转换 from→to 成功执行。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")
        # 先推到 from_status
        path_to = _path_to_status(from_status)
        for s in path_to:
            svc.update(iid, status=s)
        assert svc.get(iid).status == from_status

        svc.update(iid, status=to_status)
        assert svc.get(iid).status == to_status

    def test_open_to_closed_direct(self, db_conn):
        """open→closed 直接关闭（跳过 analyzing/verified）。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")
        svc.update(iid, status="closed")
        assert svc.get(iid).status == "closed"

    def test_analyzing_to_open_rollback(self, db_conn):
        """analyzing→open 回退到待处理。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")
        svc.update(iid, status="analyzing")
        svc.update(iid, status="open")
        assert svc.get(iid).status == "open"

    def test_analyzing_to_closed(self, db_conn):
        """analyzing→closed 直接关闭。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")
        svc.update(iid, status="analyzing")
        svc.update(iid, status="closed")
        assert svc.get(iid).status == "closed"


def _path_to_status(target: str) -> list[str]:
    """返回从 open 到达 target 状态的最短路径。"""
    paths = {
        "open": [],
        "analyzing": ["analyzing"],
        "verified": ["analyzing", "verified"],
        "closed": ["analyzing", "verified", "closed"],
    }
    return paths.get(target, [])


class _no_warning:
    """Context manager: no-op fallback for pytest.warns."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


# ═══════════════════════════════════════════════════════════════════
#  7. FA/CAPA 联动不受 ISSUE_TRANSITIONS 限制
# ═══════════════════════════════════════════════════════════════════

class TestFACAPABypassTransitions:
    """FA/CAPA 自动状态推进绕过 ISSUE_TRANSITIONS 规则。"""

    def test_fa_auto_push_open_to_analyzing(self, db_conn, caplog):
        """添加 FA 记录后 Issue 自动从 open→analyzing（无需经过转换规则）。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")

        # 模拟 FA 联动：直接 update 状态（实际由 handler 调用）
        # 此处验证 service 层不阻断自动转换
        with caplog.at_level(logging.WARNING, logger="src.services.issue_service"):
            svc.update(iid, status="analyzing")

        # open→analyzing 是合法转换，不应有 warning
        assert not any("not in allowed set" in r.message for r in caplog.records)
        assert svc.get(iid).status == "analyzing"

    def test_capa_auto_push_analyzing_to_verified(self, db_conn, caplog):
        """全部 CAPA 完成后 Issue 自动从 analyzing→verified。"""
        svc = _make_service(db_conn)
        iid = _create_issue(svc, status="open")
        svc.update(iid, status="analyzing")

        # 模拟 CAPA 联动：直接 update 到 verified
        with caplog.at_level(logging.WARNING, logger="src.services.issue_service"):
            svc.update(iid, status="verified")

        # analyzing→verified 是合法转换，不应有 warning
        assert not any("not in allowed set" in r.message for r in caplog.records)
        assert svc.get(iid).status == "verified"
