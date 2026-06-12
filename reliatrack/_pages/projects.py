"""项目管理页面 — 项目 CRUD。"""

from __future__ import annotations

import streamlit as st

from reliatrack._pages._shared import get_services, dataclass_to_df, render_delete_confirm
from src.constants import PROJECT_STATUS_LABELS, PROJECT_STATUS_MAP


def render() -> None:
    st.title("项目管理")
    svc = get_services()
    p_svc = svc["project"]

    # ── 侧边栏：新建项目 ──
    with st.sidebar:
        st.subheader("新建项目")
        with st.form("project_form", clear_on_submit=True):
            st.caption("标 * 为必填")
            name = st.text_input("项目名称 *", max_chars=200)
            product = st.text_input("产品", max_chars=200)
            customer = st.text_input("客户", max_chars=200)
            description = st.text_area("描述", max_chars=2000)
            submitted = st.form_submit_button("创建", type="primary")
            if submitted and name:
                p_svc.create(
                    name=name, product=product,
                    customer=customer, description=description,
                )
                st.success(f"项目「{name}」已创建")
                st.rerun()
            elif submitted:
                st.error("请填写必填字段")

    # ── 主区域：项目列表 ──
    projects = p_svc.list_all()

    # 搜索过滤
    search_term = st.text_input(
        "搜索",
        placeholder="输入项目名称/产品/客户过滤...",
        key="search_project",
    )
    if search_term:
        stxt = search_term.lower()
        projects = [
            p
            for p in projects
            if stxt in (p.name or "").lower()
            or stxt in (p.product or "").lower()
            or stxt in (p.customer or "").lower()
        ]

    if not projects:
        st.info("暂无项目。请在侧边栏创建。")
        return

    # 数据表格
    df = dataclass_to_df(
        projects,
        exclude={"id", "description"},
        rename={
            "name": "项目名称",
            "product": "产品",
            "customer": "客户",
            "status": "状态",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        columns=["项目名称", "产品", "客户", "状态", "创建时间", "更新时间"],
    )
    if not df.empty and "状态" in df.columns:
        from src.constants import PROJECT_STATUS_REVERSE as _PSR
        df["状态"] = df["状态"].map(lambda x: _PSR.get(x, x))

    st.dataframe(
        df,
        column_config={
            "项目名称": st.column_config.TextColumn(width="medium"),
            "产品": st.column_config.TextColumn(width="medium"),
            "客户": st.column_config.TextColumn(width="medium"),
            "状态": st.column_config.TextColumn(width="small"),
            "创建时间": st.column_config.TextColumn(width="medium"),
            "更新时间": st.column_config.TextColumn(width="medium"),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("项目操作")

    # 选择项目
    proj_names = {p.name: p for p in projects if p.name}
    selected_name = st.selectbox("选择项目", list(proj_names.keys()))
    p = proj_names[selected_name]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("编辑")
        new_name = st.text_input("名称", value=p.name, max_chars=200, key="edit_name")
        new_product = st.text_input("产品", value=p.product, max_chars=200, key="edit_product")
        new_customer = st.text_input("客户", value=p.customer, max_chars=200, key="edit_customer")
        new_desc = st.text_area("描述", value=p.description, max_chars=2000, key="edit_desc")
        if st.button("保存修改", type="primary"):
            upd = {}
            if new_name != p.name:
                upd["name"] = new_name
            if new_product != p.product:
                upd["product"] = new_product
            if new_customer != p.customer:
                upd["customer"] = new_customer
            if new_desc != p.description:
                upd["description"] = new_desc
            if upd and p.id:
                p_svc.update(p.id, **upd)
                st.success("已更新")
                st.rerun()
            if not upd:
                st.info("没有需要保存的修改")

    with col2:
        st.subheader("状态切换")
        status_labels = list(PROJECT_STATUS_MAP.keys())  # ["进行中", "暂停", ...]
        current_label = PROJECT_STATUS_LABELS.get(p.status, "进行中")
        current_index = (
            status_labels.index(current_label)
            if current_label in status_labels
            else 0
        )
        new_status_label = st.selectbox(
            "状态",
            status_labels,
            index=current_index,
            key="status_sel",
        )
        if st.button("更新状态"):
            new_status_val = PROJECT_STATUS_MAP[new_status_label]
            if p.id:
                p_svc.update(p.id, status=new_status_val)
                st.rerun()

        st.subheader("危险操作")
        if p.id:
            stats = p_svc.cascade_stats(p.id)
            total = sum(stats.values())
            if total > 0:
                st.warning(
                    f"将删除 {stats['plans']} 个计划、{stats['tasks']} 个任务、"
                    f"{stats['samples']} 个样品、{stats['issues']} 个 Issue。"
                    f"共计 {total} 条记录。"
                )
            if render_delete_confirm(
                "此项目及其所有测试计划、样品、Issue",
                f"del_proj_{p.id}",
            ):
                p_svc.delete(p.id)
                st.success("已删除")
                st.rerun()
