"""导入导出页面 — 批量导入 + Excel/PDF/Word 下载。"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import io

from pages._shared import get_services
from src.services.import_service import import_equipment, import_technicians


def _render_import_upload(
    label: str,
    description: str,
    upload_key: str,
    import_func,
    service_key: str,
    svc: dict,
) -> None:
    """渲染单个导入区域，提取共享逻辑。"""
    st.markdown(description)
    uploaded = st.file_uploader(
        label,
        type=["xlsx", "xls"],
        key=upload_key,
    )
    if uploaded:
        try:
            df_upload = pd.read_excel(uploaded)
            rows = df_upload.to_dict("records")
            result = import_func(rows, svc[service_key])
            st.success(f"导入完成: {result.success} 成功, {result.skipped} 跳过")
            if result.errors:
                with st.expander("查看详情"):
                    for err in result.errors:
                        st.caption(err)
        except Exception as e:
            st.error(f"导入失败: {e}")


def render() -> None:
    st.title("导入 / 导出")
    svc = get_services()

    tab1, tab2 = st.tabs(["导入", "导出"])

    # ═══════════════════════════════════════════════════════════════
    #  导入
    # ═══════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("批量导入设备")
        _render_import_upload(
            label="选择设备导入文件",
            description="上传 Excel 文件（.xlsx），列名: name, type, model, location, status, asset_no, manufacturer 等",
            upload_key="upload_eq",
            import_func=import_equipment,
            service_key="equipment",
            svc=svc,
        )

        st.markdown("---")
        st.subheader("批量导入技术员")
        _render_import_upload(
            label="选择技术员导入文件",
            description="上传 Excel 文件（.xlsx），列名: name, employee_id, role, department, phone, email 等",
            upload_key="upload_tech",
            import_func=import_technicians,
            service_key="technician",
            svc=svc,
        )

    # ═══════════════════════════════════════════════════════════════
    #  导出
    # ═══════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("导出报告")

        p_svc = svc["project"]
        plan_svc = svc["plan"]

        projects = p_svc.list_all()
        proj_map = {p.name: p.id for p in projects if p.id}

        if not proj_map:
            st.info("暂无项目可以导出")
            return

        export_proj = st.selectbox(
            "选择导出项目", list(proj_map.keys()), key="export_proj",
        )
        proj_id = proj_map[export_proj]
        proj_obj = p_svc.get(proj_id)

        # ── 计划选择器 ──
        plans = plan_svc.get_plans_by_project(proj_id)
        selected_plan = None
        plan_sel_map = {}
        if plans:
            plan_sel_map = {p.name: p for p in plans if p.name}
            if plan_sel_map:
                plan_sel_name = st.selectbox(
                    "选择导出计划", list(plan_sel_map.keys()), key="export_plan",
                )
                selected_plan = plan_sel_map[plan_sel_name]

        if not selected_plan:
            st.info("所选项目暂无测试计划，请先创建计划。")
            return

        export_service = svc["export"]
        issue_svc = svc["issue"]
        sample_svc = svc["sample"]

        # 获取项目数据
        issues = issue_svc.get_by_project(proj_id)
        samples = sample_svc.get_by_project(proj_id)

        col_e1, col_e2, col_e3 = st.columns(3)

        # ── Excel 导出 ──
        with col_e1:
            st.markdown("##### Excel")
            if st.button("导出任务 Excel", use_container_width=True):
                if selected_plan and selected_plan.id:
                    tasks = plan_svc.get_tasks(selected_plan.id)
                    buf = io.BytesIO()
                    try:
                        path = export_service.export_tasks_excel(
                            selected_plan,
                            tasks,
                            filepath=f"/tmp/report_{export_proj}.xlsx",
                        )
                        with open(path, "rb") as f:
                            buf.write(f.read())
                        st.download_button(
                            "下载任务报表",
                            data=buf.getvalue(),
                            file_name=f"{export_proj}_tasks.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    except Exception as e:
                        st.error(f"导出失败: {e}")

            if st.button("导出 Issue Excel", use_container_width=True):
                if issues:
                    buf = io.BytesIO()
                    try:
                        path = export_service.export_issues_excel(
                            issues,
                            filepath=f"/tmp/issues_{export_proj}.xlsx",
                        )
                        with open(path, "rb") as f:
                            buf.write(f.read())
                        st.download_button(
                            "下载 Issue 报表",
                            data=buf.getvalue(),
                            file_name=f"{export_proj}_issues.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    except Exception as e:
                        st.error(f"导出失败: {e}")

        # ── PDF 导出 ──
        with col_e2:
            st.markdown("##### PDF")
            if st.button("导出报告 PDF", use_container_width=True):
                if selected_plan and proj_obj:
                    tasks = plan_svc.get_tasks(selected_plan.id) if selected_plan.id else []
                    buf = io.BytesIO()
                    try:
                        path = export_service.export_report_pdf(
                            proj_obj, tasks, issues, samples,
                            filepath=f"/tmp/report_{export_proj}.pdf",
                        )
                        with open(path, "rb") as f:
                            buf.write(f.read())
                        st.download_button(
                            "下载 PDF 报告",
                            data=buf.getvalue(),
                            file_name=f"{export_proj}_report.pdf",
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"导出失败: {e}")

            if st.button("导出 DVPR PDF", use_container_width=True):
                if selected_plan and selected_plan.id:
                    tasks = plan_svc.get_tasks(selected_plan.id)
                    results = plan_svc.get_task_results(tasks[0].id) if tasks else []
                    buf = io.BytesIO()
                    try:
                        path = export_service.export_dvpr_pdf(
                            selected_plan, tasks, results, issues, samples,
                            filepath=f"/tmp/dvpr_{export_proj}.pdf",
                        )
                        with open(path, "rb") as f:
                            buf.write(f.read())
                        st.download_button(
                            "下载 DVPR PDF",
                            data=buf.getvalue(),
                            file_name=f"{export_proj}_dvpr.pdf",
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"导出失败: {e}")

        # ── Word 导出 ──
        with col_e3:
            st.markdown("##### Word")
            if st.button("导出 Word 报告", use_container_width=True):
                if selected_plan and proj_obj:
                    tasks = plan_svc.get_tasks(selected_plan.id) if selected_plan.id else []
                    buf = io.BytesIO()
                    try:
                        path = export_service.export_to_word(
                            proj_obj, tasks, issues, samples,
                            filepath=f"/tmp/report_{export_proj}.docx",
                        )
                        with open(path, "rb") as f:
                            buf.write(f.read())
                        st.download_button(
                            "下载 Word 报告",
                            data=buf.getvalue(),
                            file_name=f"{export_proj}_report.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    except Exception as e:
                        st.error(f"导出失败: {e}")
