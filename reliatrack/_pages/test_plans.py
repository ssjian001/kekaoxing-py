"""测试计划页面 — 计划 → 任务 → 结果，三级联动。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from reliatrack._pages._shared import (
    get_services, dataclass_to_df, render_pagination, render_delete_confirm,
)
from src.constants import PLAN_STATUS_OPTIONS, RESULT_OPTIONS, TASK_STATUS_LABELS


def render() -> None:
    st.title("测试计划")
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
            st.caption("标 * 为必填")
            pname = st.text_input("计划名称 *", max_chars=200)
            test_std = st.text_input("测试标准", max_chars=200)
            submitted = st.form_submit_button("创建", type="primary")
            if submitted and pname:
                plan_svc.create_plan(
                    project_id=proj_id, name=pname,
                    test_standard=test_std, status=PLAN_STATUS_OPTIONS[0][0],
                )
                st.success(f"计划「{pname}」已创建")
                st.rerun()
            elif submitted:
                st.error("请填写必填字段")

    # ── 选择计划 ──
    plans = plan_svc.get_plans_by_project(proj_id)
    if not plans:
        st.info("该项目暂无测试计划")
        return

    plan_map = {p.name: p for p in plans if p.name}
    plan_name = st.selectbox("选择测试计划", list(plan_map.keys()), key="plan_sel")
    # 重置删除确认（切换计划时）
    st.session_state.confirm_delete_plan = False
    plan = plan_map[plan_name]
    st.caption(
        f"状态: {plan.status} | 标准: {plan.test_standard} "
        f"| 日期: {plan.start_date} ~ {plan.end_date}"
    )

    # ── 计划操作 ──
    col_plan1, col_plan2 = st.columns(2)
    with col_plan1:
        st.caption("更新计划状态")
        status_opts = dict(PLAN_STATUS_OPTIONS)
        cur_label = status_opts.get(plan.status, list(status_opts.values())[0])
        new_status = st.selectbox(
            "状态", list(status_opts.values()),
            index=(
                list(status_opts.values()).index(cur_label)
                if cur_label in status_opts.values() else 0
            ),
            key="plan_status",
        )
        if st.button("更新状态"):
            rev = {v: k for k, v in status_opts.items()}
            plan_svc.update_plan(plan.id, status=rev[new_status])
            st.success("状态已更新")
            st.rerun()

    with col_plan2:
        if plan.id and render_delete_confirm(plan_name, "del_plan"):
            plan_svc.delete_plan(plan.id)
            st.success("已删除")
            st.rerun()

    st.markdown("---")

    tab_tasks, tab_matrix = st.tabs(["任务管理", "结果矩阵"])

    with tab_tasks:
        st.subheader("测试任务")
        if plan.id:
            tasks = plan_svc.get_tasks(plan.id)
        else:
            tasks = []

        # 新建任务（侧边栏）
        with st.expander("新建任务"):
            with st.form("task_form", clear_on_submit=True):
                st.caption("标 * 为必填")
                tname = st.text_input("任务名称 *", max_chars=200)
                category = st.text_input("类别", max_chars=200)
                t_std = st.text_input("测试标准", max_chars=200)
                duration = st.number_input("工期（天）", min_value=1, value=1)
                priority = st.selectbox("优先级", [1, 2, 3, 4, 5], index=2)
                temp = st.text_input("温度条件", max_chars=200)
                humidity = st.text_input("湿度条件", max_chars=200)
                criteria = st.text_area("判定准则", max_chars=2000)
                notes = st.text_area("备注", max_chars=2000)
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
                    else:
                        st.error("请填写必填字段")

        # ── 搜索过滤 ──
        search_term = st.text_input(
            "搜索...",
            placeholder="输入任务名称/标准过滤...",
            key="search_task",
        )
        if search_term:
            stxt = search_term.lower()
            tasks = [
                t for t in tasks
                if stxt in (t.name or "").lower()
                or stxt in (t.test_standard or "").lower()
            ]

        if tasks:
            # 任务表格
            task_df = dataclass_to_df(
                tasks,
                exclude={
                    "id", "plan_id", "sample_ids", "environment",
                    "dependencies", "log_file", "sort_order", "manual_scheduled",
                },
                rename={
                    "name": "任务名称", "category": "类别",
                    "test_standard": "标准", "technician_id": "技术员ID",
                    "equipment_id": "设备ID", "duration": "工期",
                    "start_day": "起始日", "progress": "进度%",
                    "status": "状态", "priority": "优先级",
                    "notes": "备注",
                },
                columns=[
                    "任务名称", "类别", "标准", "工期", "起始日",
                    "进度%", "状态", "优先级", "备注",
                ],
            )
            st.dataframe(task_df, use_container_width=True, hide_index=True)

            # ── 任务操作（选择任务后） ──
            st.markdown("---")
            task_map = {t.name or f"任务#{t.id}": t for t in tasks if t.id}
            if task_map:
                t_label = st.selectbox(
                    "选择任务操作", list(task_map.keys()), key="task_sel",
                )
                task = task_map[t_label]

                col_t1, col_t2 = st.columns(2)

                with col_t1:
                    st.markdown("#### 编辑任务")
                    new_progress = st.slider(
                        "进度 %", 0, 100, int(task.progress or 0), key="t_progress",
                    )
                    if st.button("更新进度"):
                        plan_svc.update_task_progress(task.id, float(new_progress))
                        st.success("进度已更新")
                        st.rerun()

                    if render_delete_confirm(task.name, f"del_task_{task.id}"):
                        plan_svc.delete_task(task.id)
                        st.success("已删除")
                        st.rerun()

                with col_t2:
                    st.markdown("#### 结果录入")
                    res_opts = dict(RESULT_OPTIONS)
                    res_val = st.selectbox(
                        "结果", list(res_opts.values()), key="result_val",
                    )
                    rev_res = {v: k for k, v in res_opts.items()}
                    measured = st.text_input("测量值", max_chars=200, key="measured")
                    res_notes = st.text_area("备注", max_chars=2000, key="res_notes")
                    if st.button("保存结果"):
                        plan_svc.save_result(
                            task_id=task.id, sample_id=None,
                            result=rev_res[res_val],
                            measured_value=measured,
                            notes=res_notes,
                        )
                        st.success("结果已保存")
                        st.rerun()

                # 已有结果
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

    with tab_matrix:
        if not plan.id:
            st.info("请先选择计划")
            return

        tasks = plan_svc.get_tasks(plan.id)
        task_ids = [t.id for t in tasks if t.id]
        if not task_ids:
            st.info("暂无任务数据")
            return

        all_results = plan_svc.get_all_results_by_tasks(task_ids)
        if not all_results:
            st.info("暂无测试结果数据")
            return

        # 收集样品信息
        sample_svc = svc["sample"]
        all_samples = sample_svc.list_all()
        sample_sn_map = {s.id: s.sn for s in all_samples if s.id}

        # 构建结果矩阵
        task_name_map = {t.id: t.name or f"任务#{t.id}" for t in tasks if t.id}
        task_order = [t.id for t in tasks if t.id]

        # 收集所有涉及样品的 ID
        involved_sample_ids = {r.sample_id for r in all_results if r.sample_id}

        # 构建行数据
        matrix_rows = {}
        for sid in sorted(involved_sample_ids):
            sn = sample_sn_map.get(sid, f"样品#{sid}")
            row = {}
            for tid in task_order:
                row[task_name_map[tid]] = "N/A"
            matrix_rows[sn] = row

        # 填入结果
        RESULT_LABEL_MAP = {
            "pass": "Pass", "fail": "Fail", "conditional": "Cond",
            "pending": "N/A", "skip": "Skip",
        }
        for r in all_results:
            if r.sample_id is None:
                continue
            sn = sample_sn_map.get(r.sample_id, f"样品#{r.sample_id}")
            tname = task_name_map.get(r.task_id, f"任务#{r.task_id}")
            if sn in matrix_rows and tname in matrix_rows[sn]:
                matrix_rows[sn][tname] = RESULT_LABEL_MAP.get(r.result, "N/A")

        df_matrix = pd.DataFrame.from_dict(matrix_rows, orient="index")
        df_matrix.index.name = "样品SN"

        # 通过率行
        pass_rate_row = {}
        for col in df_matrix.columns:
            pass_count = (df_matrix[col] == "Pass").sum()
            total = (df_matrix[col] != "N/A").sum()
            pass_rate_row[col] = f"{pass_count}/{total}" if total else "-"

        df_pass_rate = pd.DataFrame([pass_rate_row], index=["通过率"])
        df_display = pd.concat([df_matrix, df_pass_rate])

        # 条件着色
        def _color_cell(val: str) -> str:
            if val == "Pass":
                return (
                    "background-color: #d4edda; color: #155724; "
                    "font-weight: bold; text-align: center"
                )
            elif val == "Fail":
                return (
                    "background-color: #f8d7da; color: #721c24; "
                    "font-weight: bold; text-align: center"
                )
            elif val in ("N/A", "-"):
                return (
                    "background-color: #e2e3e5; color: #6c757d; text-align: center"
                )
            # 通过率数值行
            return "background-color: #f8f9fa; font-weight: bold; text-align: center"

        styled = df_display.style.map(_color_cell)
        st.dataframe(styled, use_container_width=True)
