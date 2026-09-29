"""v11 / v13 迁移原子性与中断恢复回归测试（审计 P0-1，数据丢失级）。

背景
----
v11（`src/db/schema.py::_migrate_v11`）通过 7 次 DROP TABLE + RENAME 重建核心表
（issue_attachments / fa_records / capa_records / sample_transactions /
test_results / issues / test_tasks）。旧实现整段迁移没有事务，且注释断言
"SQLite DDL 不可回滚"（错误：SQLite 的 DDL 是可事务化的，只有
PRAGMA foreign_keys 不能在事务内修改）。

致命路径：进程恰在「DROP TABLE issues」与「RENAME issues_new → issues」之间
被杀（或该语句失败）后，落盘状态为「issues 不存在、issues_new 是唯一数据副本」。
重试时 `_rebuild_table` 第一步就 `DROP TABLE IF EXISTS issues_new` —— 删掉唯一
副本，随后重建空表、`old_cols` 为空导致 `INSERT INTO issues_new () SELECT FROM
issues` 语法错误，except 分支再删一次 issues_new → issues 整表数据物理丢失且
不可恢复。v13（schema_version 表重建）有同构问题：该现场下 init_schema 会先
建出一张空表，版本号读成 0，整条迁移链从 v1 重放、版本历史被重写（实测，而
不是版本表从此消失）。

覆盖
----
1. `_rebuild_table` 在「旧表缺失、*_new 存在」现场直接 RENAME 收尾
2. v11 断链现场重试 init_schema：issues 数据完整
3. v13 断链现场重试 init_schema：schema_version 与版本历史完整，且不把库当空库重放 v1+
4. v11 中途失败 → 整体回滚，不留半重建状态（索引/表结构/数据/版本号均不变）
5. 真 SIGKILL 落在 DROP 与 RENAME 之间 → 库文件回到迁移前状态，重试可恢复
6. v13 中途失败 → schema_version 不被提前改写（重复版本记录原样保留）
7. 正常路径 v10→v28：数据/索引/列集合无损，FK 约束恢复开启
"""
from __future__ import annotations

import inspect
import os
import re
import signal
import subprocess
import sys

import apsw
import pytest

import src.db.schema as schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# v11 重建的 7 张表（全部都在本次审计的丢失半径内）
_REBUILT_TABLES = (
    "issue_attachments",
    "fa_records",
    "capa_records",
    "sample_transactions",
    "test_results",
    "issues",
    "test_tasks",
)

ISSUE_ROWS = 3
FA_ROWS = 2


# ── 从源码提取真实 DDL（避免测试内复制一份会漂移的 DDL 副本）──

def _v11_ddl(name: str) -> str:
    src = inspect.getsource(schema._migrate_v11)
    m = re.search(rf'_rebuild_table\(\s*conn,\s*"{name}",\s*"""(.*?)"""', src, re.S)
    assert m, f"schema._migrate_v11 中找不到 {name} 的重建 DDL"
    return m.group(1)


def _v13_schema_version_ddl() -> str:
    src = inspect.getsource(schema._migrate_v13)
    m = re.search(r'"""(CREATE TABLE schema_version_new \(.*?\))\s*"""', src, re.S)
    assert m, "schema._migrate_v13 中找不到 schema_version 的重建 DDL"
    return m.group(1)


# ── DB 构造 / 自省工具 ──

def _legacy_schema_version_table(conn: apsw.Connection) -> None:
    """还原成 v13 之前的 schema_version（无 UNIQUE 约束，允许重复版本记录）。"""
    conn.execute("DROP TABLE IF EXISTS schema_version")
    conn.execute(
        """CREATE TABLE schema_version (
            version     INTEGER NOT NULL,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )"""
    )


def _seed(conn: apsw.Connection) -> None:
    conn.execute("INSERT INTO projects (name) VALUES ('P1')")
    conn.execute("INSERT INTO samples (sn, project_id) VALUES ('SN1', 1)")
    conn.execute("INSERT INTO test_plans (project_id, name) VALUES (1, 'PLAN1')")
    conn.execute("INSERT INTO test_tasks (plan_id, name) VALUES (1, 'TASK1')")
    conn.execute("INSERT INTO test_results (task_id, result) VALUES (1, 'pass')")
    for i in range(ISSUE_ROWS):
        conn.execute(
            "INSERT INTO issues (title, project_id, status) VALUES (?, 1, 'open')",
            (f"ISSUE{i}",),
        )
    for i in range(FA_ROWS):
        conn.execute("INSERT INTO fa_records (issue_id, step_no) VALUES (1, ?)", (i + 1,))
    conn.execute("INSERT INTO capa_records (issue_id, action) VALUES (1, 'fix')")
    conn.execute(
        "INSERT INTO issue_attachments (issue_id, file_path) VALUES (1, 'a.png')"
    )
    conn.execute(
        "INSERT INTO sample_transactions (sample_id, type) VALUES (1, 'check_in')"
    )


