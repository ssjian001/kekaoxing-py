"""tests/test_auto_save.py — 自动保存与快照测试。"""
import os
import json
import tempfile


class TestAutoSaveManager:
    def test_create_manager(self):
        """AutoSaveManager can be created with a db_path."""
        from src.core.auto_save import AutoSaveManager
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            # Create a dummy db file first
            with open(db_path, "w") as f:
                f.write("")
            mgr = AutoSaveManager(db_path)
            assert str(mgr.db_path) == db_path
            assert mgr.bak_path.name.endswith(".db.bak")

    def test_snapshot_lifecycle(self, tmp_path):
        """Create snapshot → verify file exists and is valid SQLite."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        db = Database(db_path)

        # Write data
        db.insert_task(Task(id=0, num="1", name_en="Snapshot Test",
                            name_cn="快照测试",
                            section=Section.ENV, duration=5, start_day=0))
        assert db.task_count() == 1

        # Close DB connection so WAL data is visible to snapshot
        db.conn.close()

        # Create snapshot
        mgr = AutoSaveManager(db_path)
        snap_path = mgr.create_snapshot("test snapshot")
        assert os.path.exists(snap_path)

        # Verify snapshot file is a valid SQLite with the data
        import apsw
        snap_conn = apsw.Connection(snap_path)
        rows = snap_conn.execute("SELECT name_cn FROM tasks").fetchall()
        snap_conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "快照测试"

        # List snapshots
        snapshots = mgr.list_snapshots()
        assert len(snapshots) >= 1
        assert any(s["path"] == snap_path for s in snapshots)

    def test_restore_snapshot(self, tmp_path):
        """Restore a snapshot and verify the DB file is replaced."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        db = Database(db_path)
        db.insert_task(Task(id=0, num="1", name_en="Original",
                            name_cn="原始", section=Section.ENV, duration=5, start_day=0))
        db.conn.close()  # flush WAL

        mgr = AutoSaveManager(db_path)
        snap_path = mgr.create_snapshot("before change")

        # Overwrite DB with different data
        db2 = Database(db_path)
        db2.conn.execute("DELETE FROM tasks")
        db2.insert_task(Task(id=0, num="2", name_en="Changed",
                             name_cn="已修改", section=Section.MECH, duration=3, start_day=0))
        db2.conn.close()  # explicitly close to flush WAL

        # Restore
        success = mgr.restore_snapshot(snap_path)
        assert success is True

        # Verify restored content
        db3 = Database(db_path)
        tasks = db3.get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].name_cn == "原始"
        assert tasks[0].section == "env"

    def test_max_snapshots(self, tmp_path):
        """Should not exceed MAX_SNAPSHOTS after creating many."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        Database(db_path)  # Create empty DB
        mgr = AutoSaveManager(db_path)

        # Create more than MAX_SNAPshots (10) snapshots
        for i in range(15):
            mgr.create_snapshot(f"snapshot {i}")

        snapshots = mgr.list_snapshots()
        # Should be at most MAX_SNAPSHOTS (10)
        assert len(snapshots) <= 10

    def test_check_crash_recovery_no_backup(self, tmp_path):
        """No .bak file → recovery returns None."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        Database(db_path)
        mgr = AutoSaveManager(db_path)

        result = mgr.check_crash_recovery()
        assert result is None

    def test_list_snapshots_empty(self, tmp_path):
        """Empty snapshot directory returns empty list."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        Database(db_path)
        mgr = AutoSaveManager(db_path)

        snapshots = mgr.list_snapshots()
        assert snapshots == []

    def test_restore_nonexistent_snapshot(self, tmp_path):
        """Restoring from nonexistent path returns False."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        Database(db_path)
        mgr = AutoSaveManager(db_path)

        success = mgr.restore_snapshot("/nonexistent/path.db")
        assert success is False

    def test_snapshot_metadata_fields(self, tmp_path):
        """Snapshot metadata should have expected fields."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        Database(db_path)
        mgr = AutoSaveManager(db_path)

        mgr.create_snapshot("my label")
        snapshots = mgr.list_snapshots()
        snap = snapshots[0]
        assert "path" in snap
        assert "label" in snap
        assert "timestamp" in snap
        assert "size_mb" in snap
        assert snap["label"] == "my label"

    def test_recover_from_backup(self, tmp_path):
        """recover_from_backup copies .bak to .db."""
        from src.core.auto_save import AutoSaveManager
        from src.db.database import Database
        from src.models import Task, Section

        db_path = str(tmp_path / "project.db")
        Database(db_path)
        mgr = AutoSaveManager(db_path)

        # Create a backup file
        import shutil
        shutil.copy2(db_path, str(mgr.bak_path))

        # Overwrite db with something
        with open(db_path, "w") as f:
            f.write("corrupted")

        # Recover
        success = mgr.recover_from_backup()
        assert success is True
        assert os.path.exists(db_path)
        assert os.path.getsize(db_path) > 5  # Not the corrupted text

    def test_create_snapshot_no_db_raises(self, tmp_path):
        """Creating snapshot when db file doesn't exist raises FileNotFoundError."""
        from src.core.auto_save import AutoSaveManager

        db_path = str(tmp_path / "nonexistent.db")
        mgr = AutoSaveManager(db_path)

        # AutoSaveManager.__init__ creates snapshot_dir but doesn't create db
        # create_snapshot should raise
        with pytest.raises(FileNotFoundError):
            mgr.create_snapshot("should fail")


import pytest
