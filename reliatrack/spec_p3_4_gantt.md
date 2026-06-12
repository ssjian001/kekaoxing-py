# 任务: Phase 3.4 — 排程甘特图增强

## 目标
增强 scheduler.py 的甘特图：
1. 增加设备资源视图（按设备着色的甘特图）
2. 增加导出甘特图为 PNG 图片

## 修改文件
pages/scheduler.py

## 实现方式

### 1. 设备资源视图
当前甘特图已按"状态"着色。新增按"设备"着色的视图：
```python
# 在现有甘特图下方增加切换
view_mode = st.radio("甘特图模式", ["按状态", "按设备"], horizontal=True, key="gantt_mode")
color_col = "状态" if view_mode == "按状态" else "设备"
fig = px.timeline(df_gantt, x_start="开始日期", x_end="结束日期",
                  y="任务", color=color_col, ...)
```

### 2. 导出甘特图为 PNG
使用 plotly 内置导出:
```python
if st.button("📷 导出甘特图 PNG"):
    fig.write_image(f"/tmp/gantt_{plan_name}.png", width=1200, height=600)
    with open(f"/tmp/gantt_{plan_name}.png", "rb") as f:
        btn = st.download_button("下载 PNG", data=f, file_name=f"gantt_{plan_name}.png", mime="image/png")
```

注意: plotly 的 write_image 需要 kaleido 或 orca 引擎。
如果 kaleido 未安装: 先 pip install kaleido，或改用 plotly.io.to_image()。
检查当前环境的 plotly 导出能力:
```python
import plotly.io as pio
# pio.renderers 查看可用渲染器
```

若 kaleido 不可用，备选方案：用 html 截图或 streamlit plotly_chart 的右键另存为提示。

## 验收标准
1. 甘特图支持"按状态"/"按设备"切换
2. 导出按钮可用（有错误处理）
3. python -m py_compile 通过
4. pytest -q 341 passed

## 不用做的事
- 不要运行 streamlit
- 不改 service/repo 层
- 不改 _shared.py
