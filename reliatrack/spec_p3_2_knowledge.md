# 任务: Phase 3.2 — 知识库富文本渲染

## 目标
知识库条目的详情/编辑区支持 Markdown 渲染。目前是纯 text_area 显示。

## 修改文件
pages/knowledge.py

## 实现方式
在查看/编辑详情区 (`with st.expander("📝 查看/编辑详情", expanded=True):`):
1. 非编辑模式：用 st.markdown(entry.content) 渲染富文本
2. 编辑模式用 text_area
3. 支持 Markdown 字段: summary, cause_analysis, improvement

### 具体实现
```python
with st.expander("📝 查看/编辑详情", expanded=True):
    with st.form("kb_edit_form"):
        # 当前编辑字段保留
        ...
    
    # 在表单下方或旁边增加只读 Markdown 预览
    st.markdown("---")
    st.markdown(f"**摘要**: {entry.summary}")
    st.markdown(f"**原因分析**: {entry.cause_analysis}")
    st.markdown(f"**改进措施**: {entry.improvement}")
    # 如果包含 Markdown 语法:
    # st.markdown(entry.cause_analysis)
```

更简单的方案：把详情从 expander 移到主区域，分成左右两列——左列编辑、右列 Markdown 预览。

或者最简单的：在现有的编辑表单中将 summary/cause/improve 字段用 st.text_area + 该字段下方加 st.markdown 显示渲染效果。

## 验收标准
1. 知识库详情区文本以 Markdown 格式渲染
2. 编辑时用 text_area
3. python -m py_compile 通过
4. pytest -q 341 passed
