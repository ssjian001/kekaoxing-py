"""P0 审计修复回归测试（2026-10-06）。

1. 8D 导出参数错位：ExportWorker 以 (provider, svc, fmt, project_id, plan_id, issue_id)
   调用 handler，_export_8d 必须按同序接收，否则 plan_id 落到 issue_id 上。
2. 命令面板 backup 动作调用不存在的 _on_backup_db → 应走 _backup_handlers._on_data_manage。
3. 库文件损坏时恢复：恢复前安全备份（apsw）必然失败，必须回退裸文件拷贝而非中止恢复。
   + 回滚路径必须清理残留 -wal/-shm。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import apsw
import pytest

from src.db.schema import init_schema
from src.services.backup_service import BackupService


# ── 1. 8D 导出签名对齐 ─────────────────────────────────────────────

def test_export_8d_uses_issue_id_not_plan_id(tmp_path):
    from src.handlers.export_handlers import ExportHandlers

    seen: dict = {}

    class _IssueSvc:
        def get(self, issue_id):
            seen["issue_id"] = issue_id
            raise ValueError("stop early")  # 拿到 id 即停

        def get_fa_records(self, _):
            return []

        def get_capa_records(self, _):
            return []

    ctrl = SimpleNamespace(issue_service=_IssueSvc(), test_plan_service=SimpleNamespace(),
                           sample_service=None, technicians=[])
    svc = SimpleNamespace()
    try:
        ExportHandlers._export_8d(ctrl, svc, "PDF", 1, 999, 5)
    except ValueError:
        pass
    assert seen.get("issue_id") == 5, f"issue_id 应为 5（传入的 issue_id），实际 {seen.get('issue_id')}（错位拿到 plan_id）"


# ── 2. 命令面板 backup 动作 ─────────────────────────────────────────

def test_palette_backup_action_dispatches_to_backup_handlers():
    from main import MainWindow

    called = []
    fake_handlers = SimpleNamespace(_on_data_manage=lambda: called.append(True))
    fake_self = SimpleNamespace(_backup_handlers=fake_handlers)
    MainWindow._on_command_palette_action(fake_self, ("action", "backup"))
    assert called == [True]


def test_main_has_no_dead_backup_ref():
    """防止再引入对不存在的 _on_backup_db 的调用。"""
    src = Path(__file__).resolve().parent.parent / "main.py"
    text = src.read_text(encoding="utf-8")
    assert "_on_backup_db()" not in text


# ── 3. 损坏库恢复不被安全备份堵死 ──────────────────────────────────

def test_restore_when_current_db_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.services.backup_service.DEFAULT_BACKUPS_DIR", tmp_path / "backups"
    )
    live_db = tmp_path / "live.db"
    conn = apsw.Connection(str(live_db))
    init_schema(conn)
    conn.execute("INSERT INTO projects (name, product, customer, status) VALUES ('P','P','C','active')")
    conn.close()

    svc = BackupService(db_path=str(live_db))
    good_backup = tmp_path / "good.db"
    svc.create_backup(good_backup)

    # 破坏当前库（模拟损坏）
    live_db.write_bytes(b"GARBAGE-NOT-A-SQLITE-DB" * 100)

    # 恢复应成功（安全备份 apsw 会失败 → 回退裸拷贝），不抛 RuntimeError
    svc.restore_backup(good_backup)

    assert live_db.read_bytes() == good_backup.read_bytes()
    pre_restore = list((tmp_path / "backups").glob("reliatrack_pre_restore_*.db"))
    assert pre_restore, "应留有恢复前的安全备份（裸拷贝）"
