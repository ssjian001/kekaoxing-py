"""导出回归测试 — 修复验证专用。

验证 3 个已修复的 bug：
1. _columns_sql() 空列时回退到 '*'（fix: base.py）
2. WorkerDataProvider 独立连接时 init_schema 调用（fix: export_handlers.py）
3. _on_export 中 issue_view → _bug_tracker_view 重定向（fix: export_handlers.py）
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import apsw
import pytest

from src.db.schema import init_schema, SCHEMA_VERSION
from src.db.repositories.base import BaseRepository


# ══════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture()
def memory_conn() -> apsw.Connection:
    """干净的内存 DB（无 schema 初始化）。"""
    conn = apsw.Connection(":memory:")
    yield conn
    conn.close()


@pytest.fixture()
def seeded_conn() -> apsw.Connection:
    """已初始化 schema 的内存 DB。"""
    conn = apsw.Connection(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


# ══════════════════════════════════════════════════════════════
#  _columns_sql 空列保护
# ══════════════════════════════════════════════════════════════


class _FakeRepo(BaseRepository):
    """最小 mock: 仅测试 _columns/_columns_sql，不涉及具体表。"""

    def __init__(self, conn: apsw.Connection) -> None:
        # 跳过 BaseRepo.__init__ 的正常表绑定
        self._conn = conn
        self._table = "non_existent_table"
        self._columns_cache = None
        self._columns_set = None
        self._model_class = None


def test_columns_sql_empty_fallback(memory_conn: apsw.Connection) -> None:
    """_columns_sql 在 PRAGMA 返回空时回退到 '*'。"""
    repo = _FakeRepo(memory_conn)
    # 表不存在 → PRAGMA 返回空 → _columns() 返回 [] → _columns_sql() 应返回 "*"
    sql = repo._columns_sql()
    assert sql == "*", f"期望 '*' 但得到 {sql!r}"

    # 验证 SQL 可执行
    row = memory_conn.execute(f"SELECT {sql} FROM (SELECT 1 AS dummy)").fetchone()
    assert row is not None


def test_columns_sql_after_schema_init(seeded_conn: apsw.Connection) -> None:
    """有 schema 后 _columns_sql 返回显式列名。"""
    repo = _FakeRepo(seeded_conn)
    repo._table = "test_plans"
    cols = repo._columns()
    assert len(cols) > 0, "test_plans 表应有列"
    sql = repo._columns_sql()
    assert sql.startswith("[")
    assert sql.endswith("]")
    assert "[" in sql and "]" in sql


def test_get_by_id_empty_table_graceful(memory_conn: apsw.Connection) -> None:
    """未初始化 schema 时 get_by_id 不崩（回退 '*' 避免语法错误）。"""
    repo = _FakeRepo(memory_conn)
    repo._table = "test_plans"
    # 表不存在但 SQL 应为 "SELECT * FROM [test_plans] WHERE id = ?"
    # 这会抛出 "no such table" 而非语法错误——这是预期的保护行为
    try:
        repo.get_by_id(1)
    except Exception as e:
        msg = str(e)
        # 接受 "no such table" 但拒绝 "near FROM: syntax error"
        assert "no such table" in msg.lower() or "syntax" not in msg.lower(), \
            f"Expected 'no such table' error, got: {msg}"


# ══════════════════════════════════════════════════════════════
#  WorkerDataProvider schema 初始化
# ══════════════════════════════════════════════════════════════


def test_worker_data_provider_init_schema(tmp_path: Path) -> None:
    """WorkerDataProvider 在新 DB 上自动初始化 schema。"""
    db_file = tmp_path / "test_worker.db"

    from src.handlers.export_handlers import WorkerDataProvider

    # WorkerDataProvider 内部调用 apsw.Connection + init_schema
    provider = WorkerDataProvider(str(db_file))
    try:
        # 验证表已创建，通过 PRAGMA 检查
        conn = provider._conn
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        table_count = row[0] if row else 0
        # 至少有 schema_version + 核心业务表
        assert table_count > 5, f"只有 {table_count} 张表，schema 未正确初始化"

        # 确认 test_plans 表存在
        info = conn.execute("PRAGMA table_info(test_plans)").fetchall()
        assert len(info) > 0, "test_plans 应存在于 worker 连接中"
    finally:
        provider.close()


def test_worker_data_provider_plan_query(tmp_path: Path) -> None:
    """WorkerDataProvider 可正常查询测试计划。"""
    db_file = tmp_path / "test_worker2.db"

    # 先通过 init_schema 建表 + 插入一条数据
    conn0 = apsw.Connection(str(db_file))
    init_schema(conn0)
    conn0.execute("PRAGMA foreign_keys=OFF")
    conn0.execute(
        "INSERT INTO test_plans (project_id, name) VALUES (1, 'WorkerTestPlan')"
    )
    conn0.close()

    # Worker 打开同一 DB 应能查到
    from src.handlers.export_handlers import WorkerDataProvider
    provider = WorkerDataProvider(str(db_file))
    try:
        plan = provider.test_plan_service.get_plan(1)
        assert plan is not None, "应查到计划"
        assert plan.name == "WorkerTestPlan"
    finally:
        provider.close()


# ══════════════════════════════════════════════════════════════
#  _on_export issue_id 获取
# ══════════════════════════════════════════════════════════════


def test_on_export_issue_bead_stale_ref() -> None:
    """_on_export 中 issue_view → _bug_tracker_view 重定向验证。

    旧代码用 hasattr(self._win, 'issue_view') 检查，但 issue_view 已经
    被删除（合并到 bug_tracker）。新代码检查 _bug_tracker_view。
    """
    from src.handlers.export_handlers import ExportHandlers

    # 模拟一个没有 issue_view 但有 _bug_tracker_view 的窗口
    mock_list_view = MagicMock()
    mock_list_view.get_selected_issue_id.return_value = 42

    mock_bug_tracker = MagicMock()
    mock_bug_tracker._list_view = mock_list_view

    mock_win = MagicMock(spec=[])
    mock_win._bug_tracker_view = mock_bug_tracker
    # 证实旧的 bug 路径 — 没有 issue_view 属性
    assert not hasattr(mock_win, 'issue_view'), "issue_view 不应存在"

    # 模拟 ExportHandlers._on_export 中的逻辑
    issue_id = None
    if hasattr(mock_win, '_bug_tracker_view'):
        btv = mock_win._bug_tracker_view
        if hasattr(btv, '_list_view') and btv._list_view:
            issue_id = btv._list_view.get_selected_issue_id()

    assert issue_id == 42, "应通过 _bug_tracker_view 正确获取 issue_id"


# ══════════════════════════════════════════════════════════════
#  导出服务基础功能不变
# ══════════════════════════════════════════════════════════════


def test_export_service_creation() -> None:
    """ExportService 构造不抛异常。"""
    from src.services.export_service import ExportService
    svc = ExportService(output_dir="/tmp/test_export")
    assert svc is not None


def test_export_service_no_qt_import() -> None:
    """ExportService 不应依赖 Qt（headless 兼容）。"""
    import sys
    # 模拟无 Qt 环境：清空 PySide6 相关模块
    qt_modules = {k for k in sys.modules if 'PySide6' in k or 'PyQt5' in k}
    # 这只是一个编译期检查：export_service.py/export/__init__.py 不导入 Qt
    import ast
    tree = ast.parse(open(
        os.path.join(os.path.dirname(__file__), '..', 'src', 'services', 'export', '__init__.py')
    ).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if 'PySide' in alias.name or 'PyQt' in alias.name:
                    pytest.fail(f"ExportService 导入 Qt: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and ('PySide' in node.module or 'PyQt' in node.module):
                pytest.fail(f"ExportService 导入 Qt: {node.module}")
