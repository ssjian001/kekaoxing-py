"""数据库 Schema 定义与版本管理。

包含所有 16 张表的 DDL，通过 schema_version 表追踪版本，
支持增量迁移。
"""

from __future__ import annotations

import logging

import apsw

from src.db.sql_ident import is_safe_ident, quote_ident

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 28

# ═══════════════════════════════════════════════════════════════════
#  表 DDL
# ═══════════════════════════════════════════════════════════════════

_DDL_TABLES: list[str] = [
    # ── schema_version（迁移追踪）──
    """CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL UNIQUE,
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
        asset_no    TEXT    NOT NULL DEFAULT '',
        manufacturer TEXT   NOT NULL DEFAULT '',
        accuracy    TEXT    NOT NULL DEFAULT '',
        calibration_date TEXT NOT NULL DEFAULT '',
        next_calibration_date TEXT NOT NULL DEFAULT '',
        calibration_interval_months INTEGER NOT NULL DEFAULT 12,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 人员 ──
    """CREATE TABLE IF NOT EXISTS technicians (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        employee_id TEXT    NOT NULL DEFAULT '',
        role        TEXT    NOT NULL DEFAULT '',
        department  TEXT    NOT NULL DEFAULT '',
        phone       TEXT    NOT NULL DEFAULT '',
        email       TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 样品 ──
    """CREATE TABLE IF NOT EXISTS samples (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sn          TEXT    NOT NULL UNIQUE,
        batch_no    TEXT    NOT NULL DEFAULT '',
        spec        TEXT    NOT NULL DEFAULT '',
        project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        status      TEXT    NOT NULL DEFAULT 'in_stock',
        location    TEXT    NOT NULL DEFAULT '',
        test_hours  REAL    NOT NULL DEFAULT 0.0,
        qr_code     TEXT    NOT NULL DEFAULT '',
        notes       TEXT    NOT NULL DEFAULT '',
        supplier         TEXT    NOT NULL DEFAULT '',
        scrapped_reason  TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 样品出入库记录 ──
    """CREATE TABLE IF NOT EXISTS sample_transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        sample_id       INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
        type            TEXT    NOT NULL,
        operator_id     INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        purpose         TEXT    NOT NULL DEFAULT '',
        related_task_id INTEGER DEFAULT NULL REFERENCES test_tasks(id) ON DELETE SET NULL,
        expected_return TEXT    DEFAULT '',
        actual_return   TEXT    DEFAULT '',
        notes           TEXT    NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 测试计划 ──
    """CREATE TABLE IF NOT EXISTS test_plans (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name            TEXT    NOT NULL,
        test_standard   TEXT    NOT NULL DEFAULT '',
        start_date      TEXT    NOT NULL DEFAULT '',
        end_date        TEXT    NOT NULL DEFAULT '',
        status          TEXT    NOT NULL DEFAULT 'draft',
        apqp_phase      TEXT    NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        task_prefix     TEXT    NOT NULL DEFAULT '',
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 测试任务 ──
    """CREATE TABLE IF NOT EXISTS test_tasks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id         INTEGER NOT NULL REFERENCES test_plans(id) ON DELETE CASCADE,
        name            TEXT    NOT NULL,
        category        TEXT    NOT NULL DEFAULT '',
        test_standard   TEXT    NOT NULL DEFAULT '',
        technician_id   INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        equipment_id    INTEGER REFERENCES equipment(id) ON DELETE SET NULL,
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
        temperature     TEXT    NOT NULL DEFAULT '',
        humidity        TEXT    NOT NULL DEFAULT '',
        accept_criteria TEXT    NOT NULL DEFAULT '',
        sort_order      INTEGER NOT NULL DEFAULT 0,
        actual_start_date TEXT  NOT NULL DEFAULT '',
        actual_end_date   TEXT  NOT NULL DEFAULT '',
        manual_scheduled INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 测试结果 ──
    """CREATE TABLE IF NOT EXISTS test_results (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id         INTEGER NOT NULL REFERENCES test_tasks(id) ON DELETE CASCADE,
        sample_id       INTEGER DEFAULT NULL REFERENCES samples(id) ON DELETE SET NULL,
        result          TEXT    NOT NULL DEFAULT 'pending',
        test_date       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        tester_id       INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        environment     TEXT    NOT NULL DEFAULT '{}',
        notes           TEXT    NOT NULL DEFAULT '',
        attachments     TEXT    NOT NULL DEFAULT '[]',
        measured_value  TEXT    NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue / 失效追踪 ──
    """CREATE TABLE IF NOT EXISTS issues (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        plan_id         INTEGER REFERENCES test_plans(id) ON DELETE CASCADE,
        task_id         INTEGER REFERENCES test_tasks(id) ON DELETE CASCADE,
        sample_id       INTEGER REFERENCES samples(id) ON DELETE CASCADE,
        title           TEXT    NOT NULL,
        failure_mode    TEXT    NOT NULL DEFAULT '',
        failure_stage   TEXT    NOT NULL DEFAULT '',
        description     TEXT    NOT NULL DEFAULT '',
        severity        TEXT    NOT NULL DEFAULT 'major',
        status          TEXT    NOT NULL DEFAULT 'open',
        priority        INTEGER NOT NULL DEFAULT 3,
        assignee_id     INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        category        TEXT    NOT NULL DEFAULT '',
        root_cause      TEXT    NOT NULL DEFAULT '',
        resolution      TEXT    NOT NULL DEFAULT '',
        reporter_name   TEXT    NOT NULL DEFAULT '',
        failure_code    TEXT    NOT NULL DEFAULT '',
        occurrence_count INTEGER NOT NULL DEFAULT 1,
        is_deleted      INTEGER NOT NULL DEFAULT 0,
        deleted_at      TEXT    NOT NULL DEFAULT '',
        dri_name        TEXT    NOT NULL DEFAULT '',
        improvement_measures TEXT NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── FA 分析记录 ──
    """CREATE TABLE IF NOT EXISTS fa_records (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id        INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        step_no         INTEGER NOT NULL DEFAULT 1,
        step_title      TEXT    NOT NULL DEFAULT '',
        description     TEXT    NOT NULL DEFAULT '',
        method          TEXT    NOT NULL DEFAULT '',
        findings        TEXT    NOT NULL DEFAULT '',
        possible_cause  TEXT    NOT NULL DEFAULT '',
        cause_category  TEXT    NOT NULL DEFAULT '',
        failure_mechanism TEXT  NOT NULL DEFAULT '',
        confirmed       INTEGER NOT NULL DEFAULT 0,
        analyst_id      INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        attachments     TEXT    NOT NULL DEFAULT '[]',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue 附件 ──
    """CREATE TABLE IF NOT EXISTS issue_attachments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        file_path   TEXT    NOT NULL,
        file_type   TEXT    NOT NULL DEFAULT 'image',
        description TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── CAPA 纠正预防措施 ──
    """CREATE TABLE IF NOT EXISTS capa_records (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id            INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        action              TEXT    NOT NULL,
        assignee_id         INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        assignee_name       TEXT    NOT NULL DEFAULT '',
        due_date            TEXT    NOT NULL DEFAULT '',
        status              TEXT    NOT NULL DEFAULT 'pending',
        verification_result TEXT    NOT NULL DEFAULT '',
        verified_by         INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
        verifier_name     TEXT    DEFAULT '',
        root_cause          TEXT    DEFAULT '',
        effectiveness       TEXT    DEFAULT '',
        follow_up           TEXT    DEFAULT '',
        created_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue 评论（v23 新增）──
    """CREATE TABLE IF NOT EXISTS issue_comments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        author_name TEXT    NOT NULL DEFAULT '',
        content     TEXT    NOT NULL,
        is_deleted  INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue 活动日志（v23 新增 — 自动记录字段变更）──
    """CREATE TABLE IF NOT EXISTS issue_activity_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        field       TEXT    NOT NULL,
        old_value   TEXT    NOT NULL DEFAULT '',
        new_value   TEXT    NOT NULL DEFAULT '',
        operator    TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── Issue 关联（v23 新增 — 阻塞/重复/关联等关系）──
    """CREATE TABLE IF NOT EXISTS issue_links (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id   INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        target_id   INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        link_type   TEXT    NOT NULL DEFAULT 'relates_to',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        CHECK(source_id != target_id),
        UNIQUE(source_id, target_id, link_type)
    )""",

    # ── 知识库（Phase 2 预建）──
    """CREATE TABLE IF NOT EXISTS knowledge_entries (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        category          TEXT    NOT NULL DEFAULT '',
        failure_mode      TEXT    NOT NULL DEFAULT '',
        cause_analysis    TEXT    NOT NULL DEFAULT '',
        improvement       TEXT    NOT NULL DEFAULT '',
        reference_standard TEXT   NOT NULL DEFAULT '',
        keywords          TEXT    NOT NULL DEFAULT '[]',
        summary           TEXT    NOT NULL DEFAULT '',
        root_cause        TEXT    NOT NULL DEFAULT '',
        resolution        TEXT    NOT NULL DEFAULT '',
        related_issues    TEXT    NOT NULL DEFAULT '[]',
        created_at        TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 待办事项 (v26) ──
    """CREATE TABLE IF NOT EXISTS todos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        title       TEXT    NOT NULL,
        description TEXT    NOT NULL DEFAULT '',
        priority    TEXT    NOT NULL DEFAULT 'medium',
        status      TEXT    NOT NULL DEFAULT 'pending',
        category    TEXT    NOT NULL DEFAULT '',
        due_date    TEXT    NOT NULL DEFAULT '',
        remind_at   TEXT    NOT NULL DEFAULT '',
        reminded    INTEGER NOT NULL DEFAULT 0,
        archived    INTEGER NOT NULL DEFAULT 0,
        quadrant    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    )""",

    # ── 系统设置 ──
    """CREATE TABLE IF NOT EXISTS settings (
        key         TEXT    PRIMARY KEY,
        value       TEXT    NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS holidays (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL UNIQUE,
        name        TEXT    NOT NULL DEFAULT '',
        source      TEXT    NOT NULL DEFAULT 'builtin'
    )""",
]

# ═══════════════════════════════════════════════════════════════════
#  索引 DDL
# ═══════════════════════════════════════════════════════════════════

_DDL_INDEXES: list[str] = [
    # samples (sn 已有 UNIQUE 隐式索引，无需显式创建)
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
    # capa_records
    "CREATE INDEX IF NOT EXISTS idx_capa_issue ON capa_records(issue_id)",
    "CREATE INDEX IF NOT EXISTS idx_capa_status ON capa_records(status)",
    # issue_comments (v23)
    "CREATE INDEX IF NOT EXISTS idx_comments_issue ON issue_comments(issue_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_created ON issue_comments(created_at)",
    # issue_activity_log (v23)
    "CREATE INDEX IF NOT EXISTS idx_activity_issue ON issue_activity_log(issue_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_created ON issue_activity_log(created_at)",
    # issue_activity_log (v24): project_id 筛选
    "CREATE INDEX IF NOT EXISTS idx_activity_project ON issue_activity_log(project_id)",
    # issue_links (v23)
    "CREATE INDEX IF NOT EXISTS idx_links_source ON issue_links(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_links_target ON issue_links(target_id)",
    # knowledge_entries
    "CREATE INDEX IF NOT EXISTS idx_knowledge_mode ON knowledge_entries(failure_mode)",
    # equipment
    "CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status)",
    # technicians
    "CREATE INDEX IF NOT EXISTS idx_technicians_name ON technicians(name)",
    # todos (v25)
    "CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)",
    # todos (v26)
    "CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at)",
    "CREATE INDEX IF NOT EXISTS idx_todos_quadrant ON todos(quadrant)",
    # todos (v27)
    "CREATE INDEX IF NOT EXISTS idx_todos_archived ON todos(archived)",
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
        "INSERT INTO schema_version (version) VALUES (1)",
    )


def _migrate_v2(conn: apsw.Connection) -> None:
    """v2: 设备表新增校准日期字段（如果 CREATE TABLE 已包含则跳过）。

    注意：v8 也会添加 calibration_date / next_calibration_date，
    因为早期 v1→v8 升级路径可能跳过 v2。v2 是首次引入这些字段的版本。
    """
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(equipment)").fetchall()
    }
    for col in ("calibration_date", "next_calibration_date"):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE equipment ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (2)"
    )


def _migrate_v3(conn: apsw.Connection) -> None:
    """v3: 技术员表新增工号、联系方式、邮箱字段（如果 CREATE TABLE 已包含则跳过）。"""
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(technicians)").fetchall()
    }
    for col, default in [("employee_id", ""), ("phone", ""), ("email", "")]:
        if col not in cols:
            conn.execute(
                f"ALTER TABLE technicians ADD COLUMN {col} TEXT NOT NULL DEFAULT '{default}'"
            )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (3)"
    )


