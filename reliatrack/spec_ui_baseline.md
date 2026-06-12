# 任务: Streamlit UI 改造 — baseline-ui 适配

## 参考
ibelick/ui-skills baseline-ui 规范，适配到 Streamlit 语境。

## 改造范围
所有 reliatrack/pages/*.py + app.py + .streamlit/config.toml

## 具体改造项

### 1. 主题配置（.streamlit/config.toml）
设置自定义主题，替代 Streamlit 默认红色 accent:
```toml
[theme]
primaryColor = "#2563eb"       # 蓝色 accent（专业、工程）
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f8fafc"
textColor = "#0f172a"
font = "sans serif"
```
- 不用紫色、不用渐变
- accent 色每页只用一个（蓝色系）

### 2. 页面标题去 emoji
baseline-ui 规范: 不用 emoji 作为主要 UI affordance。
- `st.title("📊 仪表盘")` → `st.title("仪表盘")` 
- 侧边栏导航已有 emoji 作图标区分，保留
- st.subheader / st.markdown 中的 emoji 前缀也去掉

### 3. 空状态要有明确行动点
baseline-ui: "MUST give empty states one clear next action"
当前: `st.info("暂无项目数据")` — 只说没数据
修复: 
```python
st.info("暂无项目数据。请在左侧创建第一个项目。")
```
或用 st.empty() + st.button

### 4. 错误信息显示在操作旁边
baseline-ui: "MUST show errors next to where the action happens"
当前已有 st.error 在 form 内，OK。
但某些 st.error 远离操作按钮（如 issues.py 批量操作的 disabled 状态）
修复: disabled 的按钮旁加 help tooltip 说明为什么禁用

### 5. 表格列宽/对齐
- 数据列用等宽字体（tabular-nums 思路）
- 结果矩阵 HTML table 加 font-family: monospace 对齐数字

### 6. 表单 label 清晰
fixing-accessibility: 所有 input 必须有 label
当前已有 label（st.text_input("项目名称 *")），OK。
但 "项目名称 *" 的星号含义不明确。
修复: 改为 `st.text_input("项目名称", help="必填")` 或保留 * 但加 help

### 7. 侧边栏精简
- app.py 侧边栏标题层级: markdown("# xxx") 太大
- 改为 markdown("### ReliaTrack") + caption

### 8. metric 卡片去 emoji
dashboard.py 的 st.metric("📁 项目数", 5) → st.metric("项目数", 5)
emoji 在 metric label 中不专业

### 9. 按钮 label 清晰
- "保存" → "保存修改"
- "出库" → "确认出库" 
- "删除" → 已有"删除项目"/"删除计划"，OK
- 不可逆操作按钮用 type="secondary"（灰色，不突出）已实现

### 10. HTML table（结果矩阵）优化
- 加 border-collapse、字体、单元格 padding 已有
- 优化: 固定列宽、首列 sticky、单色配色

## 不做的事
- 不加动画
- 不加渐变/光晕
- 不改 Streamlit 组件为自定义 HTML
- 不引入 CSS 框架
- 保持 Streamlit 原生组件

## 验收
1. .streamlit/config.toml 有主题
2. 所有 st.title/st.metric 无 emoji
3. 空状态有行动点
4. python -m py_compile 通过
5. pytest -q 341 passed
