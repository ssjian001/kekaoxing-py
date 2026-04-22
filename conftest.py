"""pytest 全局 fixtures — 所有测试共享。

策略：
  - 数据库测试用 :memory: SQLite，零 IO
  - GUI 测试用 offscreen platform，无需 X11
  - 每个 test function 独立 DB 实例，无状态污染
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

# ── GUI offscreen ──────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ── project root on sys.path ───────────────────────────────
# conftest.py 在项目根目录，src/ 已在 path 中


# ── fixtures ────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    """内存 SQLite 数据库，每个测试独立。"""
    from src.db.database import Database
    return Database(":memory:")


@pytest.fixture()
def tmp_db(tmp_path):
    """临时文件 SQLite 数据库（用于需要多连接的场景，如 backup）。"""
    from src.db.database import Database
    fp = str(tmp_path / "test.db")
    return Database(fp), fp


@pytest.fixture()
def sample_tasks(db):
    """预填充 5 条任务，返回 list[Task]。"""
    from src.models import Task
    tasks = []
    for i in range(1, 6):
        t = Task(
            num=str(i), name_en=f"Task {i}", name_cn=f"任务{i}",
            section="ENV", duration=5, start_day=(i - 1) * 10,
            progress=0.0, priority=i, done=0,
        )
        db.insert_task(t)
        tasks.append(t)
    # 重新读取（含自增 id）
    return db.get_all_tasks()


@pytest.fixture()
def sample_resources(db):
    """预填充 2 设备 + 1 样品池。"""
    from src.models import Resource, ResourceType
    r1 = Resource(name="温箱A", type=ResourceType.EQUIPMENT,
                  category="环境", unit="台", available_qty=2, icon="🌡️")
    r2 = Resource(name="振动台", type=ResourceType.EQUIPMENT,
                  category="机械", unit="台", available_qty=1, icon="📳")
    r3 = Resource(name="样品池A", type=ResourceType.SAMPLE_POOL,
                  category="通用", unit="批", available_qty=10, icon="📦")
    for r in (r1, r2, r3):
        db.insert_resource(r)
    return db.get_all_resources()
