"""性能測試：大數據量下應用各環節的響應時間。

目標：模擬生產環境 1-2 年使用後的數據規模（~1000 任務、~5000 結果、~200 Issue），
profiling 關鍵路徑：DB 查詢、Service 計算、UI 渲染。
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager

# 必須在 import 應用模組前設置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 確保引入專案根
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)


@contextmanager
def _timed(label: str):
    t0 = time.perf_counter()
    yield
    dt = (time.perf_counter() - t0) * 1000
    print(f"  {label:<40s} {dt:>8.2f} ms")


def _seed_large_db(conn, n_tasks: int = 1000, n_results_per_task: int = 5, n_issues: int = 200):
    """填充測試數據。"""
    from datetime import date, timedelta

    today = date.today()

    # 先建一個項目 + 計劃
    conn.execute(
        "INSERT INTO projects (name, status, created_at, updated_at) "
        "VALUES (?, 'active', datetime('now'), datetime('now'))",
        ("Perf Project",),
    )
    project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO test_plans (name, project_id, status, start_date, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, datetime('now'), datetime('now'))",
        ("Perf Test Plan", project_id, today.isoformat()),
    )
    plan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 批量插入任務
    print(f"\n[Seed] 插入 {n_tasks} 個任務 + {n_tasks * n_results_per_task} 個結果...")
    t0 = time.perf_counter()
    with conn:
        for i in range(n_tasks):
            conn.execute(
                "INSERT INTO test_tasks (plan_id, name, category, duration, start_day, "
                "status, priority, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
                (plan_id, f"任務-{i:04d}", "功能" if i % 2 == 0 else "可靠度",
                 5 + (i % 30), i, "pending" if i % 3 else "in_progress",
                 1 + (i % 5), i),
            )
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            # 每任務 N 個結果
            for j in range(n_results_per_task):
                conn.execute(
                    "INSERT INTO test_results (task_id, sample_id, result, test_date) "
                    "VALUES (?, NULL, ?, date('now'))",
                    (task_id, "pass" if (i + j) % 4 else "fail"),
                )
    dt = (time.perf_counter() - t0) * 1000
    print(f"  插入耗時: {dt:.0f} ms")


def _profile_repositories(conn):
    """測試 Repository 查詢性能。"""
    from src.db.repositories import TestTaskRepository, TestResultRepository

    task_repo = TestTaskRepository(conn)

    print("\n[Repository 查詢]")
    with _timed("list_all() (1000 行)"):
        tasks = task_repo.list_all()
        assert len(tasks) == 1000, f"預期 1000，實際 {len(tasks)}"

    with _timed("get_by_plan(plan_id=1) (1000 行)"):
        tasks2 = task_repo.get_by_plan(plan_id=1)
        assert len(tasks2) == 1000

    with _timed("結果彙總 N+1 查詢"):
        # 模擬 N+1 模式：每個任務單獨查
        counts = {}
        for t in tasks:
            r = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN result='pass' THEN 1 ELSE 0 END) "
                "FROM test_results WHERE task_id=?", (t.id,)
            ).fetchone()
            counts[t.id] = (r[1] or 0, r[0])

    # 單次查詢版本（正確寫法）
    with _timed("結果彙總 單次 GROUP BY"):
        bulk = {r[0]: (r[1] or 0, r[2]) for r in conn.execute(
            "SELECT task_id, SUM(CASE WHEN result='pass' THEN 1 ELSE 0 END), COUNT(*) "
            "FROM test_results GROUP BY task_id"
        ).fetchall()}


def _profile_service(conn):
    """測試 Service 層聚合性能。"""
    from src.db.repositories import (
        TestPlanRepository, TestTaskRepository, TestResultRepository,
    )
    from src.services.test_plan_service import TestPlanService

    plan_repo = TestPlanRepository(conn)
    task_repo = TestTaskRepository(conn)
    result_repo = TestResultRepository(conn)

    svc = TestPlanService(plan_repo, task_repo, result_repo)

    print("\n[Service 層]")
    with _timed("get_tasks(plan_id=1)"):
        try:
            tasks = svc.get_tasks(plan_id=1)
            assert len(tasks) == 1000
        except Exception as e:
            print(f"    (skipped: {e})")

    with _timed("get_pass_counts_by_tasks(1000 ids)"):
        try:
            task_ids = [t.id for t in tasks[:1000]]
            counts = svc.get_pass_counts_by_tasks(task_ids)
        except Exception as e:
            print(f"    (skipped: {e})")

    with _timed("get_all_results_by_tasks(1000 ids)"):
        try:
            results = svc.get_all_results_by_tasks(task_ids)
        except Exception as e:
            print(f"    (skipped: {e})")


def _profile_ui_render(conn):
    """測試 UI 渲染性能（offscreen）。"""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from src.db.repositories import TestTaskRepository

    task_repo = TestTaskRepository(conn)

    print("\n[UI 渲染]")
    with _timed("list_all() 1000 任務"):
        tasks = task_repo.list_all()

    from src.views.widgets.task_table import _TaskTable
    table = _TaskTable()

    from datetime import date
    start_date = date.today().isoformat()
    with _timed("table.set_tasks(1000 行)"):
        table.set_tasks(tasks, technician_map={}, result_map={}, start_date=start_date)

    with _timed("sort by 進度列"):
        table.sortItems(6)

    with _timed("sort by 名稱列"):
        table.sortItems(1)

    with _timed("filter 100 行（模擬 search）"):
        filtered = [t for t in tasks if "005" in t.name or "010" in t.name]
        table.set_tasks(filtered, technician_map={}, result_map={}, start_date=start_date)


def main():
    import apsw
    from src.db.schema import init_schema

    print("=" * 60)
    print("ReliaTrack 性能 Profile")
    print("=" * 60)

    # 內存 DB + schema
    conn = apsw.Connection(":memory:")
    init_schema(conn)

    _seed_large_db(conn, n_tasks=1000, n_results_per_task=5, n_issues=200)
    _profile_repositories(conn)
    _profile_service(conn)
    _profile_ui_render(conn)

    print("\n" + "=" * 60)
    print("Profile 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
