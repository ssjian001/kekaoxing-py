"""ReliaTrack — Streamlit 导航入口。"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="ReliaTrack", layout="wide", page_icon="🔬")

# 侧边栏导航（无 emoji，分组简洁）
with st.sidebar:
    st.title("ReliaTrack")
    st.caption("可靠性测试管理系统")

    nav_section = st.radio(
        "功能模块",
        [
            "仪表盘",
            "项目管理",
            "样品管理",
            "测试计划",
            "排程管理",
            "Issue 管理",
            "设备人员",
            "知识库",
            "导入导出",
        ],
        label_visibility="collapsed",
    )

# 页面路由
if nav_section == "仪表盘":
    from reliatrack._pages.dashboard import render

    render()
elif nav_section == "项目管理":
    from reliatrack._pages.projects import render

    render()
elif nav_section == "样品管理":
    from reliatrack._pages.samples import render
    render()
elif nav_section == "测试计划":
    from reliatrack._pages.test_plans import render
    render()
elif nav_section == "排程管理":
    from reliatrack._pages.scheduler import render
    render()
elif nav_section == "Issue 管理":
    from reliatrack._pages.issues import render
    render()
elif nav_section == "设备人员":
    from reliatrack._pages.equipment_technician import render
    render()
elif nav_section == "知识库":
    from reliatrack._pages.knowledge import render
    render()
elif nav_section == "导入导出":
    from reliatrack._pages.import_export import render
    render()
