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

## 2026-09-23 Pass/Fail 统一中文 (634f947)
- 仪表盘卡片 Pass→通过 / Fail→不通过; 测试进度卡图例 PASS/FAIL→通过/不通过
- 导出判定结论 export_utils: FAIL→不通过, PASS→通过, CONDITIONAL→条件接受(与 constants.py RESULT_LABELS 对齐)
- 全 src 已无用户可见 Pass/Fail 英文残留; 947 passed
- 待人工: 导出一份报告肉眼确认判定列文字

## 2026-09-23 业务逻辑层审计+修复 (7ed2230)
- P1批量改状态绕状态机漏洞: batch_dialog 改状态操作改调 transition_status, 被拒计入failed提示
- M1 undo/redo失败保护: main.py _on_undo/_on_redo 包 try, FK冲突弹友好提示而非全局错误窗, 命令回栈可重试
- M2 _auto_update_task_progress: 无结果时 skipped/paused 任务不再被拖回 pending
- 其余审计确认正常: 排程日历计算/出库防呆/事务原子性/SQL参数化/嵌套事务/删除级联/7300防死循环
- 测试: +2条回归(test_batch_status_machine) 全量 949 passed
- 待人工: 批量改状态实测一次(含非法转换被拒的提示)

## 2026-09-29 全量对抗审计修复（P0-1 / P2-x / P3-x，8 commit 已推送 origin/main）

**审计项 → 修复（每条都带回归测试）**

| commit | 审计项 | 关键修复 |
|---|---|---|
| `a06c6c5` | P0-1 | schema v11 重建/续跑原子化（迁移中断不再丢数据） |
| `87f8648` | P2-1/P2-2/P2-3/P3-1/P3-5 | 陈旧/损坏连接自愈（捕 `apsw.Error`）、附件白名单 `is_relative_to`、先删 DB 后删磁盘、未知字段不再静默丢弃、撤销冲突抛 `UndoConflictError` |
| `2d72f9a` | P2-7/P2-10/P2-14/P3-2/P3-6 | 导入单元格全类型兜底、批量导入补"入库"台账、编辑框不洗枚举外状态、台账"行+状态联动"两步写原子、holidays 非法行告警 |
| `d07ae03` | P2-4/P2-5/P2-6/P3-16/P3-18 | 体检线程独立连接、后台线程不跑迁移、报告 PDF 失败清半成品、导出取消改协作式退出（不再 `terminate`）、体检框关闭等扫描线程 |
| `8313e49` | P2-8/P2-11/P2-13/P3-11/P3-12/P3-15 | 刷新失败不静默、选中计划不重复查询、闪烁后恢复行底色、批量更新失败逆序回滚、去掉无效 `notify("result")`、启动只做一次全量加载 |
| `b192d36` | P3-3/P3-4/P3-7～P3-9/P3-17/P3-18 | 恢复后重启改进程退出时执行（原 `startDetached` 与 QLockFile 竞态恒失败）、自动备份同秒撞名递增序号、排程 `strptime` 加缓存、`user_locked_days` 锁住 `start_day=0`、docx 显式路径净化、空状态标签死代码、同列拖放写库/甘特滚轮劫持/结果弹窗「应用到全部」回退/出库手输操作人/看板卡片拖拽期被销毁 |
| `04fb2d0` | — | 回归测试集（P0-1 + P2-1..P2-14 + P3-1..P3-16）+ `ExportWorker` 协作式取消测试桩补齐 |
| 本次追加 | P3-10 | 任务状态软校验（详见下节） |

**P3-10 任务状态机 — 方案 A（软校验，只告警不拦截）**
- `src/constants.py` 新增 `TASK_TRANSITIONS`；`TestPlanService._warn_if_unusual_status_transition` 在 `update_task(status=...)` 时校验
- 刻意不做硬状态机：结果回算（`_auto_update_task_progress`）可产出 pending/completed/failed/in_progress **任意**目标、任务编辑对话框 5 状态自由选、批量菜单可跨状态批改、undo 按旧值反向写回 —— 硬约束会打断这些合法流程
- 矩阵未收的 3 条语义矛盾跳跃会打 WARNING（不阻断）：`completed→skipped`、`skipped→completed`、`skipped→failed`（编辑对话框/批量标记完成可达，属提示性告警）
- 枚举外状态值（如 `paused`）单独告警且**原样保留**（与 P1-6 语义一致）
- 软校验自身绝不抛异常（取任务失败/任务不存在都只 `logger.debug` 后放行）

