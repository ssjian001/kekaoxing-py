"""⚠️ Issue 页面 — Issue 列表 + 筛选 + CAPA 跟踪。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import get_services, dataclass_to_df
from src.constants import (
    ISSUE_STATUS_LABELS, SEVERITY_OPTIONS, PRIORITY_LABELS,
    ISSUE_CATEGORY_OPTIONS,
)


def show() -> None:
    st.title("⚠️ Issue 管理")
    svc = get_services()
    issue_svc = svc["issue"]
    p_svc = svc["project"]

    # ── 侧边栏：新建 Issue ──
    projects = p_svc.list_all()
    proj_map = {p.name: p.id for p in projects if p.id}

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新建 Issue")
        with st.form("issue_form", clear_on_submit=True):
            title = st.text_input("标题 *", max_chars=200)
            proj_name = st.selectbox("项目", list(proj_map.keys()) + ["无"], key="iss_proj")
            severity_opts = dict(SEVERITY_OPTIONS)
            severity = st.selectbox("严重度", list(severity_opts.keys()), index=1)
            cat_opts = dict(ISSUE_CATEGORY_OPTIONS)
            category = st.selectbox("责任类别", list(cat_opts.keys()), index=0)
            failure_mode = st.text_input("失效模式", max_chars=200)
            description = st.text_area("描述", max_chars=2000)
            if st.form_submit_button("创建", type="primary"):
                if not title:
                    st.error("请填写必填字段")
                else:
                    pid = proj_map.get(proj_name)
                    issue_svc.create(
                        title=title, project_id=pid,
                        severity=severity_opts[severity],
                        category=cat_opts[category],
                        failure_mode=failure_mode,
                        description=description,
                    )
                    st.success(f"Issue「{title}」已创建")
                    st.rerun()

    # ── 筛选 ──
    all_issues = issue_svc.list_all()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        status_filter = st.multiselect(
            "状态筛选",
            list(ISSUE_STATUS_LABELS.values()),
            default=[],
            key="iss_status_filter",
        )
    with col_f2:
        severity_filter = st.multiselect(
            "严重度筛选",
            list(dict(SEVERITY_OPTIONS).keys()),
            default=[],
            key="iss_sev_filter",
        )

    # 应用筛选
    status_rev = {v: k for k, v in ISSUE_STATUS_LABELS.items()}
    sev_map = dict(SEVERITY_OPTIONS)  # {"严重":"critical", "主要":"major", ...}
    filtered = all_issues
    if status_filter:
        filter_statuses = {status_rev[s] for s in status_filter if s in status_rev}
        filtered = [i for i in filtered if i.status in filter_statuses]
    if severity_filter:
        filter_sevs = {sev_map[s] for s in severity_filter if s in sev_map}
        filtered = [i for i in filtered if i.severity in filter_sevs]

    # ── 关键词搜索 ──
    search_term = st.text_input(
        "🔍 搜索...",
        placeholder="输入标题/失效模式过滤...",
        key="search_issue",
    )
    if search_term:
        stxt = search_term.lower()
        filtered = [
            i
            for i in filtered
            if stxt in (i.title or "").lower()
            or stxt in (i.failure_mode or "").lower()
        ]

    # ── 显示表格 ──
    PAGE_SIZE = 50
    if "page_issues" not in st.session_state:
        st.session_state["page_issues"] = 1

    if filtered:
        total = len(filtered)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = st.session_state["page_issues"]
        if page > total_pages:
            st.session_state["page_issues"] = total_pages
            page = total_pages
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_data = filtered[start:end]

        df = dataclass_to_df(
            page_data,
            exclude={"id", "plan_id", "task_id", "sample_id",
                     "failure_stage", "root_cause", "improvement_measures",
                     "reporter_name", "failure_code", "occurrence_count",
                     "is_deleted", "deleted_at", "resolution"},
            rename={
                "title": "标题", "project_id": "项目ID",
                "failure_mode": "失效模式",
                "description": "描述", "severity": "严重度",
                "status": "状态", "priority": "优先级",
                "assignee_id": "负责人ID", "category": "类别",
                "dri_name": "DRI", "created_at": "创建时间",
            },
            columns=["标题", "项目ID", "严重度", "状态", "优先级",
                     "类别", "DRI", "失效模式", "创建时间"],
        )
        display_df = df.copy()
        display_df.insert(0, "选择", False)

        # ── 批量操作栏 ──
        prev_edited = st.session_state.get("iss_table")
        selected_ids = []
        if prev_edited is not None and "选择" in prev_edited.columns:
            selected_mask = prev_edited["选择"].tolist()
            selected_indices = [i for i, sel in enumerate(selected_mask) if sel]
            selected_ids = [page_data[i].id for i in selected_indices if page_data[i].id]

        status_opts = {v: k for k, v in ISSUE_STATUS_LABELS.items()}
        col_b1, col_b2, col_b3, col_b4 = st.columns([1, 2, 2, 2])
        with col_b1:
            select_all = st.checkbox("全选", key="iss_select_all")
            if select_all:
                for i in range(len(display_df)):
                    st.session_state[f"iss_table_editor_sel_{i}"] = True
        with col_b2:
            batch_status = st.selectbox(
                "批量更新状态", list(status_opts.keys()),
                key="iss_batch_status",
                disabled=not selected_ids,
            )
        with col_b3:
            batch_assign = st.selectbox(
                "批量分配", ["未分配"],
                key="iss_batch_assign",
                disabled=not selected_ids,
            )
        with col_b4:
            if st.button("执行批量操作", disabled=not selected_ids):
                for iid in selected_ids:
                    if batch_status:
                        issue_svc.update_status(iid, status_opts[batch_status])
                st.success(f"已更新 {len(selected_ids)} 个 Issue")
                st.rerun()

        edited = st.data_editor(
            display_df,
            column_config={"选择": st.column_config.CheckboxColumn("选择")},
            use_container_width=True,
            hide_index=True,
            disabled=[c for c in display_df.columns if c != "选择"],
            key="iss_table",
        )

        if total_pages > 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("◀ 上一页", disabled=page <= 1):
                    st.session_state["page_issues"] -= 1
                    st.rerun()
            with col2:
                st.write(f"第 {page}/{total_pages} 页（共 {total} 条）")
            with col3:
                if st.button("下一页 ▶", disabled=page >= total_pages):
                    st.session_state["page_issues"] += 1
                    st.rerun()
    else:
        st.info("暂无 Issue 数据")

    if not filtered:
        return

    st.markdown("---")
    st.subheader("Issue 操作")

    issue_map = {f"{i.title} (ID:{i.id})": i for i in filtered if i.id}
    if not issue_map:
        return
    sel_label = st.selectbox("选择 Issue", list(issue_map.keys()), key="iss_sel")
    iss = issue_map[sel_label]

    # ── Issue 状态更新 ──
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.markdown("#### 更新状态")
        status_opts = {v: k for k, v in ISSUE_STATUS_LABELS.items()}
        current_label = status_opts.get(iss.status, iss.status)
        new_status_label = st.selectbox(
            "新状态", list(status_opts.keys()),
            index=list(status_opts.keys()).index(current_label)
            if current_label in status_opts else 0,
            key="iss_new_status",
        )
        if st.button("更新状态"):
            issue_svc.update_status(iss.id, status_opts[new_status_label])
            st.success(f"状态已更新为 {new_status_label}")
            st.rerun()

    with col_i2:
        st.markdown("#### 编辑")
        new_title = st.text_input("标题", value=iss.title, max_chars=200, key="iss_edit_title")
        new_desc = st.text_area("描述", value=iss.description, max_chars=2000, key="iss_edit_desc")
        if st.button("保存修改"):
            issue_svc.update(iss.id, title=new_title, description=new_desc)
            st.success("已更新")
            st.rerun()

    # ── FA 分析记录 ──
    st.markdown("---")
    st.subheader("🔬 FA 分析记录")
    fa_records = issue_svc.get_fa_records(iss.id)
    if fa_records:
        fa_df = dataclass_to_df(
            fa_records,
            exclude={"id", "issue_id", "attachments", "analyst_id"},
            rename={
                "step_no": "步骤", "step_title": "标题",
                "description": "描述", "method": "方法",
                "findings": "发现", "possible_cause": "可能原因",
                "cause_category": "原因分类", "failure_mechanism": "失效机理",
                "confirmed": "已确认", "created_at": "创建时间",
            },
        )
        st.dataframe(fa_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 FA 记录")

    # 新增 FA 步骤
    with st.expander("➕ 新增 FA 步骤"):
        with st.form("fa_form", clear_on_submit=True):
            step_title = st.text_input("步骤标题 *", max_chars=200)
            fa_method = st.selectbox("分析方法",
                                     ["外观检查", "切片分析", "CT扫描",
                                      "SEM", "EDS", "XRF", "热分析",
                                      "电性能测试", "其他"])
            findings = st.text_area("发现", max_chars=2000)
            possible_cause = st.text_area("可能原因", max_chars=2000)
            cause_cat = st.selectbox("原因分类",
                                     ["", "人", "机", "料", "法", "环", "测"])
            if st.form_submit_button("添加 FA 步骤"):
                if not step_title:
                    st.error("请填写必填字段")
                else:
                    issue_svc.add_fa_record(
                        iss.id, step_title=step_title, method=fa_method,
                        findings=findings, possible_cause=possible_cause,
                        cause_category=cause_cat,
                    )
                    st.success("FA 步骤已添加")
                    st.rerun()

    # ── CAPA 跟踪 ──
    st.markdown("---")
    st.subheader("📋 CAPA 跟踪")
    capa_records = issue_svc.get_capa_records(iss.id)
    if capa_records:
        capa_df = dataclass_to_df(
            capa_records,
            exclude={"id", "issue_id", "assignee_id", "verified_by"},
            rename={
                "action": "措施", "assignee_name": "负责人",
                "due_date": "截止日期", "status": "状态",
                "verification_result": "验证结果",
                "verifier_name": "验证人", "created_at": "创建时间",
            },
        )
        st.dataframe(capa_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 CAPA 记录")

    with st.expander("➕ 新增 CAPA 措施"):
        with st.form("capa_form", clear_on_submit=True):
            action = st.text_area("措施描述 *", max_chars=2000)
            assignee_name = st.text_input("责任人", max_chars=200)
            due_date = st.text_input("截止日期 (YYYY-MM-DD)", max_chars=30,
                                     placeholder="如: 2026-12-31")
            if st.form_submit_button("添加 CAPA"):
                if not action:
                    st.error("请填写必填字段")
                else:
                    issue_svc.add_capa_record(
                        iss.id, action=action,
                        assignee_name=assignee_name, due_date=due_date,
                    )
                    st.success("CAPA 措施已添加")
                    st.rerun()

    # ── 删除 Issue ──
    st.markdown("---")
    if st.button("🗑️ 软删除此 Issue", type="secondary"):
        issue_svc.soft_delete(iss.id)
        st.success("已软删除")
        st.rerun()
