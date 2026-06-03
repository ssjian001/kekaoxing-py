"""软删除试点测试 — issues 表 is_deleted / deleted_at。

覆盖: v17 migration, list_all 过滤, soft_delete, restore, list_deleted, purge_old。
"""

from __future__ import annotations

import pytest
import apsw

from src.db.schema import init_schema, SCHEMA_VERSION
from src.db.repositories import IssueRepository
from src.services.issue_service import IssueService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def issue_svc(db_conn) -> IssueService:
    return IssueService(IssueRepository(db_conn))


@pytest.fixture()
def issue_repo(db_conn) -> IssueRepository:
    return IssueRepository(db_conn)


def _create_issue(svc: IssueService, title: str = "Test Issue", **kw) -> int:
    """创建一个 Issue，返回 ID。"""
    return svc.create(title=title, **kw)


# ═══════════════════════════════════════════════════════════════════
#  Schema v17 Migration
# ═══════════════════════════════════════════════════════════════════

class TestSchemaV17:
    def test_schema_version_is_17(self):
        assert SCHEMA_VERSION == 22

    def test_migration_adds_soft_delete_columns(self, db_conn):
        """v17 迁移后 issues 表应有 is_deleted 和 deleted_at 列。"""
        cols = {
            r[1]
            for r in db_conn.execute("PRAGMA table_info(issues)").fetchall()
        }
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_fresh_db_has_correct_version(self, db_conn):
        row = db_conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 22

    def test_upgrade_from_v16(self):
        """从 v16 数据库升级到 v17，列应正确添加。"""
        conn = apsw.Connection(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        # 手动构建 v16 schema（用 init_schema 然后回退版本号）
        init_schema(conn)
        # 模拟当前在 v16: 删除 v17 和 v18 记录
        conn.execute("DELETE FROM schema_version WHERE version >= 17")
        # 重新运行迁移
        from src.db.schema import _migrate_v17, _migrate_v18, _migrate_v19, _migrate_v20, _migrate_v21
        conn.execute("BEGIN")
        _migrate_v17(conn)
        _migrate_v18(conn)
        _migrate_v19(conn)
        _migrate_v20(conn)
        _migrate_v21(conn)
        conn.execute("COMMIT")
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(issues)").fetchall()
        }
        assert "is_deleted" in cols
        assert "deleted_at" in cols
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 21
        conn.close()

    def test_existing_data_has_default_values(self, db_conn):
        """已有数据的 is_deleted=0, deleted_at=''。"""
        repo = IssueRepository(db_conn)
        iid = repo.insert(title="Legacy Issue")
        issue = repo.get_by_id(iid)
        assert issue is not None
        assert issue.is_deleted == 0
        assert issue.deleted_at == ""


# ═══════════════════════════════════════════════════════════════════
#  list_all 过滤已删除
# ═══════════════════════════════════════════════════════════════════

class TestListAllFilter:
    def test_list_all_excludes_soft_deleted(self, issue_svc, issue_repo):
        id1 = _create_issue(issue_svc, "Keep")
        id2 = _create_issue(issue_svc, "Delete Me")
        issue_repo.soft_delete(id2)
        result = issue_svc.list_all()
        assert len(result) == 1
        assert result[0].id == id1

    def test_list_all_with_filter_still_excludes_deleted(self, issue_repo):
        id1 = issue_repo.insert(title="Open Issue", status="open")
        id2 = issue_repo.insert(title="Closed Issue", status="closed")
        issue_repo.soft_delete(id2)
        result = issue_repo.list_all(status="open")
        assert len(result) == 1
        assert result[0].id == id1

    def test_list_all_empty_after_all_deleted(self, issue_svc, issue_repo):
        id1 = _create_issue(issue_svc, "A")
        id2 = _create_issue(issue_svc, "B")
        issue_repo.soft_delete(id1)
        issue_repo.soft_delete(id2)
        assert issue_svc.list_all() == []


