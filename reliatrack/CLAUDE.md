# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
.venv/bin/python3 main.py           # 启动应用
QT_QPA_PLATFORM=offscreen .venv/bin/python3 tests/test_e2e_full.py  # E2E 测试
.venv/bin/python3 -m pytest tests/ -v  # 单元测试
```

### 数据库

```bash
.venv/bin/python3 migrate.py     # 手动运行 pending migrations（通常启动应用时自动执行）
```

### 项目结构

```
src/
├── constants.py   # 全局常量
├── controllers/   # 页面控制器（AppController）
├── db/
│   ├── connection.py
│   ├── repositories/   # 数据访问层（repo 模式）
│   └── schema.py        # SQLite schema 初始化
├── handlers/      # 信号处理器（9个 Handler 类）
├── models/        # 数据模型
├── services/      # 业务逻辑层
├── styles/        # QSS 样式
└── views/          # Qt 视图 + dialogs/
```

## 架构说明（2026-05-06 更新）

### Tab 结构（7 个 Tab，含快捷键索引）

| 索引 | Tab | 视图文件 |
|-----|-----|---------|
| 0 | 📊 仪表盘 | dashboard_view.py |
| 1 | 📁 项目管理 | project_view.py |
| 2 | 📦 样品管理 | sample_view.py |
| 3 | 📋 测试计划 | test_plan_view.py |
| 4 | 🐛 Issue 追踪 | issue_view.py |
| 5 | 🔧 设备管理 | equipment_view.py + technician_view.py |
| 6 | 📚 知识库 | knowledge_view.py |

### Handler 层（9 个 Handler）

project/sample/plan/issue/equipment/knowledge/technician/refresh + 全局快捷键在 main.py

### 导出服务

- `export_service.py`（AppController.export_service）：8D 报告 PDF 导出（reportlab + CJK 字体）
- 信号链：issue_view `_on_export_8d` → `export_8d_requested` signal → `issue_handlers._handle_export_8d`
- CAPA 写入：`issue_view capa_record_added` → `issue_handlers._handle_capa_record_added` → `issue_service.add_capa_record`（列名白名单校验）

### 排程引擎

- `scheduler.py`（546行）：3阶段算法（greedy → left-shift → report），拓扑排序+资源约束
- `scheduler_service.py`：DB 读写封装，支持 skip_weekends/skip_holidays/lock_existing
- 排程报告弹窗：`schedule_report_dialog.py`（利用率条形图+瓶颈+建议）

### 仪表盘 KPI

- 12 个 KPI 卡片（任务/Issue/设备/样品/通过率/闭环率/失效率/CAPA完成率等）
- 3 个 QPainter 条形图（任务状态/样品状态/Issue 严重度）
- 校准到期预警列表（最多 5 条，30 天内到期设备）
- DashboardData 封装 17 个参数

### Schema（v13）

- **v13**：修复 v11 迁移丢失的 20 个索引，schema_version 加 UNIQUE，v12 迁移加事务包裹
- **v12**：修补迁移链遗漏列（samples.notes、equipment.asset_no/manufacturer/accuracy）
- **v11**：FK ON DELETE SET NULL + CASCADE 完善，表重建方式迁移（`_rebuild_table` 辅助函数）
- **v8-v10**：设备校准、样品字段、测试结果、假期表等增量迁移
- **SELECT \***：全部消除，所有查询使用显式列名
- **base.py**：空字符串→0 int 防御 + ESCAPE 子句修复 + search() 模糊搜索修复
- **issue.py**：priority/occurrence_count 防御性类型转换（str→int）
- **Dashboard refresh**：16参数封装为 `DashboardData` 数据类

### 数据库路径

- 生产 DB: `data/reliatrack.db`（由 `app_controller.py` 指定）
- 备份: `data/backups/reliatrack_YYYYMMDD.db`
- 连接: apsw，WAL 模式，FK 约束启用

### 测试覆盖

- `tests/test_e2e_full.py` — E2E 测试 56 项（需 `QT_QPA_PLATFORM=offscreen`）
- `tests/` 目录下按模块分，测试 repo 层和 service 层
- 使用 `pytest` + `pytest-xvfb`（CI 无头环境）
