"""数据库 Schema 定义与版本管理。

包含所有 12 张表的 DDL，通过 schema_version 表追踪版本，
支持增量迁移。
"""

from __future__ import annotations

import apsw

SCHEMA_VERSION = 1

# ═══════════════════════════════════════════════════════════════════
#  表 DDL
# ═══════════════════════════════════════════════════════════════════

_DDL_TABLES: list[str] = [
    # ── schema_version（迁移追踪）──
    """CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL,
        applied_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 项目 ──
    """CREATE TABLE IF NOT EXISTS projects (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        product     TEXT    NOT NULL DEFAULT '',
        customer    TEXT    NOT NULL DEFAULT '',
        description TEXT    NOT NULL DEFAULT '',
        status      TEXT    NOT NULL DEFAULT 'active',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 设备 ──
    """CREATE TABLE IF NOT EXISTS equipment (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        type        TEXT    NOT NULL DEFAULT '',
        model       TEXT    NOT NULL DEFAULT '',
        location    TEXT    NOT NULL DEFAULT '',
        status      TEXT    NOT NULL DEFAULT 'available',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 人员 ──
    """CREATE TABLE IF NOT EXISTS technicians (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        role        TEXT    NOT NULL DEFAULT '',
        department  TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 样品 ──
    """CREATE TABLE IF NOT EXISTS samples (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sn          TEXT    NOT NULL UNIQUE,
        batch_no    TEXT    NOT NULL DEFAULT '',
        spec        TEXT    NOT NULL DEFAULT '',
        project_id  INTEGER REFERENCES projects(id),
        status      TEXT    NOT NULL DEFAULT 'in_stock',
        location    TEXT    NOT NULL DEFAULT '',
        qr_code     TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 样品出入库记录 ──
    """CREATE TABLE IF NOT EXISTS sample_transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        sample_id       INTEGER NOT NULL REFERENCES samples(id),
        type            TEXT    NOT NULL,
        operator_id     INTEGER REFERENCES technicians(id),
        purpose         TEXT    NOT NULL DEFAULT '',
        related_task_id INTEGER DEFAULT NULL,
        expected_return TEXT    DEFAULT '',
        actual_return   TEXT    DEFAULT '',
        notes           TEXT    NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 测试计划 ──
    """CREATE TABLE IF NOT EXISTS test_plans (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id      INTEGER NOT NULL REFERENCES projects(id),
        name            TEXT    NOT NULL,
        test_standard   TEXT    NOT NULL DEFAULT '',
        start_date      TEXT    NOT NULL DEFAULT '',
        end_date        TEXT    NOT NULL DEFAULT '',
        status          TEXT    NOT NULL DEFAULT 'draft',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 测试任务 ──
    """CREATE TABLE IF NOT EXISTS test_tasks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id         INTEGER NOT NULL REFERENCES test_plans(id),
        name            TEXT    NOT NULL,
        category        TEXT    NOT NULL DEFAULT '',
        test_standard   TEXT    NOT NULL DEFAULT '',
        technician_id   INTEGER REFERENCES technicians(id),
        equipment_id    INTEGER REFERENCES equipment(id),
        sample_ids      TEXT    NOT NULL DEFAULT '[]',
        duration        INTEGER NOT NULL DEFAULT 1,
        start_day       INTEGER NOT NULL DEFAULT 0,
        progress        REAL    NOT NULL DEFAULT 0.0,
        status          TEXT    NOT NULL DEFAULT 'pending',
        priority        INTEGER NOT NULL DEFAULT 3,
        environment     TEXT    NOT NULL DEFAULT '{}',
        log_file        TEXT    NOT NULL DEFAULT '',
        dependencies    TEXT    NOT NULL DEFAULT '[]',
        notes           TEXT    NOT NULL DEFAULT '',
        sort_order      INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 测试结果 ──
    """CREATE TABLE IF NOT EXISTS test_results (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id         INTEGER NOT NULL REFERENCES test_tasks(id),
        sample_id       INTEGER DEFAULT NULL REFERENCES samples(id),
        result          TEXT    NOT NULL DEFAULT 'pending',
        test_date       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        tester_id       INTEGER REFERENCES technicians(id),
        environment     TEXT    NOT NULL DEFAULT '{}',
        notes           TEXT    NOT NULL DEFAULT '',
        attachments     TEXT    NOT NULL DEFAULT '[]',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue / 失效追踪 ──
    """CREATE TABLE IF NOT EXISTS issues (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id      INTEGER REFERENCES projects(id),
        plan_id         INTEGER REFERENCES test_plans(id),
        task_id         INTEGER REFERENCES test_tasks(id),
        sample_id       INTEGER REFERENCES samples(id),
        title           TEXT    NOT NULL,
        failure_mode    TEXT    NOT NULL DEFAULT '',
        failure_stage   TEXT    NOT NULL DEFAULT '',
        description     TEXT    NOT NULL DEFAULT '',
        severity        TEXT    NOT NULL DEFAULT 'major',
        status          TEXT    NOT NULL DEFAULT 'open',
        priority        INTEGER NOT NULL DEFAULT 3,
        assignee_id     INTEGER REFERENCES technicians(id),
        root_cause      TEXT    NOT NULL DEFAULT '',
        resolution      TEXT    NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── FA 分析记录 ──
    """CREATE TABLE IF NOT EXISTS fa_records (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id        INTEGER NOT NULL REFERENCES issues(id),
        step_no         INTEGER NOT NULL DEFAULT 1,
        step_title      TEXT    NOT NULL DEFAULT '',
        description     TEXT    NOT NULL DEFAULT '',
        method          TEXT    NOT NULL DEFAULT '',
        findings        TEXT    NOT NULL DEFAULT '',
        analyst_id      INTEGER REFERENCES technicians(id),
        attachments     TEXT    NOT NULL DEFAULT '[]',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue 附件 ──
    """CREATE TABLE IF NOT EXISTS issue_attachments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id    INTEGER NOT NULL REFERENCES issues(id),
        file_path   TEXT    NOT NULL,
        file_type   TEXT    NOT NULL DEFAULT 'image',
        description TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 知识库（Phase 2 预建）──
    """CREATE TABLE IF NOT EXISTS knowledge_entries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        failure_mode    TEXT    NOT NULL,
        keywords        TEXT    NOT NULL DEFAULT '[]',
        summary         TEXT    NOT NULL DEFAULT '',
        root_cause      TEXT    NOT NULL DEFAULT '',
        resolution      TEXT    NOT NULL DEFAULT '',
        related_issues  TEXT    NOT NULL DEFAULT '[]',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 系统设置 ──
    """CREATE TABLE IF NOT EXISTS settings (
        key         TEXT    UNIQUE PRIMARY KEY,
        value       TEXT    NOT NULL,
        updated_at  TEXT    DEFAULT (datetime('now','localtime'))
    )""",
]

# ═══════════════════════════════════════════════════════════════════
#  索引 DDL
# ═══════════════════════════════════════════════════════════════════

_DDL_INDEXES: list[str] = [
    # samples
    "CREATE INDEX IF NOT EXISTS idx_samples_sn ON samples(sn)",
    "CREATE INDEX IF NOT EXISTS idx_samples_batch ON samples(batch_no)",
    "CREATE INDEX IF NOT EXISTS idx_samples_project ON samples(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status)",
    # sample_transactions
    "CREATE INDEX IF NOT EXISTS idx_txn_sample ON sample_transactions(sample_id)",
    "CREATE INDEX IF NOT EXISTS idx_txn_type ON sample_transactions(type)",
    "CREATE INDEX IF NOT EXISTS idx_txn_created ON sample_transactions(created_at)",
    # test_plans
    "CREATE INDEX IF NOT EXISTS idx_plans_project ON test_plans(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_plans_status ON test_plans(status)",
    # test_tasks
    "CREATE INDEX IF NOT EXISTS idx_tasks_plan ON test_tasks(plan_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_category ON test_tasks(category)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON test_tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_technician ON test_tasks(technician_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_equipment ON test_tasks(equipment_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_sort ON test_tasks(plan_id, sort_order)",
    # test_results
    "CREATE INDEX IF NOT EXISTS idx_results_task ON test_results(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_results_sample ON test_results(sample_id)",
    # issues
    "CREATE INDEX IF NOT EXISTS idx_issues_project ON issues(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_issues_task ON issues(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)",
    "CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity)",
    "CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues(assignee_id)",
    # fa_records
    "CREATE INDEX IF NOT EXISTS idx_fa_issue ON fa_records(issue_id)",
    # issue_attachments
    "CREATE INDEX IF NOT EXISTS idx_attachments_issue ON issue_attachments(issue_id)",
    # knowledge_entries
    "CREATE INDEX IF NOT EXISTS idx_knowledge_mode ON knowledge_entries(failure_mode)",
    # equipment
    "CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status)",
    # technicians
    "CREATE INDEX IF NOT EXISTS idx_technicians_name ON technicians(name)",
]


# ═══════════════════════════════════════════════════════════════════
#  迁移函数（将来每个版本一个函数）
# ═══════════════════════════════════════════════════════════════════

def _migrate_v1(conn: apsw.Connection) -> None:
    """从零创建 v1 schema（初始版本）。"""
    for ddl in _DDL_TABLES:
        conn.execute(ddl)
    for ddl in _DDL_INDEXES:
        conn.execute(ddl)
    # 记录版本
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )


def _get_current_version(conn: apsw.Connection) -> int:
    """读取当前 schema 版本号。数据库为空时返回 0。"""
    try:
        cursor = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    except apsw.SQLError:
        return 0


# ═══════════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════════

def init_schema(conn: apsw.Connection) -> int:
    """初始化数据库 schema，按需执行迁移。

    Args:
        conn: apsw 数据库连接。

    Returns:
        初始化后的 schema 版本号。
    """
    # 确保迁移追踪表存在
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER NOT NULL,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )"""
    )

    current = _get_current_version(conn)

    if current < 1:
        _migrate_v1(conn)

    # 将来在此处添加：
    # if current < 2:
    #     _migrate_v2(conn)
    # if current < 3:
    #     _migrate_v3(conn)

    return _get_current_version(conn)