def _make_old_db(path, version: int, *, legacy_schema_version: bool = False) -> None:
    """构造"已升到 v<version> 的旧库"：建全量 schema → 回退版本号 → 填数据。

    与 tests/test_soft_delete.py、tests/test_bug_tracker.py 一样，用现成 schema
    加版本号回退来模拟旧库（生产上 v11 只在打开旧备份时触发）。
    """
    conn = apsw.Connection(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    schema.init_schema(conn)
    if legacy_schema_version:
        _legacy_schema_version_table(conn)
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    _seed(conn)
    conn.close()


def _break_window(path, name: str, ddl: str) -> None:
    """把库推进到「旧表已 DROP、*_new 未 RENAME」的断链现场。

    全部语句自动提交（不 BEGIN），等价于旧版无事务迁移被强杀后落盘的状态。
    """
    conn = apsw.Connection(str(path))
    new = f"{name}_new"
    conn.execute(f"DROP TABLE IF EXISTS [{new}]")
    conn.execute(ddl)
    new_cols = [r[1] for r in conn.execute(f"PRAGMA table_info([{new}])").fetchall()]
    old_cols = {r[1] for r in conn.execute(f"PRAGMA table_info([{name}])").fetchall()}
    cols = ", ".join(c for c in new_cols if c in old_cols)
    conn.execute(f"INSERT INTO [{new}] ({cols}) SELECT {cols} FROM [{name}]")
    conn.execute(f"DROP TABLE [{name}]")
    conn.close()


def _query(path, sql: str, params=()):
    conn = apsw.Connection(str(path))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _row_counts(path, tables=_REBUILT_TABLES) -> dict:
    """逐表 COUNT(*)；表缺失会直接抛 SQLError —— 这正是"整表丢失"的证据。"""
    conn = apsw.Connection(str(path))
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            for t in tables
        }
    finally:
        conn.close()


def _table_names(path) -> set:
    return {r[0] for r in _query(path, "SELECT name FROM sqlite_master WHERE type='table'")}


def _index_names(path) -> set:
    return {r[0] for r in _query(path, "SELECT name FROM sqlite_master WHERE type='index'")}


def _table_ddl(path) -> dict:
    return {
        r[0]: r[1]
        for r in _query(path, "SELECT name, sql FROM sqlite_master WHERE type='table'")
    }


def _column_map(path) -> dict:
    return {t: sorted(r[1] for r in _query(path, f"PRAGMA table_info([{t}])")) for t in _table_names(path)}


def _versions(path) -> tuple:
    return tuple(r[0] for r in _query(path, "SELECT version FROM schema_version ORDER BY version"))


# ═══════════════════════════════════════════════════════════════════
#  1. _rebuild_table 的断链收尾
# ═══════════════════════════════════════════════════════════════════

class TestRebuildTableResume:
    def test_resumes_when_old_table_missing_and_new_holds_only_copy(self):
        """旧表缺失、_new 是唯一副本时必须 RENAME 收尾，绝不能 DROP 掉副本。"""
        conn = apsw.Connection(":memory:")
        conn.execute("CREATE TABLE t_new (a INTEGER, b TEXT)")
        conn.execute("INSERT INTO t_new VALUES (1, 'keep')")

        schema._rebuild_table(conn, "t", "CREATE TABLE t_new (a INTEGER, b TEXT)")

        assert conn.execute("SELECT a, b FROM t").fetchall() == [(1, "keep")]
        assert not conn.execute("PRAGMA table_info(t_new)").fetchall(), "遗留 _new 表"
        conn.close()

    def test_normal_rebuild_still_replaces_old_table(self):
        """无断链现场时行为不变：旧表内容按列交集搬到重建后的表。"""
        conn = apsw.Connection(":memory:")
        conn.execute("CREATE TABLE t (a INTEGER, b TEXT, gone TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'v', 'x')")

        schema._rebuild_table(conn, "t", "CREATE TABLE t_new (a INTEGER, b TEXT)")

        assert conn.execute("SELECT a, b FROM t").fetchall() == [(1, "v")]
        assert [r[1] for r in conn.execute("PRAGMA table_info(t)").fetchall()] == ["a", "b"]
        conn.close()


