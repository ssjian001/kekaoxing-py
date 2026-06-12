# 功能缺陷修复清单

共 8 个问题，按严重度排序。

---

## Bug 1 [高] samples.py 出库状态守卫用错值
- **文件**: pages/samples.py 行 121
- **问题**: `sel.status not in ("available", "returned")` — DB 存的是 `"in_stock"` 不是 `"available"`
- **影响**: 所有在库样品出库被拦截（状态永远不匹配 "available"），出库功能完全失效
- **修复**: `"available"` → `"in_stock"`

## Bug 2 [高] 仪表盘饼图显示英文状态值
- **文件**: pages/dashboard.py 行 59-66, 74-82
- **问题**: 饼图 labels 直接用 `s.status`（"in_stock"/"checked_out"/"open" 等英文），用户看到的是英文代码
- **影响**: 仪表盘不可读
- **修复**: 用 SAMPLE_STATUS_LABELS 和 ISSUE_STATUS_LABELS 翻译成中文

## Bug 3 [中] 仪表盘项目列表状态也显示英文
- **文件**: pages/dashboard.py 行 99
- **问题**: `rename={"status": "状态"}` 但值还是英文 "active"/"paused" 等
- **修复**: 用 PROJECT_STATUS_REVERSE 或映射翻译

## Bug 4 [中] samples.py 操作区 selectbox 用全量 samples 而非搜索过滤后
- **文件**: pages/samples.py 行 111
- **问题**: `sample_ids = {f"{s.sn}...": s for s in samples if s.id}` — 这里的 `samples` 是搜索过滤后的（正确），但操作区应该在分页外展示全量可操作对象
- **影响**: 搜索过滤后，操作区的 selectbox 只显示过滤后的样品，用户可能想操作不在当前搜索结果中的样品
- **修复**: selectbox 用全量样品列表（另取一份 `all_samples`）

## Bug 5 [中] test_plans.py col_plan3 空列
- **文件**: pages/test_plans.py 行 57
- **问题**: `col_plan1, col_plan2, col_plan3 = st.columns(3)` — col_plan3 无任何内容
- **修复**: 改为 2 列，或给 col_plan3 加"编辑计划名称"功能

## Bug 6 [中] 技术员只有删除，无编辑功能
- **文件**: pages/equipment_technician.py 行 189-201
- **问题**: 设备有编辑（名称/位置/状态），但技术员只有删除，无编辑姓名/工号/职位等
- **修复**: 在技术员操作区增加编辑表单（类似设备的编辑区）

## Bug 7 [低] samples.py 分页状态未在搜索/新增后重置
- **文件**: pages/samples.py
- **问题**: 搜索关键词变化或新增样品后，page_samples 可能停留在旧页码，超过新总页数
- **修复**: 虽然已有 `if page > total_pages` 回拉，但搜索变化时 page 应重置为 1

## Bug 8 [低] test_plans.py 删除计划无确认
- **文件**: pages/test_plans.py 行 73-78
- **问题**: 删除计划直接调用 `delete_plan()`，无确认提示，可能误删含任务的计划
- **修复**: 参考 projects.py 的 session_state 确认模式

---

## 修复规范
- 不运行 streamlit
- 不改 service/repo 层
- 每个文件改完 `python -m py_compile` 验证
- 全部改完 `.venv/bin/python -m pytest -q --tb=short` 确认 341 passed
