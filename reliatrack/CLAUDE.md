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
├── handlers/      # 信号处理器（9个 Handler 类，含 export_handlers）
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

project/sample/plan/issue/equipment/knowledge/technician/refresh/export + 全局快捷键在 main.py

### 导出服务

- `export_service.py`（AppController.export_service）：8D 报告 PDF/Word 导出（reportlab + python-docx）
- `export_handlers.py`：统一导出入口，支持按项目筛选（`_get_issues`/`_get_samples` 按 project_id 过滤）
- `export_dialog.py`：导出选项对话框（内容类型 + 格式 + 项目筛选下拉）
- 8D Word：`export_8d_docx()` — 结构与 PDF 一致（基本信息表、D1-D8 章节、签字栏），格式选择对话框
- 信号链：issue_view `_on_export_8d` → `export_8d_requested` signal → `issue_handlers._handle_export_8d`（弹出 PDF/Word 选择）
- CAPA 写入：`issue_view capa_record_added` → `issue_handlers._handle_capa_record_added` → `issue_service.add_capa_record`（列名白名单校验）
- CAPA 编辑/删除：`capa_record_edited`/`capa_record_deleted` 信号 → `issue_handlers._handle_edit_capa`/`_handle_delete_capa` → service.update/delete
- CAPA 负责人：自由文本输入（`assignee_name`），非下拉选择
- CAPA PDCA：`root_cause`（根因分析）/`effectiveness`（效果验证）/`follow_up`（改善追踪），Schema v15 新增

### Issue 视图

- 表格 9 列：ID/标题/严重度/状态/优先级/DRI/根因/解决方案/创建时间
- FA + CAPA 面板左右等宽排列（`QHBoxLayout`），各带标题标签
- **Issue ↔ FA/CAPA 双向联动**（`issue_handlers._sync_issue_from_fa` / `_sync_issue_from_capa`）：
  - FA 添加 → 状态 `open`→`analyzing`；确认的根因（confirmed=1）回写 `root_cause`
  - CAPA 变更 → 汇总 action 到 `resolution`；全部 completed/verified → `analyzing`→`verified`
  - 状态只进不退（`verified` 不会自动回退）
- 甘特图任务标签格式：`1. 任务名`（序号前缀）

### 测试计划视图

- `_TaskTable`：13 列（#, 名称, 类别, 天数, 预计开始, 预计结束, 进度, 优先级, 状态, 技术员, 通过率, 实际开始, 实际完成），# 列显示数据库 ID
- `_GanttWidget`：支持预计/实际日期切换（`_task_day_range` 方法，RadioButton 切换），实际模式下禁拖拽；标签列 8pt 字体、260px 初始宽度、可拖拽分隔线调节、hover tooltip
- `_ResultMatrixWidget`：任务×样品矩阵 + 行统计列（通过率）+ 列统计行 + 右下角总计
- 依赖编辑：弹出式对话框（QListWidget checkbox 多选），按排程排序 + 当前任务参照行，保存时校验自依赖和 ID 有效性

### 排程引擎

- `scheduler.py`（546行）：3阶段算法（greedy → left-shift → report），拓扑排序+资源约束
- `scheduler_service.py`：DB 读写封装，支持 skip_weekends/skip_holidays/lock_existing
- 排程报告弹窗：`schedule_report_dialog.py`（利用率条形图+瓶颈+建议）

### 仪表盘（v2 — 现代企业 SaaS 风格）