# ═══════════════════════════════════════════════════════════════════
#  soft_delete
# ═══════════════════════════════════════════════════════════════════

class TestSoftDelete:
    def test_soft_delete_marks_deleted(self, issue_repo):
        iid = issue_repo.insert(title="To Soft Delete")
        issue_repo.soft_delete(iid)
        issue = issue_repo.get_by_id(iid)
        assert issue is not None
        assert issue.is_deleted == 1
        assert issue.deleted_at != ""

    def test_soft_delete_sets_timestamp(self, issue_repo):
        iid = issue_repo.insert(title="Timestamp Test")
        issue_repo.soft_delete(iid)
        issue = issue_repo.get_by_iat(iid) if hasattr(issue_repo, "get_by_iat") else None
        # 直接查 DB
        row = issue_repo._conn.execute(
            "SELECT deleted_at FROM issues WHERE id = ?", (iid,)
        ).fetchone()
        assert row[0] != ""

    def test_soft_delete_via_service(self, issue_svc, issue_repo):
        iid = _create_issue(issue_svc, "Service Delete")
        issue_svc.soft_delete(iid)
        issue = issue_repo.get_by_id(iid)
        assert issue.is_deleted == 1


# ═══════════════════════════════════════════════════════════════════
#  list_deleted
# ═══════════════════════════════════════════════════════════════════

class TestListDeleted:
    def test_list_deleted_returns_only_soft_deleted(self, issue_repo):
        id1 = issue_repo.insert(title="Active")
        id2 = issue_repo.insert(title="Deleted")
        id3 = issue_repo.insert(title="Also Deleted")
        issue_repo.soft_delete(id2)
        issue_repo.soft_delete(id3)
        deleted = issue_repo.list_deleted()
        assert len(deleted) == 2
        assert {d.id for d in deleted} == {id2, id3}

    def test_list_deleted_empty_when_none(self, issue_repo):
        issue_repo.insert(title="Active")
        assert issue_repo.list_deleted() == []

    def test_list_deleted_via_service(self, issue_svc, issue_repo):
        id1 = _create_issue(issue_svc, "Gone")
        issue_svc.soft_delete(id1)
        deleted = issue_svc.list_deleted()
        assert len(deleted) == 1
        assert deleted[0].id == id1


# ═══════════════════════════════════════════════════════════════════
#  restore
# ═══════════════════════════════════════════════════════════════════

class TestRestore:
    def test_restore_clears_deleted_flag(self, issue_repo):
        iid = issue_repo.insert(title="Restore Me")
        issue_repo.soft_delete(iid)
        assert issue_repo.get_by_id(iid).is_deleted == 1

        issue_repo.restore(iid)
        issue = issue_repo.get_by_id(iid)
        assert issue.is_deleted == 0
        assert issue.deleted_at == ""

    def test_restore_appears_in_list_all(self, issue_repo):
        iid = issue_repo.insert(title="Restore Back")
        issue_repo.soft_delete(iid)
        assert len(issue_repo.list_all()) == 0

        issue_repo.restore(iid)
        assert len(issue_repo.list_all()) == 1

    def test_restore_via_service(self, issue_svc, issue_repo):
        iid = _create_issue(issue_svc, "Svc Restore")
        issue_svc.soft_delete(iid)
        issue_svc.restore(iid)
        assert issue_repo.get_by_id(iid).is_deleted == 0


# ═══════════════════════════════════════════════════════════════════
#  purge_old
# ═══════════════════════════════════════════════════════════════════

