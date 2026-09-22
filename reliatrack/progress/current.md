# ReliaTrack 进度 — 2026-09-03 (修复归档视图崩溃 + 本机环境重建)

## 本次完成

| commit | 内容 |
|---|---|
| `14dc65b` | fix: 补 TestPlanService.get_archived_plans_by_project，修复归档视图崩溃 |

## Bug 修复详情

**现象**：Windows 端勾选"显示归档计划"开关时 AttributeError:
`'TestPlanService' object has no attribute 'get_archived_plans_by_project'`

**根因**：main.py:832 调用 `get_archived_plans_by_project()`，但 service/repo 只实现了
`get_active_plans_by_project`（镜像方法缺失），属于"调用存在但实现缺失"的静默断点。

**修复**（3 文件，+60 行）：
- `src/db/repositories/test_plan_repo.py` — 新增 `get_archived_by_project`（SQL 层 `status='archived'` 过滤）
- `src/services/test_plan_service.py` — 新增 `get_archived_plans_by_project`（转发 repo）
- `tests/test_handlers.py` — 新增 `TestArchivedPlansByProject` 回归测试（2 用例：active/archived 互斥过滤 + 空归档不崩溃）

## 本机环境重建（Linux/ThinkPad X250）

- venv：`kekaoxing-py/.venv`（Python 3.11.16）
- 依赖：`requirements.lock.txt` + pytest + pytest-qt + pytest-cov（CI 同款组合）
- 注意：**必须装 pytest-qt**，否则 qapp fixture 缺失 → 部分 UI 测试 ERROR，
  且 Qt 状态异常引发 QProgressDialog 段错误（已踩坑确认因果）
- 必须设 `QT_QPA_PLATFORM=minimal`（X250 无显示输出；offscreen 平台在
  batch_import_dialog.py:387 QProgressDialog 处有段错误 bug，minimal 正常）

## 验证证据

- `pytest tests/ -q` 全量 938 tests，exit=0 全绿（minimal 平台，2026-09-03）
- `py_compile` 三文件通过
- 历史已对齐：本地 main = origin/main(d93b297) + 1 fix commit(14dc65b)，无分叉

## 待办 / 阻塞

- [ ] git push 需凭证：本机 SSH key 是 hermes-config 专用 deploy key（对
  kekaoxing-py 无权限）；需用户提供 GitHub PAT（写入 key.md）或把
  ~/.ssh/hermes_deploy.pub 加为账号级 SSH key
- [ ] Windows 端同步此修复（git pull 或手补三文件）
- [ ] 用户真机验证：勾选"显示归档计划"开关不再崩溃、归档计划正确过滤显示

## 2026-09-19 仪表盘"已完成"语义修正 + Pass 卡片
- 问题：仪表盘"已完成"= status=completed，不含 failed 任务；用户要求"已完成"= 做完的测试（Pass+Fail 都算做完）
- 改动：refresh_handlers.py 新增 task_done=completed+failed 填入 DashboardData；dashboard_view.py 加 task_done 槽、左栏 KPI 4卡→5卡（已完成/Pass/进行中/待开始/Fail），Pass 卡=pass_count（结果维度）；Fail 卡 jump "fail"→"failed"（原值在 filter combo 不存在，跳转静默失效，顺手修复）
- 验证：py_compile 通过；pytest 938 passed
- 待人工：UI 实际点一次卡片跳转确认

## 2026-09-22 显示层审计修复批次（7项）
- P1①环形图 task_map 补 paused（原暂停任务扇区消失）②SeverityBar 接通（原死代码, 有数据无UI）
- P1③plan_summary 已完成口径统一 =completed+failed（与仪表盘 task_done 一致）
- P2④DashboardData 删恒None死槽 pass_rate_trend/capa_trend（其余4槽保留, handler已填）
- P2⑤样品表状态列上色（复用 SAMPLE_STATUS_COLORS + resolve_status_color, 补 QColor import）
- P2⑥删 done 幽灵枚举值; compute_summary 超期口径补跳过 failed（两函数一致）
- P2⑦fa_capa_panels 25+13+14 处繁体→简体（用户可见文案+docstring）
- 验证: pytest 938 passed；已推送 371afce
- 待人工: UI 双主题各看一眼 severity bar 与样品状态色

## 2026-09-23 优化批次：KPI 自检 + 搜索防抖
- ④ KPI 自检：src/services/kpi_audit.py — 8 项 DashboardData 一致性断言（状态求和=total、task_done=completed+failed、done/failed≤total、pass/fail非负、closed≤total Issue、weekly≤closed、pass_rate∈[0,100]、None安全），违规 logger.warning + 首次toast(每会话限1次防刷屏)
- ② 任务表搜索防抖：test_plan_view textChanged→QTimer单触发300ms，程序化恢复不延迟
- 测试：tests/test_kpi_audit.py 9条；全量 947 passed；推送 3add1a5
- 待人工：UI 实测搜索输入手感（300ms 是否合适）+ 人为弄脏数据看 toast 是否触发
