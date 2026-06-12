# 任务: Phase 3.1 — 结果矩阵（任务×样品网格）

## 目标
在 test_plans.py 增加"结果矩阵"tab，显示任务×样品 pass/fail 着色网格。
参考 PySide6 版: src/views/widgets/result_matrix.py

## 需求
- 行 = 测试任务，列 = 样品 SN
- 单元格着色: pass=🟢 green, fail=🔴 red, conditional=🟡 yellow, pending=⚪ gray
- 单元格显示: 结果符号 (P/F/C/—)
- 末列 = 任务通过率
- 末行 = 样品通过率
- 选择计划后自动加载

## 实现方式
在 test_plans.py 的 show() 函数中，在计划操作区域下方增加 tab:
```python
tab_tasks, tab_matrix = st.tabs(["📋 任务列表", "📊 结果矩阵"])
```

结果矩阵 tab 内容:
1. 获取该计划的所有任务和所有结果
2. 获取涉及的所有样品 (from results)
3. 构建 pandas pivot table: 行=任务名, 列=样品SN, 值=结果
4. 用 st.dataframe + Styler 着色，或用 HTML table 自定义着色

### 方案 A: st.dataframe + Styler（推荐，简单）
```python
import pandas as pd
# 构建矩阵
pivot = pd.DataFrame(index=[t.name for t in tasks], columns=all_sample_sns)
for r in results:
    pivot.loc[task_name_of(r), sample_sn_of(r)] = result_symbol(r)

# 着色函数
def color_result(val):
    if val == "P": return "background-color: #4CAF50; color: white"
    if val == "F": return "background-color: #F44336; color: white"
    if val == "C": return "background-color: #FF9800; color: white"
    return ""

styled = pivot.style.applymap(color_result)
st.dataframe(styled, use_container_width=True)
```

### 方案 B: HTML table（更灵活，推荐）
这个方案对颜色和布局控制更强，不会被 Streamlit 主题覆盖：
```python
def build_matrix_html(tasks, results, all_samples) -> str:
    # 构建 HTML table, 单元格着色, 行列统计
    ...

st.markdown(html, unsafe_allow_html=True)
```

推荐方案 B 因为颜色控制更可靠。

## 验收标准
1. test_plans 页面有"结果矩阵"tab
2. 矩阵显示正确着色
3. 末列显示任务通过率，末行显示样品通过率
4. 无数据时显示"暂无数据"
5. 切换计划自动刷新
6. python -m py_compile 通过
7. pytest -q 341 passed

## 不用做的事
- 不要运行 streamlit
- 不改 service/repo 层（现有 plan_svc.get_task_results() 够用）
- 不实现显示模式切换（符号模式即可）
