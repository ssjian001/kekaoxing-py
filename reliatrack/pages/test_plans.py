"""📋 测试计划页面 — 计划 → 任务 → 结果，三级联动。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import get_services, dataclass_to_df
from src.constants import PLAN_STATUS_OPTIONS, RESULT_OPTIONS, TASK_STATUS_LABELS


def show() -> None:
    st.title("📋 测试计划")
    svc = get_services()
    plan_svc = svc["plan"]
    p_svc = svc["project"]

    projects = p_svc.list_all()
    proj_map = {p.name: p.id for p in projects if p.id}
    if not proj_map:
        st.info("请先在「项目管理」中创建项目")
        return

    # ── 选择项目 ──
    proj_name = st.selectbox("选择项目", list(proj_map.keys()), key="plan_proj")
    proj_id = proj_map[proj_name]

    # ── 侧边栏：新建计划 ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新建测试计划")
        with st.form("plan_form", clear_on_submit=True):
            pname = st.text_input("计划名称 *")
            test_std = st.text_input("测试标准")
            status_idx = 0
            status_val = PLAN_STATUS_OPTIONS[status_idx][0]
            submitted = st.form_submit_button("创建", type="primary")
            if submitted and pname:
                plan_svc.create_plan(
                    project_id=proj_id, name=pname,
                    test_standard=test_std, status=status_val,
                )
                st.success(f"计划「{pname}」已创建")
                st.rerun()

    # ── 选择计划 ──
    plans = plan_svc.get_plans_by_project(proj_id)
    if not plans:
        st.info("该项目暂无测试计划")
        return

    plan_map = {p.name: p for p in plans if p.name}
    plan_name = st.selectbox("选择测试计划", list(plan_map.keys()), key="plan_sel")
    plan = plan_map[plan_name]
    st.caption(f"状态: {plan.status} | 标准: {plan.test_standard} | 日期: {plan.start_date} ~ {plan.end_date}")

    # ── 计划操作 ──
    col_plan1, col_plan2, col_plan3 = st.columns(3)
    with col_plan1:
        new_status_idx = 0
        st.caption("更新计划状态")
        status_opts = dict(PLAN_STATUS_OPTIONS)
        new_status = st.selectbox("状态", list(status_opts.values()),
                                  key="plan_status")
        if st.button("更新状态"):
            rev = {v: k for k, v in status_opts.items()}
            plan_svc.update_plan(plan.id, status=rev[new_status])
            st.success("状态已更新")
            st.rerun()

    with col_plan2:
        if st.button("删除计划", type="secondary"):
            if plan.id:
                plan_svc.delete_plan(plan.id)
                st.success("已删除")
                st.rerun()

    st.markdown("---")

    # ── 任务列表 ──
    st.subheader("测试任务")
    if plan.id:
        tasks = plan_svc.get_tasks(plan.id)
    else:
        tasks = []

    # 新建任务
    with st.expander("➕ 新建任务"):
        with st.form("task_form", clear_on_submit=True):
            tname = st.text_input("任务名称 *")
            category = st.text_input("类别")
            t_std = st.text_input("测试标准")
            duration = st.number_input("工期（天）", min_value=1, value=1)
            priority = st.selectbox("优先级", [1, 2, 3, 4, 5], index=2)
            temp = st.text_input("温度条件")
            humidity = st.text_input("湿度条件")
            criteria = st.text_area("判定准则")
            notes = st.text_area("备注")
            if st.form_submit_button("创建任务"):
                if tname and plan.id:
                    plan_svc.create_task(
                        plan.id, name=tname, category=category,
                        test_standard=t_std, duration=duration,
                        priority=priority, temperature=temp,
                        humidity=humidity, accept_criteria=criteria,
                        notes=notes,
                    )
                    st.success(f"任务「{tname}」已创建")
                    st.rerun()

    if tasks:
        # 显示任务表格
        task_df = dataclass_to_df(
            tasks,
            exclude={"id", "plan_id", "sample_ids", "environment",
                     "dependencies", "log_file", "sort_order", "manual_scheduled"},
            rename={
                "name": "任务名称", "category": "类别",
                "test_standard": "标准", "technician_id": "技术员ID",
                "equipment_id": "设备ID", "duration": "工期",
                "start_day": "起始日", "progress": "进度%",
                "status": "状态", "priority": "优先级",
                "notes": "备注",
            },
            columns=["任务名称", "类别", "标准", "工期", "起始日",
                     "进度%", "状态", "优先级", "备注"],
        )
        st.dataframe(task_df, use_container_width=True, hide_index=True)

        # ── 任务操作（选择任务后） ──
        st.markdown("---")
        task_map = {f"{t.name} (ID:{t.id})": t for t in tasks if t.id}
        if task_map:
            t_label = st.selectbox("选择任务操作", list(task_map.keys()), key="task_sel")
            task = task_map[t_label]

            col_t1, col_t2 = st.columns(2)

            with col_t1:
                st.markdown("#### 编辑任务")
                new_progress = st.slider("进度 %", 0, 100, int(task.progress or 0), key="t_progress")
                if st.button("更新进度"):
                    plan_svc.update_task_progress(task.id, float(new_progress))
                    st.success("进度已更新")
                    st.rerun()

                if st.button("删除任务", type="secondary"):
                    plan_svc.delete_task(task.id)
                    st.success("已删除")
                    st.rerun()

            # ── 结果录入 ──
            with col_t2:
                st.markdown("#### 结果录入")
                res_opts = dict(RESULT_OPTIONS)
                res_val = st.selectbox("结果", list(res_opts.values()), key="result_val")
                rev_res = {v: k for k, v in res_opts.items()}
                measured = st.text_input("测量值", key="measured")
                res_notes = st.text_area("备注", key="res_notes")
                if st.button("保存结果"):
                    plan_svc.save_result(
                        task_id=task.id, sample_id=None,
                        result=rev_res[res_val],
                        measured_value=measured,
                        notes=res_notes,
                    )
                    st.success("结果已保存")
                    st.rerun()

            # 显示已有结果
            results = plan_svc.get_task_results(task.id)
            if results:
                st.markdown("#### 已有结果")
                res_df = dataclass_to_df(
                    results,
                    exclude={"id", "task_id", "attachments", "environment"},
                    rename={
                        "sample_id": "样品ID", "result": "结果",
                        "test_date": "测试日期", "tester_id": "测试人ID",
                        "measured_value": "测量值", "notes": "备注",
                    },
                )
                st.dataframe(res_df, use_container_width=True, hide_index=True)

    else:
        st.info("该计划暂无任务")