def _migrate_v4(conn: apsw.Connection) -> None:
    """v4: test_tasks 表新增 temperature, humidity 环境参数字段。"""
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(test_tasks)").fetchall()
    }
    for col in ("temperature", "humidity"):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE test_tasks ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (4)"
    )


def _migrate_v5(conn: apsw.Connection) -> None:
    """v5: knowledge_entries 表新增 category, cause_analysis, improvement, reference_standard 字段。"""
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(knowledge_entries)").fetchall()
    }
    for col in ("category", "cause_analysis", "improvement", "reference_standard"):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE knowledge_entries ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (5)"
    )


def _migrate_v6(conn: apsw.Connection) -> None:
    """v6: test_tasks 表新增 actual_start_date, actual_end_date 字段。"""
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(test_tasks)").fetchall()
    }
    for col in ("actual_start_date", "actual_end_date"):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE test_tasks ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (6)"
    )


def _migrate_v7(conn: apsw.Connection) -> None:
    """v7: test_tasks 增加 accept_criteria; fa_records 增加 possible_cause/cause_category/confirmed; 新增 capa_records 表。"""
    # test_tasks: accept_criteria
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(test_tasks)").fetchall()
    }
    if "accept_criteria" not in cols:
        conn.execute(
            "ALTER TABLE test_tasks ADD COLUMN accept_criteria TEXT NOT NULL DEFAULT ''"
        )

    # fa_records: possible_cause, cause_category, confirmed
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(fa_records)").fetchall()
    }
    for col, col_type, default in [
        ("possible_cause", "TEXT", "''"),
        ("cause_category", "TEXT", "''"),
        ("confirmed", "INTEGER", "0"),
    ]:
        if col not in cols:
            conn.execute(
                f"ALTER TABLE fa_records ADD COLUMN {col} {col_type} NOT NULL DEFAULT {default}"
            )

    # capa_records 表（仅新增，已存在则跳过）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS capa_records (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id            INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            action              TEXT    NOT NULL,
            assignee_id         INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            due_date            TEXT    NOT NULL DEFAULT '',
            status              TEXT    NOT NULL DEFAULT 'pending',
            verification_result TEXT    NOT NULL DEFAULT '',
            verified_by         INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )"""
    )
    # capa_records 索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_capa_issue ON capa_records(issue_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_capa_status ON capa_records(status)")

    conn.execute(
        "INSERT INTO schema_version (version) VALUES (7)"
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


def _migrate_v8(conn: apsw.Connection) -> None:
    """v7→v8: equipment 校准字段 + samples test_hours + test_results measured_value。

    注意：calibration_date / next_calibration_date 首次在 v2 引入，
    v8 追加了 calibration_interval_months 并确保前两列在旧库中存在（幂等）。
    """
    # Equipment calibration fields
    cols = {r[1] for r in conn.execute("PRAGMA table_info(equipment)").fetchall()}
    for col, col_type, default in [
        ("calibration_date", "TEXT", "''"),
        ("next_calibration_date", "TEXT", "''"),
        ("calibration_interval_months", "INTEGER", "12"),
    ]:
        if col not in cols:
            conn.execute(
                f"ALTER TABLE equipment ADD COLUMN {col} {col_type} NOT NULL DEFAULT {default}"
            )
    # Sample test_hours
    sample_cols = {r[1] for r in conn.execute("PRAGMA table_info(samples)").fetchall()}
    if "test_hours" not in sample_cols:
        conn.execute(
            "ALTER TABLE samples ADD COLUMN test_hours REAL NOT NULL DEFAULT 0.0"
        )
    for col in ("supplier", "scrapped_reason"):
        if col not in sample_cols:
            conn.execute(
                f"ALTER TABLE samples ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )
    # test_results measured_value
    result_cols = {r[1] for r in conn.execute("PRAGMA table_info(test_results)").fetchall()}
    if "measured_value" not in result_cols:
        conn.execute(
            "ALTER TABLE test_results ADD COLUMN measured_value TEXT NOT NULL DEFAULT ''"
        )
    # test_plans: apqp_phase
    plan_cols = {r[1] for r in conn.execute("PRAGMA table_info(test_plans)").fetchall()}
    if "apqp_phase" not in plan_cols:
        conn.execute(
            "ALTER TABLE test_plans ADD COLUMN apqp_phase TEXT NOT NULL DEFAULT ''"
        )
    # issues: failure_code, occurrence_count
    issue_cols = {r[1] for r in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "failure_code" not in issue_cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN failure_code TEXT NOT NULL DEFAULT ''"
        )
    if "occurrence_count" not in issue_cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN occurrence_count INTEGER NOT NULL DEFAULT 1"
        )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (8)"
    )


def _migrate_v9(conn: apsw.Connection) -> None:
    """v8→v9: fa_records 增加 failure_mechanism 失效机理分类。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fa_records)").fetchall()}
    if "failure_mechanism" not in cols:
        conn.execute(
            "ALTER TABLE fa_records ADD COLUMN failure_mechanism TEXT NOT NULL DEFAULT ''"
        )
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (9)"
    )


