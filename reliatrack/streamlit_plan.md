# ReliaTrack Streamlit 迁移 — 开发计划

## 分支: feat/streamlit-frontend
## 基座: Streamlit 1.58 + Plotly
## 测试基线: 341 passed

---

## Phase 2 — 核心页面打磨（高优先级）

### 2.1 全页面搜索/筛选增强
**目标**: 每个 CRUD 页面顶部增加搜索框，支持模糊匹配
**涉及**: projects, samples, test_plans, issues, equipment_technician, knowledge
**方式**: st.text_input(placeholder="搜索...") → 过滤 DataFrame 或调用 service.search()
**注意**: 现 issues.py 已有状态/严重度筛选，可保留

### 2.2 表单验证
**目标**: 必填字段加验证、日期格式校验、长度限制
**涉及**: 所有 st.form
**方式**: 
- 提交前检查（if not name: st.error("必填")）
- st.text_input(max_chars=200) 防长输入
- 日期格式 regex 校验

### 2.3 大数据集分页/加载
**目标**: 超过 100 条记录时分页显示
**涉及**: issues, knowledge, samples
**方式**: st.dataframe + st.session_state 页码 + 切片

### 2.4 编辑/详情弹窗
**目标**: 从原位 inline 编辑改为 st.dialog（Streamlit 1.36+）
**涉及**: projects, samples, issues, knowledge
**方式**: @st.dialog 装饰器

---

## Phase 3 — 功能页面增强（中优先级）

### 3.1 结果矩阵（任务×样品网格）
**目标**: 在 test_plans 页面增加"结果矩阵"tab，显示 pass/fail/conditional 着色网格
**参考**: src/views/widgets/result_matrix.py (PySide6 版)
**方式**: Plotly 热力图或 HTML table 着色

### 3.2 知识库富文本
**目标**: 知识库支持 Markdown 渲染（st.markdown）
**涉及**: knowledge.py

### 3.3 Issue 批量操作
**目标**: 支持批量更新状态/分配
**涉及**: issues.py

### 3.4 排程甘特图增强
**目标**: 设备资源视图、导出甘特图图片
**涉及**: scheduler.py

---

## Phase 4 — 集成与完善（低优先级）

### 4.1 DQE Portal 集成
**目标**: app.py 入口模式判断 + 加入 dqe.sh 启动

### 4.2 数据桥写入
**目标**: 共享数据到 ~/.dqe-shared/

### 4.3 页面状态持久化
**目标**: 切换页面不丢筛选条件

### 4.4 性能优化
**目标**: lazy service 加载、分页、索引
