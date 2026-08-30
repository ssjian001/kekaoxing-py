"""ReliaTrack 测试 fixtures。

提供共享的测试辅助工具：内存数据库连接、示例数据生成器。
"""

from __future__ import annotations

import os

# 必须在 PySide6 导入前设置，避免在 CI/无头环境中弹出 GUI 窗口
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import apsw

from src.db.schema import init_schema


@pytest.fixture(autouse=True)
def _qt_widget_cleanup():
    """每个测试结束后回收该测试期间新出现的顶层控件。

    前序测试泄漏的 Qt 控件会让 QApplication.setStyleSheet 的重刷成本
    随套件推进线性累积（表现为后段测试从 0.1s 涨到 14s）。
    只删除测试开始后新建的顶层控件，模块/会话级 fixture 持有的
    控件（快照中已存在）不受影响；纯服务层测试直接跳过。
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    before = set(app.topLevelWidgets()) if app is not None else None
    yield
    if before is None:
        return
    from PySide6.QtCore import QEvent

    for w in app.topLevelWidgets():
        if w not in before:
            w.close()
            w.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture(autouse=True, scope="module")
def _qt_module_widget_cleanup():
    """每个测试模块结束时回收所有顶层控件。

    module 级 UI fixture（如 MainWindow）没有 teardown，模块结束后其
    控件树会泄漏到套件其余部分，让 QApplication.setStyleSheet 的重刷
    成本累积（后段测试从 0.1s 涨到 14s）。模块终态化时其 fixture 已
    全部终结（本 fixture 的 teardown 最后执行），此时回收是安全的。
    """
    yield
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        w.close()
        w.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture()
def db_conn() -> apsw.Connection:
    """创建一个内存数据库连接，并初始化完整 schema。

    每个测试用例获得独立的数据库实例，互不干扰。
    """
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    # 通过 close_connection 清理单例缓存，避免后续测试拿到已关闭连接
    # 使用公共 API 而非直接操作私有属性 _connections
    from src.db.connection import close_connection
    try:
        close_connection(":memory:")
    except Exception:
        # 内存数据库关闭失败不影响测试结果
        pass


@pytest.fixture()
def sample_project(db_conn: apsw.Connection) -> dict:
    """插入一条示例项目数据并返回其字段。"""
    db_conn.execute(
        """INSERT INTO projects (name, product, customer, description, status)
           VALUES (?, ?, ?, ?, ?)""",
        ("可靠性验证项目A", "SmartWidget Pro", "客户X", "产品生命周期验证", "active"),
    )
    cursor = db_conn.execute(
        "SELECT * FROM projects WHERE name = '可靠性验证项目A'"
    )
    row = cursor.fetchone()
    return {
        "id": row[0],
        "name": row[1],
        "product": row[2],
        "customer": row[3],
        "description": row[4],
        "status": row[5],
    }


@pytest.fixture()
def sample_technician(db_conn: apsw.Connection) -> dict:
    """插入一条示例技术员数据并返回其字段。"""
    db_conn.execute(
        """INSERT INTO technicians (name, role, department)
           VALUES (?, ?, ?)""",
        ("张工", "DQE", "质量部"),
    )
    cursor = db_conn.execute(
        "SELECT * FROM technicians WHERE name = '张工'"
    )
    row = cursor.fetchone()
    return {
        "id": row[0],
        "name": row[1],
        "role": row[2],
        "department": row[3],
    }


@pytest.fixture()
def sample_equipment(db_conn: apsw.Connection) -> dict:
    """插入一条示例设备数据并返回其字段。"""
    db_conn.execute(
        """INSERT INTO equipment (name, type, model, location, status)
           VALUES (?, ?, ?, ?, ?)""",
        ("高低温试验箱-01", "高低温箱", "ESL-1000", "实验室A区", "available"),
    )
    cursor = db_conn.execute(
        "SELECT * FROM equipment WHERE name = '高低温试验箱-01'"
    )
    row = cursor.fetchone()
    return {
        "id": row[0],
        "name": row[1],
        "type": row[2],
        "model": row[3],
        "location": row[4],
        "status": row[5],
    }


@pytest.fixture()
def sample_sample(db_conn: apsw.Connection, sample_project: dict) -> dict:
    """插入一条示例样品数据并返回其字段。"""
    db_conn.execute(
        """INSERT INTO samples (sn, batch_no, spec, project_id, status)
           VALUES (?, ?, ?, ?, ?)""",
        ("SN-2026-001", "BATCH-001", "SWP-PRO-V2", sample_project["id"], "in_stock"),
    )
    cursor = db_conn.execute(
        "SELECT * FROM samples WHERE sn = 'SN-2026-001'"
    )
    row = cursor.fetchone()
    return {
        "id": row[0],
        "sn": row[1],
        "batch_no": row[2],
        "spec": row[3],
        "project_id": row[4],
        "status": row[5],
    }

# Script-based test files — exclude from pytest collection
# (they create their own QApplication / have non-fixture signatures)
collect_ignore = ["test_e2e_full.py", "test_performance.py"]
