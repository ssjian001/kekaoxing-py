# 任务: Phase 2.1 — 全页面搜索/筛选增强

## 目标
给 6 个 CRUD 页面增加搜索框，支持模糊匹配过滤。保留现有 issues 页的状态/严重度筛选。

## 涉及文件 (reliatrack/pages/)
- `projects.py` — 无搜索，项目列表上方加 st.text_input(placeholder="搜索项目...")
- `samples.py` — 无搜索，样品列表上方加
- `test_plans.py` — 无搜索，任务列表上方加
- `issues.py` — 已有状态/严重度 multiselect，保持，下面加搜索框
- `equipment_technician.py` — 无搜索，设备/技术员列表上方各加
- `knowledge.py` — 已有 keyword 搜索框（service 层调用 search），保持

## 实现方式
### 方案 A: 前端过滤（简单，推荐）
```python
search_term = st.text_input("🔍 搜索...", placeholder="输入关键词过滤...", key="search_xxx")
filtered = [item for item in data if search_term.lower() in (item.name or "").lower()
            or search_term.lower() in (item.sn or "").lower() ...]
```
在页面顶部、操作区域之前加。不影响已有表单/操作。

### 方案 B: Service 层搜索（knowledge 已用方案）
调用 `svc["xxx"].search(keyword)` — 已有实现。

## 每个页面的搜索字段
- projects: name, product, customer
- samples: sn, batch_no, spec, supplier
- test_plans: name, test_standard
- issues: title, failure_mode (在 multiselect 下方加)
- equipment: name, model, location, asset_no
- knowledge: 已有方案 B，不动

## 验收标准
1. 搜索框在 CRUD 区域上方，不影响侧边栏表单
2. 输入关键词后 DataFrame 实时过滤
3. 空搜索=显示全部
4. 不修改原有 service/repo 层代码（纯前端过滤）
5. python -m py_compile 通过
6. pytest -q 341 passed 零回归

## 不用做的事
- 不要运行 streamlit
- 不要改 _shared.py
- 不要改 service/repo 层
