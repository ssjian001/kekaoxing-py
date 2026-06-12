# 任务: Phase 2.3 — 数据集分页

## 目标
数据量 > 100 条时自动分页，减少页面渲染量。

## 涉及文件 (reliatrack/pages/)
- issues.py: 全量拉取后筛选，可能有大量数据
- knowledge.py: 知识库条目可能多
- samples.py: 样品可能多
- projects.py: 通常少，可不加分页

## 实现方式
```python
PAGE_SIZE = 50
if "page_xxx" not in st.session_state:
    st.session_state["page_xxx"] = 1

total = len(filtered_data)
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

start = (page - 1) * PAGE_SIZE
end = start + PAGE_SIZE
page_data = filtered_data[start:end]

# 分页按钮
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("◀ 上一页", disabled=page<=1):
        st.session_state["page_xxx"] -= 1
        st.rerun()
with col2:
    st.write(f"第 {page}/{total_pages} 页（共 {total} 条）")
with col3:
    if st.button("下一页 ▶", disabled=page>=total_pages):
        st.session_state["page_xxx"] += 1
        st.rerun()
```

分页器放在 DataFrame 下方。

## 验收标准
1. 超过 50 条记录自动分页
2. 少于 50 条不显示分页按钮
3. 切换分页保留搜索/筛选条件
4. python -m py_compile 通过
5. pytest -q 341 passed

## 不用做的事
- 不要运行 streamlit
- 不改 service/repo 层
- 不改 _shared.py
