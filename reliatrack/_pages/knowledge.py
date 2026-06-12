"""知识库页面 — 文章列表、搜索、编辑。"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from pages._shared import (
    get_services,
    dataclass_to_df,
    render_pagination,
    render_delete_confirm,
)


def render() -> None:
    st.title("知识库")
    svc = get_services()
    k_svc = svc["knowledge"]

    # ── 即时搜索（无按钮） ──
    keyword = st.text_input("搜索", placeholder="输入关键词搜索...", key="kb_search")

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
            st.caption("标 * 为必填")
            category = st.text_input("类别 *", max_chars=200)
            failure_mode = st.text_input("失效模式", max_chars=200)
            cause_analysis = st.text_area("原因分析", max_chars=2000)
            improvement = st.text_area("改进措施", max_chars=2000)
            ref_std = st.text_input("参考标准", max_chars=200)
            keywords_str = st.text_input("关键词（逗号分隔）", max_chars=200)
            summary = st.text_area("摘要", max_chars=2000)
            if st.form_submit_button("创建", type="primary"):
                if not category:
                    st.error("请填写必填字段")
                else:
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
    total = len(entries)
    st.write(f"共 {total} 条记录")

    if not entries:
        if keyword:
            st.info("未找到匹配条目")
        else:
            st.info("暂无知识条目。请在左侧「新增知识条目」表单中创建。")
        return

    PAGE_SIZE = 50
    page, total_pages = render_pagination(total, PAGE_SIZE, "knowledge")
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_data = entries[start:end]

    df = dataclass_to_df(
        page_data,
        exclude={"id", "root_cause", "resolution", "related_issues"},
        rename={
            "category": "类别",
            "failure_mode": "失效模式",
            "cause_analysis": "原因分析",
            "improvement": "改进措施",
            "reference_standard": "参考标准",
            "keywords": "关键词",
            "summary": "摘要",
            "created_at": "创建时间",
        },
        columns=[
            "类别", "失效模式", "原因分析", "改进措施",
            "参考标准", "关键词", "摘要", "创建时间",
        ],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── 编辑/查看详情 ──
    st.markdown("---")
    entry_map = {
        e.summary or e.failure_mode or f"ID:{e.id}": e
        for e in page_data
        if e.id
    }
    if not entry_map:
        return

    sel_label = st.selectbox(
        "选择条目查看/编辑", list(entry_map.keys()), key="kb_sel",
    )
    entry = entry_map[sel_label]

    st.markdown("#### 编辑条目")
    with st.form("kb_edit_form"):
        new_category = st.text_input("类别", value=entry.category, max_chars=200)
        new_fm = st.text_input("失效模式", value=entry.failure_mode, max_chars=200)
        new_cause = st.text_area("原因分析", value=entry.cause_analysis, max_chars=2000)
        new_improve = st.text_area("改进措施", value=entry.improvement, max_chars=2000)
        new_std = st.text_input("参考标准", value=entry.reference_standard, max_chars=200)
        new_kw = st.text_input("关键词", value=entry.keywords, max_chars=200)

        # Markdown 预览
        new_summary = st.text_area("摘要", value=entry.summary, max_chars=2000)
        st.markdown("**摘要预览**")
        st.markdown(new_summary or "*（空）*")

        # 内容 Markdown 预览（合并 cause_analysis 和 improvement）
        content_md = ""
        if new_cause:
            content_md += f"**原因分析**\n\n{new_cause}\n\n"
        if new_improve:
            content_md += f"**改进措施**\n\n{new_improve}\n\n"
        if content_md:
            st.markdown("**内容预览**")
            st.markdown(content_md)

        if st.form_submit_button("保存修改"):
            k_svc.update(
                entry.id,
                summary=new_summary,
                category=new_category,
                failure_mode=new_fm,
                cause_analysis=new_cause,
                improvement=new_improve,
                reference_standard=new_std,
                keywords=new_kw,
            )
            st.success("已更新")
            st.rerun()

    if render_delete_confirm(sel_label, "kb_del"):
        k_svc.delete(entry.id)
        st.success("已删除")
        st.rerun()
