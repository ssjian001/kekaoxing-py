"""📁 项目管理页面 — 项目 CRUD。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import get_services, dataclass_to_df
from src.constants import PROJECT_STATUS_REVERSE


def show() -> None:
    st.title("📁 项目管理")
    svc = get_services()
    p_svc = svc["project"]

    # ── 侧边栏：新增/编辑 ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新建项目")
        with st.form("project_form", clear_on_submit=True):
            name = st.text_input("项目名称 *")
            product = st.text_input("产品")
            customer = st.text_input("客户")
            description = st.text_area("描述")
            submitted = st.form_submit_button("创建", type="primary")
            if submitted and name:
                p_svc.create(name=name, product=product,
                             customer=customer, description=description)
                st.success(f"项目「{name}」已创建")
                st.rerun()

    # ── 主区域：项目列表 ──
    projects = p_svc.list_all()

    df = dataclass_to_df(
        projects,
        exclude={"id", "description"},
        rename={
            "name": "项目名称", "product": "产品", "customer": "客户",
            "status": "状态", "created_at": "创建时间", "updated_at": "更新时间",
        },
        columns=["项目名称", "产品", "客户", "状态", "创建时间", "更新时间"],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("项目操作")

    if not projects:
        st.info("暂无项目")
        return

    # 选择项目进行操作
    proj_names = {p.name: p for p in projects if p.name}
    selected_name = st.selectbox("选择项目", list(proj_names.keys()))
    proj = proj_names[selected_name]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 编辑")
        new_name = st.text_input("名称", value=proj.name, key="edit_name")
        new_product = st.text_input("产品", value=proj.product, key="edit_product")
        new_customer = st.text_input("客户", value=proj.customer, key="edit_customer")
        new_desc = st.text_area("描述", value=proj.description, key="edit_desc")
        if st.button("保存修改", type="primary"):
            upd = {}
            if new_name != proj.name:
                upd["name"] = new_name
            if new_product != proj.product:
                upd["product"] = new_product
            if new_customer != proj.customer:
                upd["customer"] = new_customer
            if new_desc != proj.description:
                upd["description"] = new_desc
            if upd and proj.id:
                p_svc.update(proj.id, **upd)
                st.success("已更新")
                st.rerun()

    with col2:
        st.markdown("#### 状态切换")
        status_opts = {v: k for k, v in PROJECT_STATUS_REVERSE.items()}
        current_label = status_opts.get(proj.status, proj.status)
        new_status_label = st.selectbox(
            "状态", list(status_opts.keys()),
            index=list(status_opts.keys()).index(current_label)
            if current_label in status_opts else 0,
            key="status_sel",
        )
        if st.button("更新状态"):
            new_status_val = status_opts[new_status_label]
            if proj.id:
                p_svc.update(proj.id, status=new_status_val)
                st.success(f"状态已更新为 {new_status_label}")
                st.rerun()

        st.markdown("#### 危险操作")
        if st.button("删除项目", type="secondary", use_container_width=True):
            if proj.id:
                stats = p_svc.cascade_stats(proj.id)
                total = sum(stats.values())
                if total > 0:
                    st.warning(
                        f"将删除 {stats['plans']} 个计划、{stats['tasks']} 个任务、"
                        f"{stats['samples']} 个样品、{stats['issues']} 个 Issue。"
                        f"共计 {total} 条记录。"
                    )
                confirm = st.checkbox("确认删除？")
                if confirm:
                    p_svc.delete(proj.id)
                    st.success("已删除")
                    st.rerun()