class TestPurgeOld:
    def test_purge_old_removes_expired(self, db_conn, issue_repo):
        iid = issue_repo.insert(title="Old Deleted")
        issue_repo.soft_delete(iid)
        # 手动把 deleted_at 改成 31 天前
        db_conn.execute(
            "UPDATE issues SET deleted_at = datetime('now','localtime','-31 days') "
            "WHERE id = ?",
            (iid,),
        )
        count = issue_repo.purge_old(days=30)
        assert count == 1
        assert issue_repo.get_by_id(iid) is None

    def test_purge_old_keeps_recent(self, db_conn, issue_repo):
        iid = issue_repo.insert(title="Recent Deleted")
        issue_repo.soft_delete(iid)
        # deleted_at 是刚刚设置的，不会超过 30 天
        count = issue_repo.purge_old(days=30)
        assert count == 0
        assert issue_repo.get_by_id(iid) is not None

    def test_purge_old_does_not_touch_active(self, db_conn, issue_repo):
        iid = issue_repo.insert(title="Active Issue")
        # 模拟一个很久的 deleted_at 但 is_deleted=0
        db_conn.execute(
            "UPDATE issues SET deleted_at = datetime('now','localtime','-60 days') "
            "WHERE id = ?",
            (iid,),
        )
        count = issue_repo.purge_old(days=30)
        assert count == 0
        assert issue_repo.get_by_id(iid) is not None

    def test_purge_old_via_service(self, db_conn, issue_svc, issue_repo):
        iid = _create_issue(issue_svc, "Purge Svc")
        issue_repo.soft_delete(iid)
        db_conn.execute(
            "UPDATE issues SET deleted_at = datetime('now','localtime','-40 days') "
            "WHERE id = ?",
            (iid,),
        )
        count = issue_svc.purge_old(days=30)
        assert count == 1


# ═══════════════════════════════════════════════════════════════════
#  原有测试不受影响
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    def test_normal_crud_unaffected(self, issue_svc):
        iid = _create_issue(issue_svc, "Normal")
        issue = issue_svc.get(iid)
        assert issue is not None
        assert issue.title == "Normal"
        assert issue.is_deleted == 0
        assert issue.deleted_at == ""

        issue_svc.update(iid, title="Updated")
        issue = issue_svc.get(iid)
        assert issue.title == "Updated"

    def test_list_all_returns_normal_issues(self, issue_svc):
        _create_issue(issue_svc, "A")
        _create_issue(issue_svc, "B")
        assert len(issue_svc.list_all()) == 2

    def test_get_by_id_still_works_for_deleted(self, issue_svc, issue_repo):
        """get_by_id 仍能获取已软删除的 Issue（不过 list_all 不返回）。"""
        iid = _create_issue(issue_svc, "Hidden")
        issue_repo.soft_delete(iid)
        issue = issue_svc.get(iid)
        assert issue is not None
        assert issue.is_deleted == 1
        assert issue not in issue_svc.list_all()


# ── SoftDeleteCommand undo 测试 ──────────────────────────────


class TestSoftDeleteCommand:
    """SoftDeleteCommand 通过 UndoManager 执行后可撤销/重做。"""

    def test_soft_delete_command_undo(self, issue_repo, issue_svc):
        from src.services.undo_manager import SoftDeleteCommand, UndoManager

        iid = _create_issue(issue_svc, "Undoable")
        mgr = UndoManager()

        cmd = SoftDeleteCommand(issue_repo, iid, "Issue")
        mgr.execute(cmd)

        # 已软删除
        assert issue_repo.get_by_id(iid).is_deleted == 1
        assert len(issue_repo.list_all()) == 0

        # 撤销
        mgr.undo()
        issue = issue_repo.get_by_id(iid)
        assert issue.is_deleted == 0
        assert len(issue_repo.list_all()) == 1

    def test_soft_delete_command_redo(self, issue_repo, issue_svc):
        from src.services.undo_manager import SoftDeleteCommand, UndoManager

        iid = _create_issue(issue_svc, "Redoable")
        mgr = UndoManager()

        cmd = SoftDeleteCommand(issue_repo, iid, "Issue")
        mgr.execute(cmd)
        mgr.undo()

        # 重做
        mgr.redo()
        assert issue_repo.get_by_id(iid).is_deleted == 1
        assert len(issue_repo.list_all()) == 0
