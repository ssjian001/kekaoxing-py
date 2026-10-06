# ReliaTrack 交接文档（2026-10-06）

> 写给接手这份代码/会话的人。先读根目录 `CLAUDE.md` 与 `reliatrack/AGENTS.md`；这里是到当前为止的「现场快照」。

## 1. 项目定位

- **是什么**：可靠性测试全生命周期管理系统，PySide6 + SQLite（apsw）桌面应用。
- **代码目录**：`reliatrack/reliatrack/`（仓库根 `.venv` 在外层，**命令一律在代码目录下执行**）。
- **技术栈**：Python 3.11 + PySide6 6.11 + apsw；schema v29，20+ 张表；`bd`(beads) 在 Linux 侧未安装，不用它。

## 2. 当前状态（2026-10-06）

- 全量测试：**1136 passed / EXIT=0**（约 46s）。
- 所有审计项已修清零：`start_day` 哨兵化（schema v29）、排程 cycle 冻结、ExportWorker 线程安全、导出 None 崩溃、undo/redo 状态机穿透、样品台账一致性等均已处理。
- Git：本地 `main` 已推送到 `origin/main`（HEAD 约 `a1bb053`），工作区干净。

## 3. 本次会话干了什么

| commit | 内容 |
|---|---|
| `a479169` | UI 实测三项脚本 `tests/manual/verify_ui_3items.py`（甘特 Ctrl+滚轮、看板卡片拖拽 isValid 守卫、出库手输操作人）9/9 |
| `a514931` | 审计 P0×3：8D 导出参数错位、命令面板 backup 动作、损坏库恢复堵死 + 回滚 WAL 清理 |
| `f2f1fd5` | P1/P2×15：QThread 遮蔽 finished、Word 技术员列、export None 崩溃、aql conditional 吞结论、图表负宽、frozen 重启双 exe、备份权限 0600 等 |
| `5717866` | 导出协作式取消、恢复重启先确认关窗、`max_scan_days` 配置化、`auto_schedule` 清零防线、cycle 计入 total_days |
| `ea501a3` | **`TestTask.start_day` 哨兵重构**：`None=未排期`、v29 表重建 + 存量 0→NULL（manual_scheduled=0） |
| `a1bb053` | 多模块审计：履历入口崩溃、样品编辑写流水、aging 锚点、weekly_closed DISTINCT、undo 系列表全部 + 1130→1136 |

## 4. 运行方式

```bash
cd ~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack        # 仓库根
.venv/bin/python -m pytest reliatrack/tests/ -o addopts= # 全量
python3 reliatrack/main.py                             # 启动（有 DISPLAY 时）
# Qt 无头验证 / 脚本：
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/manual/verify_ui_3items.py
```

- pytest 不要加 `-q`（`pytest.ini` 的 addopts 已含 `-q`，叠加会变 `-qq` 吞掉 summary 行）；判全绿看最后一行 `N passed`。
- Lang：提交信息全中文，消息末附数量变更点。

## 5. 重要约定（踩过坑）

1. **改 Tab 结构=全局改魔法数字索引**：`_StatCard(`、`search_map`、`setCurrentIndex(`、`card_clicked` 都要一起同步。
2. **就地编辑必须走写 DB 路径**，不能复用弹窗回调（会导致 modal 冲突直接崩）。
3. **新增 `set_*/setup_*` 方法必须追到真实调用点**验证，定义了但没人调等于静默失效。
4. **QThread 不要用 deleteLater 在未结束时**；ExportWorker 已改用内建 `finished` 驱动 deleteLater。
5. **Qt 对象不准跨线程共享**（`connection.py` 明令）：内存库场景的体检已同步到主线程执行。
6. **`bd` 在这台 Linux 机器没装**，issue/任务进度以 `reliatrack/progress/current.md` + `feature_list.json` 为准。
7. 备份/恢复测试现有 `restored_id` 语义已固化（undo 实际恢复的 id 供 redo 删除），不要回改。

## 6. 数据/Schema 现状

- `SCHEMA_VERSION = 29`：`test_tasks.start_day` 可空，NULL 即未排期；`schema_version` 表记录 28→29 的迁移（表重建 + `0 & manual_scheduled=0 → NULL`）。
- 全局 DB 默认路径 `~/.reliatrack/reliatrack.db`；迁移在启动时自动执行，失败会整体回滚可重试。
- 全部测试均在 `:memory:` 或临时文件库上跑，无需依赖真实库。

## 7. 未收尾（刻意保留）

- **DB corrupt 时的 `DbCorruptDialog`** 已可从备份恢复，但不要再回退修改它的中止路径；损坏库走裸文件拷贝安全网。
- **`_empty_report` schema** 已对齐正常报告（`skipped_cycle_tasks` / `unschedulable_tasks` / `technician_utilization`）。
- 尚未修（无明确缺陷单）：看板 closed 折叠用 `updated_at` 属于刻意口径；aging 已改用 `created_at` 作为未变更状态的初始锚点。

## 8. 日常操作手册

- **新增功能**：先在根目录 `CLAUDE.md` 找架构约定；`src/` 三组件（view/handler/service/repo）模式保持一致；涉及颜色样式的改动，亮/暗双主题各确认一次。
- **改了测试**：必须跑全量 `pytest -o addopts=`，全绿才能提交。
- **升级数据库**：修改 `src/db/schema.py`（新 `SCHEMA_VERSION` + `_migrate_vNN`），旧库在下次启动自动重放。
- **新的交接**：在本文件末尾追加一行 commit 和结论，不要覆盖旧行。

---

*生成于 2026-10-06；如果你只看这一句：品牌是 Python 3.11 + PySide6 的本地工具，1136 个绿色测试,别把 `start_day=0` 再当未排期哨兵（改用 `None`）。*
