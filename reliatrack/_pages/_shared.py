"""ReliaTrack Streamlit — 共享工具模块。

提供数据库连接、Service 工厂、DataFrame 展示辅助、状态徽章、分页、删除确认等。
"""
from __future__ import annotations

import sys
import os

# 确保能从 reliatrack/ 找到 src/
# __file__ = reliatrack/_pages/_shared.py → 需要 reliatrack/ 在 sys.path
_PAGES_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PAGES_DIR)  # reliatrack/
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

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
    """将 dataclass 列表转为 DataFrame，支持排除/重命名字段。

    None 值自动转为空字符串。
    """
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
        # None → "" 转换
        row = {k: ("" if v is None else v) for k, v in row.items()}
        rows.append(row)
    df = pd.DataFrame(rows)
    if rename:
        df = df.rename(columns=rename)
    if columns:
        cols = [c for c in columns if c in df.columns]
        return df[cols]
    return df


# ── 状态颜色映射（hex 颜色，替代 emoji） ──────────────────

STATUS_COLORS: dict[str, str] = {
    # 项目
    "active": "#22c55e", "paused": "#eab308", "completed": "#3b82f6",
    "archived": "#94a3b8", "closed": "#1e293b",
    # 样品
    "in_stock": "#22c55e", "in_test": "#3b82f6", "checked_out": "#f97316",
    "returned": "#a855f7", "scrapped": "#ef4444", "suspended": "#eab308",
    # 任务
    "pending": "#94a3b8", "in_progress": "#eab308", "completed": "#22c55e",
    "skipped": "#1e293b",
    # 计划
    "draft": "#94a3b8", "in_progress": "#eab308", "completed": "#22c55e",
    "paused": "#eab308", "archived": "#1e293b",
    # Issue
    "open": "#ef4444", "analyzing": "#eab308", "verified": "#3b82f6",
    "closed": "#22c55e",
    # 设备
    "available": "#22c55e", "maintenance": "#f97316", "offline": "#ef4444",
    # CAPA
    "pending": "#94a3b8", "in_progress": "#eab308", "completed": "#22c55e",
    "verified": "#3b82f6",
}

# 默认颜色（fallback）
_DEFAULT_COLOR = "#94a3b8"


def status_badge(status: str) -> str:
    """返回 HTML 彩色圆点 + 状态文本。

    配合 ``st.markdown(..., unsafe_allow_html=True)`` 使用。

    Examples
    --------
    >>> st.markdown(status_badge(\"active\"), unsafe_allow_html=True)
    """
    color = STATUS_COLORS.get(status, _DEFAULT_COLOR)
    return (
        '<span style="display:inline-flex;align-items:center;gap:4px">'
        f'<span style="width:8px;height:8px;border-radius:50%;'
        f'background:{color};display:inline-block;flex-shrink:0"></span>'
        f' {status}</span>'
    )


# ── 统一分页组件 ───────────────────────────────────────────

def render_pagination(total: int, page_size: int, page_key: str) -> tuple[int, int]:
    """渲染分页控件，返回 (current_page, total_pages)。

    Parameters
    ----------
    total : int
        总记录数。
    page_size : int
        每页条数。
    page_key : str
        Streamlit session_state key 前缀，用于保存当前页码。

    Returns
    -------
    tuple[int, int]
        (current_page, total_pages)

    Notes
    -----
    使用 ``st.columns([1, 2, 1])`` 布局，左右为上一页/下一页按钮，
    中间显示 "第 X / Y 页（共 N 条）"。
    """
    total_pages = max(1, (total + page_size - 1) // page_size)
    state_key = f"{page_key}_page"

    if state_key not in st.session_state:
        st.session_state[state_key] = 1

    current = st.session_state[state_key]
    if current > total_pages:
        current = total_pages
        st.session_state[state_key] = current

    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("◀ 上一页", key=f"{page_key}_prev",
                      disabled=(current <= 1),
                      use_container_width=True):
            st.session_state[state_key] = max(1, current - 1)
            st.rerun()
    with col_info:
        st.markdown(
            f"<div style='text-align:center;padding-top:4px'>"
            f"第 {current} / {total_pages} 页（共 {total} 条）"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("下一页 ▶", key=f"{page_key}_next",
                      disabled=(current >= total_pages),
                      use_container_width=True):
            st.session_state[state_key] = min(total_pages, current + 1)
            st.rerun()

    return current, total_pages


# ── 统一删除确认 ───────────────────────────────────────────

def render_delete_confirm(entity_name: str, confirm_key: str) -> bool:
    """用 st.popover 渲染删除确认，返回 True 表示确认删除。

    只在用户点击 popover 内的「确认删除」按钮时返回 True，
    其他情况（popover 未打开/点击取消/关闭 popover）均返回 False。

    Parameters
    ----------
    entity_name : str
        实体名称，显示在确认文案中。
    confirm_key : str
        Streamlit widget key 前缀，用于按钮唯一标识。

    Returns
    -------
    bool
        用户点击确认删除按钮时返回 True。
    """
    confirmed = False
    with st.popover("🗑️ 删除", use_container_width=True):
        st.warning(f"确定要删除「{entity_name}」吗？")
        st.caption("此操作不可撤销。")
        if st.button("确认删除", type="primary", key=confirm_key):
            confirmed = True
    return confirmed