**验证证据（2026-09-29）**
- 全量 `pytest tests/` = **1111 collected / 1111 passed / 0 failed / EXIT=0**（P3-10 追加后；P3-10 之前的基线是 1103，本次新增 8 条）
- 反向验证（防"测试放水"）：`src` 层 13 项逐条"撤销修复 → 对应测试必失败 → 还原后 sha256 一致"；他人批次用 sandbox（`git archive HEAD` 的**旧源码** + 当前 `tests/`）复跑 → 大量 FAILED / `UndoConflictError` 收集即 ERROR，证明修复真在源码改动里而非只在测试里
- P3-10 反向探针：现状 completed→skipped 告警 1 条且写入仍成功；去掉新代码 → 0 条；换成硬校验 → 抛异常（即方案 B 会打断写入）
- 推送核对：本地 HEAD == `git ls-remote origin refs/heads/main` == `1a13536`(P3-10) → `4fc4839`(文档)；7 commit 共 41 文件零 junk（无 `__pycache__`/`.log`/`.db`/`.env`）

**P3-10 软校验的作用边界（刻意如此，非疏漏）**
- 只覆盖经 `TestPlanService.update_task(status=...)` 的写入。绕过它的路径**不受校验**：undo/redo 按旧值写回、批量编辑保存、导入批次、迁移回填 —— 这些是"恢复/回填"语义，校验它们反而会产生误报。
- 代价：带 `status` 的单次更新会多一次 `get_by_id` 读库（SQLite 主键单条，可忽略）。

**待人工确认**
- [ ] P3-10 的 3 条提示性告警是否接受（任务编辑对话框"已完成 → 已跳过"会记 WARNING，不阻断）；不想看可放宽矩阵或降级为 DEBUG
- [ ] 审计报告把批量改状态归属写成 `issue_dialog.py`，但实际代码在 `bug_tracker/batch_dialog.py:145-170` 且已走 `transition_status` —— 确认无需再改
- [ ] UI 实测：甘特 Ctrl+滚轮缩放、看板卡片拖拽期间触发刷新、出库弹窗手输操作人
- [ ] `bd`（beads）本机未安装，AGENTS.md 的 `bd dolt push` 步骤本次跳过

---

## 2026-09-29（下）：文档/环境同步（neat-freak）

**发现并修复的真实断链**
- `init.sh` 用系统 `python3` 跑语法/schema/测试校验 → 系统解释器无 apsw/pytest/PySide6（实测 `ModuleNotFoundError`），脚本在 `set -e` 下第 2 步必然失败；且第 4 步读的是**仓库根**那份旧格式 `feature_list.json`。已改为 `../.venv/bin/python` + 读代码目录权威副本（dict 格式 `_meta`/`features`，并打印 last_updated/tests）
- 文档里的 `.venv/bin/...` 全部不可执行：**venv 在仓库根，不在代码目录**（正确写法是 `../.venv/bin/python`，已实测 Python 3.11.16 + PySide6 6.11.1 + `pytest --collect-only` 通过）。受影响：`README.md`、`reliatrack/README.md`、`docs/runbook.md`
- 数字过时：测试 738 → **1111**（runbook/README）；E2E 断言 57 → **53**（实测 `r.record(` 计数）；`docs/architecture.md` "Handler 12个类" → **11 个 Handler 类 + crud_helpers**（实测 `src/handlers` 11 个 `*Handlers`）
- 仓库根 `README.md` 由重复的功能/技术栈清单改为**指针**（指向 `reliatrack/README.md`），消除两份 README 数字打架
- `docs/runbook.md` 补 bd 适用性说明（Linux 侧无 bd，`.beads/` 数据由 Windows 端维护）

**已验证一致（无需改动）**
- runbook 的 `schema v28 / 20 张表` ✓（Python 解析 `schema.py` 计数，非 shell grep）
- 代码目录 `feature_list.json` `_meta` = schema 28 / 1111 passed / last_updated 2026-09-29 ✓
- 目录计数（2026-09-29 实测）：dialogs 30（含 `base_dialog.py`）、widgets 40（不含 `__init__`）、services 18、repos 11 + base、views 9、handlers 11

**未处理（需人工放行/决策）**
- `CLAUDE.md` / `AGENTS.md` 是 Hermes 写保护的 agent-instruction 文件（patch/write_file 均被拦，审批超时）。仓库根 `CLAUDE.md` 的"两份合并 + 数字校正 + 路径显式化"内容已备好但未落地；内层 `reliatrack/CLAUDE.md`（停留 08-22，含已失效的 CI-only bug 说明与旧 PyInstaller 命令）应改为指针
- 仓库根 `feature_list.json`（list 格式 v2.0.0，2026-08-30）是旧布局残留，与代码目录 dict 格式副本重复 → 建议删除，但要等 CLAUDE.md 的 `cat feature_list.json` 指引同步修改后再动