_SEED_HOLIDAYS_2025: tuple[tuple[str, str], ...] = (
    ("2025-01-01", "元旦"),
    ("2025-01-28", "春节"), ("2025-01-29", "春节"), ("2025-01-30", "春节"),
    ("2025-01-31", "春节"), ("2025-02-01", "春节"), ("2025-02-02", "春节"),
    ("2025-02-03", "春节"), ("2025-02-04", "春节"),
    ("2025-04-04", "清明"), ("2025-04-05", "清明"), ("2025-04-06", "清明"),
    ("2025-05-01", "劳动节"), ("2025-05-02", "劳动节"), ("2025-05-03", "劳动节"),
    ("2025-05-04", "劳动节"), ("2025-05-05", "劳动节"),
    ("2025-05-31", "端午"), ("2025-06-01", "端午"), ("2025-06-02", "端午"),
    ("2025-10-01", "国庆"), ("2025-10-02", "国庆"), ("2025-10-03", "国庆"),
    ("2025-10-04", "国庆"), ("2025-10-05", "国庆"), ("2025-10-06", "国庆"),
    ("2025-10-07", "国庆"), ("2025-10-08", "国庆"),
)


_SEED_HOLIDAYS_2026: tuple[tuple[str, str], ...] = (
    ("2026-01-01", "元旦"), ("2026-01-02", "元旦"), ("2026-01-03", "元旦"),
    ("2026-02-17", "春节"), ("2026-02-18", "春节"), ("2026-02-19", "春节"),
    ("2026-02-20", "春节"), ("2026-02-21", "春节"), ("2026-02-22", "春节"),
    ("2026-02-23", "春节"),
    ("2026-04-04", "清明"), ("2026-04-05", "清明"), ("2026-04-06", "清明"),
    ("2026-05-01", "劳动节"), ("2026-05-02", "劳动节"), ("2026-05-03", "劳动节"),
    ("2026-05-04", "劳动节"), ("2026-05-05", "劳动节"),
    ("2026-05-30", "端午"), ("2026-05-31", "端午"), ("2026-06-01", "端午"),
    ("2026-10-01", "国庆"), ("2026-10-02", "国庆"), ("2026-10-03", "国庆"),
    ("2026-10-04", "国庆"), ("2026-10-05", "国庆"), ("2026-10-06", "国庆"),
    ("2026-10-07", "国庆"),
)


