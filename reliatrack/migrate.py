#!/usr/bin/env python3
"""数据迁移脚本：旧 kekaoxing.db → ReliaTrack 新 schema。

用法:
    python migrate.py [旧数据库路径] [新数据库路径]
    默认: python migrate.py ../kekaoxing.db ./data/reliatrack.db
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在路径中
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import apsw


def migrate(old_db_path: str, new_db_path: str) -> None:
    """执行数据迁移。"""
    print(f"📋 旧数据库: {old_db_path}")
    print(f"📋 新数据库: {new_db_path}")

    # ── 1. 检查旧数据库 ──
    if not os.path.exists(old_db_path):
        print(f"❌ 旧数据库不存在: {old_db_path}")
        sys.exit(1)

    old = apsw.Connection(old_db_path)

    # 统计旧数据
    old_tables = [r[0] for r in old.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    print(f"   旧表: {old_tables}")
    for t in old_tables:
        cnt = old.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        if cnt > 0:
            print(f"   {t}: {cnt} rows")

    # ── 2. 创建新数据库 ──
    new_dir = os.path.dirname(new_db_path)
    if new_dir:
        os.makedirs(new_dir, exist_ok=True)

    if os.path.exists(new_db_path):
        print(f"⚠️  新数据库已存在，备份为 {new_db_path}.bak")
        shutil.copy2(new_db_path, new_db_path + ".bak")
        os.remove(new_db_path)

    new = apsw.Connection(new_db_path)

    # 读取并执行 schema
    schema_path = os.path.join(_SCRIPT_DIR, "src", "db", "schema.py")
    if not os.path.exists(schema_path):
        print(f"❌ Schema 文件不存在: {schema_path}")
        sys.exit(1)

    # 直接内联 schema DDL（避免 import 循环）
    _init_new_schema(new)

    print("\n🔄 开始迁移数据...")

    # ── 3. 迁移 project_settings → settings ──
    migrated = 0
    for row in old.execute("SELECT key, value, updated_at FROM project_settings"):
        new.execute(
            "INSERT OR REPLACE INTO [settings] (key, value, updated_at) VALUES (?, ?, ?)",
            row,
        )
        migrated += 1
    print(f"   ✅ settings: {migrated} rows")

    # ── 4. 迁移 resources → equipment ──
    migrated = 0
    for row in old.execute(
        "SELECT name, type, description, created_at, updated_at FROM resources"
    ):
        new.execute(
            "INSERT INTO [equipment] (name, type, model, location, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row[0], row[1], "", "", "available", row[3]),
        )
        migrated += 1
    print(f"   ✅ equipment: {migrated} rows")

    # ── 5. 迁移 sections → projects ──
    # 旧系统只有一个隐含项目，创建一个默认项目
    settings_data = dict(
        old.execute("SELECT key, value FROM project_settings").fetchall()
    )
    start_date = settings_data.get("start_date", "2026-01-01")
    new.execute(
        "INSERT INTO [projects] (name, product, customer, description, status) "
        "VALUES (?, ?, ?, ?, ?)",
        ("默认项目（迁移自旧版）", "", "", f"从 kekaoxing.db 迁移，起始日期 {start_date}", "active"),
    )
    project_id = new.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"   ✅ projects: 1 row (id={project_id})")

    # ── 6. 迁移 tasks → test_plans + test_tasks ──
    # 旧系统所有任务属于同一个隐含计划
    new.execute(
        "INSERT INTO [test_plans] (project_id, name, status) VALUES (?, ?, ?)",
        (project_id, "默认测试计划（迁移自旧版）", "draft"),
    )
    plan_id = new.execute("SELECT last_insert_rowid()").fetchone()[0]

    task_id_map: dict[int, int] = {}  # 旧 task.id → 新 test_task.id
    migrated = 0
    for idx, row in enumerate(old.execute(
        "SELECT id, name_cn, section, duration, start_day, progress, "
        "priority, done, dependencies, requirements, created_at, updated_at "
        "FROM tasks ORDER BY id"
    )):
        old_id, name_cn, section, duration, start_day, progress, \
            priority, done, dependencies, requirements, \
            created_at, updated_at = row

        status = "completed" if done else ("in_progress" if progress > 0 else "pending")

        new.execute(
            "INSERT INTO [test_tasks] (plan_id, name, category, duration, start_day, "
            "progress, priority, status, dependencies, notes, sort_order, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_id, name_cn or "未命名", section, duration, start_day, progress,
             priority, status, dependencies, requirements or "",
             idx + 1, created_at, updated_at),
        )
        new_id = new.execute("SELECT last_insert_rowid()").fetchone()[0]
        task_id_map[old_id] = new_id
        migrated += 1
    print(f"   ✅ test_plans: 1 row (id={plan_id})")
    print(f"   ✅ test_tasks: {migrated} rows")

    # ── 7. 迁移 test_issues → issues（如有） ──
    migrated = 0
    for row in old.execute(
        "SELECT task_id, title, description, issue_type, severity, status, "
        "priority, phase, assignee, found_date, resolved_date, resolution, "
        "cause, countermeasure, tags, created_at, updated_at FROM test_issues"
    ):
        old_task_id = row[0]
        new_task_id = task_id_map.get(old_task_id)
        if new_task_id is None:
            continue  # 找不到对应任务，跳过
        new.execute(
            "INSERT INTO [issues] (project_id, plan_id, task_id, title, description, "
            "failure_mode, failure_stage, severity, status, priority, assignee_id, "
            "root_cause, resolution, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, plan_id, new_task_id, row[1], row[2],
             row[3] or "", row[7] or "",  # failure_mode, failure_stage
             row[4] or "minor",  # severity
             row[5] or "open",  # status
             row[6] or 3,  # priority
             None,  # assignee_id
             row[12] or "",  # root_cause (旧 cause)
             row[11] or "",  # resolution
             row[14], row[15]),  # created_at, updated_at
        )
        migrated += 1
    if migrated > 0:
        print(f"   ✅ issues: {migrated} rows")
    else:
        print(f"   ℹ️  issues: 0 rows (无数据)")

    # ── 8. 写入迁移记录 ──
    new.execute(
        "INSERT INTO [settings] (key, value, updated_at) VALUES (?, ?, ?)",
        ("migration_from_kekaoxing", json.dumps({
            "source": old_db_path,
            "timestamp": datetime.now().isoformat(),
            "tasks_migrated": len(task_id_map),
        }), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )

    # ── 9. 验证 ──
    print("\n📊 迁移后验证:")
    for table in ["projects", "equipment", "test_plans", "test_tasks", "issues", "settings"]:
        cnt = new.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        print(f"   {table}: {cnt} rows")

    new.execute("VACUUM")
    new.close()
    old.close()

    print(f"\n✅ 迁移完成！新数据库: {new_db_path}")


def _init_new_schema(conn: apsw.Connection) -> None:
    """初始化新数据库 schema（内联 DDL，避免循环导入）。"""
    from src.db.schema import _DDL_TABLES, SCHEMA_VERSION, _DDL_INDEXES
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    for ddl in _DDL_TABLES:
        conn.execute(ddl)
    for ddl in _DDL_INDEXES:
        conn.execute(ddl)
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
    )
    print(f"   新 schema v{SCHEMA_VERSION} 已创建")


def main() -> None:
    old_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        _PROJECT_ROOT, "kekaoxing.db"
    )
    new_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        _SCRIPT_DIR, "data", "reliatrack.db"
    )
    migrate(old_path, new_path)


if __name__ == "__main__":
    main()
