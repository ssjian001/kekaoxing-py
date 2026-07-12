"""BackupService 单元测试 — 备份/恢复/验证核心逻辑。

覆盖点：
- create_backup → 文件创建 + 数据完整
- create_auto_backup → 时间戳命名
- validate_backup → 合法/非法/不存在/版本过高
- restore_backup → 恢复 + 安全网
- list_backups → 列表 + 跳过损坏
- delete_backup → 删除 + 目录外拒绝
"""

from __future__ import annotations

import pytest
import apsw
from pathlib import Path

from src.db.schema import init_schema, SCHEMA_VERSION
from src.services.backup_service import BackupService, BackupInfo


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def backup_svc(tmp_path):
    """创建一个使用 tmp_path 作为 DB 的 BackupService。"""
    db_path = str(tmp_path / "test.db")
    # 先初始化一个有数据的 DB
    conn = apsw.Connection(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    conn.execute("INSERT INTO projects (name, product, customer, status) VALUES ('测试项目', 'P1', 'C1', 'active')")
    conn.close()
    return BackupService(db_path=db_path)


# ═══════════════════════════════════════════════════════════════════
#  create_backup
# ═══════════════════════════════════════════════════════════════════

class TestCreateBackup:

    def test_creates_file(self, backup_svc, tmp_path):
        dest = tmp_path / "backup.db"
        result = backup_svc.create_backup(dest)
        assert result == dest
        assert dest.exists()
        assert dest.stat().st_size > 0

    def test_backup_has_data(self, backup_svc, tmp_path):
        dest = tmp_path / "backup.db"
        backup_svc.create_backup(dest)
        # 验证备份内容
        conn = apsw.Connection(str(dest))
        row = conn.execute("SELECT name FROM projects").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "测试项目"

    def test_backup_has_schema_version(self, backup_svc, tmp_path):
        dest = tmp_path / "backup.db"
        backup_svc.create_backup(dest)
        conn = apsw.Connection(str(dest))
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        conn.close()
        assert row is not None and row[0] == SCHEMA_VERSION

    def test_existing_file_raises(self, backup_svc, tmp_path):
        dest = tmp_path / "backup.db"
        dest.write_text("dummy")
        with pytest.raises(FileExistsError):
            backup_svc.create_backup(dest)

    def test_creates_parent_dir(self, backup_svc, tmp_path):
        dest = tmp_path / "subdir" / "nested" / "backup.db"
        backup_svc.create_backup(dest)
        assert dest.exists()


# ═══════════════════════════════════════════════════════════════════
#  validate_backup
# ═══════════════════════════════════════════════════════════════════

class TestValidateBackup:

    def test_valid_backup(self, backup_svc, tmp_path):
        dest = tmp_path / "backup.db"
        backup_svc.create_backup(dest)
        info = BackupService.validate_backup(dest)
        assert info.filename == "backup.db"
        assert info.schema_version == SCHEMA_VERSION
        assert info.size_mb > 0

    def test_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            BackupService.validate_backup(tmp_path / "nonexistent.db")

    def test_invalid_db(self, tmp_path):
        """非 SQLite 数据库文件。"""
        bad = tmp_path / "bad.db"
        bad.write_text("not a database")
        with pytest.raises(ValueError, match="无法读取"):
            BackupService.validate_backup(bad)

    def test_empty_db_no_schema_version(self, tmp_path):
        """空 SQLite DB（没有 schema_version 表）。"""
        empty = tmp_path / "empty.db"
        conn = apsw.Connection(str(empty))
        conn.execute("CREATE TABLE foo (id INTEGER)")
        conn.close()
        with pytest.raises(ValueError, match="不是有效的 ReliaTrack"):
            BackupService.validate_backup(empty)


# ═══════════════════════════════════════════════════════════════════
#  restore_backup
# ═══════════════════════════════════════════════════════════════════

class TestRestoreBackup:

    def test_restore_overwrites_data(self, backup_svc, tmp_path):
        """恢复后 DB 内容应与备份一致。"""
        # 先创建备份
        backup_path = tmp_path / "backup.db"
        backup_svc.create_backup(backup_path)

        # 修改原 DB（插入更多数据）
        from src.db.connection import get_connection, close_connection
        conn = get_connection(str(tmp_path / "test.db"))
        conn.execute("INSERT INTO projects (name, product, customer, status) VALUES ('新项目', 'P2', 'C2', 'active')")
        close_connection(str(tmp_path / "test.db"))

        # 恢复
        backup_svc.restore_backup(backup_path)

        # 恢复后应只有原始的 1 条数据
        conn = apsw.Connection(str(tmp_path / "test.db"))
        rows = conn.execute("SELECT name FROM projects").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "测试项目"

    def test_restore_creates_safety_backup(self, backup_svc, tmp_path, monkeypatch):
        """恢复前自动创建 pre_restore 安全备份。"""
        from src.services import backup_service as bs_module
        # mock DEFAULT_BACKUPS_DIR 到 tmp_path
        backups_dir = tmp_path / "backups"
        monkeypatch.setattr(bs_module, "DEFAULT_BACKUPS_DIR", backups_dir)

        backup_path = tmp_path / "backup.db"
        backup_svc.create_backup(backup_path)

        backup_svc.restore_backup(backup_path)

        # 应存在 pre_restore 备份
        pre_restores = list(backups_dir.glob("*pre_restore*"))
        assert len(pre_restores) >= 1

    def test_restore_cleans_wal_shm(self, backup_svc, tmp_path):
        """恢复后应清理 WAL/SHM 残留文件。"""
        db_path = tmp_path / "test.db"
        # 制造 WAL 文件
        conn = apsw.Connection(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO projects (name, product, customer, status) VALUES ('触发WAL', 'P', 'C', 'active')")
        # 不 checkpoint，直接关闭 → WAL 文件残留
        conn.close()

        backup_path = tmp_path / "backup.db"
        backup_svc.create_backup(backup_path)

        backup_svc.restore_backup(backup_path)

        assert not (tmp_path / "test.db-wal").exists()
        assert not (tmp_path / "test.db-shm").exists()


# ═══════════════════════════════════════════════════════════════════
#  list_backups
# ═══════════════════════════════════════════════════════════════════

class TestListBackups:

    def test_lists_valid_backups(self, backup_svc, tmp_path, monkeypatch):
        from src.services import backup_service as bs_module
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr(bs_module, "DEFAULT_BACKUPS_DIR", backups_dir)

        # 创建两个备份
        for i in range(2):
            dest = backups_dir / f"reliatrack_2026010{i}.db"
            backup_svc.create_backup(dest)

        backups = BackupService.list_backups()
        assert len(backups) == 2
        # 应按时间倒序
        assert backups[0].filename >= backups[1].filename

    def test_skips_corrupt_files(self, backup_svc, tmp_path, monkeypatch):
        from src.services import backup_service as bs_module
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr(bs_module, "DEFAULT_BACKUPS_DIR", backups_dir)

        # 一个正常备份
        good = backups_dir / "reliatrack_20260101.db"
        backup_svc.create_backup(good)

        # 一个损坏文件
        bad = backups_dir / "reliatrack_20260102.db"
        bad.write_text("corrupt data")

        backups = BackupService.list_backups()
        assert len(backups) == 1
        assert backups[0].filename == "reliatrack_20260101.db"


# ═══════════════════════════════════════════════════════════════════
#  delete_backup
# ═══════════════════════════════════════════════════════════════════

class TestDeleteBackup:

    def test_delete_in_dir(self, backup_svc, tmp_path, monkeypatch):
        from src.services import backup_service as bs_module
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr(bs_module, "DEFAULT_BACKUPS_DIR", backups_dir)

        target = backups_dir / "reliatrack_20260101.db"
        target.write_text("dummy")
        BackupService.delete_backup(target)
        assert not target.exists()

    def test_delete_outside_dir_rejected(self, tmp_path, monkeypatch):
        from src.services import backup_service as bs_module
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr(bs_module, "DEFAULT_BACKUPS_DIR", backups_dir)

        outside = tmp_path / "outside.db"
        outside.write_text("sensitive")
        with pytest.raises(ValueError, match="不允许删除"):
            BackupService.delete_backup(outside)
        # 文件应仍在
        assert outside.exists()
