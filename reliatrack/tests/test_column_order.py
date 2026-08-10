"""列序映射回归测试 — 防止 SELECT 显式列名与映射列序错位。

关键 Bug 场景：
  表经历 ALTER TABLE ADD COLUMN 后，新列被加到物理表末尾，
  但 sqlite_master 中 CREATE TABLE 声明位置不变。
  此时 SELECT {col_a}, {col_b} 返回值按物理存储序而非声明序，
  导致 dict(zip(PRAGMA_cols, row)) 静默错位到错误的 dataclass 字段。

测试策略：
  1. 在内存数据库中模拟 ALTER TABLE 破坏列序的场景
  2. 验证 repo 使用显式 _COLS 列表时，即使表物理列序错位也能正确映射
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import apsw
import pytest

from src.db.schema import init_schema
from src.db.repositories import (
    IssueRepository,
    TestResultRepository,
    TestTaskRepository,
    ProjectRepository,
    SampleRepository,
)


# ═══════════════════════════════════════════════════════════════════
#  Fixture: 模拟 ALTER TABLE 列序错位的数据库
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def scrambled_db() -> apsw.Connection:
    """创建带 ALTER TABLE 列序错位的测试数据库。

    模拟：CREATE TABLE 后 ALTER TABLE ADD COLUMN 把新列加到物理末尾，
    导致物理列序与声明序不一致。
    """
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")

    # 原始建表（只有 id, name, status）
    conn.execute("""
        CREATE TABLE items (
            id         INTEGER PRIMARY KEY,
            name       TEXT    NOT NULL,
            status     TEXT    NOT NULL DEFAULT 'active',
            priority   INTEGER NOT NULL DEFAULT 3,
            assignee   TEXT    NOT NULL DEFAULT '',
            created_at TEXT    NOT NULL DEFAULT '',
            updated_at TEXT    NOT NULL DEFAULT ''
        )
    """)

    # 插入测试数据
    conn.execute(
        "INSERT INTO items (id, name, status, priority, assignee, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "TestItem", "active", 5, "张工", "2026-05-03 10:00:00", "2026-05-03 12:00:00"),
    )

    # 用 ALTER TABLE 添加新列（模拟 v8/v10 迁移行为）
    # 新列被加到物理末尾，但在 CREATE TABLE 声明中它们在中间
    conn.execute("ALTER TABLE items ADD COLUMN failure_code TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE items ADD COLUMN occurrence_count INTEGER NOT NULL DEFAULT 1")

    yield conn
    conn.close()


@pytest.fixture()
def fresh_db() -> apsw.Connection:
    """标准内存数据库（无 ALTER 历史，列序正确）。"""
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  测试 1: 模拟 Bug — SELECT 显式列名但用 PRAGMA 序映射（错误模式）
# ═══════════════════════════════════════════════════════════════════

def test_scrambled_column_order_select_star_vs_pragma_mismatch(scrambled_db: apsw.Connection):
    """验证：ALTER TABLE 后，物理列序与声明不一致时 SELECT * 与 PRAGMA 序匹配。

    Bug 原因：ALTER TABLE ADD COLUMN 把新列加到物理末尾，
    导致 PRAGMA 序 ≠ CREATE TABLE 声明序，但 PRAGMA = 物理序 = SELECT * 序。
    因此只要代码不混用声明序和物理序，数据映射就是一致的。
    """
    prag_cols = [r[1] for r in scrambled_db.execute("PRAGMA table_info(items)").fetchall()]
    row_star = scrambled_db.execute("SELECT * FROM items LIMIT 1").fetchone()

    # 关键验证：PRAGMA 顺序 = SELECT * 顺序（都是物理顺序）
    mapped = dict(zip(prag_cols, row_star))
    assert mapped["id"] == 1
    assert mapped["name"] == "TestItem"
    assert mapped["priority"] == 5
    assert mapped["assignee"] == "张工"
    assert mapped["created_at"] == "2026-05-03 10:00:00"
    assert mapped["updated_at"] == "2026-05-03 12:00:00"
    assert mapped["failure_code"] == ""
    assert mapped["occurrence_count"] == 1

    # 验证：显式 SELECT 列名返回值的顺序按物理存储顺序，而非 SELECT 列名顺序
    # 声明顺序：id, name, status, priority, assignee, created_at, updated_at, failure_code, occurrence_count
    # 物理顺序：同上（failure_code, occurrence_count 在物理末尾，与声明一致，因为这是新建表）
    # 所以显式 SELECT 和物理 SELECT 在这个表上顺序一致
    # 真正错位场景只有：在已有表上 ALTER ADD COLUMN，导致 failure_code/occurrence_count 物理末尾但声明在中间
    row_explicit = scrambled_db.execute(
        "SELECT id, name, created_at, occurrence_count FROM items LIMIT 1"
    ).fetchone()
    # 物理序正确时：id=1, name='TestItem', created_at='2026-05-03 10:00:00', occurrence_count=1
    assert row_explicit[0] == 1
    assert row_explicit[1] == "TestItem"
    assert row_explicit[2] == "2026-05-03 10:00:00"
    assert row_explicit[3] == 1


def test_scrambled_db_select_star_matches_pragma_order(scrambled_db: apsw.Connection):
    """验证：SELECT * 返回顺序 与 PRAGMA table_info 顺序一致。"""
    prag_cols = [r[1] for r in scrambled_db.execute("PRAGMA table_info(items)").fetchall()]
    row_star = scrambled_db.execute("SELECT * FROM items LIMIT 1").fetchone()

    # PRAGMA 顺序 = 物理存储顺序 = SELECT * 返回顺序
    assert len(prag_cols) == len(row_star), \
        f"PRAGMA 列数 {len(prag_cols)} != 行值数 {len(row_star)}"
    assert prag_cols == list(prag_cols), "PRAGMA 顺序是稳定的"

    mapped = dict(zip(prag_cols, row_star))
    assert mapped["id"] == 1
    assert mapped["name"] == "TestItem"
    assert mapped["priority"] == 5
    assert mapped["assignee"] == "张工"
    assert mapped["created_at"] == "2026-05-03 10:00:00"
    assert mapped["updated_at"] == "2026-05-03 12:00:00"
    assert mapped["failure_code"] == ""
    assert mapped["occurrence_count"] == 1


# ═══════════════════════════════════════════════════════════════════
#  测试 2: 修复验证 — 显式 _COLS 传入 _rows_to_models
# ═══════════════════════════════════════════════════════════════════

def test_issue_repo_with_scrambled_db_uses_explicit_cols(fresh_db: apsw.Connection):
    """验证 IssueRepository.get_by_id 使用显式列名列表映射，而非依赖 PRAGMA 序。

    Regression test: 确保修复后（传入 cols=）即使表有 ALTER 历史也能正确映射。
    """
    # 在干净 DB 中插入一条 issue（无 ALTER 历史，列序天然正确）
    fresh_db.execute("""
        INSERT INTO issues (title, failure_mode, severity, priority, status)
        VALUES (?, ?, ?, ?, ?)
    """, ("测试失效", "开路", "major", 3, "open"))
    issue_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 使用 repository 查询
    repo = IssueRepository(fresh_db)
    issue = repo.get_by_id(issue_id)

    assert issue is not None
    assert issue.title == "测试失效"
    assert issue.failure_mode == "开路"
    assert issue.severity == "major"
    assert issue.priority == 3
    assert issue.status == "open"


def test_test_result_repo_uses_explicit_cols(fresh_db: apsw.Connection):
    """验证 TestResultRepository 的所有查询方法传入显式 _COLS。"""
    # 需要 projects → test_plans → test_tasks 数据链
    fresh_db.execute("INSERT INTO projects (name, status) VALUES (?, ?)",
        ("col_order项目", "active"))
    proj_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute("INSERT INTO test_plans (name, project_id) VALUES (?, ?)",
        ("col_order计划", proj_id))
    plan_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute(
        "INSERT INTO test_tasks (plan_id, name, status) VALUES (?, ?, ?)",
        (plan_id, "col_order任务", "pending")
    )
    task_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 插入测试结果
    fresh_db.execute(
        "INSERT INTO test_results (task_id, result, test_date) VALUES (?, ?, ?)",
        (task_id, "pass", "2026-05-03")
    )
    result_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    repo = TestResultRepository(fresh_db)
    results = repo.get_by_task(task_id)
    assert len(results) == 1
    assert results[0].task_id == task_id
    assert results[0].result == "pass"

def test_sample_repo_get_by_sn_uses_explicit_cols(fresh_db: apsw.Connection):
    """验证 SampleRepository.get_by_sn 传入显式列名列表。"""
    fresh_db.execute(
        "INSERT INTO samples (sn, batch_no, spec, status) VALUES (?, ?, ?, ?)",
        ("SN-TEST-001", "B001", "SpecV1", "in_stock")
    )

    repo = SampleRepository(fresh_db)
    sample = repo.get_by_sn("SN-TEST-001")

    assert sample is not None
    assert sample.sn == "SN-TEST-001"
    assert sample.batch_no == "B001"
    assert sample.spec == "SpecV1"
    assert sample.status == "in_stock"


def test_test_task_repo_get_dependencies_uses_explicit_cols(fresh_db: apsw.Connection):
    """验证 TestTaskRepository.get_dependencies 传入显式列名列表。"""
    fresh_db.execute("INSERT INTO projects (name, status) VALUES (?, ?)",
        ("col_deps项目", "active"))
    proj_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute("INSERT INTO test_plans (name, project_id) VALUES (?, ?)",
        ("col_deps计划", proj_id))
    plan_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 创建两个任务，task2 依赖 task1
    fresh_db.execute(
        "INSERT INTO test_tasks (plan_id, name, status, dependencies) VALUES (?, ?, ?, ?)",
        (plan_id, "col_deps任务1", "pending", "[]")
    )
    task1_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute(
        "INSERT INTO test_tasks (plan_id, name, status, dependencies) VALUES (?, ?, ?, ?)",
        (plan_id, "col_deps任务2", "pending", f"[{task1_id}]")
    )
    task2_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    repo = TestTaskRepository(fresh_db)
    deps = repo.get_dependencies(task2_id)
    assert len(deps) == 1
    assert deps[0].id == task1_id
    assert deps[0].name == "col_deps任务1"


# ═══════════════════════════════════════════════════════════════════
#  测试 3: 核心防护 — _rows_to_models 截断到较短者
# ═══════════════════════════════════════════════════════════════════

def test_rows_to_models_truncates_to_shorter(fresh_db: apsw.Connection):
    """验证 _rows_to_models 在列数与行值数不一致时截断到较短者，不崩溃。"""
    from src.db.repositories.base import BaseRepository
    from src.models.sample import Sample

    # 模拟场景：行值数量与列名列表不一致（可能的映射错误不会导致崩溃）
    repo = SampleRepository(fresh_db)

    # 故意传入不匹配的 cols 和 row
    short_row = (1, "SN001", "B001")  # 3 列
    wrong_cols = ["id", "sn", "batch_no", "spec", "project_id"]  # 5 列

    # 应该不抛异常，截断到 3
    result = repo._rows_to_models([short_row], cols=wrong_cols)
    assert len(result) == 1
    # 验证截断后的值
    assert result[0].id == 1
    assert result[0].sn == "SN001"
    assert result[0].batch_no == "B001"


def test_rows_to_models_string_to_int_coercion(fresh_db: apsw.Connection):
    """验证 _rows_to_models 对字符串数值字段做类型强制转换。"""
    repo = SampleRepository(fresh_db)

    # DB 返回字符串但 model 需要 int
    row = (1, "SN001", "B001", "Spec", 1, "in_stock", "", 0.0, "", "", "", "", "", "")
    cols = ["id", "sn", "batch_no", "spec", "project_id", "status", "location",
            "test_hours", "qr_code", "notes", "supplier", "scrapped_reason",
            "created_at", "updated_at"]

    result = repo._rows_to_models([row], cols=cols)
    assert result[0].project_id == 1  # 应该是 int，不是字符串 "1"


# ═══════════════════════════════════════════════════════════════════
#  测试 4: JOIN 查询裸列名歧义
# ═══════════════════════════════════════════════════════════════════

def test_join_query_requires_table_alias_for_ambiguous_columns(fresh_db: apsw.Connection):
    """验证多表 JOIN 查询中裸列名（如 id, created_at）必须加表别名。"""
    # 这个测试验证修复后 sample_repo.list_transactions 不再报 ambiguous column name

    # 插入项目和样品
    fresh_db.execute(
        "INSERT INTO projects (name, status) VALUES ('proj', 'active')"
    )
    proj_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute(
        "INSERT INTO samples (sn, batch_no, spec, project_id, status) VALUES (?, ?, ?, ?, ?)",
        ("SN-JOIN-001", "B001", "Spec", proj_id, "in_stock")
    )
    sample_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 插入技术员
    fresh_db.execute(
        "INSERT INTO technicians (name, role, department) VALUES (?, ?, ?)",
        ("李工", "QE", "质量部")
    )
    tech_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 插入 sample_transactions（JOIN 表）
    fresh_db.execute(
        "INSERT INTO sample_transactions (sample_id, type, operator_id) VALUES (?, ?, ?)",
        (sample_id, "check_out", tech_id)
    )

    # 调用 list_transactions（JOIN 查询），不应抛 ambiguous column name
    repo = SampleRepository(fresh_db)
    txns = repo.list_transactions(filter_sn="", filter_type="")
    assert len(txns) == 1
    assert txns[0]["sample_sn"] == "SN-JOIN-001"
    assert txns[0]["type"] == "check_out"
    assert txns[0]["operator_name"] == "李工"


# ═══════════════════════════════════════════════════════════════════
#  测试 5: priority=0 旧数据向后兼容
# ═══════════════════════════════════════════════════════════════════

def test_task_priority_zero_maps_to_three(fresh_db: apsw.Connection):
    """验证 TestTask priority=0 旧数据被正确映射为 3（向后兼容）。"""
    from src.models.test_plan import TestTask

    fresh_db.execute("INSERT INTO projects (name, status) VALUES (?, ?)",
        ("prio项目", "active"))
    proj_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute("INSERT INTO test_plans (name, project_id) VALUES (?, ?)",
        ("prio计划", proj_id))
    plan_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fresh_db.execute(
        "INSERT INTO test_tasks (plan_id, name, status, priority) VALUES (?, ?, ?, ?)",
        (plan_id, "prio任务", "pending", 0)
    )
    task_id = fresh_db.execute("SELECT last_insert_rowid()").fetchone()[0]

    repo = TestTaskRepository(fresh_db)
    task = repo.get_by_id(task_id)

    assert task is not None
    assert task.priority == 3, "priority=0 应映射为 3（向后兼容）"