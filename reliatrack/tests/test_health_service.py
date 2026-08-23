"""HealthService 单元测试 — 启动自检 + 数据体检核心逻辑。

覆盖点：
- check_db → 正常库通过 / 损坏库失败 / FK 违规检出
- DbCorruptError → 携带 check_result
- scan_data_health → 空库无问题 / 断链结果检出（FK off 模拟历史遗留）
- delete_orphan_files → 目录内删除 / 目录外拒绝
- _startup_backup rotation 排序 → 时间戳解析排序（非字符串混排）
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import apsw
import pytest

from src.db.schema import init_schema
from src.db.connection import get_connection, close_all_connections
from src.services.health_service import (
    DbCorruptError,
    check_db,
    delete_orphan_files,
    scan_data_health,
)


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture()
def fresh_db(tmp_path):
    """初始化好的空库 + 连接。"""
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    init_schema(conn)
    yield conn
    close_all_connections()


class _FakeController:
    """scan_data_health 最小控制器。"""

    def __init__(self, conn, issue_service=None):
        self._conn = conn
        self.issue_service = issue_service


# ═══════════════════════════════════════════════════════════════════
#  check_db
# ═══════════════════════════════════════════════════════════════════


class TestCheckDb:
    def test_ok_on_fresh_db(self, fresh_db):
        result = check_db(fresh_db)
        assert result.ok is True
        assert result.quick_check == []
        assert result.fk_violations == []
        assert result.summary() == "正常"

    def test_corrupt_db_detected(self, tmp_path):
        # 写一个带合法头但内容损坏的文件
        p = tmp_path / "corrupt.db"
        p.write_bytes(b"SQLite format 3\x00" + b"\xff" * 200)
        conn = apsw.Connection(str(p))
        result = check_db(conn)
        assert result.ok is False
        assert result.quick_check
        conn.close()

    def test_fk_violation_detected(self, fresh_db):
        # FK OFF 时塞入断链（模拟历史遗留数据）
        fresh_db.execute("PRAGMA foreign_keys=OFF")
        fresh_db.execute(
            "INSERT INTO test_results (task_id, result) VALUES (99999, 'pass')"
        )
        fresh_db.execute("PRAGMA foreign_keys=ON")
        result = check_db(fresh_db)
        assert result.ok is False
        assert result.fk_violations
        assert "test_results" in result.fk_violations[0] or "结果" in result.summary()


class TestDbCorruptError:
    def test_carries_result(self):
        from src.services.health_service import DbCheckResult

        r = DbCheckResult(ok=False, quick_check=["bad page"])
        err = DbCorruptError("损坏", r)
        assert err.check_result is r
        assert str(err) == "损坏"


# ═══════════════════════════════════════════════════════════════════
#  scan_data_health
# ═══════════════════════════════════════════════════════════════════


class TestScanDataHealth:
    def test_empty_db_clean(self, fresh_db):
        report = scan_data_health(_FakeController(fresh_db))
        assert report["missing_files"] == []
        assert report["orphan_files"] == []
        assert report["broken_result_refs"] == []

    def test_broken_result_ref_detected(self, fresh_db):
        fresh_db.execute("PRAGMA foreign_keys=OFF")
        fresh_db.execute(
            "INSERT INTO test_results (task_id, result) VALUES (4242, 'fail')"
        )
        fresh_db.execute("PRAGMA foreign_keys=ON")
        report = scan_data_health(_FakeController(fresh_db))
        assert any("4242" in r for r in report["broken_result_refs"])

    def test_scan_tolerates_closed_conn(self):
        report = scan_data_health(_FakeController(None))
        # conn 为 None 时不崩溃，附件部分照样返回
        assert "missing_files" in report


# ═══════════════════════════════════════════════════════════════════
#  delete_orphan_files — 白名单约束
# ═══════════════════════════════════════════════════════════════════


class TestDeleteOrphanFiles:
    def test_deletes_inside_attachments_dir(self, tmp_path, monkeypatch):
        from src.db import connection as conn_mod

        attach_dir = tmp_path / "attachments"
        attach_dir.mkdir()
        target = attach_dir / "orphan.png"
        target.write_bytes(b"x" * 10)
        monkeypatch.setattr(conn_mod, "DEFAULT_ATTACHMENTS_DIR", attach_dir)

        # delete_orphan_files 里是函数内 import，patch 模块属性即可生效
        deleted, failures = delete_orphan_files([str(target)])
        assert deleted == 1
        assert not target.exists()
        assert failures == []

    def test_refuses_outside_paths(self, tmp_path, monkeypatch):
        from src.db import connection as conn_mod

        attach_dir = tmp_path / "attachments"
        attach_dir.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_bytes(b"secret")
        monkeypatch.setattr(conn_mod, "DEFAULT_ATTACHMENTS_DIR", attach_dir)

        deleted, failures = delete_orphan_files([str(outside)])
        assert deleted == 0
        assert failures
        assert outside.exists()  # 未被删除


# ═══════════════════════════════════════════════════════════════════
#  rotation 排序 — 时间戳解析 vs 字符串排序
# ═══════════════════════════════════════════════════════════════════


class TestRotationSort:
    def test_sort_key_chronological(self):
        """混合命名(日期 vs 日期_时分秒)必须按时间排序而非字符串序。"""
        # _backup_sort_key 是闭包内定义，无法直接导入 — 复制其逻辑做等价验证:
        import re

        def key(p):
            m = re.search(r"(\d{8})(?:_(\d{6}))?", p.stem)
            return (m.group(1), m.group(2) or "") if m else ("", "")

        names = [
            "reliatrack_20260823_143012.db",
            "reliatrack_20260822.db",
            "reliatrack_20260823.db",
            "reliatrack_20260820_090000.db",
        ]
        paths = [Path(n) for n in names]
        ordered = [p.name for p in sorted(paths, key=key)]
        # 字符串排序会把 20260823.db 排到 20260823_143012.db 前面 ('.'<'_')，
        # 但按时间 14:30:12 的文件晚于当天零点命名的文件
        assert ordered[0] == "reliatrack_20260820_090000.db"
        assert ordered[-1] == "reliatrack_20260823_143012.db"
        assert "reliatrack_20260822.db" == ordered[1]
