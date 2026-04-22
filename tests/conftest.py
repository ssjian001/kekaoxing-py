"""Shared fixtures for all tests."""
import os
import tempfile
import pytest


@pytest.fixture()
def db(tmp_path):
    """Create a fresh, temporary Database for each test."""
    from src.db.database import Database
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    # Clear default sections so tests get a clean slate
    db.conn.execute("DELETE FROM sections")
    yield db


@pytest.fixture()
def sample_tasks(db):
    """Insert 5 sample tasks and return them as a list."""
    from src.models import Task, Section
    tasks = [
        Task(id=0, num="1", name_en="Thermal Cycle", name_cn="温度循环",
             section=Section.ENV, duration=10, start_day=0, progress=0.0),
        Task(id=0, num="2", name_en="Vibration", name_cn="振动测试",
             section=Section.MECH, duration=5, start_day=10, progress=0.0),
        Task(id=0, num="3", name_en="Salt Spray", name_cn="盐雾试验",
             section=Section.SURF, duration=7, start_day=15, progress=0.0),
        Task(id=0, num="4", name_en="Drop Test", name_cn="跌落试验",
             section=Section.PACK, duration=3, start_day=22, progress=50.0),
        Task(id=0, num="5", name_en="IP67", name_cn="IP67防水",
             section=Section.ENV, duration=4, start_day=25, progress=100.0, done=True),
    ]
    inserted = []
    for t in tasks:
        tid = db.insert_task(t)
        inserted.append(db.get_task(tid))
    return inserted


@pytest.fixture()
def sample_resources(db):
    """Insert 3 sample resources and return them as a list."""
    from src.models import Resource, ResourceType
    resources = [
        Resource(id=0, name="振动台", type=ResourceType.EQUIPMENT,
                 category="机械", unit="台", available_qty=2, icon="📳"),
        Resource(id=0, name="盐雾箱", type=ResourceType.EQUIPMENT,
                 category="表面", unit="台", available_qty=1, icon="🧂"),
        Resource(id=0, name="产品样机", type=ResourceType.SAMPLE_POOL,
                 category="样品", unit="台", available_qty=3, icon="📦"),
    ]
    inserted = []
    for r in resources:
        rid = db.insert_resource(r)
        inserted.append(db.get_resource(rid))
    return inserted
