"""📊 仪表盘页面 — KPI 卡片 + 进度饼图 + 近期活动。"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from pages._shared import get_services, dataclass_to_df


def show() -> None:
    st.title("📊 仪表盘")
    svc = get_services()

    # 获取数据
    projects = svc["project"].list_all()
    samples = svc["sample"].list_all()
    plans = svc["plan"].list_all_plans()
    issues = svc["issue"].list_all()

    # 统计
    total_projects = len(projects)
    total_samples = len(samples)
    total_plans = len(plans)
    total_issues = len(issues)

    active_issues = sum(1 for i in issues if i.status in ("open", "analyzing"))
    in_progress_tasks = 0
    for plan in plans:
        if plan.id:
            try:
                in_progress_tasks += sum(
                    1 for t in svc["plan"].get_tasks(plan.id)
                    if t.status == "in_progress"
                )
            except Exception:
                pass

    # KPI 卡片
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📁 项目数", total_projects)
    with col2:
        st.metric("🔬 样品数", total_samples)
    with col3:
        st.metric("📋 计划数", total_plans)
    with col4:
        st.metric("⚙️ 进行中任务", in_progress_tasks)
    with col5:
        st.metric("⚠️ 待处理 Issue", active_issues)

    st.markdown("---")

    # 饼图：样品状态分布
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("样品状态分布")
        if samples:
            status_counts: dict[str, int] = {}
            for s in samples:
                status_counts[s.status] = status_counts.get(s.status, 0) + 1
            df_status = pd.DataFrame(
                list(status_counts.items()), columns=["状态", "数量"]
            )
            fig = px.pie(df_status, names="状态", values="数量",
                         title="样品状态", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无样品数据")

    with col_right:
        st.subheader("Issue 状态分布")
        if issues:
            issue_counts: dict[str, int] = {}
            for i in issues:
                issue_counts[i.status] = issue_counts.get(i.status, 0) + 1
            df_issue = pd.DataFrame(
                list(issue_counts.items()), columns=["状态", "数量"]
            )
            fig2 = px.pie(df_issue, names="状态", values="数量",
                          title="Issue 状态", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("暂无 Issue 数据")

    st.markdown("---")

    # 近期活动表
    st.subheader("项目列表")
    if projects:
        df = dataclass_to_df(
            projects,
            exclude={"description"},
            rename={
                "id": "ID",
                "name": "项目名称",
                "product": "产品",
                "customer": "客户",
                "status": "状态",
                "created_at": "创建时间",
            },
            columns=["ID", "项目名称", "产品", "客户", "状态", "创建时间"],
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无项目数据")
