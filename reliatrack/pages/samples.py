"""🔬 样品管理页面 — 样品 CRUD + 入库/出库/归还 + FA 记录。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import get_services, dataclass_to_df
from src.constants import SAMPLE_STATUS_REVERSE, SAMPLE_STATUS_LABELS


def show() -> None:
    st.title("🔬 样品管理")
    svc = get_services()
    s_svc = svc["sample"]
    p_svc = svc["project"]
    issue_svc = svc["issue"]

    projects = p_svc.list_all()
    proj_map = {p.name: p.id for p in projects if p.id}

    # ── 侧边栏：入库 ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新增样品（入库）")
        with st.form("sample_form", clear_on_submit=True):
            sn = st.text_input("序列号 SN *")
            batch_no = st.text_input("批次号")
            spec = st.text_input("规格型号")
            project_name = st.selectbox("所属项目", list(proj_map.keys()) + ["无"])
            supplier = st.text_input("供应商")
            notes = st.text_area("备注")
            submitted = st.form_submit_button("入库", type="primary")
            if submitted and sn:
                pid = proj_map.get(project_name)
                s_svc.create(
                    sn=sn, batch_no=batch_no, spec=spec,
                    project_id=pid, supplier=supplier, notes=notes,
                )
                st.success(f"样品 {sn} 已入库")
                st.rerun()

    # ── 样品列表 ──
    samples = s_svc.list_all()
    df = dataclass_to_df(
        samples,
        exclude={"id", "qr_code", "test_hours"},
        rename={
            "sn": "序号", "batch_no": "批次", "spec": "规格",
            "project_id": "项目ID", "status": "状态",
            "location": "位置", "supplier": "供应商",
            "notes": "备注", "created_at": "入库时间",
        },
        columns=["序号", "批次", "规格", "项目ID", "状态", "位置",
                 "供应商", "备注", "入库时间"],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not samples:
        st.info("暂无样品")
        return

    st.markdown("---")
    st.subheader("样品操作")

    sample_ids = {f"{s.sn} (ID:{s.id})": s for s in samples if s.id}
    sel_label = st.selectbox("选择样品", list(sample_ids.keys()))
    sel = sample_ids[sel_label]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 出库")
        purpose = st.text_input("用途", key="out_purpose")
        if st.button("出库"):
            s_svc.add_transaction(sel.id, "check_out", purpose=purpose)
            s_svc.update_status(sel.id, "checked_out")
            st.success(f"样品 {sel.sn} 已出库")
            st.rerun()

    with col2:
        st.markdown("#### 归还")
        result = st.selectbox("归还结果", ["正常", "异常"], key="return_result")
        if st.button("归还"):
            s_svc.add_transaction(sel.id, "return", notes=result)
            s_svc.update_status(sel.id, "returned")
            st.success(f"样品 {sel.sn} 已归还")
            st.rerun()

    with col3:
        st.markdown("#### 报废")
        reason = st.text_input("报废原因", key="scrap_reason")
        if st.button("报废"):
            s_svc.update(sel.id, scrapped_reason=reason)
            s_svc.update_status(sel.id, "scrapped")
            st.success(f"样品 {sel.sn} 已报废")
            st.rerun()

    # ── FA 记录 ──
    st.markdown("---")
    st.subheader("FA 失效分析记录")
    # 找到该样品的 Issue
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

    # 出入库流水
    st.markdown("---")
    st.subheader("出入库流水")
    txns = s_svc.get_transactions(sel.id)
    if txns:
        txn_df = dataclass_to_df(
            txns,
            exclude={"id", "sample_id", "related_task_id"},
            rename={
                "type": "类型", "operator_id": "操作人ID",
                "purpose": "用途", "notes": "备注",
                "created_at": "时间",
            },
        )
        st.dataframe(txn_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无流水记录")
