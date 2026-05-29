"""数据库连接管理器 — 单例模式。

使用 apsw (Another Python SQLite Wrapper) 提供高性能 SQLite 访问。
默认启用 WAL 模式和外键约束。

⚠️ 线程安全说明：
  - 连接的 *创建* 由 threading.Lock 保护，线程安全。
  - 返回的 apsw.Connection 本身 **不是线程安全的**，禁止跨线程并发写入。
  - 当前架构为 Qt 单线程事件循环，所有 DB 操作在主线程执行，安全。
  - 如果将来引入 QThread 做后台导出/同步，需为子线程创建独立连接，
    不可共享 get_connection() 返回的连接对象。
  - BackupService.create_backup() 使用 apsw.backup API 在主连接上操作，
    期间主线程不应有并发写入——当前架构下安全，但需注意。
"""

from __future__ import annotations

import threading
from pathlib import Path

import apsw

_DEFAULT_DB_DIR = Path.home() / ".reliatrack"
_DEFAULT_DB_NAME = "reliatrack.db"
DEFAULT_ATTACHMENTS_DIR = _DEFAULT_DB_DIR / "attachments"
DEFAULT_BACKUPS_DIR = _DEFAULT_DB_DIR / "backups"
DEFAULT_LOGS_DIR = _DEFAULT_DB_DIR / "logs"

_connections: dict[str, apsw.Connection] = {}
_lock = threading.Lock()


def _ensure_dir(db_path: str) -> None:
    """确保数据库文件所在目录存在。"""
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: str = "") -> apsw.Connection:
    """获取数据库连接（单例模式）。

    Args:
        db_path: 数据库文件路径。为空时使用默认路径 ~/.reliatrack/reliatrack.db。
                 传入 ":memory:" 可创建内存数据库（用于测试）。

    Returns:
        apsw.Connection 实例。对相同 db_path 多次调用返回同一连接。
    """
    if not db_path:
        db_path = str(_DEFAULT_DB_DIR / _DEFAULT_DB_NAME)

    with _lock:
        if db_path in _connections:
            conn = _connections[db_path]
            # 检查连接是否仍然可用（可能被外部 close()）
            try:
                conn.execute("SELECT 1")
            except apsw.SQLError:
                # 连接已关闭或损坏，清理后重建
                try:
                    conn.close()
                except apsw.SQLError:
                    pass
                del _connections[db_path]
                # fall through to recreate

        if db_path not in _connections:
            if db_path != ":memory:":
                _ensure_dir(db_path)

            conn = apsw.Connection(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            _connections[db_path] = conn

        return _connections[db_path]


def close_connection(db_path: str = "") -> None:
    """关闭指定路径的数据库连接。

    Args:
        db_path: 要关闭的数据库路径。为空时使用默认路径。
    """
    if not db_path:
        db_path = str(_DEFAULT_DB_DIR / _DEFAULT_DB_NAME)

    with _lock:
        conn = _connections.pop(db_path, None)
        if conn is not None:
            conn.close()


def close_all_connections() -> None:
    """关闭所有已打开的数据库连接（先 checkpoint 再关闭）。"""
    with _lock:
        for conn in _connections.values():
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            conn.close()
        _connections.clear()