# ═══════════════════════════════════════════════════════════════════
#  2/3. 断链现场重试 init_schema
# ═══════════════════════════════════════════════════════════════════

class TestRetryAfterInterruption:
    def test_v11_issue_rows_survive_retry_in_drop_rename_window(self, tmp_path):
        """重试时 issues_new 是唯一数据副本 —— 旧实现会让 issues 整表消失。"""
        db = tmp_path / "v11_window.db"
        _make_old_db(db, 10)
        counts = _row_counts(db)

        _break_window(db, "issues", _v11_ddl("issues"))
        assert "issues" not in _table_names(db)
        assert "issues_new" in _table_names(db), "未构造出断链现场"

        conn = apsw.Connection(str(db))
        try:
            assert schema.init_schema(conn) == schema.SCHEMA_VERSION
        finally:
            conn.close()

        assert _row_counts(db) == counts
        assert "issues_new" not in _table_names(db)

    def test_v13_schema_version_survives_retry_in_drop_rename_window(self, tmp_path):
        """schema_version 表同样会被重建：断链现场必须先收尾恢复，再读版本号。

        init_schema 开头有 CREATE TABLE IF NOT EXISTS schema_version——若不在
        「读版本号之前」收尾，这里会建出一张空表，current 归零，于是整条迁移链
        从 v1 重放：v1..v12 被重新执行，v13 的去重又把它们压回一行 MAX=12，
        因此版本号看起来"没变"，真正的证据是 v12 的 applied_at 被改写成当前时间。
        """
        db = tmp_path / "v13_window.db"
        _make_old_db(db, 12, legacy_schema_version=True)
        counts = _row_counts(db)
        conn = apsw.Connection(str(db))
        try:
            # v12 是"当年"落下的版本记录，时间戳是历史的一部分
            conn.execute(
                "UPDATE schema_version SET applied_at = '2020-01-01 00:00:00'"
            )
        finally:
            conn.close()

        _break_window(db, "schema_version", _v13_schema_version_ddl())
        assert "schema_version" not in _table_names(db)
        assert "schema_version_new" in _table_names(db), "未构造出断链现场"

        conn = apsw.Connection(str(db))
        try:
            assert schema.init_schema(conn) == schema.SCHEMA_VERSION
        finally:
            conn.close()

        # 保留 v12 记录 + 其后逐版本推进；不得出现"从 v1 重放"的版本行
        assert _versions(db) == (12, *range(13, schema.SCHEMA_VERSION + 1))
        assert _query(
            db, "SELECT applied_at FROM schema_version WHERE version = 12"
        ) == [("2020-01-01 00:00:00",)], (
            "断链现场被当成空库处理：v1..v12 被重放，版本历史（applied_at）被重写"
        )
        assert "schema_version_new" not in _table_names(db)
        assert _row_counts(db) == counts


# ═══════════════════════════════════════════════════════════════════
#  4/6. 迁移中途失败必须整体回滚
# ═══════════════════════════════════════════════════════════════════

class TestFailedMigrationRollsBack:
    def test_v11_failure_leaves_no_half_rebuilt_state(self, tmp_path, monkeypatch):
        """第 4 张表重建时失败：前 3 次重建（含索引丢失）必须被回滚。"""
        db = tmp_path / "v11_fail.db"
        _make_old_db(db, 10)
        ddl_before = _table_ddl(db)
        idx_before = _index_names(db)
        counts_before = _row_counts(db)

        real_rebuild = schema._rebuild_table
        calls = {"n": 0}

        def failing_rebuild(conn, name, ddl):
            calls["n"] += 1
            if calls["n"] == 4:
                raise RuntimeError("simulated failure mid-v11")
            return real_rebuild(conn, name, ddl)

        monkeypatch.setattr(schema, "_rebuild_table", failing_rebuild)
        conn = apsw.Connection(str(db))
        try:
            with pytest.raises(RuntimeError):
                schema.init_schema(conn)
        finally:
            conn.close()

        assert calls["n"] == 4, "未真正在重建中途失败"
        assert _index_names(db) == idx_before, "失败迁移留下了索引已被删掉的半重建状态"
        assert _table_ddl(db) == ddl_before, "失败迁移改写了表结构且未回滚"
        assert _row_counts(db) == counts_before
        assert _versions(db) == (10,), "失败迁移不得写入新版本号"

    def test_v13_failure_does_not_touch_schema_version(self, tmp_path, monkeypatch):
        """v13 索引补建阶段失败：schema_version 的 UNIQUE 重建/去重必须回滚。"""
        db = tmp_path / "v13_fail.db"
        _make_old_db(db, 12, legacy_schema_version=True)
        conn = apsw.Connection(str(db))
        try:
            # 旧库允许重复版本记录（v13 加 UNIQUE 的动因）
            conn.execute("INSERT INTO schema_version (version) VALUES (10)")
            conn.execute("INSERT INTO schema_version (version) VALUES (10)")
        finally:
            conn.close()
        versions_before = _versions(db)
        ddl_before = _table_ddl(db)
        assert versions_before == (10, 10, 12)

        monkeypatch.setattr(
            schema, "_DDL_INDEXES", [*schema._DDL_INDEXES, "CREATE INDEX broken ON ;"]
        )
        conn = apsw.Connection(str(db))
        try:
            with pytest.raises(apsw.SQLError):
                schema.init_schema(conn)
        finally:
            conn.close()

        assert _versions(db) == versions_before, "失败的 v13 改写了版本记录（重复项被吞并）"
        assert _table_ddl(db) == ddl_before, "失败的 v13 重写了 schema_version 表"


