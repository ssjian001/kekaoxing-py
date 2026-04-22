"""SQLite 数据库层 - 任务和资源的 CRUD 操作（使用 apsw）"""

from __future__ import annotations
import json
from datetime import date
from pathlib import Path

import apsw

from src.models import (
    Task, Resource, Section, ResourceType,
    EquipmentRequirement, UnavailablePeriod,
    DEFAULT_SECTION_LABELS, DEFAULT_SECTION_COLORS, PRESET_COLORS,
)

DB_NAME = "kekaoxing.db"

# ── Schema ──────────────────────────────────────────

_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    num          TEXT    NOT NULL UNIQUE,
    name_en      TEXT    NOT NULL,
    name_cn      TEXT    NOT NULL,
    section      TEXT    NOT NULL,
    duration     INTEGER NOT NULL DEFAULT 1,
    start_day    INTEGER NOT NULL DEFAULT 0,
    progress     REAL    NOT NULL DEFAULT 0.0,
    priority     INTEGER NOT NULL DEFAULT 3,
    done         INTEGER NOT NULL DEFAULT 0,
    is_serial    INTEGER NOT NULL DEFAULT 0,
    serial_group TEXT    NOT NULL DEFAULT '',
    sample_pool  TEXT    NOT NULL DEFAULT 'product',
    sample_qty   INTEGER NOT NULL DEFAULT 3,
    setup_time   REAL    NOT NULL DEFAULT 0,
    teardown_time REAL   NOT NULL DEFAULT 0,
    dependencies TEXT    NOT NULL DEFAULT '[]',
    requirements TEXT    NOT NULL DEFAULT '[]',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_RESOURCES = """
CREATE TABLE IF NOT EXISTS resources (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    type         TEXT    NOT NULL,
    category     TEXT    NOT NULL DEFAULT '',
    unit         TEXT    NOT NULL DEFAULT '台',
    available_qty INTEGER NOT NULL DEFAULT 1,
    icon         TEXT    NOT NULL DEFAULT '📦',
    description  TEXT    NOT NULL DEFAULT '',
    unavailable_periods TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_SECTIONS = """
CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,
    label       TEXT    NOT NULL,
    color       TEXT    NOT NULL DEFAULT '#89b4fa',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_PROJECT_SETTINGS = """
CREATE TABLE IF NOT EXISTS project_settings (
    key         TEXT    UNIQUE PRIMARY KEY,
    value       TEXT    NOT NULL,
    updated_at  TEXT    DEFAULT (datetime('now','localtime'))
)
"""

_CREATE_TEST_RESULTS = """
CREATE TABLE IF NOT EXISTS test_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    test_date   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    result      TEXT NOT NULL DEFAULT 'pending',
    -- result: 'pass' | 'fail' | 'pending' | 'skip' | 'conditional'
    test_data   TEXT NOT NULL DEFAULT '',
    -- 测试数据摘要 (JSON 或纯文本)
    notes       TEXT NOT NULL DEFAULT '',
    tester      TEXT NOT NULL DEFAULT '',
    attachments TEXT NOT NULL DEFAULT '[]',
    -- 附件路径列表 JSON: ["/path/to/file1", ...]
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
)
"""

_CREATE_TEST_ISSUES = """
CREATE TABLE IF NOT EXISTS test_issues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    issue_type  TEXT NOT NULL DEFAULT 'bug',
    -- issue_type: 'bug' | 'improvement' | 'feature' | 'task'
    severity    TEXT NOT NULL DEFAULT 'medium',
    -- severity: 'critical' | 'major' | 'minor' | 'cosmetic' | 'suggestion'
    status      TEXT NOT NULL DEFAULT 'open',
    -- status: 'open' | 'in_progress' | 'fixed' | 'verified' | 'closed' | 'wontfix'
    priority    INTEGER NOT NULL DEFAULT 3,
    phase       TEXT NOT NULL DEFAULT '',
    -- phase: 测试阶段 (初样试验/正样试验/定型试验/例行试验/鉴定检验/交付检验/其他)
    assignee    TEXT NOT NULL DEFAULT '',
    found_date  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    resolved_date TEXT NOT NULL DEFAULT '',
    resolution  TEXT NOT NULL DEFAULT '',
    -- 解决方案描述
    cause        TEXT NOT NULL DEFAULT '',
    -- 问题原因分析
    countermeasure TEXT NOT NULL DEFAULT '',
    -- 改善对策
    tags        TEXT NOT NULL DEFAULT '[]',
    -- 标签列表 JSON: ["regression", "intermittent"]
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
)
"""

