"""📅 排程管理页面 — Plotly 甘特图 + 排程参数配置。"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from pages._shared import get_services, dataclass_to_df
from src.models.test_plan import TestTask


def show() -> None:
    st.title("📅 排程管理")
    svc = get_services()
    sched_svc = svc["scheduler"]
    plan_svc = svc["plan"]
    p_svc = svc["project"]

    # ── 选择项目 → 计划 ──
    projects = p_svc.list_all()
    proj_map = {p.name: p.id for p in projects if p.id}
    if not proj_map:
        st.info("请先在「项目管理」中创建项目")
        return

    proj_name = st.selectbox("选择项目", list(proj_map.keys()), key="sched_proj")
    proj_id = proj_map[proj_name]

    plans = plan_svc.get_plans_by_project(proj_id)
    plan_map = {p.name: p for p in plans if p.name and p.id}
    if not plan_map:
        st.info("该项目暂无测试计划")
        return

    plan_name = st.selectbox("选择测试计划", list(plan_map.keys()), key="sched_plan")
    plan = plan_map[plan_name]

    # ── 排程参数配置 ──
    with st.expander("⚙️ 排程参数", expanded=True):
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            skip_weekends = st.checkbox("跳过周末", value=True)
            skip_holidays = st.checkbox("跳过节假日", value=True)
        with col_p2:
            deadline = st.text_input("截止日期 (YYYY-MM-DD)", value="")
            lock_existing = st.checkbox("锁定已有排程", value=False)
        with col_p3:
            daily_start_limit = st.number_input("每日最大启动数", min_value=0, value=0,
                                                help="0=不限制")

    # ── 执行排程（预览） ──
    if st.button("🚀 执行自动排程", type="primary"):
        if plan.id:
            result = sched_svc.preview_schedule(
                plan_id=plan.id,
                skip_weekends=skip_weekends,
                skip_holidays=skip_holidays,
                lock_existing=lock_existing,
                deadline=deadline,
                daily_start_limit=daily_start_limit,
            )
            st.session_state["sched_result"] = result
            st.session_state["sched_plan_id"] = plan.id
            st.success("排程完成！")
            st.rerun()

    # ── 显示排程结果 ──
    sched_result = st.session_state.get("sched_result")
    sched_plan_id = st.session_state.get("sched_plan_id")

    if sched_result and sched_plan_id == plan.id:
        tasks: list[TestTask] = sched_result["tasks"]
        report = sched_result["report"]
        original = sched_result["original_start_days"]
        start_date = sched_result["start_date"]
        equipment = sched_result["equipment"]

        # 报告摘要
        st.markdown("---")
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            st.metric("总任务数", report.get("task_count", 0))
        with col_r2:
            st.metric("更新任务", report.get("updated_count", 0))
        with col_r3:
            st.metric("总工期(天)", report.get("total_days", 0))
        with col_r4:
            imp = report.get("improvement", 0)
            st.metric("优化率", f"{imp:.1%}" if isinstance(imp, float) else imp)

        # 瓶颈提示
        bottlenecks = report.get("bottlenecks", [])
        if bottlenecks:
            st.warning("⚠️ 瓶颈设备: " + "; ".join(bottlenecks))

        # 甘特图
        st.subheader("📊 甘特图")
        if tasks:
            gantt_data = []
            base_date = datetime.strptime(start_date, "%Y-%m-%d") if isinstance(start_date, str) and start_date else datetime.today()
            for t in tasks:
                if t.id is None:
                    continue
                task_start_day = t.start_day or 0
                start_dt = base_date + timedelta(days=task_start_day)
                end_dt = base_date + timedelta(days=task_start_day + t.duration)
                gantt_data.append({
                    "任务": t.name or f"任务#{t.id}",
                    "开始日期": start_dt,
                    "结束日期": end_dt,
                    "工期(天)": t.duration,
                    "状态": t.status or "pending",
                    "设备": t.equipment_id or "—",
                })

            if gantt_data:
                df_gantt = pd.DataFrame(gantt_data)
                fig = px.timeline(
                    df_gantt,
                    x_start="开始日期",
                    x_end="结束日期",
                    y="任务",
                    color="状态",
                    hover_data=["工期(天)", "设备"],
                    title=f"测试排程 — {plan_name}",
                )
                fig.update_yaxes(autorange="reversed")
                fig.update_layout(xaxis_title="日期", height=400)
                st.plotly_chart(fig, use_container_width=True)

        # 任务详细列表
        st.subheader("排程任务明细")
        task_df = dataclass_to_df(
            tasks,
            exclude={"id", "plan_id", "sample_ids", "environment",
                     "dependencies", "log_file", "sort_order", "manual_scheduled",
                     "accept_criteria", "temperature", "humidity",
                     "actual_start_date", "actual_end_date",
                     "technician_id", "equipment_id",
                     "test_standard", "category", "notes", "priority",
                     "progress"},
            rename={
                "name": "任务名称", "duration": "工期",
                "start_day": "起始日", "status": "状态",
            },
            columns=["任务名称", "工期", "起始日", "状态"],
        )
        st.dataframe(task_df, use_container_width=True, hide_index=True)

        # 应用排程
        if st.button("✅ 应用排程到数据库", type="primary"):
            changes = []
            for t in tasks:
                orig = original.get(t.id)
                if t.id is not None and orig is not None and t.start_day != orig:
                    changes.append((t.id, t.start_day or 0))
            if changes and plan.id:
                sched_svc.apply_schedule(plan.id, changes)
                st.success(f"已更新 {len(changes)} 个任务的排程")
                if "sched_result" in st.session_state:
                    del st.session_state["sched_result"]
                st.rerun()
            else:
                st.info("没有变化需要写入")

    else:
        st.info("选择一个计划并点击「执行自动排程」")
