# CLAUDE.md — ReliaTrack (kekaoxing-py/reliatrack/)

项目：可靠性测试全生命周期管理系统（PySide6 + SQLite）。

## 运行

```bash
cd ~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack
python3 -m venv .venv  # 首次
.venv/bin/pip install -r requirements.txt  # 首次
.venv/bin/python3 main.py
```

- PyInstaller 打包：`cd reliatrack && pyinstaller main.py --name ReliaTrack`
- 测试：`cd reliatrack && python -m pytest tests/ -x -q`

## 技术栈

- Python 3.11 + PySide6 + apsw (SQLite) + openpyxl / reportlab
- 架构：MVC 变体 — Controller → Handlers → Services → Repos → DB
- DB 版本：schema v17（16 张表）
- 主题：Catppuccin Latte 明亮 (theme.py)

## 项目结构

```
reliatrack/
main.py                 # 入口（含 DB 路径逻辑）
migrate.py              # DB 迁移工具
src/
  configs/              # 测试类型模板
  constants.py          # 状态标签、枚举映射（全局唯一来源）
  controllers/
    app_controller.py   # 应用主控制器
  db/
    connection.py       # SQLite 连接管理
    schema.py           # DDL + 版本管理（SCHEMA_VERSION）
    repositories/       # 数据访问层（Repo 模式）
      base.py           # BaseRepo 基类
      equipment_repo.py, issue_repo.py, knowledge_repo.py,
      project_repo.py, sample_repo.py, settings_repo.py,
      technician_repo.py, test_plan_repo.py, test_result_repo.py,
      test_task_repo.py
  handlers/             # UI 事件处理层
    crud_helpers.py     # 通用 CRUD 辅助
    equipment_handlers.py, export_handlers.py, issue_handlers.py,
    knowledge_handlers.py, plan_handlers.py, project_handlers.py,
    refresh_handlers.py, sample_handlers.py, technician_handlers.py
  models/               # 数据模型（dataclass）
    common.py, issue.py, knowledge.py, project.py,
    sample.py, test_plan.py
  services/             # 业务逻辑层
    export/             # 导出子模块（PDF/Word/Excel）
    export_service.py   # 导出入口（零 Qt 依赖）
    import_service.py   # 批量导入
    issue_service.py, knowledge_service.py,
    project_service.py, sample_service.py,
    scheduler.py, scheduler_service.py,
    settings_service.py, technician_service.py,
    test_plan_service.py, undo_manager.py
  styles/
    constants.py        # 颜色/尺寸常量
    theme.py            # 主题定义
    toast.py            # Toast 通知
    column_persistence.py  # 列宽持久化
  views/
    dashboard_view.py   # 仪表盘
    equipment_view.py, issue_view.py, knowledge_view.py,
    project_view.py, sample_view.py, technician_view.py,
    test_plan_view.py
    dialogs/            # 对话框（15+ 编辑/配置对话框）
    widgets/            # 自定义控件
      analysis_widget.py, gantt_widget.py,
      result_matrix.py, task_table.py
tests/                  # pytest 测试套件
```

## 核心业务规则

- **DB 路径**：dev 模式优先 `data/reliatrack.db`，fallback `~/.reliatrack/`；PyInstaller 固定 `~/.reliatrack/`
- **排序安全**：`setSortingEnabled(True)` 后必须用 `UserRole` 存 ID，通过 ID 查找而非索引
- **导出零依赖**：ExportService 不依赖 Qt，可在 headless + `:memory:` DB 环境下自动化测试
- **Schema 第一**：改 SQL 前先读 `schema.py`，确认列名和版本

## 开发规范

- **语法先行**：每写完一个文件立即 `python -m py_compile` 验证
- **提交单位**：每个逻辑单元单独 commit
- **编辑模式**：用 patch 不用 write_file，除非文件结构大幅改变
- **会话结束必须 git push**（见 AGENTS.md）

## Issue 跟踪

使用 **bd (beads)** 进行 issue 跟踪。详见 `AGENTS.md`。
```bash
bd ready              # 查找可用工作
bd show <id>          # 查看详情
bd update <id> --claim  # 认领
bd close <id>         # 完成
bd dolt push          # 同步
```

## CI/CD

- GitHub Actions：ci.yml (3.11/3.12 matrix) + release.yml (PyInstaller, tag v* 触发)
- 已知 CI-only bug：test_boundary.py 在 CI 上 init_schema 返回空表，本地无法复现，CI 中 `--ignore` 跳过

## 已知 Qt 坑

- 全局 QSS padding 侵占 QSpinBox 按钮 → QSpinBox 必须单独处理，padding 2px 4px
- QPushButton 设 `background: transparent; border: none` 在 Windows 上不可见 → 必须有可见背景和边框
- QLockFile: Qt5 `setStaleLockTimeout(ms)` → PySide6 6.x `setStaleLockTime(ms)`
