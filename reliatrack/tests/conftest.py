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


@pytest.fixture()
def db_conn() -> apsw.Connection:
    """创建一个内存数据库连接，并初始化完整 schema。

    每个测试用例获得独立的数据库实例，互不干扰。
    """
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


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
