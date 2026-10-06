# ReliaTrack 进度

> **会话开始必读。**结构/约定的权威文档是仓库根 `../CLAUDE.md`，本文件只记「做到哪了 + 还欠什么」。
> 2026-09-03 ~ 09-23 的已完成批次已归档至 `progress/archive/current-2026-09-03_to_09-23.md`。

## 未决事项（跨日期汇总，先看这里）

- [x] **P3-10 三条提示性告警是否接受**（已确认 2026-10-03）：保留 WARNING，软校验只提醒不拦截为刻意设计，矩阵不放宽、不降级
- [x] **审计报告与代码归属不符**（已核实 2026-10-03）：批量改状态确走 `transition_status`，代码在 `src/views/bug_tracker/batch_dialog.py:149-152`，**代码侧无需修改**；`docs/audit-2026-05-*.md` 中未见该错配，仅本文件曾记过 —— 已消项
- [x] **UI 实测三项**（已验证 2026-10-06）：甘特 Ctrl+滚轮缩放、看板卡片拖拽期间触发刷新、出库弹窗手输操作人 —— 全部通过，取证脚本 `tests/manual/verify_ui_3items.py`（9/9，offscreen 平台 + QTest 语义注入事件）
- [x] `bd`（beads）本机未安装（已核实 2026-10-03）：`AGENTS.md` 第 74-77 行已明确 Linux 侧全跳过 `bd *`，本项已文档化，无需再动
- [x] **2026-10-06 P0 审计修复 3 条**（`a514931`）：①8D 导出参数错位（`_export_8d` 签名补 `plan_id` 占位）②命令面板 backup 动作指向不存在的方法 → 改调 `_backup_handlers._on_data_manage()` ③损坏库恢复被恢复前 apsw 安全备份堵死 → 回退裸文件拷贝；顺手修回滚路径未清 `-wal/-shm`。回归测试 +4（`tests/test_audit_p0_20261006.py`），全量 1115 绿

### 待修（中危/低危，2026-10-06 审计记录）

- [ ] 排程：cycle 任务 `start_day` 被清零且预览路径抹回 DB；`start_day=0` 双重语义（未排期 vs 排在起始日）导致 auto_schedule 防线误拒（`start_day` 未排期哨兵化未做）；「重新排程」隐式强制 lock_existing 已修（2026-10-06 第二批）；cycle 任务冻结当前排期（Phase 1a 占位、不清零、不左移）已修
- [ ] ExportWorker 遮蔽 QThread.finished + deleteLater 竞态已修（`done` 信号改名，deleteLater 只挂内建 finished，2026-10-06 第二批）；Word 导出技术员列已对齐真名；`_judge_conclusion` 吞 conditional 已修；取消不中断导出待定；任务 duration/start_day 为 NULL 时导出崩溃已修
- [ ] 恢复重启 frozen 模式多一层 argv、撤销确认被 quit() 架空、备份文件权限未收紧、`_empty_report` schema 缺 key、`find_earliest_slot` 硬编码 365 天上限、排程报告 total_days 不含 cycle 占用（`a514931` 起：frozen argv / 权限 / `_empty_report` 已修 2026-10-06 第二批；`find_earliest_slot` 365 上限与 total_days 失真待定；撤销确认框语义需真实 GUI 环境确认）

---
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
- [x] UI 实测：甘特 Ctrl+滚轮缩放、看板卡片拖拽期间触发刷新、出库弹窗手输操作人（2026-10-06 已由 `tests/manual/verify_ui_3items.py` 验证 9/9）
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

**已解决（2026-09-29 晚，用户授权后落地）**
- ✅ 仓库根 `CLAUDE.md` 与内层 `reliatrack/CLAUDE.md` 完成**并集合并**：根 = 唯一权威（补入内层独有的 4 条 Qt 坑 + 结构树细节；保留根侧更新的 CI 结论与 `ReliaTrack.spec` 打包命令；修正 `.venv` 解释器路径、测试命令去掉 `-x`）；内层改为指针（含 cwd/解释器说明与关键路径表）。守恒核对：两份旧文件共 93 条实质条目，26 处差异**全部为有意替换**，无知识丢失
- ✅ `AGENTS.md` 在 Beads 自动生成块（`BEGIN/END`）之后补 Linux 无 `bd` 的适用说明，未触碰自动块内容
- ✅ 仓库根 `feature_list.json`（旧 list 格式 v2.0.0，2026-08-30）**已删除**：仓库内零代码/脚本/CI 引用；内容经逐条核对是代码目录 dict 副本的**严格子集**（23 vs 25 条目，无独有 id）。恢复：`git checkout 4d6b532 -- feature_list.json`

---

## 2026-09-29（晚）：`init.sh` 真跑暴露 P3-4 测试的时序竞态（已修）

**现象**：`init.sh` 第 3 步真跑全量时（16:43，`DISPLAY=:0`）首个失败即停：
```
FAILED tests/test_p3_audit_fixes.py::TestP34AutoBackupSameSecond::test_two_backups_in_same_second_both_succeed
AssertionError: 撞名应加序号后缀: reliatrack_20260929_164358.db
```