- **布局**: QScrollArea + 浅灰背景(#F7F8FC) + 白底圆角卡片(16px)
- **Header**: 项目/计划筛选标签 + 最后更新时间
- **测试进度卡片**(`_TestProgressCard`): `_StackedBar` 堆叠条(PASS绿+FAIL红+进行中黄+待开始灰) + 图例 + 2辅助(通过率/最后更新)
- **左栏(测试执行)**: 3 KPI `_StatCard`(已完成/进行中/待开始) + `_DonutChart`环形图(右侧垂直图例)
- **右栏(质量与问题)**: 4 KPI `_StatCard` + 2× `_ProgressRing`(100px) + `_SeverityBar`严重度分段条
- **配色**: 5 语义色映射 Catppuccin Latte (PRIMARY/SUCCESS/WARNING/DANGER/NEUTRAL)
- **卡片样式**: `card_qss()`/`add_shadow()` 提升至 `constants.py` 全局复用
- **组件**: `_StatCard` / `_TestProgressCard` / `_StackedBar` / `_DonutChart` / `_ProgressRing` / `_SeverityBar`
- **DashboardData**: 22 字段，含 pass_count / fail_count / last_update
- **自动创建 Issue**: 测试结果为 fail 时可选自动创建（title=任务名, severity=MAJOR）
- **刷新机制**: FA/CAPA 增删改后 `notify_data_changed("issue")` 触发仪表盘刷新

### 全局样式（SaaS 风格统一）

- **色值**: BASE=#F7F8FC(浅灰背景), MANTLE=#FFFFFF(白底卡片), SURFACE0=#F1F5F9(输入框), TEXT=#1E293B(深色文字)
- **圆角**: QGroupBox 12px, 输入控件/按钮 8px, Tab 6px, 卡片 12-16px
- **工具函数**: `card_qss(radius=12)` 和 `add_shadow(widget)` 在 `constants.py`，供所有 Tab/Dialog 复用

### Schema（v16）

- **v16**：Issue 加 `dri_name`（DRI 责任人自由输入）；CAPA 加 `verifier_name`（验证人自由输入）；测试结果保存时可自动创建 Issue
- **v15**：CAPA PDCA 扩展 — capa_records 加 `root_cause`/`effectiveness`/`follow_up` 三字段；CAPA 编辑/删除 UI；`count_capa_done` SQL bug 修复（`'done'`→`'completed'`）
- **v14**：capa_records 加 assignee_name（责任人自由文本）；test_tasks 安全补列（dependencies/accept_criteria 等 9 列，防旧库缺失）
- **v13**：修复 v11 迁移丢失的 20 个索引，schema_version 加 UNIQUE，v12 迁移加事务包裹
- **v12**：修补迁移链遗漏列（samples.notes、equipment.asset_no/manufacturer/accuracy）
- **v11**：FK ON DELETE SET NULL + CASCADE 完善，表重建方式迁移（`_rebuild_table` 辅助函数）
- **v8-v10**：设备校准、样品字段、测试结果、假期表等增量迁移
- **SELECT \***：全部消除，所有查询使用显式列名
- **base.py**：空字符串→0 int 防御 + ESCAPE 子句修复 + search() 模糊搜索修复
- **issue.py**：priority/occurrence_count 防御性类型转换（str→int）
- **Dashboard refresh**：`_collect_dashboard_data()` 收集 → `DashboardData` 封装 → `dashboard.refresh()` 推送（SaaS 风格 v2）；任务加载用 SQL 过滤（`get_by_plan`/`get_tasks_by_project`），非全表

### 数据库路径

- 生产 DB: `data/reliatrack.db`（由 `app_controller.py` 指定）
- 备份: `data/backups/reliatrack_YYYYMMDD.db`
- 连接: apsw，WAL 模式，FK 约束启用

### 安全机制（2026-05-08 审计）

- **SQL 列名注入**：`base._safe_kwargs()` 过滤非法列名；各 repo 有独立白名单（`_TXN_SAFE_COLS` 等）
- **XML 颜色注入**：`export_service._set_cell_shading()` 用 `re.fullmatch(r"[0-9A-Fa-f]{6}")` 校验
- **路径遍历**：`_validate_output_path()` 校验 resolve 后路径在允许目录内
- **原子性**：出库操作用 `repo.transaction()` 包裹；scheduler 用 `deepcopy` 隔离原始对象
- **附件完整性**：`shutdown()` 时 `scan_attachment_integrity()` 检查 DB 记录 vs 磁盘文件，缺失/孤立写入日志
- **Column tuple**：`_TXN_COLS`/`_FA_COLS`/`_ATTACH_COLS`/`_CAPA_SELECT_COLS` 为 tuple（单一真相源）
- **审计报告**：`docs/audit-2026-05-08.md` — 完整修复记录 + P2 待修清单

### 测试覆盖

- `tests/test_capa_pdca.py` — 9 项 CAPA PDCA（v15 迁移 + CRUD + count bug 修复）
- `tests/test_security_regression.py` — 36 项安全回归（P0/P1 修复点）
- `tests/test_services.py` — 20 项 Service 层 CRUD
- `tests/test_new_features.py` — 16 项新增功能
- `tests/test_column_order.py` — 11 项列序映射
- `tests/test_boundary.py` — 7 项 Dialog 构造 + 边界场景
- `tests/test_e2e_full.py` — 脚本式 E2E（需 `QT_QPA_PLATFORM=offscreen`，pytest 已 skip）
- `tests/test_performance.py` — 性能基准（pytest 已 skip）
- 共 **115 个 pytest 测试**，全量通过
- `conftest.py` 提供 `:memory:` 数据库 fixture

### 架构优化进展（2026-05-09）

16/22 项已完成：P3/P7-P11/P14-P17/P18-P22。P4 跳过。
剩余 6 项（P1/P2/P5/P6/P12/P13）已完成侦察，Phase 1-4 计划就绪，Phase 1 cron 已安排。
