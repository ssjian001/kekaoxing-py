"""📚 知识库页面 — 文章列表 + 搜索 + 编辑。"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import get_services, dataclass_to_df


def show() -> None:
    st.title("📚 知识库")
    svc = get_services()
    k_svc = svc["knowledge"]

    # ── 搜索 ──
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        keyword = st.text_input("🔍 搜索关键词", placeholder="输入关键词搜索...")
    with col_s2:
        st.markdown("&nbsp;")
        if keyword:
            if st.button("搜索"):
                st.rerun()

    # ── 获取数据 ──
    if keyword:
        entries = k_svc.search(keyword)
    else:
        entries = k_svc.list_all()

    # ── 侧边栏：新增 ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 新增知识条目")
        with st.form("knowledge_form", clear_on_submit=True):
            category = st.text_input("类别 *")
            failure_mode = st.text_input("失效模式")
            cause_analysis = st.text_area("原因分析")
            improvement = st.text_area("改进措施")
            ref_std = st.text_input("参考标准")
            keywords_str = st.text_input("关键词（逗号分隔）")
            summary = st.text_area("摘要")
            if st.form_submit_button("创建", type="primary"):
                k_svc.create(
                    category=category, failure_mode=failure_mode,
                    cause_analysis=cause_analysis,
                    improvement=improvement,
                    reference_standard=ref_std,
                    keywords=keywords_str,
                    summary=summary,
                )
                st.success("知识条目已创建")
                st.rerun()

    # ── 显示列表 ──
    st.subheader(f"共 {len(entries)} 条记录")

    if entries:
        df = dataclass_to_df(
            entries,
            exclude={"id", "root_cause", "resolution", "related_issues"},
            rename={
                "category": "类别", "failure_mode": "失效模式",
                "cause_analysis": "原因分析",
                "improvement": "改进措施",
                "reference_standard": "参考标准",
                "keywords": "关键词", "summary": "摘要",
                "created_at": "创建时间",
            },
            columns=["类别", "失效模式", "原因分析", "改进措施",
                     "参考标准", "关键词", "摘要", "创建时间"],
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── 编辑/查看详情 ──
        st.markdown("---")
        entry_map = {f"{e.summary or e.failure_mode or f'ID:{e.id}'}": e
                     for e in entries if e.id}
        if entry_map:
            sel_label = st.selectbox("选择条目查看/编辑", list(entry_map.keys()),
                                     key="kb_sel")
            entry = entry_map[sel_label]

            with st.expander("📝 查看/编辑详情", expanded=True):
                with st.form("kb_edit_form"):
                    new_summary = st.text_input("摘要", value=entry.summary)
                    new_category = st.text_input("类别", value=entry.category)
                    new_fm = st.text_input("失效模式", value=entry.failure_mode)
                    new_cause = st.text_area("原因分析", value=entry.cause_analysis)
                    new_improve = st.text_area("改进措施", value=entry.improvement)
                    new_std = st.text_input("参考标准", value=entry.reference_standard)
                    new_kw = st.text_input("关键词", value=entry.keywords)
                    if st.form_submit_button("保存修改"):
                        k_svc.update(
                            entry.id,
                            summary=new_summary, category=new_category,
                            failure_mode=new_fm, cause_analysis=new_cause,
                            improvement=new_improve,
                            reference_standard=new_std, keywords=new_kw,
                        )
                        st.success("已更新")
                        st.rerun()

                if st.button("🗑️ 删除", type="secondary"):
                    k_svc.delete(entry.id)
                    st.success("已删除")
                    st.rerun()
    else:
        st.info("暂无知识库条目" if not keyword else "未找到匹配条目")