**根因**：`create_auto_backup()` 用 `datetime.now().strftime("%Y%m%d_%H%M%S")`（**秒级**）生成文件名，撞名时才追加 `_1/_2`。测试连调两次并**隐含假设两次落在同一秒**；高负载下两次调用跨秒 → 第二次本就该拿新时间戳 → 断言失败。**生产代码的撞名重试逻辑正确，问题在测试。**

**修复**：`tests/test_p3_audit_fixes.py` fixture 内冻结 wall clock（`monkeypatch.setattr(bs, "datetime", _FrozenDatetime)`，`now()` 恒返回 `2026-09-29 16:43:58`）。撞名路径由"碰运气命中"变为 100% 覆盖，且不再依赖调度时序；生产代码零改动。

**验证证据**
- 单跑 3 次 `2 passed`；全量真跑 **exit 0**（⚠️ 本轮原记"`-q` 看到 1111 passed"**不实** —— 见下节：本仓库 `-q` 实为 `-qq`，根本没有 summary 行；正确判据 = exit code + `--collect-only` 计数）；逐文件计数求和 = **1111**，与进度点（15×72+31）一致
- **反向探针**（key 证据）：临时把"序号后缀重试循环"替换为单次尝试（= 修复前行为）→ 两个测试**同时 FAILED（`FileExistsError`）**；还原后 `sha256` 与探针前一致（`1c98d865…`）。证明冻结时间后测试**仍有区分度**，不是靠放宽断言换来的绿
- 同类隐患全目录扫描：仅此一处有"同一秒/同一时刻"假设；其余 `datetime.now()` 均为 past/future 相对偏移

**教训**：①新增测试不得依赖 wall clock（用 monkeypatch 冻结时间）；②`init.sh` 带 `set -e` 且 pytest 带 `-x`，首个失败即停会隐藏后续失败，判断"是否全绿"必须真跑全量并看 exit code；③`pytest -q | tail -N` 会把 summary 行挤掉，取证要落文件再 grep —— **并且见下节：本仓库的 `-q` 本身就是 `-qq`**。

---

## 2026-09-29（深夜）：neat-freak 第二轮 —— 验证方法本身失效

**⚠️ 最大发现：文档记的"看 summary 判全绿"在本仓库从未生效**

`pytest.ini` 有 `addopts = -q`；文档里照抄的 `pytest tests/ -q` 实际是 **`-qq`** → 进度点照打，但 **summary 行（`N passed`）完全消失**。全量跑几分钟只看到一串点，容易被当成"没输出=正常"。受影响位置：DoD 第 2 条、启动工作流第 4 步、根 `README.md`、`docs/runbook.md`。

**修复后的正确姿势（均实测）**
- 全量判据：`../.venv/bin/python -m pytest tests/`（不带 `-q`）→ 末行 `1111 passed in 69.41s` + `EXIT=0`
- 快速环境检查：`--collect-only -o addopts= -q | tail -1` → `1111 tests collected in 0.97s`
- 教训：**文档里的耗时同属腐败源** —— 原写"约 5 分钟"，实测 **69 秒**

**本轮其他修复**
- 根 `README.md` 的全量测试命令仍带 `-x`（与 CLAUDE.md 去 `-x` 规则矛盾）→ 已去除并加两条警示
- 启动工作流第 4 步原为 `pytest tests/ -q | tail -5`，正是 skill 记录过的"summary 被挤掉"反面教材 → 已改
- 根 `CLAUDE.md` handlers 目录树样例只列 10 个，与"11 个 Handler 类"不符 → 补 `backup_handlers.py`
- `progress/current.md` 瘦身：159 行 / 14.6KB → **92 行 / 10.2KB**；2026-09-03~09-23 的 4 个已完成批次外迁 `progress/archive/current-2026-09-03_to_09-23.md`（含一条**已失效**的"push 需凭证"待办，归档头已注明失效原因：现用 ssjian001 账号级 key）；**未决事项已汇总到本文件顶部**

**计数口径澄清（防下轮误判）**
- `src/handlers` = 12 个 .py = **11 个 `*_handlers.py` + `crud_helpers.py`** → 文档写"11 个 Handler 类 + crud_helpers"**正确**，不是笔误
- dialogs 30 含 `base_dialog.py`；widgets 40 不含 `__init__`；services 18；views 9

**本轮核对为一致（无需改动）**
- `docs/runbook.md`：schema v28 / 20 张表 / `../.venv` 路径 / Linux 无 `bd` 说明 ✓
- `docs/architecture.md`：v28 + "11 个 Handler 类 + crud_helpers" ✓
- `feature_list.json` `_meta`：schema 28 / 1111 passed / 2026-09-29 ✓；全仓引用均指向代码目录副本，无指向已删的仓库根副本
- `progress/current.md` 的相对路径 `cat feature_list.json` 在 cwd = 代码目录下有效 ✓
- 无相对时间词残留（"今天/最近"）= 0 ✓
