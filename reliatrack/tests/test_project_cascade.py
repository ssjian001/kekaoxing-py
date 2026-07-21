"""ProjectService 級聯刪除測試。

覆蓋點：
- cascade_stats: 準確統計各表關聯記錄數
- delete (cascade): 級聯刪除 projects → plans → tasks → results / samples / issues
- 隔離性: 刪除一個項目不影響其他項目的數據
- 空項目: 無關聯數據時不報錯
"""

from __future__ import annotations

import pytest
import apsw

from src.db.schema import init_schema
from src.db.repositories import (
    ProjectRepository, TestPlanRepository, TestTaskRepository,
    SampleRepository, IssueRepository,
)
from src.services.project_service import ProjectService


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def db_conn():
    """內存 DB + 完整 schema。"""
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn


@pytest.fixture()
def project_svc(db_conn):
    """已填充測試數據的 ProjectService。"""
    # 插入 2 個項目 + 關聯數據
    db_conn.execute("INSERT INTO projects (name, status) VALUES ('項目A', 'active')")
    proj_a = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    db_conn.execute("INSERT INTO projects (name, status) VALUES ('項目B', 'active')")
    proj_b = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 項目 A：1 plan + 2 tasks + 3 results + 1 sample + 2 issues
    db_conn.execute("INSERT INTO test_plans (name, project_id, status, start_date) VALUES ('計劃A1', ?, 'active', '2026-07-19')", (proj_a,))
    plan_a = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i in range(2):
        db_conn.execute(
            "INSERT INTO test_tasks (plan_id, name, category, duration, start_day, status, priority, sort_order) "
            "VALUES (?, ?, '功能', 3, 0, 'pending', 3, ?)",
            (plan_a, f"任務A-{i}", i),
        )
        task_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        db_conn.execute("INSERT INTO test_results (task_id, sample_id, result, test_date) VALUES (?, NULL, 'pass', '2026-07-19')", (task_id,))
        if i == 0:
            for _ in range(2):
                db_conn.execute("INSERT INTO test_results (task_id, sample_id, result, test_date) VALUES (?, NULL, 'fail', '2026-07-19')", (task_id,))

    db_conn.execute("INSERT INTO samples (sn, project_id, status) VALUES ('SN-A001', ?, 'pending')", (proj_a,))

    for i in range(2):
        db_conn.execute(
            "INSERT INTO issues (title, project_id, severity, status, created_at, updated_at) "
            "VALUES (?, ?, 'major', 'open', datetime('now'), datetime('now'))",
            (f"Issue A-{i}", proj_a),
        )

    # 項目 B：1 plan + 1 task（驗證隔離性）
    db_conn.execute("INSERT INTO test_plans (name, project_id, status, start_date) VALUES ('計劃B1', ?, 'active', '2026-07-19')", (proj_b,))
    plan_b = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    db_conn.execute(
        "INSERT INTO test_tasks (plan_id, name, category, duration, start_day, status, priority, sort_order) "
        "VALUES (?, '任務B-0', '功能', 3, 0, 'pending', 3, 0)",
        (plan_b,),
    )

    proj_repo = ProjectRepository(db_conn)
    plan_repo = TestPlanRepository(db_conn)
    task_repo = TestTaskRepository(db_conn)
    sample_repo = SampleRepository(db_conn)
    issue_repo = IssueRepository(db_conn)

    return ProjectService(proj_repo, plan_repo, task_repo, sample_repo, issue_repo)


# ═══════════════════════════════════════════════════════════════════
#  cascade_stats
# ═══════════════════════════════════════════════════════════════════

class TestCascadeStats:

    def test_stats_accurate(self, project_svc, db_conn):
        """統計項目 A 的關聯記錄數應準確。"""
        proj_a = db_conn.execute("SELECT id FROM projects WHERE name='項目A'").fetchone()[0]
        stats = project_svc.cascade_stats(proj_a)

        assert stats["plans"] == 1
        assert stats["tasks"] == 2
        assert stats["samples"] == 1
        assert stats["issues"] == 2

    def test_stats_empty_project(self, project_svc, db_conn):
        """空項目（無關聯數據）應全為 0。"""
        db_conn.execute("INSERT INTO projects (name, status) VALUES ('空項目', 'active')")
        empty_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        stats = project_svc.cascade_stats(empty_id)
        assert stats == {"plans": 0, "tasks": 0, "samples": 0, "issues": 0}

    def test_stats_nonexistent_project(self, project_svc):
        """不存在的項目 ID 應返回全 0（不報錯）。"""
        stats = project_svc.cascade_stats(99999)
        assert stats == {"plans": 0, "tasks": 0, "samples": 0, "issues": 0}


