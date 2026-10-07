"""最近 3 个迁移（v27/v28/v29）的 round-trip 测试。

做法：把 SCHEMA_VERSION 临时压到 N-1，init_schema 只跑到对应版本，
再恢复后 init_schema 跑剩余迁移。升级后校验目标列/数据约定存在。
"""

from __future__ import annotations

import apsw
import pytest

import src.db.schema as schema


def _upgrade_to(conn, target: int) -> None:
    orig = schema.SCHEMA_VERSION
    schema.SCHEMA_VERSION = target
    try:
        schema.init_schema(conn)
    finally:
        schema.SCHEMA_VERSION = orig


def test_migration_v27_todos_archived(tmp_path):
    conn = apsw.Connection(str(tmp_path / "v27.db"))
    try:
        _upgrade_to(conn, 26)
        # 注意：新建库的 v1 DDL 已含现行列定义，列是否已存在取决于 DDL 基线；
        # round-trip 校验重点在「升级后列与索引必然存在且可用」

        _upgrade_to(conn, 27)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(todos)").fetchall()}
        assert "archived" in cols
        idx = {
            r[1] for r in conn.execute(
                "PRAGMA index_list(todos)"
            ).fetchall()
        }
        assert "idx_todos_archived" in idx
        ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert ver == 27
    finally:
        conn.close()


def test_migration_v28_task_category_mapping(tmp_path):
    conn = apsw.Connection(str(tmp_path / "v28.db"))
    try:
        _upgrade_to(conn, 27)
        conn.execute("INSERT INTO projects (name) VALUES ('p')")
        conn.execute("INSERT INTO test_plans (project_id, name) VALUES (1, 'plan')")
        conn.execute(
            "INSERT INTO test_tasks (plan_id, name, category, duration) "
            "VALUES (1, 't1', '环境', 1), (1, 't2', '力学', 1), (1, 't3', '电测', 1)"
        )

        _upgrade_to(conn, 28)
        cats = sorted(
            r[0] for r in conn.execute("SELECT category FROM test_tasks ORDER BY name")
        )
        assert cats == ["其他", "机械试验", "环境试验"]  # ORDER BY name 的实际序
    finally:
        conn.close()


def test_migration_v29_start_day_sentinel(tmp_path):
    conn = apsw.Connection(str(tmp_path / "v29.db"))
    try:
        _upgrade_to(conn, 28)
        conn.execute("INSERT INTO projects (name) VALUES ('p')")
        conn.execute("INSERT INTO test_plans (project_id, name) VALUES (1, 'plan')")
        # 未手动排期且 start_day=0 → 应迁为 NULL；手动排期保留 0
        conn.execute(
            "INSERT INTO test_tasks (plan_id, name, duration, start_day, manual_scheduled) "
            "VALUES (1, 'auto', 1, 0, 0), (1, 'manual', 1, 0, 1)"
        )

        _upgrade_to(conn, 29)
        rows = {
            r[0]: r[1]
            for r in conn.execute("SELECT name, start_day FROM test_tasks")
        }
        assert rows["auto"] is None
        assert rows["manual"] == 0
        # 版本推进到 v29，且幂等（重复 init 不报错）
        ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert ver == 29
        schema.init_schema(conn)
    finally:
        conn.close()
