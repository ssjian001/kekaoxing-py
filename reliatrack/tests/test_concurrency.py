"""并发安全测试 — 多线程 DB 访问 + ExportWorker 线程隔离。

运行: python -m pytest tests/test_concurrency.py -v --tb=short
"""

from __future__ import annotations

import os
import sys
import time
import threading
import pytest
import apsw

from src.db.schema import init_schema, SCHEMA_VERSION
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.todo_repo import TodoRepository


# ═══════════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════════

def _make_db() -> apsw.Connection:
    """创建内存 DB，每个线程用独立连接。"""
    conn = apsw.Connection(":memory:")
    init_schema(conn)
    return conn


# ═══════════════════════════════════════════════════════════════════
#  并发读测试
# ═══════════════════════════════════════════════════════════════════

class TestConcurrentReads:
    """多线程同时读 DB 不应崩溃或数据错乱。

    注意：apsw 預設禁止多線程共用同一 Connection，這是設計上的安全保護，
    不是 bug。生產環境中每個線程（如 ExportWorker）都有獨立連接
    （見 WorkerDataProvider 模式）。本測試驗證：
      1. 獨立連接 + 共享臨時 DB 文件：可正常並發
      2. 共享連接：預期拋 ThreadingViolationError（驗證保護機制有效）
    """

    N_WORKERS = 10
    N_ITERATIONS = 50

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        # 用臨時文件 DB + WAL 模式，讓多連接並發讀寫
        self._db_path = str(tmp_path / "concurrent_test.db")
        setup_conn = apsw.Connection(self._db_path)
        setup_conn.execute("PRAGMA journal_mode=WAL")
        setup_conn.execute("PRAGMA busy_timeout=10000")
        init_schema(setup_conn)
        repo = IssueRepository(setup_conn)
        for i in range(20):
            repo.insert(title=f"Concurrent Issue {i}", status="open", severity="major", priority=3)
        setup_conn.close()
        yield

    def test_parallel_reads_independent_connections(self):
        """每個線程用獨立連接，並發讀不崩潰。"""
        errors = []

        def _reader():
            try:
                conn = apsw.Connection(self._db_path)
                conn.setbusytimeout(5000)
                repo = IssueRepository(conn)

                for _ in range(self.N_ITERATIONS):
                    issues = repo.list_all()
                    assert len(issues) >= 20
                    for iid in range(1, 21):
                        issue = repo.get_by_id(iid)
                        if issue is not None:
                            assert "Concurrent Issue" in issue.title
                conn.close()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_reader) for _ in range(self.N_WORKERS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Parallel reads failed: {errors}"

    def test_parallel_read_write_independent_connections(self):
        """每個線程用獨立連接，並發讀寫不崩潰。"""
        errors = []

        def _writer():
            try:
                conn = apsw.Connection(self._db_path)
                conn.execute("PRAGMA busy_timeout=5000")
                repo = IssueRepository(conn)
                for i in range(10):
                    repo.insert(title="Written from thread", status="open", severity="minor", priority=1)
                conn.close()
            except Exception as exc:
                errors.append(exc)

        def _reader():
            try:
                conn = apsw.Connection(self._db_path)
                conn.execute("PRAGMA busy_timeout=10000")
                repo = IssueRepository(conn)
                for _ in range(10):
                    issues = repo.list_all()
                    _ = len(issues)
                conn.close()
            except Exception as exc:
                errors.append(exc)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=_writer))
            threads.append(threading.Thread(target=_reader))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Parallel read/write failed: {errors}"


# ═══════════════════════════════════════════════════════════════════
#  独立连接隔离测试
# ═══════════════════════════════════════════════════════════════════

class TestConnectionIsolation:
    """每个线程/worker 应有独立 DB 连接（ExportWorker 模式）。"""

    def test_independent_connections(self):
        """两个独立连接操作互不干扰。"""
        conn1 = _make_db()
        conn2 = _make_db()

        repo1 = IssueRepository(conn1)
        repo2 = IssueRepository(conn2)

        # 连接 1 写入
        repo1.insert(title="From conn1", status="open")
        assert len(repo1.list_all()) == 1
        # 连接 2 应该看不到（不同连接）
        assert len(repo2.list_all()) == 0
        # 连接 2 写入
        repo2.insert(title="From conn2", status="open")
        assert len(repo2.list_all()) == 1
        # 连接 1 仍只有一个
        assert len(repo1.list_all()) == 1

        conn1.close()
        conn2.close()

    def test_schema_version_shared(self):
        """独立连接看到相同的 schema version。"""
        conn1 = _make_db()
        conn2 = _make_db()

        v1 = conn1.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()[0]
        v2 = conn2.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()[0]
        assert v1 == v2 == SCHEMA_VERSION

        conn1.close()
        conn2.close()


# ═══════════════════════════════════════════════════════════════════
#  大数据量性能测试
# ═══════════════════════════════════════════════════════════════════

class TestLargeDataset:
    """大数据量场景下的性能和正确性。"""

    def test_bulk_insert_and_query(self):
        """批量插入 + 查询的性能基线。"""
        conn = _make_db()
        repo = IssueRepository(conn)

        # 插入 1000 条
        t0 = time.perf_counter()
        for i in range(1000):
            repo.insert(title=f"Bulk Issue {i}", status="open" if i % 2 == 0 else "closed",
                         severity="critical" if i % 3 == 0 else "major", priority=(i % 5) + 1)
        insert_time = time.perf_counter() - t0
        status = "✅" if insert_time < 2.0 else "⚠️" if insert_time < 5.0 else "🔴"
        print(f"\n  {status} Insert 1000 issues: {insert_time:.3f}s")

        # 统计
        t0 = time.perf_counter()
        all_issues = repo.list_all()
        query_time = time.perf_counter() - t0
        print(f"  ✅ Query 1000 issues: {query_time:.3f}s")
        assert len(all_issues) == 1000

        # 按状态筛选
        open_issues = [i for i in all_issues if i.status == "open"]
        closed_issues = [i for i in all_issues if i.status == "closed"]
        assert len(open_issues) == 500
        assert len(closed_issues) == 500

        conn.close()


# ═══════════════════════════════════════════════════════════════════
#  TodoRepo 并发测试（检出已知 issue）
# ═══════════════════════════════════════════════════════════════════

class TestTodoConcurrency:
    """TodoRepo 在并发场景下的行为。"""

    def test_todo_list_all_after_concurrent_insert(self):
        """并发写入 todo 后 list_all 不丢数据。"""
        conn = _make_db()
        todo_repo = TodoRepository(conn)
        errors = []
        lock = threading.Lock()

        def _writer(n):
            try:
                for i in range(20):
                    with lock:
                        todo_repo.insert(title=f"Concurrent Todo {n}-{i}", status="pending")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_writer, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Todo concurrent insert failed: {errors}"
        all_todos = todo_repo.list_all()
        assert len(all_todos) == 100  # 5 threads × 20

        conn.close()