# ═══════════════════════════════════════════════════════════════════
#  delete (cascade)
# ═══════════════════════════════════════════════════════════════════

class TestCascadeDelete:

    def test_delete_removes_all_related(self, project_svc, db_conn):
        """刪除項目 A 後，其所有關聯數據應被清除。"""
        proj_a = db_conn.execute("SELECT id FROM projects WHERE name='項目A'").fetchone()[0]

        project_svc.delete(proj_a)

        # 項目本身
        assert db_conn.execute("SELECT COUNT(*) FROM projects WHERE id=?", (proj_a,)).fetchone()[0] == 0
        # 計劃
        assert db_conn.execute("SELECT COUNT(*) FROM test_plans WHERE project_id=?", (proj_a,)).fetchone()[0] == 0
        # 任務（通過 plan_id IN ...）
        assert db_conn.execute(
            "SELECT COUNT(*) FROM test_tasks WHERE plan_id IN (SELECT id FROM test_plans WHERE project_id=?)",
            (proj_a,)
        ).fetchone()[0] == 0
        # 樣品
        assert db_conn.execute("SELECT COUNT(*) FROM samples WHERE project_id=?", (proj_a,)).fetchone()[0] == 0
        # Issue
        assert db_conn.execute("SELECT COUNT(*) FROM issues WHERE project_id=?", (proj_a,)).fetchone()[0] == 0

    def test_delete_isolation(self, project_svc, db_conn):
        """刪除項目 A 不應影響項目 B 的數據。"""
        proj_a = db_conn.execute("SELECT id FROM projects WHERE name='項目A'").fetchone()[0]
        proj_b = db_conn.execute("SELECT id FROM projects WHERE name='項目B'").fetchone()[0]
        b_plan_count_before = db_conn.execute("SELECT COUNT(*) FROM test_plans WHERE project_id=?", (proj_b,)).fetchone()[0]
        b_task_count_before = db_conn.execute(
            "SELECT COUNT(*) FROM test_tasks WHERE plan_id IN (SELECT id FROM test_plans WHERE project_id=?)",
            (proj_b,)
        ).fetchone()[0]

        project_svc.delete(proj_a)

        # 項目 B 數據完整
        assert db_conn.execute("SELECT COUNT(*) FROM projects WHERE id=?", (proj_b,)).fetchone()[0] == 1
        assert db_conn.execute("SELECT COUNT(*) FROM test_plans WHERE project_id=?", (proj_b,)).fetchone()[0] == b_plan_count_before
        assert db_conn.execute(
            "SELECT COUNT(*) FROM test_tasks WHERE plan_id IN (SELECT id FROM test_plans WHERE project_id=?)",
            (proj_b,)
        ).fetchone()[0] == b_task_count_before

    def test_delete_empty_project(self, project_svc, db_conn):
        """刪除無關聯數據的項目應正常工作。"""
        db_conn.execute("INSERT INTO projects (name, status) VALUES ('待刪空項目', 'active')")
        empty_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        project_svc.delete(empty_id)

        assert db_conn.execute("SELECT COUNT(*) FROM projects WHERE id=?", (empty_id,)).fetchone()[0] == 0

    def test_delete_cascades_test_results(self, project_svc, db_conn):
        """刪除項目時，test_results 應跟隨任務被刪除。"""
        proj_a = db_conn.execute("SELECT id FROM projects WHERE name='項目A'").fetchone()[0]
        # 拿一個 task_id 記下
        task_ids = db_conn.execute(
            "SELECT id FROM test_tasks WHERE plan_id IN (SELECT id FROM test_plans WHERE project_id=?)",
            (proj_a,)
        ).fetchall()
        assert len(task_ids) > 0
        results_before = db_conn.execute(
            f"SELECT COUNT(*) FROM test_results WHERE task_id IN ({','.join('?'*len(task_ids))})",
            [t[0] for t in task_ids]
        ).fetchone()[0]
        assert results_before > 0

        project_svc.delete(proj_a)

        # 所有 results 應被級聯刪除（因為 test_results.task_id FK）
        remaining = db_conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        assert remaining == 0

    def test_delete_nonexistent_id_no_error(self, project_svc):
        """刪除不存在的項目 ID 不應報錯（冪等）。"""
        # 應正常結束，不拋異常
        project_svc.delete(99999)