def _migrate_v10(conn: apsw.Connection) -> None:
    """v9→v10: 新建 holidays 表 + 种子数据。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS holidays (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL UNIQUE,
            name        TEXT    NOT NULL DEFAULT '',
            source      TEXT    NOT NULL DEFAULT 'builtin'
        )"""
    )
    # 插入种子数据（INSERT OR IGNORE 防重复）
    for date_str, name in _SEED_HOLIDAYS_2025 + _SEED_HOLIDAYS_2026:
        conn.execute(
            "INSERT OR IGNORE INTO holidays (date, name, source) VALUES (?, ?, 'builtin')",
            (date_str, name),
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (10)")


def _rebuild_table(conn: apsw.Connection, name: str, new_ddl: str) -> None:
    """通过 DROP TABLE + RENAME 重建表（用于 SQLite 不支持的 ALTER CONSTRAINT）。

    步骤：CREATE name_new → INSERT 显式列名 → DROP name → RENAME name_new → name
    需在 PRAGMA foreign_keys = OFF 环境下调用。
    使用新表列名显式映射，避免 SELECT * 在列顺序不一致时数据错乱。
    """
    if not is_safe_ident(name):
        raise ValueError(f"非法表名: {name!r}")
    conn.execute(f"DROP TABLE IF EXISTS {quote_ident(name + '_new')}")
    conn.execute(new_ddl)
    # 获取新表列名（从 new_ddl 创建的表）
    new_cols = [
        r[1] for r in conn.execute(
            f"PRAGMA table_info({quote_ident(name + '_new')})"
        ).fetchall()
    ]
    # 获取旧表列名
    old_cols = [
        r[1] for r in conn.execute(
            f"PRAGMA table_info({quote_ident(name)})"
        ).fetchall()
    ]
    # 只取新表中在旧表里也存在的列（交集），确保数据安全
    common_cols = [c for c in new_cols if c in old_cols]
    cols_str = ", ".join(quote_ident(c) for c in common_cols)
    try:
        conn.execute(
            f"INSERT INTO {quote_ident(name + '_new')} ({cols_str})"
            f" SELECT {cols_str} FROM {quote_ident(name)}"
        )
    except Exception:
        logger.exception("DDL rebuild failed")
        # 迁移失败：清理 _new 表，保留原始数据不丢失
        conn.execute(f"DROP TABLE IF EXISTS {quote_ident(name + '_new')}")
        raise
    conn.execute(f"DROP TABLE {quote_ident(name)}")
    conn.execute(f"ALTER TABLE {quote_ident(name + '_new')} RENAME TO {quote_ident(name)}")


def _migrate_v11(conn: apsw.Connection) -> None:
    """v10→v11: 为所有外键列补充 ON DELETE SET NULL 策略。

    SQLite 不支持 ALTER TABLE ADD CONSTRAINT，迁移通过表重建实现。
    使用 _rebuild_table 辅助函数避免重复代码。

    ⚠️ 涉及 DROP TABLE / CREATE TABLE / RENAME（SQLite DDL 不可回滚）。
    schema_version 记录在重建全部成功后最后写入，确保版本与实际状态一致。
    若中途崩溃，schema_version 保持旧版本号，下次启动会重试迁移。
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # ── 重建顺序：先子表后父表 ──
        _rebuild_table(conn, "issue_attachments", """CREATE TABLE issue_attachments_new (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            file_path   TEXT    NOT NULL,
            file_type   TEXT    NOT NULL DEFAULT 'image',
            description TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        _rebuild_table(conn, "fa_records", """CREATE TABLE fa_records_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id        INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            step_no         INTEGER NOT NULL DEFAULT 1,
            step_title      TEXT    NOT NULL DEFAULT '',
            description     TEXT    NOT NULL DEFAULT '',
            method          TEXT    NOT NULL DEFAULT '',
            findings        TEXT    NOT NULL DEFAULT '',
            possible_cause  TEXT    NOT NULL DEFAULT '',
            cause_category  TEXT    NOT NULL DEFAULT '',
            failure_mechanism TEXT  NOT NULL DEFAULT '',
            confirmed       INTEGER NOT NULL DEFAULT 0,
            analyst_id      INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            attachments     TEXT    NOT NULL DEFAULT '[]',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        _rebuild_table(conn, "capa_records", """CREATE TABLE capa_records_new (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id            INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            action              TEXT    NOT NULL,
            assignee_id         INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            assignee_name       TEXT    NOT NULL DEFAULT '',
            due_date            TEXT    NOT NULL DEFAULT '',
            status              TEXT    NOT NULL DEFAULT 'pending',
            verification_result TEXT    NOT NULL DEFAULT '',
            verified_by         INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            root_cause          TEXT    DEFAULT '',
            effectiveness       TEXT    DEFAULT '',
            follow_up           TEXT    DEFAULT '',
            created_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        _rebuild_table(conn, "sample_transactions", """CREATE TABLE sample_transactions_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id       INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
            type            TEXT    NOT NULL,
            operator_id     INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            purpose         TEXT    NOT NULL DEFAULT '',
            related_task_id INTEGER REFERENCES test_tasks(id) ON DELETE SET NULL,
            expected_return TEXT    DEFAULT '',
            actual_return   TEXT    DEFAULT '',
            notes           TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        _rebuild_table(conn, "test_results", """CREATE TABLE test_results_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         INTEGER NOT NULL REFERENCES test_tasks(id) ON DELETE CASCADE,
            sample_id       INTEGER REFERENCES samples(id) ON DELETE SET NULL,
            result          TEXT    NOT NULL DEFAULT 'pending',
            test_date       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            tester_id       INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            environment     TEXT    NOT NULL DEFAULT '{}',
            notes           TEXT    NOT NULL DEFAULT '',
            attachments     TEXT    NOT NULL DEFAULT '[]',
            measured_value  TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        _rebuild_table(conn, "issues", """CREATE TABLE issues_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            plan_id         INTEGER REFERENCES test_plans(id) ON DELETE CASCADE,
            task_id         INTEGER REFERENCES test_tasks(id) ON DELETE CASCADE,
            sample_id       INTEGER REFERENCES samples(id) ON DELETE CASCADE,
            title           TEXT    NOT NULL,
            failure_mode    TEXT    NOT NULL DEFAULT '',
            failure_stage   TEXT    NOT NULL DEFAULT '',
            description     TEXT    NOT NULL DEFAULT '',
            severity        TEXT    NOT NULL DEFAULT 'major',
            status          TEXT    NOT NULL DEFAULT 'open',
            priority        INTEGER NOT NULL DEFAULT 3,
            assignee_id     INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            category        TEXT    NOT NULL DEFAULT '',
            root_cause      TEXT    NOT NULL DEFAULT '',
            resolution      TEXT    NOT NULL DEFAULT '',
            reporter_name   TEXT    NOT NULL DEFAULT '',
            failure_code    TEXT    NOT NULL DEFAULT '',
            occurrence_count INTEGER NOT NULL DEFAULT 1,
            is_deleted      INTEGER NOT NULL DEFAULT 0,
            deleted_at      TEXT    NOT NULL DEFAULT '',
            dri_name        TEXT    NOT NULL DEFAULT '',
            improvement_measures TEXT NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        # test_tasks (被子表引用，最后重建)
        _rebuild_table(conn, "test_tasks", """CREATE TABLE test_tasks_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id         INTEGER NOT NULL REFERENCES test_plans(id) ON DELETE CASCADE,
            name            TEXT    NOT NULL,
            category        TEXT    NOT NULL DEFAULT '',
            test_standard   TEXT    NOT NULL DEFAULT '',
            technician_id   INTEGER REFERENCES technicians(id) ON DELETE SET NULL,
            equipment_id    INTEGER REFERENCES equipment(id) ON DELETE SET NULL,
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
            temperature     TEXT    NOT NULL DEFAULT '',
            humidity        TEXT    NOT NULL DEFAULT '',
            accept_criteria TEXT    NOT NULL DEFAULT '',
            sort_order      INTEGER NOT NULL DEFAULT 0,
            actual_start_date TEXT  NOT NULL DEFAULT '',
            actual_end_date   TEXT  NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        conn.execute("INSERT INTO schema_version (version) VALUES (11)")
    except Exception:
        # 中途失败时恢复 FK 并重新抛出，让调用方处理
        conn.execute("PRAGMA foreign_keys = ON")
        logger.exception("Schema migration v11 failed during table rebuild")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


# ═══════════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════════

def _migrate_v12(conn: apsw.Connection) -> None:
    """v11→v12: 修补 DDL 有但迁移链遗漏的列。

    samples.notes       — CREATE TABLE 有，但 migrate_v8 只加了 test_hours/
                          supplier/scrapped_reason，漏掉 notes。
    equipment.asset_no / manufacturer / accuracy — 同理，CREATE TABLE 有
                          但从未通过 ALTER TABLE 添加到旧库。
    新建数据库走 CREATE TABLE 不受此影响；本次迁移仅修复已存在的旧库。
    """
    # samples.notes
    s_cols = {r[1] for r in conn.execute("PRAGMA table_info(samples)").fetchall()}
    if "notes" not in s_cols:
        conn.execute(
            "ALTER TABLE samples ADD COLUMN notes TEXT NOT NULL DEFAULT ''"
        )

    # equipment.asset_no, manufacturer, accuracy
    e_cols = {r[1] for r in conn.execute("PRAGMA table_info(equipment)").fetchall()}
    for col in ("asset_no", "manufacturer", "accuracy"):
        if col not in e_cols:
            conn.execute(
                f"ALTER TABLE equipment ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )

    conn.execute("INSERT INTO schema_version (version) VALUES (12)")


def _migrate_v13(conn: apsw.Connection) -> None:
    """v12→v13: 修复 v11 迁移丢失的索引 + schema_version 加 UNIQUE 约束。

    v11 通过 DROP TABLE + RENAME 重建了 7 张表，导致这些表上的索引全部丢失。
    本次迁移：
    1. 重建 schema_version 表，添加 UNIQUE 约束防止重复版本记录
    2. 重新执行所有索引 DDL（CREATE INDEX IF NOT EXISTS，已存在的会跳过）
    """
    # 1. 重建 schema_version 表，添加 UNIQUE 约束
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS schema_version_new")
        conn.execute("""CREATE TABLE schema_version_new (
            version     INTEGER NOT NULL UNIQUE,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )""")
        # 只保留最新版本号，丢弃可能的重复记录
        conn.execute("""
            INSERT INTO schema_version_new (version, applied_at)
            SELECT version, applied_at FROM schema_version
            WHERE version = (SELECT MAX(version) FROM schema_version)
        """)
        conn.execute("DROP TABLE schema_version")
        conn.execute("ALTER TABLE schema_version_new RENAME TO schema_version")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    # 2. 重建所有索引（已存在的会跳过，只补 v11 丢失的）
    for ddl in _DDL_INDEXES:
        conn.execute(ddl)

    conn.execute("INSERT INTO schema_version (version) VALUES (13)")


def _migrate_v14(conn: apsw.Connection) -> None:
    """v13→v14: capa_records 加 assignee_name；test_tasks 安全补列。

    - capa_records.assignee_name: 责任人自由文本（与 assignee_id 并存）
    - test_tasks: 安全补 dependencies/accept_criteria/sample_ids 等列（防旧库缺失）
    """
    # capa_records.assignee_name
    c_cols = {r[1] for r in conn.execute("PRAGMA table_info(capa_records)").fetchall()}
    if "assignee_name" not in c_cols:
        conn.execute(
            "ALTER TABLE capa_records ADD COLUMN assignee_name TEXT NOT NULL DEFAULT ''"
        )

    # test_tasks 安全补列（dependencies, accept_criteria, sample_ids 等）
    tt_cols = {r[1] for r in conn.execute("PRAGMA table_info(test_tasks)").fetchall()}
    for col, col_type, default in [
        ("dependencies", "TEXT", "'[]'"),
        ("accept_criteria", "TEXT", "''"),
        ("sample_ids", "TEXT", "'[]'"),
        ("notes", "TEXT", "''"),
        ("temperature", "TEXT", "''"),
        ("humidity", "TEXT", "''"),
        ("log_file", "TEXT", "''"),
        ("actual_start_date", "TEXT", "''"),
        ("actual_end_date", "TEXT", "''"),
    ]:
        if col not in tt_cols:
            conn.execute(
                f"ALTER TABLE test_tasks ADD COLUMN {col} {col_type} NOT NULL DEFAULT {default}"
            )

    conn.execute("INSERT INTO schema_version (version) VALUES (14)")


def _migrate_v15(conn: apsw.Connection) -> None:
    """v14→v15: CAPA PDCA 扩展 — root_cause + effectiveness + follow_up。"""
    c_cols = {r[1] for r in conn.execute("PRAGMA table_info(capa_records)").fetchall()}
    for col in ("root_cause", "effectiveness", "follow_up"):
        if col not in c_cols:
            conn.execute(
                f"ALTER TABLE capa_records ADD COLUMN {col} TEXT DEFAULT ''"
            )
    conn.execute("INSERT INTO schema_version (version) VALUES (15)")


def _migrate_v16(conn: apsw.Connection) -> None:
    """v15→v16: CAPA 加 verifier_name 列 + Issue 加 dri_name 列。"""
    c_cols = {r[1] for r in conn.execute("PRAGMA table_info(capa_records)").fetchall()}
    if "verifier_name" not in c_cols:
        conn.execute(
            "ALTER TABLE capa_records ADD COLUMN verifier_name TEXT DEFAULT ''"
        )
    i_cols = {r[1] for r in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "dri_name" not in i_cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN dri_name TEXT DEFAULT ''"
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (16)")


def _migrate_v17(conn: apsw.Connection) -> None:
    """v16→v17: issues 软删除字段 — is_deleted + deleted_at。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "is_deleted" not in cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"
        )
    if "deleted_at" not in cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN deleted_at TEXT NOT NULL DEFAULT ''"
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (17)")


def _migrate_v18(conn: apsw.Connection) -> None:
    """v17→v18: issues 加 resolution（幂等）+ reporter_name 列。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "resolution" not in cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN resolution TEXT NOT NULL DEFAULT ''"
        )
    if "reporter_name" not in cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN reporter_name TEXT NOT NULL DEFAULT ''"
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (18)")


def _migrate_v19(conn: apsw.Connection) -> None:
    """v18→v19: issues 加 improvement_measures 列；迁移 resolution 中的非枚举文本。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "improvement_measures" not in cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN improvement_measures TEXT NOT NULL DEFAULT ''"
        )
    # 迁移：把 resolution 中的非枚举值（旧 CAPA 汇总文本）搬到 improvement_measures
    valid_resolutions = {"", "fixed", "wont_fix", "duplicate", "cannot_reproduce", "not_an_issue"}
    rows = conn.execute("SELECT id, resolution FROM issues").fetchall()
    for row_id, res_value in rows:
        if res_value and res_value not in valid_resolutions:
            conn.execute(
                "UPDATE issues SET improvement_measures = ?, resolution = '' WHERE id = ?",
                (res_value, row_id),
            )
    conn.execute("INSERT INTO schema_version (version) VALUES (19)")


def _migrate_v20(conn: apsw.Connection) -> None:
    """v19→v20: test_plans 加 task_prefix 列（任务编号前缀）。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(test_plans)").fetchall()}
    if "task_prefix" not in cols:
        conn.execute(
            "ALTER TABLE test_plans ADD COLUMN task_prefix TEXT NOT NULL DEFAULT ''"
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (20)")


def _migrate_v21(conn: apsw.Connection) -> None:
    """v20→v21: issues 加 category 列（责任类别）。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(issues)").fetchall()}
    if "category" not in cols:
        conn.execute(
            "ALTER TABLE issues ADD COLUMN category TEXT NOT NULL DEFAULT ''"
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (21)")


def _migrate_v22(conn: apsw.Connection) -> None:
    """v21→v22: test_tasks 加 manual_scheduled 列。

    不做批量标记 — start_day > 0 可能来自自动排程引擎的依赖链推算，
    无法仅从 start_day 值区分"自动排程结果"和"用户手动调整"。
    manual_scheduled 精确写入由以下入口负责：
      - task_dialog: 用户编辑任务并设置预计日期时
      - 甘特图拖拽: MoveTaskCommand
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(test_tasks)").fetchall()}
    if "manual_scheduled" not in cols:
        conn.execute(
            "ALTER TABLE test_tasks ADD COLUMN manual_scheduled INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (22)")


def _migrate_v23(conn: apsw.Connection) -> None:
    """v22→v23: 新增 issue_comments / issue_activity_log / issue_links 三张表。

    纯新表，不修改现有表结构，不影响现有数据。
    新表在 _DDL_TABLES 中定义（CREATE TABLE IF NOT EXISTS），此处执行 DDL 重建即可。
    """
    new_tables = [
        """CREATE TABLE IF NOT EXISTS issue_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            author_name TEXT    NOT NULL DEFAULT '',
            content     TEXT    NOT NULL,
            is_deleted  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS issue_activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            field       TEXT    NOT NULL,
            old_value   TEXT    NOT NULL DEFAULT '',
            new_value   TEXT    NOT NULL DEFAULT '',
            operator    TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS issue_links (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id   INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            target_id   INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            link_type   TEXT    NOT NULL DEFAULT 'relates_to',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            CHECK(source_id != target_id),
            UNIQUE(source_id, target_id, link_type)
        )""",
    ]
    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_comments_issue ON issue_comments(issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_comments_created ON issue_comments(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_activity_issue ON issue_activity_log(issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_created ON issue_activity_log(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_links_source ON issue_links(source_id)",
        "CREATE INDEX IF NOT EXISTS idx_links_target ON issue_links(target_id)",
    ]
    for ddl in new_tables + new_indexes:
        conn.execute(ddl)
    conn.execute("INSERT INTO schema_version (version) VALUES (23)")


def _migrate_v24(conn: apsw.Connection) -> None:
    """v23→v24: issue_activity_log 加 project_id + 索引。

    该列用于仪表盘 weekly_closed 按项目筛选，避免跨项目数据泄漏。
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(issue_activity_log)").fetchall()}
    if "project_id" not in cols:
        conn.execute(
            "ALTER TABLE issue_activity_log ADD COLUMN "
            "project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE"
        )
    # 回填历史数据的 project_id
    conn.execute("""
        UPDATE issue_activity_log SET project_id = (
            SELECT project_id FROM issues WHERE issues.id = issue_activity_log.issue_id
        ) WHERE project_id IS NULL
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_project ON issue_activity_log(project_id)")
    conn.execute("INSERT INTO schema_version (version) VALUES (24)")


def _migrate_v25(conn: apsw.Connection) -> None:
    """v24→v25: 新增 todos 表（轻量待办事项）。

    纯新表，不修改现有表结构，不影响现有数据。
    新表在 _DDL_TABLES 中定义（CREATE TABLE IF NOT EXISTS），此处执行 DDL 重建即可。
    """
    new_tables = [
        """CREATE TABLE IF NOT EXISTS todos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            title       TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT '',
            priority    TEXT    NOT NULL DEFAULT 'medium',
            status      TEXT    NOT NULL DEFAULT 'pending',
            category    TEXT    NOT NULL DEFAULT '',
            due_date    TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )""",
    ]
    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)",
    ]
    for ddl in new_tables + new_indexes:
        conn.execute(ddl)
    conn.execute("INSERT INTO schema_version (version) VALUES (25)")


def _migrate_v26(conn: apsw.Connection) -> None:
    """v25→v26: todos 表加提醒 + 四象限字段。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(todos)").fetchall()}
    if "remind_at" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN remind_at TEXT NOT NULL DEFAULT ''")
    if "reminded" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN reminded INTEGER NOT NULL DEFAULT 0")
    if "quadrant" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN quadrant INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_quadrant ON todos(quadrant)")
    conn.execute("INSERT INTO schema_version (version) VALUES (26)")


def _migrate_v27(conn: apsw.Connection) -> None:
    """v26→v27: todos 表加 archived 字段。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(todos)").fetchall()}
    if "archived" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_archived ON todos(archived)")
    conn.execute("INSERT INTO schema_version (version) VALUES (27)")


def _migrate_v28(conn: apsw.Connection) -> None:
    """v27→v28: test_tasks.category 旧值统一到 TASK_CATEGORIES 新值域。

    2026-08-10 审计发现: TASK_CATEGORIES 常量已统一为 8 项新值
    (环境试验/机械试验/表面处理/工艺试验/包装/寿命试验/EMC/其他)，
    但存量数据仍是旧值 (环境/力学/电测)，导致类别筛选永远空表、
    编辑任务时 combo findText 失败静默改写类别。

    映射: 环境→环境试验, 力学→机械试验, 电测→其他 (无精确对应, 归"其他")。
    """
    mapping = {
        "环境": "环境试验",
        "力学": "机械试验",
        "电测": "其他",
    }
    for old_val, new_val in mapping.items():
        conn.execute(
            "UPDATE test_tasks SET category = ?, updated_at = datetime('now','localtime') "
            "WHERE category = ?",
            (new_val, old_val),
        )
    conn.execute("INSERT INTO schema_version (version) VALUES (28)")


# 按版本号排列的迁移函数列表（用于完整性修复时回放）
_MIGRATORS: list[tuple[int, object]] = [
    (2, _migrate_v2),
    (3, _migrate_v3),
    (4, _migrate_v4),
    (5, _migrate_v5),
    (6, _migrate_v6),
    (7, _migrate_v7),
    (8, _migrate_v8),
    (9, _migrate_v9),
    (10, _migrate_v10),
    (11, _migrate_v11),
    (12, _migrate_v12),
    (13, _migrate_v13),
    (14, _migrate_v14),
    (15, _migrate_v15),
    (16, _migrate_v16),
    (17, _migrate_v17),
    (18, _migrate_v18),
    (19, _migrate_v19),
    (20, _migrate_v20),
    (21, _migrate_v21),
    (22, _migrate_v22),
    (23, _migrate_v23),
    (24, _migrate_v24),
    (25, _migrate_v25),
    (26, _migrate_v26),
    (27, _migrate_v27),
    (28, _migrate_v28),
]


def init_schema(conn: apsw.Connection) -> int:
    """初始化数据库 schema，按需执行迁移。

    Args:
        conn: apsw 数据库连接。

    Returns:
        初始化后的 schema 版本号。
    """
    # 确保迁移追踪表存在（DDL 自动提交，无需事务）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER NOT NULL UNIQUE,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )"""
    )
    current = _get_current_version(conn)

    # 降级保护：数据库版本高于当前代码版本时拒绝启动
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"数据库 schema 版本 (v{current}) 高于当前代码版本 (v{SCHEMA_VERSION})。\n"
            f"请按以下步骤操作：\n"
            f"1. 备份数据库：cp ~/.reliatrack/reliatrack.db ~/.reliatrack/reliatrack.db.bak\n"
            f"2. 升级 ReliaTrack 到最新版本\n"
            f"3. 如无法升级，联系管理员获取匹配版本"
        )

    needs_migration = current < SCHEMA_VERSION

    if not needs_migration:
        return current

    # v1→v10 迁移包裹在事务内
    if current < 10:
        conn.execute("BEGIN")
        try:
            if current < 1:
                _migrate_v1(conn)
            if current < 2:
                _migrate_v2(conn)
            if current < 3:
                _migrate_v3(conn)
            if current < 4:
                _migrate_v4(conn)
            if current < 5:
                _migrate_v5(conn)
            if current < 6:
                _migrate_v6(conn)
            if current < 7:
                _migrate_v7(conn)
            if current < 8:
                _migrate_v8(conn)
            if current < 9:
                _migrate_v9(conn)
            if current < 10:
                _migrate_v10(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration (v1-v10) failed at version %d", current)
            raise

    # v11 需关闭 FK 约束后重建表，不能在事务内执行 PRAGMA foreign_keys
    # SQLite DDL 不可回滚，但加 try/except 保证失败有日志记录
    if current < 11:
        logger.info("Starting non-transactional migration v11...")
        try:
            _migrate_v11(conn)
        except Exception:
            logger.critical(
                "Migration v11 failed — database may be in inconsistent state"
            )
            raise

    # v12 修补 samples.notes 列（CREATE TABLE 有但历史迁移链漏掉）
    if current < 12:
        conn.execute("BEGIN")
        try:
            _migrate_v12(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v12 failed")
            raise

    # v13 修复 v11 丢失的索引 + schema_version 加 UNIQUE 约束
    if current < 13:
        logger.info("Starting non-transactional migration v13...")
        try:
            _migrate_v13(conn)
        except Exception:
            logger.critical(
                "Migration v13 failed — database may be in inconsistent state"
            )
            raise

    # v14: capa_records 加 assignee_name 列；test_tasks 安全补列
    if current < 14:
        conn.execute("BEGIN")
        try:
            _migrate_v14(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v14 failed")
            raise

    # v15: CAPA PDCA 扩展 — root_cause + effectiveness + follow_up
    if current < 15:
        conn.execute("BEGIN")
        try:
            _migrate_v15(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v15 failed")
            raise

    # v16: CAPA verifier_name + Issue dri_name
    if current < 16:
        conn.execute("BEGIN")
        try:
            _migrate_v16(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v16 failed")
            raise

    # v17: issues 软删除字段 — is_deleted + deleted_at
    if current < 17:
        conn.execute("BEGIN")
        try:
            _migrate_v17(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v17 failed")
            raise

    # v18: issues 加 resolution + reporter_name 列
    if current < 18:
        conn.execute("BEGIN")
        try:
            _migrate_v18(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v18 failed")
            raise

    # v19: issues 加 improvement_measures 列 + 迁移旧 resolution 文本
    if current < 19:
        conn.execute("BEGIN")
        try:
            _migrate_v19(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v19 failed")
            raise

    # v20: test_plans 加 task_prefix 列
    if current < 20:
        conn.execute("BEGIN")
        try:
            _migrate_v20(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v20 failed")
            raise

    # v21: issues 加 category 列
    if current < 21:
        conn.execute("BEGIN")
        try:
            _migrate_v21(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v21 failed")
            raise

    # v22: test_tasks 加 manual_scheduled 列 + 迁移已有手动调整任务
    if current < 22:
        conn.execute("BEGIN")
        try:
            _migrate_v22(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v22 failed")
            raise

    # v23: 新增 issue_comments / issue_activity_log / issue_links
    if current < 23:
        conn.execute("BEGIN")
        try:
            _migrate_v23(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v23 failed")
            raise

    # v24: issue_activity_log 加 project_id 列 + 索引
    if current < 24:
        conn.execute("BEGIN")
        try:
            _migrate_v24(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v24 failed")
            raise

    # v25: 新增 todos 表
    if current < 25:
        conn.execute("BEGIN")
        try:
            _migrate_v25(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v25 failed")
            raise

    # v26: todos 表加提醒 + 四象限字段
    if current < 26:
        conn.execute("BEGIN")
        try:
            _migrate_v26(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v26 failed")
            raise

    # v27: todos 表加 archived 字段
    if current < 27:
        conn.execute("BEGIN")
        try:
            _migrate_v27(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v27 failed")
            raise

    # v28: test_tasks.category 旧值统一到 TASK_CATEGORIES 新值域
    if current < 28:
        conn.execute("BEGIN")
        try:
            _migrate_v28(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Schema migration v28 failed")
            raise

    # 初始化后验证：schema_version 匹配但核心表可能不存在（损坏的 DB）
    _validate_schema_integrity(conn)

    return _get_current_version(conn)


def _validate_schema_integrity(conn: apsw.Connection) -> None:
    """验证所有核心表存在。如果 schema_version 正确但表缺失，用 DDL 重建缺失表。"""
    core_tables = [
        "projects", "equipment", "technicians", "samples",
        "sample_transactions", "test_plans", "test_tasks", "test_results",
        "issues", "issue_attachments", "fa_records", "capa_records",
        "issue_comments", "issue_activity_log", "issue_links",
        "knowledge_entries", "settings", "holidays", "todos",
    ]
    missing = []
    for t in core_tables:
        cols = conn.execute(f"PRAGMA table_info({quote_ident(t)})").fetchall()
        if not cols:
            missing.append(t)

    if missing:
        logger.warning(
            "Schema integrity check failed — tables missing: %s. Rebuilding with DDL.",
            missing,
        )
        # 只执行 DDL（CREATE TABLE IF NOT EXISTS），不回放迁移
        for ddl in _DDL_TABLES:
            try:
                conn.execute(ddl)
            except Exception:
                logger.exception("DDL rebuild failed for: %s", ddl[:60])
                raise
        for ddl in _DDL_INDEXES:
            try:
                conn.execute(ddl)
            except Exception:
                logger.exception("Index rebuild failed for: %s", ddl[:60])
                raise
        logger.info("Schema rebuild completed successfully")
