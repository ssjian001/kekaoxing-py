"""样品管理页面 — 样品 CRUD + 入库/出库/归还 + FA 记录。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from reliatrack._pages._shared import (
    get_services, dataclass_to_df, render_pagination, render_delete_confirm,
)
from src.constants import SAMPLE_STATUS_REVERSE


def render() -> None:
    st.title("样品管理")
    svc = get_services()
    s_svc = svc["sample"]
    p_svc = svc["project"]
    tech_svc = svc["technician"]
    issue_svc = svc["issue"]

    projects = p_svc.list_all()
    proj_map = {p.name: p.id for p in projects if p.id}
    proj_id_map = {p.id: p.name for p in projects if p.id}

    technicians = tech_svc.list_all()
    tech_map = {t.id: t.name for t in technicians if t.id}
    tech_options = list(tech_map.values())

    # ── 状态守卫 ──
    def _can_check_out(s):
        return s.status in ("in_stock", "returned")

    def _can_return(s):
        return s.status == "checked_out"

    def _can_scrap(s):
        return s.status != "scrapped"

    # ── 侧边栏：入库 ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新增样品（入库）")
        with st.form("sample_form", clear_on_submit=True):
            st.caption("标 * 为必填")
            sn = st.text_input("序列号 SN *", max_chars=100)
            batch_no = st.text_input("批次号", max_chars=200)
            spec = st.text_input("规格型号", max_chars=200)
            project_name = st.selectbox("所属项目", list(proj_map.keys()) + ["无"])
            supplier = st.text_input("供应商", max_chars=200)
            notes = st.text_area("备注", max_chars=2000)
            submitted = st.form_submit_button("入库", type="primary")
            if submitted and sn:
                pid = proj_map.get(project_name)
                s_svc.create(
                    sn=sn, batch_no=batch_no, spec=spec,
                    project_id=pid, supplier=supplier, notes=notes,
                )
                st.success(f"样品 {sn} 已入库")
                st.rerun()
            elif submitted:
                st.error("请填写必填字段")

    # ── 样品列表 ──
    samples = s_svc.list_all()

    # ── 即时搜索 ──
    def _reset_page():
        st.session_state["sample_page"] = 1

    search_term = st.text_input(
        "搜索...",
        placeholder="输入序列号/批次/规格/供应商过滤...",
        on_change=_reset_page,
        key="search_sample",
    )

    filtered_samples = samples
    if search_term:
        stxt = search_term.lower()
        filtered_samples = [
            s for s in samples
            if stxt in (s.sn or "").lower()
            or stxt in (s.batch_no or "").lower()
            or stxt in (s.spec or "").lower()
            or stxt in (s.supplier or "").lower()
        ]

    if not filtered_samples:
        st.info("暂无样品。请在左侧新建表单中入库。")
        return

    # ── 分页 ──
    PAGE_SIZE = 50
    page, total_pages = render_pagination(len(filtered_samples), PAGE_SIZE, "sample")
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_data = filtered_samples[start:end]

    # ── 表格 ──
    df = dataclass_to_df(
        page_data,
        exclude={"id", "qr_code", "test_hours"},
        rename={
            "sn": "序号", "batch_no": "批次", "spec": "规格",
            "project_id": "项目名称", "status": "状态",
            "location": "位置", "supplier": "供应商",
            "notes": "备注", "created_at": "入库时间",
        },
        columns=["序号", "批次", "规格", "项目名称", "状态", "位置",
                 "供应商", "备注", "入库时间"],
    )
    # 外键：project_id → 项目名称
    df["项目名称"] = df["项目名称"].apply(
        lambda x: proj_id_map.get(x, str(x) if x else "无")
    )
    # 状态翻译
    df["状态"] = df["状态"].apply(
        lambda x: SAMPLE_STATUS_REVERSE.get(x, x)
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── 样品操作 ──
    st.markdown("---")
    st.subheader("样品操作")

    # selectbox 只显示 SN，不暴露 ID
    sample_options = {s.sn: s for s in samples if s.id and s.sn}
    if not sample_options:
        return
    sel_label = st.selectbox("选择样品", list(sample_options.keys()), key="sample_op")
    sel = sample_options[sel_label]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 出库")
        out_tech = st.selectbox("技术员", tech_options, key="out_tech")
        purpose = st.text_input("用途", key="out_purpose")
        if st.button("出库"):
            if not _can_check_out(sel):
                st.error("当前状态不允许出库操作")
            elif not out_tech:
                st.error("请选择技术员")
            else:
                tech_id = next(k for k, v in tech_map.items() if v == out_tech)
                s_svc.add_transaction(
                    sel.id, "check_out", purpose=purpose, operator_id=tech_id,
                )
                s_svc.update_status(sel.id, "checked_out")
                st.success(f"样品 {sel.sn} 已出库")
                st.rerun()

    with col2:
        st.markdown("#### 归还")
        ret_tech = st.selectbox("技术员", tech_options, key="ret_tech")
        result = st.selectbox("归还结果", ["正常", "异常"], key="return_result")
        if st.button("归还"):
            if not _can_return(sel):
                st.error("仅已出库样品可归还")
            elif not ret_tech:
                st.error("请选择技术员")
            else:
                tech_id = next(k for k, v in tech_map.items() if v == ret_tech)
                s_svc.add_transaction(
                    sel.id, "return", notes=result, operator_id=tech_id,
                )
                s_svc.update_status(sel.id, "returned")
                st.success(f"样品 {sel.sn} 已归还")
                st.rerun()

    with col3:
        st.markdown("#### 报废")
        scrap_tech = st.selectbox("技术员", tech_options, key="scrap_tech")
        reason = st.text_input("报废原因", key="scrap_reason")
        if st.button("报废"):
            if not _can_scrap(sel):
                st.error("该样品已报废")
            elif not scrap_tech:
                st.error("请选择技术员")
            elif not reason:
                st.error("请填写报废原因")
            else:
                tech_id = next(k for k, v in tech_map.items() if v == scrap_tech)
                s_svc.update(sel.id, scrapped_reason=reason)
                s_svc.update_status(sel.id, "scrapped")
                st.success(f"样品 {sel.sn} 已报废")
                st.rerun()

    # ── FA 失效分析记录 ──
    st.markdown("---")
    st.subheader("FA 失效分析记录")
    sample_issues = [i for i in issue_svc.list_all() if i.sample_id == sel.id]
    if sample_issues:
        for iss in sample_issues:
            with st.expander(f"Issue #{iss.id}: {iss.title} ({iss.status})"):
                st.text(f"严重度: {iss.severity} | 失效模式: {iss.failure_mode}")
                st.text(f"描述: {iss.description}")
                fa_records = issue_svc.get_fa_records(iss.id)
                if fa_records:
                    fa_df = dataclass_to_df(
                        fa_records,
                        exclude={"id", "issue_id", "attachments"},
                        rename={
                            "step_no": "步骤", "step_title": "标题",
                            "method": "方法", "findings": "发现",
                            "possible_cause": "可能原因",
                            "confirmed": "确认状态",
                        },
                    )
                    st.dataframe(fa_df, use_container_width=True, hide_index=True)
    else:
        st.info("该样品暂无 FA 记录")

    # ── 出入库流水 ──
    st.markdown("---")
    st.subheader("出入库流水")
    txns = s_svc.get_transactions(sel.id)
    if txns:
        txn_df = dataclass_to_df(
            txns,
            exclude={"id", "sample_id", "related_task_id"},
            rename={
                "type": "类型", "operator_id": "操作人",
                "purpose": "用途", "notes": "备注",
                "created_at": "时间",
            },
        )
        # 外键：operator_id → 技术员姓名
        txn_df["操作人"] = txn_df["操作人"].apply(
            lambda x: tech_map.get(x, str(x) if x else "")
        )
        st.dataframe(txn_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无流水记录")