# ═══════════════════════════════════════════════════════════════════
#  5. 真 SIGKILL 落在 DROP 与 RENAME 之间
# ═══════════════════════════════════════════════════════════════════

_SIGKILL_CHILD = '''
import os, signal, sys
import apsw
import src.db.schema as schema

db = sys.argv[1]
real = schema._rebuild_table


def kill_in_window(conn, name, ddl):
    """复制 issues 到 issues_new、DROP issues，然后在 RENAME 之前被强杀。"""
    if name != "issues":
        return real(conn, name, ddl)
    new = name + "_new"
    conn.execute("DROP TABLE IF EXISTS [%s]" % new)
    conn.execute(ddl)
    new_cols = [r[1] for r in conn.execute("PRAGMA table_info([%s])" % new).fetchall()]
    old_cols = {r[1] for r in conn.execute("PRAGMA table_info([%s])" % name).fetchall()}
    cols = ", ".join(c for c in new_cols if c in old_cols)
    conn.execute("INSERT INTO [%s] (%s) SELECT %s FROM [%s]" % (new, cols, cols, name))
    conn.execute("DROP TABLE [%s]" % name)
    os.kill(os.getpid(), signal.SIGKILL)


schema._rebuild_table = kill_in_window
schema.init_schema(apsw.Connection(db))
'''


class TestHardKillSafety:
    def test_sigkill_between_drop_and_rename_keeps_db_recoverable(self, tmp_path):
        """事务化 DDL：被杀进程留下的未提交事务必须被回滚，重试能恢复。"""
        db = tmp_path / "kill.db"
        _make_old_db(db, 10)
        ddl_before = _table_ddl(db)
        counts_before = _row_counts(db)

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [ROOT, env.get("PYTHONPATH")]))
        proc = subprocess.run(
            [sys.executable, "-c", _SIGKILL_CHILD, str(db)],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=180,
        )
        assert proc.returncode == -signal.SIGKILL, (
            f"子进程应被 SIGKILL 杀死，实际 rc={proc.returncode}, stderr={proc.stderr[-800:]}"
        )

        assert _row_counts(db) == counts_before, "被强杀后 issues 数据不见了"
        assert _table_ddl(db) == ddl_before
        assert _versions(db) == (10,)

        conn = apsw.Connection(str(db))
        try:
            assert schema.init_schema(conn) == schema.SCHEMA_VERSION
        finally:
            conn.close()
        assert _row_counts(db) == counts_before


# ═══════════════════════════════════════════════════════════════════
#  7. 正常路径不回归
# ═══════════════════════════════════════════════════════════════════

class TestHappyPathV10ToLatest:
    def test_rows_indexes_and_columns_survive_full_migration(self, tmp_path):
        db = tmp_path / "happy.db"
        _make_old_db(db, 10)
        counts_before = _row_counts(db)
        idx_before = _index_names(db)
        cols_before = _column_map(db)

        conn = apsw.Connection(str(db))
        try:
            assert schema.init_schema(conn) == schema.SCHEMA_VERSION
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1, (
                "迁移结束后 FK 约束必须恢复开启"
            )
        finally:
            conn.close()

        assert _row_counts(db) == counts_before
        assert _index_names(db) == idx_before
        assert "issues_new" not in _table_names(db)
        lost_cols = {
            t: sorted(set(cols_before[t]) - set(after))
            for t, after in _column_map(db).items()
            if t in cols_before and set(cols_before[t]) - set(after)
        }
        assert not lost_cols, f"完整迁移链丢列: {lost_cols}"