_CREATE_ISSUE_HISTORY = """
CREATE TABLE IF NOT EXISTS issue_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id    INTEGER NOT NULL REFERENCES test_issues(id) ON DELETE CASCADE,
    field       TEXT NOT NULL DEFAULT 'status',
    -- 变更字段 (目前仅 status)
    old_value   TEXT NOT NULL DEFAULT '',
    new_value   TEXT NOT NULL,
    remark      TEXT NOT NULL DEFAULT '',
    changed_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    changed_by  TEXT NOT NULL DEFAULT ''
)
"""


class Database:
    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path(__file__).parent.parent.parent / DB_NAME
        self.db_path = str(path)
        self.conn = apsw.Connection(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute(_CREATE_TASKS)
        self.conn.execute(_CREATE_RESOURCES)
        self.conn.execute(_CREATE_SECTIONS)
        self.conn.execute(_CREATE_PROJECT_SETTINGS)
        self.conn.execute(_CREATE_TEST_RESULTS)
        self.conn.execute(_CREATE_TEST_ISSUES)
        self.conn.execute(_CREATE_ISSUE_HISTORY)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_section ON tasks(section)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_results_task_id ON test_results(task_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_issues_task_id ON test_issues(task_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_issues_status ON test_issues(status)"
        )

        # 迁移：为旧数据库添加新列
        for col in ("cause", "countermeasure", "issue_type", "phase"):
            try:
                default = "'bug'" if col == "issue_type" else "''"
                self.conn.execute(
                    f"ALTER TABLE test_issues ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}"
                )
            except Exception:
                pass  # 列已存在

        # 首次运行时插入默认分类
        self._seed_default_sections()
        self._seed_default_settings()

    def _task_reqs_json(self, t: Task) -> str:
        return json.dumps([
            {"resource_id": r.resource_id, "quantity": r.quantity}
            for r in t.requirements
        ])

    def _res_periods_json(self, r: Resource) -> str:
        return json.dumps([
            {"start_day": p.start_day, "end_day": p.end_day, "reason": p.reason}
            for p in r.unavailable_periods
        ])

    # ── Project Settings ──────────────────────────

    def _seed_default_settings(self):
        """首次运行时插入默认项目设置（仅当 key 不存在时，不覆盖用户修改）"""
        self.conn.execute(
            "INSERT OR IGNORE INTO project_settings (key, value) VALUES (?, ?)",
            ("start_date", date.today().strftime("%Y-%m-%d")),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO project_settings (key, value) VALUES (?, ?)",
            ("skip_weekends", "false"),
        )

    def get_setting(self, key: str, default: str = "") -> str:
        """读取设置"""
        row = self.conn.execute(
            "SELECT value FROM project_settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str):
        """写入设置（INSERT OR IGNORE + UPDATE，确保 UPSERT 语义）"""
        self.conn.execute(
            "INSERT OR IGNORE INTO project_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.execute(
            "UPDATE project_settings SET value = ?, updated_at = datetime('now','localtime') WHERE key = ?",
            (value, key),
        )

    # ── Task CRUD ─────────────────────────────────

    def get_all_tasks(self) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks ORDER BY section, num"
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        r = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(r) if r else None

    def insert_task(self, t: Task) -> int:
        section_val = t.section.value if isinstance(t.section, Section) else t.section
        self.conn.execute(
            """INSERT INTO tasks
               (num,name_en,name_cn,section,duration,start_day,
                progress,priority,done,is_serial,serial_group,
                sample_pool,sample_qty,setup_time,teardown_time,
                dependencies,requirements)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t.num, t.name_en, t.name_cn, section_val,
             t.duration, t.start_day, t.progress, t.priority,
             int(t.done), int(t.is_serial), t.serial_group,
             t.sample_pool, t.sample_qty, t.setup_time, t.teardown_time,
             json.dumps(t.dependencies), self._task_reqs_json(t)),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def update_task(self, t: Task):
        section_val = t.section.value if isinstance(t.section, Section) else t.section
        self.conn.execute(
            """UPDATE tasks SET
               num=?,name_en=?,name_cn=?,section=?,duration=?,
               start_day=?,progress=?,priority=?,done=?,is_serial=?,
               serial_group=?,sample_pool=?,sample_qty=?,
               setup_time=?,teardown_time=?,dependencies=?,requirements=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (t.num, t.name_en, t.name_cn, section_val,
             t.duration, t.start_day, t.progress, t.priority,
             int(t.done), int(t.is_serial), t.serial_group,
             t.sample_pool, t.sample_qty, t.setup_time, t.teardown_time,
             json.dumps(t.dependencies), self._task_reqs_json(t), t.id),
        )

    def update_task_fields(self, task_id: int, fields: dict):
        """更新任务的指定字段（供 UndoManager 使用）。

        Args:
            task_id: 任务 ID
            fields: 要更新的字段字典，如 {"start_day": 5, "progress": 80}
                    支持依赖/需求数组，会自动序列化为 JSON。
        """
        allowed = {
            "num", "name_en", "name_cn", "section", "duration", "start_day",
            "progress", "priority", "done", "is_serial", "serial_group",
            "sample_pool", "sample_qty", "setup_time", "teardown_time",
            "dependencies", "requirements",
        }
        updates = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "dependencies":
                updates[k] = json.dumps(v)
            elif k == "requirements":
                updates[k] = json.dumps([
                    {"resource_id": r.resource_id, "quantity": r.quantity}
                    if hasattr(r, "resource_id") else r
                    for r in v
                ])
            elif k == "section":
                updates[k] = v.value if isinstance(v, Section) else v
            else:
                updates[k] = v

        if not updates:
            return

        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [task_id]
        self.conn.execute(
            f"UPDATE tasks SET {set_clause}, updated_at=datetime('now') WHERE id=?",
            values,
        )

    def insert_task_from_dict(self, d: dict) -> int:
        """从字典插入任务并返回 ID（供 UndoManager 撤销删除用）。

        接受完整任务数据字典，字段含义同 Task 属性。
        """
        section_val = d.get("section", Section.ENV.value)
        if isinstance(section_val, Section):
            section_val = section_val.value
        deps = d.get("dependencies", [])
        reqs = d.get("requirements", [])
        reqs_json = json.dumps([
            {"resource_id": r.resource_id, "quantity": r.quantity}
            if hasattr(r, "resource_id") else r
            for r in reqs
        ])
        self.conn.execute(
            """INSERT INTO tasks
               (num,name_en,name_cn,section,duration,start_day,
                progress,priority,done,is_serial,serial_group,
                sample_pool,sample_qty,setup_time,teardown_time,
                dependencies,requirements)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(d.get("num", "")),
                str(d.get("name_en", "")),
                str(d.get("name_cn", "")),
                section_val,
                int(d.get("duration", 1)),
                int(d.get("start_day", 0)),
                float(d.get("progress", 0.0)),
                int(d.get("priority", 3)),
                int(d.get("done", 0)),
                int(d.get("is_serial", 0)),
                str(d.get("serial_group", "")),
                str(d.get("sample_pool", "product")),
                int(d.get("sample_qty", 3)),
                int(d.get("setup_time", 0)),
                int(d.get("teardown_time", 0)),
                json.dumps(deps) if isinstance(deps, list) else deps,
                reqs_json,
            ),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def insert_task_dict(self, d: dict) -> int:
        """从字典插入一条任务（Excel 导入用），缺少的字段使用默认值。"""
        section_val = d.get("section", Section.ENV.value)
        if isinstance(section_val, Section):
            section_val = section_val.value
        self.conn.execute(
            """INSERT INTO tasks
               (num,name_en,name_cn,section,duration,start_day,
                progress,priority,done,is_serial,serial_group,
                sample_pool,sample_qty,setup_time,teardown_time,
                dependencies,requirements)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(d.get("num", "")),
                str(d.get("name_en", "")),
                str(d.get("name_cn", "")),
                section_val,
                int(d.get("duration", 1)),
                int(d.get("start_day", 0)),
                float(d.get("progress", 0.0)),
                int(d.get("priority", 3)),
                int(d.get("done", 0)),
                0,  # is_serial
                "",  # serial_group
                str(d.get("sample_pool", "product")),
                int(d.get("sample_qty", 3)),
                int(d.get("setup_time", 0)),
                int(d.get("teardown_time", 0)),
                "[]",  # dependencies
                "[]",  # requirements
            ),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def delete_task(self, task_id: int):
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def batch_update_schedule(self, updates: list[dict]):
        """批量更新排程结果 {id, start_day, duration}"""
        for u in updates:
            self.conn.execute(
                "UPDATE tasks SET start_day=?, duration=?, updated_at=datetime('now') WHERE id=?",
                (u["start_day"], u["duration"], u["id"]),
            )

    def clear_done_tasks(self) -> int:
        self.conn.execute("DELETE FROM tasks WHERE done = 1")
        return self.conn.execute("SELECT changes()").fetchone()[0]

    def task_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    # ── Resource CRUD ─────────────────────────────

    def get_all_resources(self) -> list[Resource]:
        rows = self.conn.execute(
            "SELECT * FROM resources ORDER BY type, category"
        ).fetchall()
        return [self._row_to_resource(r) for r in rows]

    def get_resource(self, res_id: int) -> Optional[Resource]:
        r = self.conn.execute(
            "SELECT * FROM resources WHERE id = ?", (res_id,)
        ).fetchone()
        return self._row_to_resource(r) if r else None

    def insert_resource(self, r: Resource) -> int:
        self.conn.execute(
            """INSERT INTO resources
               (name,type,category,unit,available_qty,icon,
                description,unavailable_periods)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r.name, r.type.value, r.category, r.unit,
             r.available_qty, r.icon, r.description,
             self._res_periods_json(r)),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def update_resource(self, r: Resource):
        self.conn.execute(
            """UPDATE resources SET
               name=?,type=?,category=?,unit=?,available_qty=?,
               icon=?,description=?,unavailable_periods=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (r.name, r.type.value, r.category, r.unit,
             r.available_qty, r.icon, r.description,
             self._res_periods_json(r), r.id),
        )

    def delete_resource(self, res_id: int):
        self.conn.execute("DELETE FROM resources WHERE id = ?", (res_id,))

    # ── Helpers ───────────────────────────────────

    # tasks 表: 0=id, 1=num, 2=name_en, 3=name_cn, 4=section,
    #   5=duration, 6=start_day, 7=progress, 8=priority, 9=done,
    #   10=is_serial, 11=serial_group, 12=sample_pool, 13=sample_qty,
    #   14=setup_time, 15=teardown_time, 16=dependencies, 17=requirements,
    #   18=created_at, 19=updated_at
    @staticmethod
    def _row_to_task(r) -> Task:
        try:
            deps = json.loads(r[16])
        except (json.JSONDecodeError, TypeError, IndexError):
            deps = []
        try:
            reqs_raw = json.loads(r[17])
        except (json.JSONDecodeError, TypeError, IndexError):
            reqs_raw = []
        reqs = [
            EquipmentRequirement(resource_id=x["resource_id"], quantity=x["quantity"])
            for x in reqs_raw if isinstance(x, dict) and "resource_id" in x
        ]
        # section: 优先用枚举，否则直接存 str
        try:
            section = Section(r[4])
        except ValueError:
            section = r[4]  # type: ignore[assignment]
        return Task(
            id=r[0], num=r[1], name_en=r[2], name_cn=r[3],
            section=section, duration=r[5], start_day=r[6],
            progress=r[7], priority=r[8], done=bool(r[9]),
            is_serial=bool(r[10]), serial_group=r[11],
            sample_pool=r[12], sample_qty=r[13],
            setup_time=r[14], teardown_time=r[15],
            dependencies=deps, requirements=reqs,
            created_at=r[18] if len(r) > 18 else "",
            updated_at=r[19] if len(r) > 19 else "",
        )

    # resources 表: 0=id, 1=name, 2=type, 3=category, 4=unit,
    #   5=available_qty, 6=icon, 7=description, 8=unavailable_periods,
    #   9=created_at, 10=updated_at
    @staticmethod
    def _row_to_resource(r) -> Resource:
        try:
            periods_raw = json.loads(r[8])
        except (json.JSONDecodeError, TypeError, IndexError):
            periods_raw = []
        periods = [
            UnavailablePeriod(**p) for p in periods_raw
            if isinstance(p, dict)
        ]
        return Resource(
            id=r[0], name=r[1], type=ResourceType(r[2]),
            category=r[3], unit=r[4], available_qty=r[5],
            icon=r[6], description=r[7],
            unavailable_periods=periods,
            created_at=r[9] if len(r) > 9 else "",
            updated_at=r[10] if len(r) > 10 else "",
        )

    # ── Section CRUD ─────────────────────────────

    def _seed_default_sections(self):
        """首次运行时插入默认分类（如果表为空）"""
        count = self.conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        if count == 0:
            for i, (key, label) in enumerate(DEFAULT_SECTION_LABELS.items()):
                color = DEFAULT_SECTION_COLORS.get(key, "#89b4fa")
                self.conn.execute(
                    "INSERT INTO sections (key, label, color, sort_order) VALUES (?,?,?,?)",
                    (key, label, color, i),
                )

    def get_all_sections(self) -> list[dict]:
        """返回所有分类: [{id, key, label, color, sort_order}, ...]"""
        rows = self.conn.execute(
            "SELECT id, key, label, color, sort_order FROM sections ORDER BY sort_order, id"
        ).fetchall()
        return [
            {"id": r[0], "key": r[1], "label": r[2], "color": r[3], "sort_order": r[4]}
            for r in rows
        ]

    def get_section_labels(self) -> dict[str, str]:
        """返回 {key: label} 字典"""
        sections = self.get_all_sections()
        return {s["key"]: s["label"] for s in sections}

    def get_section_colors(self) -> dict[str, str]:
        """返回 {key: color} 字典"""
        sections = self.get_all_sections()
        return {s["key"]: s["color"] for s in sections}

    def insert_section(self, key: str, label: str, color: str = "", sort_order: int = 0) -> int:
        """插入新分类，返回 id"""
        if not color:
            # 自动分配颜色：从预设中找未使用的
            used = set(self.get_section_colors().values())
            color = next((c for c in PRESET_COLORS if c not in used), "#89b4fa")
        self.conn.execute(
            "INSERT INTO sections (key, label, color, sort_order) VALUES (?,?,?,?)",
            (key, label, color, sort_order),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def update_section(self, section_id: int, key: str, label: str, color: str, sort_order: int):
        """更新分类"""
        self.conn.execute(
            "UPDATE sections SET key=?, label=?, color=?, sort_order=? WHERE id=?",
            (key, label, color, sort_order, section_id),
        )

    def delete_section(self, section_id: int):
        """删除分类（不会删除任务，只是移除分类定义）"""
        self.conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))

    def section_task_count(self, key: str) -> int:
        """统计某分类下的任务数量"""
        return self.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE section = ?", (key,)
        ).fetchone()[0]

    # ── Test Results CRUD ──────────────────────────

    def insert_test_result(self, task_id, result, test_data="", notes="",
                           tester="", attachments=None) -> int:
        """插入测试结果，返回 id"""
        if attachments is None:
            attachments = []
        if isinstance(attachments, (list, tuple)):
            attachments = json.dumps(attachments)
        self.conn.execute(
            """INSERT INTO test_results
               (task_id, result, test_data, notes, tester, attachments)
               VALUES (?,?,?,?,?,?)""",
            (task_id, result, test_data, notes, tester, attachments),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_test_results(self, task_id: int) -> list[dict]:
        """获取某任务的所有测试结果，按 test_date 降序"""
        rows = self.conn.execute(
            """SELECT id, task_id, test_date, result, test_data,
                      notes, tester, attachments, created_at
               FROM test_results
               WHERE task_id = ?
               ORDER BY test_date DESC""",
            (task_id,),
        ).fetchall()
        return [
            {
                "id": r[0], "task_id": r[1], "test_date": r[2],
                "result": r[3], "test_data": r[4], "notes": r[5],
                "tester": r[6], "attachments": r[7], "created_at": r[8],
            }
            for r in rows
        ]

    def get_latest_test_result(self, task_id: int) -> dict | None:
        """获取某任务的最新测试结果"""
        row = self.conn.execute(
            """SELECT id, task_id, test_date, result, test_data,
                      notes, tester, attachments, created_at
               FROM test_results
               WHERE task_id = ?
               ORDER BY test_date DESC
               LIMIT 1""",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "task_id": row[1], "test_date": row[2],
            "result": row[3], "test_data": row[4], "notes": row[5],
            "tester": row[6], "attachments": row[7], "created_at": row[8],
        }

    def delete_test_result(self, result_id: int):
        """删除测试结果"""
        self.conn.execute(
            "DELETE FROM test_results WHERE id = ?", (result_id,)
        )

    def update_test_result(self, result_id, **kwargs):
        """更新测试结果字段"""
        allowed = {
            "result", "test_data", "notes", "tester", "attachments",
            "test_date",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        # 如果 attachments 是 list/tuple，序列化为 JSON
        if "attachments" in updates and isinstance(
            updates["attachments"], (list, tuple)
        ):
            updates["attachments"] = json.dumps(updates["attachments"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [result_id]
        self.conn.execute(
            f"UPDATE test_results SET {set_clause} WHERE id = ?",
            values,
        )

    # ── Test Issues CRUD ──────────────────────────

    def insert_issue(self, task_id, title, **kwargs) -> int:
        """插入 issue，返回 id"""
        severity = kwargs.get("severity", "medium")
        description = kwargs.get("description", "")
        issue_type = kwargs.get("issue_type", "bug")
        status = kwargs.get("status", "open")
        priority = kwargs.get("priority", 3)
        phase = kwargs.get("phase", "")
        assignee = kwargs.get("assignee", "")
        cause = kwargs.get("cause", "")
        countermeasure = kwargs.get("countermeasure", "")
        tags = kwargs.get("tags", [])
        if isinstance(tags, (list, tuple)):
            tags = json.dumps(tags)
        self.conn.execute(
            """INSERT INTO test_issues
               (task_id, title, description, issue_type, severity, status,
                priority, phase, assignee, cause, countermeasure, tags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, title, description, issue_type, severity, status,
             priority, phase, assignee, cause, countermeasure, tags),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_issues(self, task_id: int = None,
                   status: str = None) -> list[dict]:
        """获取 issues，可按 task_id 和 status 过滤，按 priority ASC, found_date DESC"""
        conditions: list[str] = []
        params: list = []
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        rows = self.conn.execute(
            f"""SELECT id, task_id, title, description, issue_type, severity, status,
                       priority, phase, assignee, found_date, resolved_date,
                       resolution, cause, countermeasure,
                       tags, created_at, updated_at
                FROM test_issues
                {where}
                ORDER BY priority ASC, found_date DESC""",
            params,
        ).fetchall()
        return [
            {
                "id": r[0], "task_id": r[1], "title": r[2],
                "description": r[3], "issue_type": r[4],
                "severity": r[5], "status": r[6],
                "priority": r[7], "phase": r[8],
                "assignee": r[9], "found_date": r[10],
                "resolved_date": r[11], "resolution": r[12],
                "cause": r[13], "countermeasure": r[14],
                "tags": r[15], "created_at": r[16], "updated_at": r[17],
            }
            for r in rows
        ]

    def get_issue(self, issue_id: int) -> dict | None:
        """获取单个 issue"""
        row = self.conn.execute(
            """SELECT id, task_id, title, description, issue_type, severity, status,
                      priority, phase, assignee, found_date, resolved_date,
                      resolution, cause, countermeasure,
                      tags, created_at, updated_at
               FROM test_issues
               WHERE id = ?""",
            (issue_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "task_id": row[1], "title": row[2],
            "description": row[3], "issue_type": row[4],
            "severity": row[5], "status": row[6],
            "priority": row[7], "phase": row[8],
            "assignee": row[9], "found_date": row[10],
            "resolved_date": row[11], "resolution": row[12],
            "cause": row[13], "countermeasure": row[14],
            "tags": row[15], "created_at": row[16], "updated_at": row[17],
        }

    def update_issue(self, issue_id, **kwargs):
        """更新 issue 字段，自动更新 updated_at"""
        allowed = {
            "title", "description", "issue_type", "severity", "status", "priority",
            "phase", "assignee", "resolved_date", "resolution", "cause",
            "countermeasure", "tags",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        # 如果 tags 是 list/tuple，序列化为 JSON
        if "tags" in updates and isinstance(updates["tags"], (list, tuple)):
            updates["tags"] = json.dumps(updates["tags"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [issue_id]
        self.conn.execute(
            f"UPDATE test_issues SET {set_clause}, updated_at=datetime('now','localtime') WHERE id = ?",
            values,
        )

    def delete_issue(self, issue_id: int):
        """删除 issue"""
        self.conn.execute(
            "DELETE FROM test_issues WHERE id = ?", (issue_id,)
        )

    # ── Issue History (审计日志) ─────────────────────────

    def insert_issue_history(self, issue_id: int, field: str,
                             old_value: str, new_value: str,
                             changed_by: str = "", remark: str = ""):
        """记录 issue 字段变更历史"""
        self.conn.execute(
            """INSERT INTO issue_history
               (issue_id, field, old_value, new_value, remark, changed_by)
               VALUES (?,?,?,?,?,?)""",
            (issue_id, field, old_value, new_value, remark, changed_by),
        )

    def get_issue_history(self, issue_id: int) -> list[dict]:
        """获取 issue 的变更历史，按时间倒序"""
        rows = self.conn.execute(
            """SELECT id, issue_id, field, old_value, new_value,
                      remark, changed_at, changed_by
               FROM issue_history
               WHERE issue_id = ?
               ORDER BY changed_at DESC""",
            (issue_id,),
        ).fetchall()
        return [
            {
                "id": r[0], "issue_id": r[1], "field": r[2],
                "old_value": r[3], "new_value": r[4],
                "remark": r[5], "changed_at": r[6], "changed_by": r[7],
            }
            for r in rows
        ]

    def get_issue_stats(self) -> dict:
        """返回 issue 统计: {total, open, in_progress, fixed, closed, by_severity: {critical: N, ...}}

        使用 GROUP BY 单次查询替代多次 COUNT 查询。
        """
        result: dict = {
            "total": 0, "open": 0, "in_progress": 0, "fixed": 0,
            "verified": 0, "closed": 0, "wontfix": 0,
            "by_severity": {"critical": 0, "major": 0, "minor": 0, "cosmetic": 0, "suggestion": 0},
        }

        rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM test_issues GROUP BY status"
        ).fetchall()
        total = 0
        for status, cnt in rows:
            total += cnt
            if status in result:
                result[status] = cnt
        result["total"] = total

        sev_rows = self.conn.execute(
            "SELECT severity, COUNT(*) FROM test_issues GROUP BY severity"
        ).fetchall()
        for sev, cnt in sev_rows:
            if sev in result["by_severity"]:
                result["by_severity"][sev] = cnt

        return result
