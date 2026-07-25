"""Unit tests for BackupService and ImportService (backup_service.py & import_service.py)."""

import tempfile
from pathlib import Path
import pytest
import apsw

from src.db.connection import get_connection, close_connection
from src.db.schema import SCHEMA_VERSION, init_schema
from src.services.backup_service import BackupService, BackupInfo
from src.services.import_service import import_equipment, import_technicians, ImportResult
from src.services.equipment_service import EquipmentService
from src.services.technician_service import TechnicianService
from src.db.repositories.equipment_repo import EquipmentRepository
from src.db.repositories.technician_repo import TechnicianRepository


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary initialized SQLite DB."""
    db_file = tmp_path / "test_reliatrack.db"
    conn = get_connection(str(db_file))
    init_schema(conn)
    yield str(db_file)
    close_connection(str(db_file))



class TestBackupService:
    """Test BackupService create, validate, restore, list, delete."""

    def test_create_backup(self, temp_db, tmp_path):
        service = BackupService(temp_db)
        backup_path = tmp_path / "backups" / "backup_test.db"

        result_path = service.create_backup(backup_path)
        assert result_path.exists()
        assert result_path.stat().st_size > 0

        # Create duplicate backup raises FileExistsError
        with pytest.raises(FileExistsError):
            service.create_backup(backup_path)

    def test_validate_backup(self, temp_db, tmp_path):
        service = BackupService(temp_db)
        backup_path = tmp_path / "valid_backup.db"
        service.create_backup(backup_path)

        info = BackupService.validate_backup(backup_path)
        assert isinstance(info, BackupInfo)
        assert info.filename == "valid_backup.db"
        assert info.schema_version == SCHEMA_VERSION
        assert "valid_backup.db" in info.display_name

    def test_validate_backup_invalid_files(self, tmp_path):
        # File does not exist
        non_existent = tmp_path / "non_existent.db"
        with pytest.raises(FileNotFoundError):
            BackupService.validate_backup(non_existent)

        # Invalid sqlite file
        invalid_file = tmp_path / "invalid.db"
        invalid_file.write_text("not a sqlite database")
        with pytest.raises(ValueError, match="无法读取备份文件"):
            BackupService.validate_backup(invalid_file)

        # Empty sqlite without schema_version table
        empty_db = tmp_path / "empty.db"
        conn = apsw.Connection(str(empty_db))
        conn.close()
        with pytest.raises(ValueError, match="不是有效的 ReliaTrack 数据库"):
            BackupService.validate_backup(empty_db)

    def test_restore_backup(self, temp_db, tmp_path, monkeypatch):
        # Setup custom backups dir in tmp_path
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("src.services.backup_service.DEFAULT_BACKUPS_DIR", backups_dir)

        # Create initial backup
        service = BackupService(temp_db)
        backup_path = tmp_path / "restore_source.db"
        service.create_backup(backup_path)

        # Add data to db to verify restore replaces it
        conn = get_connection(temp_db)
        conn.execute("INSERT INTO equipment (name, type) VALUES ('EqTemp', 'Chamber')")

        # Perform restore
        service.restore_backup(backup_path)

        # Re-check db content
        conn2 = get_connection(temp_db)
        row = conn2.execute("SELECT COUNT(*) FROM equipment WHERE name = 'EqTemp'").fetchone()
        assert row[0] == 0  # Restored DB should not have EqTemp

    def test_delete_backup(self, tmp_path, monkeypatch):
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("src.services.backup_service.DEFAULT_BACKUPS_DIR", backups_dir)

        backup_file = backups_dir / "reliatrack_20260101_120000.db"
        backup_file.write_text("dummy")

        BackupService.delete_backup(backup_file)
        assert not backup_file.exists()

        # Reject deleting outside DEFAULT_BACKUPS_DIR
        outside_file = tmp_path / "outside.db"
        outside_file.write_text("dummy")
        with pytest.raises(ValueError, match="不允许删除备份目录外的文件"):
            BackupService.delete_backup(outside_file)


class TestImportService:
    """Test import_equipment and import_technicians in import_service.py."""

    def test_import_equipment_success_and_skip(self, temp_db):
        conn = get_connection(temp_db)
        repo = EquipmentRepository(conn)
        service = EquipmentService(repo)

        # Pre-insert existing equipment
        service.create(name="恒温恒湿箱01", type="Chamber")

        rows = [
            {"name": "高低温试验箱02", "type": "Chamber", "model": "TH-100"},
            {"name": "", "type": "Invalid"},  # Empty name -> skip
            {"name": "恒温恒湿箱01", "type": "Chamber"},  # Pre-existing -> skip
            {"name": "振动台03", "type": "Vibration"},
            {"name": "振动台03", "type": "Vibration"},  # Duplicate in batch -> skip
        ]

        result = import_equipment(rows, service)
        assert result.success == 2
        assert result.skipped == 3
        assert len(result.errors) == 3

        all_eqs = {eq.name for eq in service.list_all()}
        assert "高低温试验箱02" in all_eqs
        assert "振动台03" in all_eqs

    def test_import_equipment_rollback_on_error(self, temp_db, monkeypatch):
        conn = get_connection(temp_db)
        repo = EquipmentRepository(conn)
        service = EquipmentService(repo)

        rows = [
            {"name": "设备A", "type": "A"},
            {"name": "设备B", "type": "B"},
        ]

        def mock_create(*args, **kwargs):
            if kwargs.get("name") == "设备B":
                raise ValueError("Simulated create failure")
            return repo.create(*args, **kwargs)

        monkeypatch.setattr(service, "create", mock_create)

        result = import_equipment(rows, service)
        assert result.success == 0
        assert len(result.errors) > 0

        # Rollback check: 设备A should NOT exist in DB
        all_eqs = {eq.name for eq in service.list_all()}
        assert "设备A" not in all_eqs

    def test_import_technicians_success_and_skip(self, temp_db):
        conn = get_connection(temp_db)
        repo = TechnicianRepository(conn)
        service = TechnicianService(repo)

        service.create(name="张三", employee_id="EMP001")

        rows = [
            {"name": "李四", "employee_id": "EMP002", "role": "测试工程师"},
            {"name": "", "employee_id": "EMP003"},  # Empty name -> skip
            {"name": "张三", "employee_id": "EMP001"},  # Duplicate -> skip
            {"name": "王五", "employee_id": "EMP004"},
            {"name": "王五", "employee_id": "EMP004"},  # Batch duplicate -> skip
        ]

        result = import_technicians(rows, service)
        assert result.success == 2
        assert result.skipped == 3
        assert len(result.errors) == 3

        all_techs = {(t.name, t.employee_id) for t in service.list_all()}
        assert ("李四", "EMP002") in all_techs
        assert ("王五", "EMP004") in all_techs
