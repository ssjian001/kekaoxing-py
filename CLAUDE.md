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

- Python 3.11+（CI: 3.11/3.12, 本地开发: 3.13）+ PySide6 6.11.1 + apsw (SQLite) + openpyxl / reportlab
- 架构：MVC 变体 — Controller → Handlers → Services → Repos → DB
- DB 版本：schema v27（20 张表）
- 主题：Catppuccin Latte 明亮 / Mocha 暗黑 (theme.py，明暗切换已完整支持)

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
      test_task_repo.py, todo_repo.py
  handlers/             # UI 事件处理层
    crud_helpers.py     # 通用 CRUD 辅助
    equipment_handlers.py, export_handlers.py, issue_handlers.py,
    knowledge_handlers.py, plan_handlers.py, project_handlers.py,
    refresh_handlers.py, sample_handlers.py, technician_handlers.py,
    todo_handlers.py
  models/               # 数据模型（dataclass）
    common.py, issue.py, knowledge.py, project.py,
    sample.py, test_plan.py, todo.py
  services/             # 业务逻辑层
    export/             # 导出子模块（PDF/Word/Excel）
    export_service.py   # 导出入口（零 Qt 依赖）
    import_service.py   # 批量导入
    issue_service.py, knowledge_service.py,
    project_service.py, sample_service.py,
    scheduler.py, scheduler_service.py,
    settings_service.py, technician_service.py,
    test_plan_service.py, todo_service.py, undo_manager.py
  styles/
    constants.py        # 颜色/尺寸常量
    theme.py            # 主题定义
    toast.py            # Toast 通知
    column_persistence.py  # 列宽持久化
  views/
    dashboard_view.py   # 仪表盘
    equipment_view.py, issue_view.py（已合并至 bug_tracker, 保留向后兼容）, knowledge_view.py,
    project_view.py, sample_view.py, technician_view.py,
    test_plan_view.py, todo_view.py
    bug_tracker/        # Issue 管理系统（看板+列表+FA+CAPA 面板，schema v23 合并重构）
      __init__.py       # BugTrackerView 主容器（看板/列表 Tab 切换）
      kanban_view.py    # 4列拖拽看板（aging色块/closed折叠/状态机约束）
      list_view.py      # 增强列表（筛选面板/批量操作/列宽持久化）
      detail_dialog.py  # 详情弹窗（5Tab: 详情+评论+活动+FA+CAPA）
      quick_create.py   # 快速创建弹窗（C键触发）
      resolve_dialog.py # 关闭流程（resolution强制选择）
      shortcuts.py      # 快捷键管理（C/Ctrl+N/Ctrl+K/←→）
    dialogs/            # 对话框（26 编辑/配置/待办对话框）
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

- **SpinBox/ComboBox 按钮样式**：`app.setStyleSheet()` 完全覆盖 `QProxyStyle.drawComplexControl`（CC_SpinBox 拦截根本不执行，已实测验证）。SpinBox 按钮必须用 QSS `::up-button`/`::down-button`/`::up-arrow`/`::down-arrow` 子控件样式。当前方案：SpinBox 透明底 + FG_PRIMARY 双杠(上)/单杠(下)（border 模拟），hover 用 BG_HOVER；DateEdit/TimeEdit/ComboBox 不覆盖子控件样式，保持 Fusion 默认
- QPushButton 设 `background: transparent; border: none` 在 Windows 上不可见 → 必须有可见背景和边框
- QLockFile: Qt5 `setStaleLockTimeout(ms)` → PySide6 6.x `setStaleLockTime(ms)`
- **QSS 不支持 #RRGGBBAA 8 位 hex**（如 `#1e66f515` 无效）→ 必须用 `rgba(r,g,b,a)`
- **`QSS ::indicator` 与 QProxyStyle 不能共存** → 必须从 theme.py 删除所有 `::indicator` 块让 ProxyStyle 全权绘制
- **QToolButton class 选择器**：`QPushButton[class="action"]` 不匹配 QToolButton，需逗号分隔同时写两个
- **theme.py `globals().update()` 注入色板变量**：Pyright 对 `_build_qss()` f-string 中的变量报 "not defined" 误报，忽略即可
- **Catppuccin Latte CRUST ≠ `#dc8a78`**（那是 ROSE），正确值 `#DCE0E8`（最浅灰）
- **`setProperty("row-state", ...)` 等 QSS 动态属性**：已渲染控件改动态属性后必须 `style().unpolish(self); style().polish(self)` 强制 Qt 重算选择器，否则视觉不更新
- **`from src.styles.theme import GREEN` 冻结快照**：`globals().update()` 不更新其他模块已导入的变量，必须用 `import src.styles.theme as _t` + `_t.GREEN` 动态引用
- **QPalette 不跟随 setStyleSheet 更新**：QSS 只覆盖匹配选择器的控件，QCalendarWidget / QComboBox popup / QScrollArea viewport 等原生子控件 fallback 到 QPalette。主题切换时必须调用 `apply_palette()` 同步 QPalette ColorRole → 当前色板
- **Windows 暗色系统主题污染**：`QWindowsVistaStyle` 从 Windows 系统主题读取暗色 palette，覆盖 `setPalette()` 效果。必须用 `QStyleFactory.create("Fusion")` 作为 base style（跨平台一致，完全遵循 QPalette），再用 `CheckboxProxyStyle(fusion)` 包一层

## 启动工作流（每次会话开始必做）

1. `cat progress/current.md` — 读取上次进度
2. `cat feature_list.json` — 确认当前功能状态
3. 验证环境：`cd reliatrack && .venv/bin/python -m pytest tests/ -x -q | tail -5`
4. 如果 progress 中有未完成任务，从断点继续

## 完成定义（Definition of Done）

一个功能"完成"必须满足全部 5 项：

1. ✅ `python -m py_compile` 语法检查通过
2. ✅ `python -m pytest tests/ -x -q` 相关测试通过
3. ✅ `git diff` 审查无敏感数据泄露
4. ✅ `feature_list.json` 中对应功能 status 更新为 `"done"`
5. ✅ 验证证据记录（测试输出/截图）写入 progress/current.md

## 范围规则

- **一次一个功能** — 完成当前功能（验证通过 + feature_list 更新）后才能开始下一个
- **不越界** — 不修改当前功能范围外的代码，除非用户明确要求
- **不擅自移动/删除 UI 元素** — 除非用户明确要求
- **依赖顺序** — 查看 feature_list.json 的 dependencies 字段，先做被依赖的功能

## 会话交接

每次会话结束前：
1. 更新 `progress/current.md`（当前状态/下一步/阻塞）
2. 更新 `feature_list.json`（已完成→done，进行中→in_progress）
3. `git add -A && git commit -m "feat: <描述>"`
4. 回答三个问题：产物在哪？什么可复用？什么需人工确认？
