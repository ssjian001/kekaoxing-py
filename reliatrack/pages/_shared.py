"""ReliaTrack Streamlit — 共享工具模块。

提供数据库连接、Service 工厂、DataFrame 展示辅助等。
"""
from __future__ import annotations

import sys
import os

# 确保能从 reliatrack/ 找到 src/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT_DIR = os.path.dirname(_PROJECT_ROOT)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from typing import Any
from dataclasses import fields, is_dataclass

import streamlit as st
import pandas as pd
import apsw

from src.db.connection import get_connection
from src.db.repositories import (
    ProjectRepository, EquipmentRepository, TechnicianRepository,
    SampleRepository, TestPlanRepository, TestTaskRepository,
    IssueRepository, TestResultRepository, KnowledgeRepository,
)
from src.services import (
    ProjectService, EquipmentService, TechnicianService,
    SampleService, TestPlanService, IssueService,
    SchedulerService, KnowledgeService, ExportService,
)


# ── 数据库连接（缓存） ─────────────────────────────────────

@st.cache_resource
def get_db() -> apsw.Connection:
    """获取数据库连接（Streamlit 层面缓存）。"""
    return get_connection()


# ── Service 工厂 ───────────────────────────────────────────

@st.cache_resource
def get_services() -> dict[str, Any]:
    """初始化所有 Service 并缓存。"""
    conn = get_db()
    project_repo = ProjectRepository(conn)
    equipment_repo = EquipmentRepository(conn)
    technician_repo = TechnicianRepository(conn)
    sample_repo = SampleRepository(conn)
    plan_repo = TestPlanRepository(conn)
    task_repo = TestTaskRepository(conn)
    result_repo = TestResultRepository(conn)
    issue_repo = IssueRepository(conn)
    knowledge_repo = KnowledgeRepository(conn)
    return {
        "project": ProjectService(project_repo, plan_repo, task_repo, sample_repo, issue_repo),
        "equipment": EquipmentService(equipment_repo),
        "technician": TechnicianService(technician_repo, task_repo, issue_repo),
        "sample": SampleService(sample_repo, result_repo, issue_repo),
        "plan": TestPlanService(plan_repo, task_repo, result_repo),
        "scheduler": SchedulerService(task_repo, equipment_repo, plan_repo),
        "issue": IssueService(issue_repo, conn),
        "knowledge": KnowledgeService(knowledge_repo),
        "export": ExportService(),
    }


# ── dataclass → DataFrame 辅助 ────────────────────────────

def dataclass_to_df(objs: list[Any],
                    exclude: set[str] | None = None,
                    rename: dict[str, str] | None = None,
                    columns: list[str] | None = None) -> pd.DataFrame:
    """将 dataclass 列表转为 DataFrame，支持排除/重命名字段。"""
    if not objs:
        return pd.DataFrame()
    exclude = exclude or set()
    rename = rename or {}
    rows = []
    for obj in objs:
        if is_dataclass(obj):
            row = {f.name: getattr(obj, f.name) for f in fields(obj)
                   if f.name not in exclude}
        elif isinstance(obj, dict):
            row = {k: v for k, v in obj.items() if k not in exclude}
        else:
            row = {}
        rows.append(row)
    df = pd.DataFrame(rows)
    if rename:
        df = df.rename(columns=rename)
    if columns:
        cols = [c for c in columns if c in df.columns]
        return df[cols]
    return df


# ── 状态标签颜色映射 ──────────────────────────────────────

STATUS_COLORS: dict[str, str] = {
    # 项目
    "active": "🟢", "paused": "🟡", "completed": "🔵", "archived": "⚪", "closed": "⚫",
    # 样品
    "in_stock": "🟢", "in_test": "🔵", "checked_out": "🟠", "returned": "🟣", "scrapped": "🔴", "suspended": "🟡",
    # 任务
    "pending": "⚪", "in_progress": "🟡", "completed": "🟢", "skipped": "⚫",
    # 计划
    "draft": "⚪", "paused": "🟡", "archived": "⚫",
    # Issue
    "open": "🔴", "analyzing": "🟡", "verified": "🔵", "closed": "🟢",
    # 设备
    "available": "🟢", "maintenance": "🟠", "offline": "🔴",
    # CAPA
    "pending": "⚪", "in_progress": "🟡", "completed": "🟢", "verified": "🔵",
}

def status_badge(status: str) -> str:
    """返回带状态图标的标签字符串。"""
    icon = STATUS_COLORS.get(status, "⚪")
    return f"{icon} {status}"
