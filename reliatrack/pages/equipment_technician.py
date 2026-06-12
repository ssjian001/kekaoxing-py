"""🔧 设备人员页面 — 设备 + 技术员 CRUD。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import get_services, dataclass_to_df
from src.constants import EQUIPMENT_STATUS_LABELS


def show() -> None:
    st.title("🔧 设备与人员管理")
    svc = get_services()
    eq_svc = svc["equipment"]
    tech_svc = svc["technician"]

    tab1, tab2 = st.tabs(["🔧 设备管理", "👤 技术员管理"])

    # ═══════════════════════════════════════════════════════════════
    #  设备
    # ═══════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("设备列表")

        # 侧边栏：新增设备
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 新增设备")
            with st.form("equipment_form", clear_on_submit=True):
                eq_name = st.text_input("设备名称 *", max_chars=200)
                eq_type = st.text_input("类型", max_chars=200)
                eq_model = st.text_input("型号", max_chars=200)
                eq_location = st.text_input("位置", max_chars=200)
                eq_status = st.selectbox(
                    "状态", list(EQUIPMENT_STATUS_LABELS.values()), index=0
                )
                eq_asset = st.text_input("资产编号", max_chars=200)
                eq_manu = st.text_input("制造商", max_chars=200)
                eq_cal = st.text_input("校准日期 (YYYY-MM-DD)", max_chars=30,
                                       placeholder="如: 2026-06-01")
                eq_next_cal = st.text_input("下次校准日期", max_chars=30,
                                            placeholder="如: 2027-06-01")
                if st.form_submit_button("添加", type="primary"):
                    if not eq_name:
                        st.error("请填写必填字段")
                    else:
                        status_rev = {v: k for k, v in EQUIPMENT_STATUS_LABELS.items()}
                        eq_svc.create(
                            name=eq_name, type=eq_type, model=eq_model,
                            location=eq_location,
                            status=status_rev.get(eq_status, "available"),
                            asset_no=eq_asset, manufacturer=eq_manu,
                            calibration_date=eq_cal,
                            next_calibration_date=eq_next_cal,
                        )
                        st.success(f"设备「{eq_name}」已添加")
                        st.rerun()

        # 设备列表
        equipments = eq_svc.list_all()

        # ── 搜索过滤 ──
        search_term_eq = st.text_input(
            "🔍 搜索设备...",
            placeholder="输入设备名称/型号/位置/资产编号过滤...",
            key="search_eq",
        )
        if search_term_eq:
            stxt = search_term_eq.lower()
            equipments = [
                e
                for e in equipments
                if stxt in (e.name or "").lower()
                or stxt in (e.model or "").lower()
                or stxt in (e.location or "").lower()
                or stxt in (e.asset_no or "").lower()
            ]

        if equipments:
            df = dataclass_to_df(
                equipments,
                exclude={"id", "accuracy", "created_at"},
                rename={
                    "name": "名称", "type": "类型", "model": "型号",
                    "location": "位置", "status": "状态",
                    "calibration_date": "校准日期",
                    "next_calibration_date": "下次校准",
                    "calibration_interval_months": "校准间隔(月)",
                    "asset_no": "资产编号", "manufacturer": "制造商",
                },
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            # 操作：选择设备
            st.markdown("---")
            eq_map = {f"{e.name} (ID:{e.id})": e for e in equipments if e.id}
            if eq_map:
                eq_sel = st.selectbox("选择设备操作", list(eq_map.keys()), key="eq_sel")
                eq = eq_map[eq_sel]

                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    st.markdown("#### 编辑")
                    new_eq_name = st.text_input("名称", value=eq.name, max_chars=200, key="eq_edit_name")
                    new_eq_loc = st.text_input("位置", value=eq.location, max_chars=200, key="eq_edit_loc")
                    status_rev = {v: k for k, v in EQUIPMENT_STATUS_LABELS.items()}
                    cur_status_label = status_rev.get(eq.status, eq.status)
                    new_eq_status = st.selectbox(
                        "状态", list(status_rev.keys()),
                        index=list(status_rev.keys()).index(cur_status_label)
                        if cur_status_label in status_rev else 0,
                        key="eq_edit_status",
                    )
                    if st.button("保存"):
                        eq_svc.update(
                            eq.id, name=new_eq_name, location=new_eq_loc,
                            status=status_rev[new_eq_status],
                        )
                        st.success("已更新")
                        st.rerun()

                with col_e2:
                    if st.button("删除设备", type="secondary"):
                        try:
                            eq_svc.delete(eq.id)
                            st.success("已删除")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
        else:
            st.info("暂无设备数据")

    # ═══════════════════════════════════════════════════════════════
    #  技术员
    # ═══════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("技术员列表")

        # 侧边栏：新增技术员（已在设备表同侧边栏复用，这里用主界面）
        with st.expander("➕ 新增技术员"):
            with st.form("tech_form", clear_on_submit=True):
                t_name = st.text_input("姓名 *", max_chars=200)
                t_emp_id = st.text_input("工号", max_chars=200)
                t_role = st.text_input("职位", max_chars=200)
                t_dept = st.text_input("部门", max_chars=200)
                t_phone = st.text_input("电话", max_chars=200)
                t_email = st.text_input("邮箱", max_chars=200)
                if st.form_submit_button("添加", type="primary"):
                    if not t_name:
                        st.error("请填写必填字段")
                    else:
                        tech_svc.create(
                            name=t_name, employee_id=t_emp_id,
                            role=t_role, department=t_dept,
                            phone=t_phone, email=t_email,
                        )
                        st.success(f"技术员「{t_name}」已添加")
                        st.rerun()

        technicians = tech_svc.list_all()

        # ── 搜索过滤 ──
        search_term_tech = st.text_input(
            "🔍 搜索技术员...",
            placeholder="输入姓名/工号过滤...",
            key="search_tech",
        )
        if search_term_tech:
            stxt = search_term_tech.lower()
            technicians = [
                t
                for t in technicians
                if stxt in (t.name or "").lower()
                or stxt in (t.employee_id or "").lower()
            ]

        if technicians:
            df_tech = dataclass_to_df(
                technicians,
                exclude={"id", "created_at"},
                rename={
                    "name": "姓名", "employee_id": "工号",
                    "role": "职位", "department": "部门",
                    "phone": "电话", "email": "邮箱",
                },
            )
            st.dataframe(df_tech, use_container_width=True, hide_index=True)

            # 操作
            st.markdown("---")
            tech_map = {f"{t.name} (ID:{t.id})": t for t in technicians if t.id}
            if tech_map:
                t_sel = st.selectbox("选择技术员操作", list(tech_map.keys()), key="tech_sel")
                tech = tech_map[t_sel]
                if st.button("删除技术员", type="secondary"):
                    try:
                        tech_svc.delete(tech.id)
                        st.success("已删除")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
        else:
            st.info("暂无技术员数据")
