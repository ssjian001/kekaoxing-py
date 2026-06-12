# 综合修复清单 — 维度 1+2 共 10 个 bug

## Bug 组 A: 状态 selectbox 预置失效（4 个，同一根因）
根因: 构建 {中文→英文} 反向 dict 后，用英文值在中文键中查找 → None → fallback → 始终显示第一个

### A1. projects.py:101-113 状态切换
当前: status_opts = {v:k for k,v in PROJECT_STATUS_REVERSE.items()} → {中文:英文}
      current_label = status_opts.get(proj.status, proj.status) → 用英文 key "active" 查中文 dict → None
修复: 直接用 PROJECT_STATUS_REVERSE（en→zh），显示 values（中文），保存时用 keys 映射

### A2. equipment_technician.py:106-117 设备编辑状态
当前: status_rev = {v:k for k,v in EQUIPMENT_STATUS_LABELS.items()}
      cur_status_label = status_rev.get(eq.status, eq.status)
修复: 同上模式

### A3. issues.py:206-215 Issue 状态更新
当前: status_opts = {v:k for k,v in ISSUE_STATUS_LABELS.items()}
修复: 同上模式

### A4. test_plans.py:62 计划状态
当前: rev = {v:k for k,v in status_opts.items()}
      cur_label = rev.get(plan.status, ...) → 用英文查中文 dict
修复: cur_label = status_opts.get(plan.status, ...) 直接用 en→zh dict

## Bug 组 B: session_state 残留导致误操作（2 个）

### B1. projects.py confirm_delete_proj 切换项目后残留
修复: 在 selected_name selectbox 之前加: st.session_state.confirm_delete_proj = False

### B2. test_plans.py confirm_delete_plan 切换计划后残留
修复: 在 plan_name selectbox 之前加: st.session_state.confirm_delete_plan = False

## Bug 组 C: issues.py 批量操作（2 个）

### C1. 翻页后 data_editor 选中状态索引错乱
修复: 在翻页按钮中清除 iss_table session state: del st.session_state["iss_table"]

### C2. 全选使用非公开 API
修复: 改为修改 DataFrame 的选择列默认值，而非直接操作 session_state

## Bug D: UX 缺陷（1 个）

### D1. projects.py 保存修改无改动时无反馈
修复: if not upd: st.info("没有需要保存的修改")

## Bug E: 低优先级（1 个）

### E1. _shared.py STATUS_COLORS 计划部分不完整
修复: 补 in_progress 和 completed
