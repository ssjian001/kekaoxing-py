# 任务: Phase 3.3 — Issue 批量操作

## 目标
在 issues.py 增加全选/批量更新状态/批量分配功能。

## 修改文件
pages/issues.py

## 实现方式
在 Issue 表格上方增加操作栏：
1. 全选 checkbox
2. 每行 checkbox
3. 选择后显示批量操作面板：
   - 批量更新状态（selectbox + 按钮）
   - 批量分配（selectbox + 按钮）

```python
# 表格上方
col_b1, col_b2, col_b3, col_b4 = st.columns([1, 2, 2, 2])
with col_b1:
    select_all = st.checkbox("全选", key="iss_select_all")
with col_b2:
    batch_status = st.selectbox("批量更新状态", list(status_opts.keys()), key="iss_batch_status",
                                disabled=not selected_ids)
with col_b3:
    # 如果有多分配人
    batch_assign = st.selectbox("批量分配", list(assignees), key="iss_batch_assign",
                                disabled=not selected_ids)
with col_b4:
    if st.button("执行批量操作", disabled=not selected_ids):
        for iid in selected_ids:
            if batch_status:
                issue_svc.update_status(iid, status_opts[batch_status])
        st.success(f"已更新 {len(selected_ids)} 个 Issue")
        st.rerun()
```

关键: 用 st.session_state 跟踪选中的 Issue ID 列表。

## 验收标准
1. 表格每行有 checkbox
2. 全选 checkbox
3. 选中后可批量更新状态/分配
4. 未选中时操作栏 disabled
5. python -m py_compile 通过
6. pytest -q 341 passed

## 不用做的事
- 不要运行 streamlit
- 不改 service/repo 层
- 不做复杂的分页联动（当前已有分页，保持各自独立）
