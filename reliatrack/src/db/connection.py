"""数据库连接管理器 — 单例模式，线程安全。

使用 apsw (Another Python SQLite Wrapper) 提供高性能 SQLite 访问。
默认启用 WAL 模式和外键约束。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import apsw

_DEFAULT_DB_DIR = Path.home() / ".reliatrack"
_DEFAULT_DB_NAME = "reliatrack.db"

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
    """关闭所有已打开的数据库连接。"""
    with _lock:
        for conn in _connections.values():
            conn.close()
        _connections.clear()
