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
.venv/bin/python3 -m pytest tests/ -v  # 运行测试
.venv/bin/python3 -m mypy src/       # 类型检查
```

### 数据库

```bash
.venv/bin/python3 migrate.py     # 手动运行 pending migrations（通常启动应用时自动执行）
```

### 项目结构

```
src/
├── configs/       # 页面配置（configs.yaml 等）
├── constants.py   # 全局常量
├── controllers/   # 页面控制器
├── db/
│   ├── connection.py
│   ├── repositories/   # 数据访问层（repo 模式）
│   └── schema.py        # SQLite schema 初始化
├── handlers/      # 全局信号处理器
├── models/        # Pydantic 请求/响应模型
├── services/      # 业务逻辑层
├── styles/        # QSS 样式
└── views/          # Qt 视图（.ui + 绑定逻辑）
```

## 架构说明（2026-05 recent）

### Schema（2026-05-04）

- **v12**：修补迁移链遗漏列（samples.notes、equipment.asset_no/manufacturer/accuracy）
- **v11**：FK ON DELETE SET NULL + CASCADE 完善，表重建方式迁移
- **v8-v10**：设备校准、样品字段、测试结果、假期表等增量迁移
- **SELECT \***：全部消除，所有查询使用显式列名
- **base.py**：空字符串→0 int 防御，避免 type mismatch warning
- **Dashboard refresh**：16参数封装为 `DashboardData` 数据类

### 数据库路径

- 生产 DB: `data/reliatrack.db`（由 `app_controller.py` 指定）
- 备份: `data/backups/reliatrack_YYYYMMDD.db`
- 连接: apsw，WAL 模式，FK 约束启用

### 测试覆盖

- `tests/` 目录下按模块分，测试 repo 层和 service 层
- 使用 `pytest` + `pytest-xvfb`（CI 无头环境）
- 70 个测试通过（排除 e2e/boundary/performance 需 GUI 环境）
