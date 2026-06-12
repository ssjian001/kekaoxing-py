"""ReliaTrack — Streamlit 前端入口。

复用现有 db/repo/service 层，提供 9 个功能页面。
"""
from __future__ import annotations

import sys
import os

# 确保能从 reliatrack/ 找到 src/
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_PROJECT_ROOT)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import streamlit as st

st.set_page_config(
    page_title="ReliaTrack — 可靠性测试管理系统",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """应用入口：侧边栏导航 + 页面路由。"""
    st.sidebar.image(
        "https://img.icons8.com/fluency/96/test-tube.png",
        width=64,
    )
    st.sidebar.markdown("# 🔬 ReliaTrack")
    st.sidebar.markdown("可靠性测试管理系统")
    st.sidebar.markdown("---")

    pages = {
        "📊 仪表盘":       "pages/1_📊_仪表盘.py",
        "📁 项目管理":     "pages/2_📁_项目管理.py",
        "🔬 样品管理":     "pages/3_🔬_样品管理.py",
        "📋 测试计划":     "pages/4_📋_测试计划.py",
        "📅 排程管理":     "pages/5_📅_排程管理.py",
        "⚠️ Issue":         "pages/6_⚠️_Issue.py",
        "🔧 设备人员":     "pages/7_🔧_设备人员.py",
        "📚 知识库":       "pages/8_📚_知识库.py",
        "📤 导入导出":     "pages/9_📤_导入导出.py",
    }

    page_name = st.sidebar.radio("导航", list(pages.keys()), index=0)
    selected = pages[page_name]

    if selected == "pages/1_📊_仪表盘.py":
        from pages import dashboard
        dashboard.show()
    elif selected == "pages/2_📁_项目管理.py":
        from pages import projects
        projects.show()
    elif selected == "pages/3_🔬_样品管理.py":
        from pages import samples
        samples.show()
    elif selected == "pages/4_📋_测试计划.py":
        from pages import test_plans
        test_plans.show()
    elif selected == "pages/5_📅_排程管理.py":
        from pages import scheduler
        scheduler.show()
    elif selected == "pages/6_⚠️_Issue.py":
        from pages import issues
        issues.show()
    elif selected == "pages/7_🔧_设备人员.py":
        from pages import equipment_technician
        equipment_technician.show()
    elif selected == "pages/8_📚_知识库.py":
        from pages import knowledge
        knowledge.show()
    elif selected == "pages/9_📤_导入导出.py":
        from pages import import_export
        import_export.show()


if __name__ == "__main__":
    main()
