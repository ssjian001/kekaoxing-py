"""Issue 页面 — Issue 列表、筛选、批量操作、FA 分析、CAPA 跟踪。"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import (
    get_services,
    dataclass_to_df,
    render_pagination,
    render_delete_confirm,
)
from src.constants import (
    ISSUE_STATUS_LABELS,
    SEVERITY_OPTIONS,
    ISSUE_CATEGORY_OPTIONS,
    SEVERITY_LABELS,
)


def render() -> None:
    st.title("Issue 管理")
    svc = get_services()
    issue_svc = svc["issue"]
    p_svc = svc["project"]
    tech_svc = svc["technician"]

    # ── 侧边栏：新建 Issue ──
    projects = p_svc.list_all()
    proj_map = {p.name: p.id for p in projects if p.id}

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新建 Issue")
        with st.form("issue_form", clear_on_submit=True):
            st.caption("标 * 为必填")
            title = st.text_input("标题 *", max_chars=200)
            proj_name = st.selectbox("项目", list(proj_map.keys()) + ["无"], key="iss_proj")
            severity = st.selectbox(
                "严重度",
                [k for k, _ in SEVERITY_OPTIONS],
                index=1,
            )
            category = st.selectbox(
                "责任类别",
                [k for k, _ in ISSUE_CATEGORY_OPTIONS],
                index=0,
            )
            failure_mode = st.text_input("失效模式", max_chars=200)
            description = st.text_area("描述", max_chars=2000)
            if st.form_submit_button("创建", type="primary"):
                if not title:
                    st.error("请填写必填字段")
                else:
                    sev_map = dict(SEVERITY_OPTIONS)
                    cat_map = dict(ISSUE_CATEGORY_OPTIONS)
                    pid = proj_map.get(proj_name)
                    issue_svc.create(
                        title=title,
                        project_id=pid,
                        severity=sev_map[severity],
                        category=cat_map[category],
                        failure_mode=failure_mode,
                        description=description,
                    )
                    st.success(f"Issue「{title}」已创建")
                    st.rerun()

    # ── 获取数据 ──
    all_issues = issue_svc.list_all()
    technicians = tech_svc.list_all()
    tech_map = {t.name: t.id for t in technicians if t.id}

    # ── 统一文本搜索 ──
    search_term = st.text_input(
        "搜索",
        placeholder="输入标题/失效模式过滤...",
        key="search_issue",
    )
    filtered = all_issues
    if search_term:
        stxt = search_term.lower()
        filtered = [
            i
            for i in filtered
            if stxt in (i.title or "").lower()
            or stxt in (i.failure_mode or "").lower()
        ]

    # ── 分页 ──
    PAGE_SIZE = 50
    total = len(filtered)

    if not filtered:
        st.info("暂无 Issue。请在左侧表单中创建。")
        return

    page, total_pages = render_pagination(total, PAGE_SIZE, "issues")
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_data = filtered[start:end]

    # ── 构建显示 DataFrame ──
    df = dataclass_to_df(
        page_data,
        exclude={
            "id", "plan_id", "task_id", "sample_id",
            "failure_stage", "root_cause", "improvement_measures",
            "reporter_name", "failure_code", "occurrence_count",
            "is_deleted", "deleted_at", "resolution",
        },
        rename={
            "title": "标题",
            "project_id": "项目ID",
            "failure_mode": "失效模式",
            "description": "描述",
            "severity": "严重度",
            "status": "状态",
            "priority": "优先级",
            "assignee_id": "负责人ID",
            "category": "类别",
            "dri_name": "DRI",
            "created_at": "创建时间",
        },
        columns=[
            "标题", "项目ID", "严重度", "状态", "优先级",
            "类别", "DRI", "失效模式", "创建时间",
        ],
    )
    display_df = df.copy()
    display_df.insert(0, "选择", False)

    # ── 获取当前页 Issue 的全局 ID 列表 ──
    page_ids = [i.id for i in page_data if i.id]
    # 从 session_state 恢复已选 ID（用全局 ID 而非页面偏移）
    selected_global_ids: set[int] = set(
        st.session_state.get("iss_selected_ids", [])
    )
    # 仅保留当前页存在的 ID
    selected_global_ids = {sid for sid in selected_global_ids if sid in page_ids}
    # 设置 data_editor 的选择状态
    for idx, iid in enumerate(page_ids):
        if idx < len(display_df):
            display_df.at[idx, "选择"] = iid in selected_global_ids

    # ── 批量操作栏 ──
    status_opts = {v: k for k, v in ISSUE_STATUS_LABELS.items()}
    col_b1, col_b2, col_b3 = st.columns([1, 2, 2])
    with col_b1:
        select_all = st.checkbox("全选", key="iss_select_all")
        if select_all:
            display_df["选择"] = True
    with col_b2:
        batch_status = st.selectbox(
            "批量更新状态",
            list(status_opts.keys()),
            key="iss_batch_status",
        )
    with col_b3:
        tech_names = list(tech_map.keys())
        batch_assign = st.selectbox(
            "批量分配技术员",
            ["未分配"] + tech_names,
            key="iss_batch_assign",
        )

    # ── data_editor ──
    edited = st.data_editor(
        display_df,
        column_config={
            "选择": st.column_config.CheckboxColumn("选择"),
        },
        use_container_width=True,
        hide_index=True,
        disabled=[c for c in display_df.columns if c != "选择"],
        key="iss_table",
    )

    # 读取选择状态
    if edited is not None and "选择" in edited.columns:
        selected_global_ids = {
            page_ids[idx]
            for idx in range(len(page_ids))
            if idx < len(edited) and edited.iloc[idx]["选择"]
        }
        st.session_state["iss_selected_ids"] = list(selected_global_ids)

    # 执行批量操作
    if st.button("执行批量操作", disabled=not selected_global_ids):
        for iid in selected_global_ids:
            if batch_status and batch_status != "未分配":
                issue_svc.update(iid, status=status_opts[batch_status])
            if batch_assign != "未分配" and batch_assign in tech_map:
                issue_svc.update(iid, assignee_id=tech_map[batch_assign])
        st.success(f"已更新 {len(selected_global_ids)} 个 Issue")
        st.session_state.pop("iss_selected_ids", None)
        st.rerun()

    # ── Issue 操作区 ──
    st.markdown("---")
    st.subheader("Issue 操作")

    issue_map = {f"{i.title} (ID:{i.id})": i for i in filtered if i.id}
    if not issue_map:
        return
    sel_label = st.selectbox("选择 Issue", list(issue_map.keys()), key="iss_sel")
    iss = issue_map[sel_label]

    # ── Issue 状态更新 + 编辑（2 列） ──
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.markdown("#### 更新状态")
        current_label = ISSUE_STATUS_LABELS.get(iss.status, "待处理")
        status_rev = {v: k for k, v in ISSUE_STATUS_LABELS.items()}
        new_status_label = st.selectbox(
            "新状态",
            list(ISSUE_STATUS_LABELS.values()),
            index=(
                list(ISSUE_STATUS_LABELS.values()).index(current_label)
                if current_label in ISSUE_STATUS_LABELS.values()
                else 0
            ),
            key="iss_new_status",
        )
        if st.button("更新状态"):
            issue_svc.update(iss.id, status=status_rev[new_status_label])
            st.rerun()

    with col_i2:
        st.markdown("#### 编辑")
        new_title = st.text_input("标题", value=iss.title, max_chars=200, key="iss_edit_title")
        new_desc = st.text_area("描述", value=iss.description, max_chars=2000, key="iss_edit_desc")
        if st.button("保存修改"):
            issue_svc.update(iss.id, title=new_title, description=new_desc)
            st.success("已更新")
            st.rerun()

    # ── 删除 Issue ──
    if render_delete_confirm(f"Issue {iss.title}", "iss_del"):
        issue_svc.soft_delete(iss.id)
        st.success("已软删除")
        st.rerun()

    # ── FA 分析记录 ──
    st.markdown("---")
    st.subheader("FA 分析记录")
    fa_records = issue_svc.get_fa_records(iss.id)
    if fa_records:
        fa_df = dataclass_to_df(
            fa_records,
            exclude={"id", "issue_id", "attachments", "analyst_id"},
            rename={
                "step_no": "步骤",
                "step_title": "标题",
                "description": "描述",
                "method": "方法",
                "findings": "发现",
                "possible_cause": "可能原因",
                "cause_category": "原因分类",
                "failure_mechanism": "失效机理",
                "confirmed": "已确认",
                "created_at": "创建时间",
            },
        )
        st.dataframe(fa_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 FA 记录")

    # 新增 FA 步骤
    with st.expander("新增 FA 步骤"):
        with st.form("fa_form", clear_on_submit=True):
            st.caption("标 * 为必填")
            step_title = st.text_input("步骤标题 *", max_chars=200)
            fa_method = st.selectbox(
                "分析方法",
                [
                    "外观检查", "切片分析", "CT扫描",
                    "SEM", "EDS", "XRF", "热分析",
                    "电性能测试", "其他",
                ],
            )
            findings = st.text_area("发现", max_chars=2000)
            possible_cause = st.text_area("可能原因", max_chars=2000)
            cause_cat = st.selectbox(
                "原因分类",
                ["", "人", "机", "料", "法", "环", "测"],
            )
            if st.form_submit_button("添加 FA 步骤"):
                if not step_title:
                    st.error("请填写必填字段")
                else:
                    issue_svc.add_fa_record(
                        iss.id,
                        step_title=step_title,
                        method=fa_method,
                        findings=findings,
                        possible_cause=possible_cause,
                        cause_category=cause_cat,
                    )
                    st.success("FA 步骤已添加")
                    st.rerun()

    # ── CAPA 跟踪 ──
    st.markdown("---")
    st.subheader("CAPA 跟踪")
    capa_records = issue_svc.get_capa_records(iss.id)
    if capa_records:
        capa_df = dataclass_to_df(
            capa_records,
            exclude={"id", "issue_id", "assignee_id", "verified_by"},
            rename={
                "action": "措施",
                "assignee_name": "负责人",
                "due_date": "截止日期",
                "status": "状态",
                "verification_result": "验证结果",
                "verifier_name": "验证人",
                "created_at": "创建时间",
            },
        )
        st.dataframe(capa_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 CAPA 记录")

    with st.expander("新增 CAPA 措施"):
        with st.form("capa_form", clear_on_submit=True):
            st.caption("标 * 为必填")
            action = st.text_area("措施描述 *", max_chars=2000)
            assignee_name = st.text_input("责任人", max_chars=200)
            due_date = st.text_input(
                "截止日期 (YYYY-MM-DD)",
                max_chars=30,
                placeholder="如: 2026-12-31",
            )
            if st.form_submit_button("添加 CAPA"):
                if not action:
                    st.error("请填写必填字段")
                else:
                    issue_svc.add_capa_record(
                        iss.id,
                        action=action,
                        assignee_name=assignee_name,
                        due_date=due_date,
                    )
                    st.success("CAPA 措施已添加")
                    st.rerun()
