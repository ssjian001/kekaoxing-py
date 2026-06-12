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
    "📊 仪表盘":       "dashboard",
    "📁 项目管理":     "projects",
    "🔬 样品管理":     "samples",
    "📋 测试计划":     "test_plans",
    "📅 排程管理":     "scheduler",
    "⚠️ Issue":         "issues",
    "🔧 设备人员":     "equipment_technician",
    "📚 知识库":       "knowledge",
    "📤 导入导出":     "import_export",
}

    page_name = st.sidebar.radio("导航", list(pages.keys()), index=0)
    selected = pages[page_name]

    if selected == "dashboard":
        from pages import dashboard
        dashboard.show()
    elif selected == "projects":
        from pages import projects
        projects.show()
    elif selected == "samples":
        from pages import samples
        samples.show()
    elif selected == "test_plans":
        from pages import test_plans
        test_plans.show()
    elif selected == "scheduler":
        from pages import scheduler
        scheduler.show()
    elif selected == "issues":
        from pages import issues
        issues.show()
    elif selected == "equipment_technician":
        from pages import equipment_technician
        equipment_technician.show()
    elif selected == "knowledge":
        from pages import knowledge
        knowledge.show()
    elif selected == "import_export":
        from pages import import_export
        import_export.show()


if __name__ == "__main__":
    main()
