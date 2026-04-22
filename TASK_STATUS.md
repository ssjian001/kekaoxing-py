# 可靠性测试甘特图 — 任务状态

> 每次恢复工作时，先读取此文件。

## 项目概览

- **项目名称**: 可靠性测试甘特图 (kekaoxing-app / kekaoxing-py)
- **技术栈**: Python 3.11 + PySide6 + apsw (SQLite) + pytest
- **项目路径**: `/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py`
- **虚拟环境**: `source .venv/bin/activate`
- **启动命令**: `python main.py`
- **测试命令**: `QT_QPA_PLATFORM=offscreen python -m pytest tests/`
- **代码规模**: 31 文件, ~13,580 行, 7 张数据库表

## 当前状态: 🟢 稳定

**最后更新**: 2026-04-22 (易用性提升 14 项)
**测试**: 133/133 passed (0.66s)
**核心逻辑覆盖率**: 76%–100% (后端), 0% (GUI 层)

---

## 已完成的工作

### 2026-04-22 自动化测试体系搭建

1. **全局 fixtures** (`conftest.py`) — db(:memory:), sample_tasks, sample_resources, sample_sections
2. **测试文件** (7 个):
   - `tests/test_database.py` — 任务/资源/Section CRUD + issue/test_result
   - `tests/test_scheduler.py` — 拓扑排序 / 贪心放置 / 左移压缩
   - `tests/test_project_io.py` — 导出导入 round-trip + 关联数据重映射 + 合并模式
   - `tests/test_data_validator.py` — 依赖冲突 / 资源超载 / 工时异常 / 孤立任务
   - `tests/test_undo_manager.py` — 6 种命令类型 + 50 步历史 + redo
   - `tests/test_models.py` — Task/Resource 默认值 + 字段验证
   - `tests/test_auto_save.py` — 快照创建 / 恢复 / 最大数量限制
3. **覆盖率**:
   | 模块 | Stmts | Cover |
   |------|-------|-------|
   | `models/__init__.py` | 91 | 100% |
   | `database.py` | 267 | 90% |
   | `undo_manager.py` | 125 | 89% |
   | `data_validator.py` | 106 | 97% |
   | `project_io.py` | 110 | 85% |
   | `scheduler.py` | 284 | 80% |
   | `auto_save.py` | 143 | 76% |

### 2026-04-22 功能修复 + 改进

- **P0**: 样品池编辑/删除按钮、`_quick_progress` 走 UndoManager、快照恢复 UI 入口（工具栏💾）
- **P1**: PDF/打印导出白色背景、5 文件 `except:pass` 补 logging、Dashboard dirty flag 缓存
- **小修**: ResourceDialog 空名称校验、StatsPanel `completed→done`、`_on_reset` 清理全部 6 表、section_manager key 唯一性
- **新增**: ResourceDialog 不可用时段编辑器（表格编辑开始天数/结束天数/原因）
- **重构**: 统一主题色常量 → `src/styles/colors.py`（21 色 Catppuccin 色板 + BASE_QSS），3 widget 已迁移

### 关键 Bug 修复

1. **`auto_save.py` backup() 方向** — apws `dst.backup("main", src, "main")` 第一个参数是目标库名，第二个是源连接。3 处全部写反
2. **快照时间戳精度** — 同秒调用 `create_snapshot` 会覆盖，添加 `_XXXXXXXX` 微秒后缀
3. **快照只读打开** — `restore_snapshot` 用 `SQLITE_OPEN_READONLY` 避免 WAL 模式创建空 -wal/-shm
4. **`compress_schedule` 依赖丢失** — start_day=0 的依赖关系被跳过

### 已修改文件清单

```
src/views/resource_view.py      — 空名称校验 + 样品池编辑删除 + 不可用时段编辑器
src/views/gantt_view.py          — _quick_progress 走 UndoManager
src/views/main_window.py         — 快照恢复按钮 + PDF 白色背景
src/widgets/stats_panel.py       — completed→done 字段名
src/widgets/section_manager.py   — key 唯一性校验
src/widgets/task_tags.py         — 导入 colors.py
src/core/project_io.py           — except 补 logging
src/core/auto_save.py            — backup 方向修正 + restore 用 backup + 微秒后缀
src/core/scheduler.py            — except 补 logging
src/core/data_validator.py       — except 补 logging
src/widgets/excel_import_dialog.py — except 补 logging
src/widgets/issue_tracker.py     — except 补 logging
src/styles/colors.py             — 新建，21 色 + BASE_QSS
```

---

## 2026-04-22 易用性提升 (14 项 P0+P1)

### P0 — 核心交互

1. **工具栏 tooltip + 快捷键** — 17 个按钮全部添加 tooltip，10 个添加快捷键 (Ctrl+N/O/S/T/E/I/P, F5 等)
2. **撤销/重做 UI 按钮** — 工具栏新增 ↩️↪️ 按钮，enabled 状态实时同步 UndoManager
3. **Tab 快捷切换** — Alt+1~5 快速跳转 5 个 Tab
4. **耗时操作进度反馈** — 排程 QProgressDialog (indeterminate)、PDF/打印状态栏提示、Excel 导入 QProgressDialog (确定性)
5. **表单实时验证** — TaskEditor (编号+名称)、SectionEditor (key 唯一性 debounce 300ms)、ResourceDialog (名称非空)

### P1 — 体验优化

6. **甘特条拖拽调整工期** — 右边缘 ±5px 拖拽改变 duration，走 UndoManager
7. **表格列头排序** — 甘特图任务表、资源表启用 setSortingEnabled
8. **资源搜索/筛选** — 样品池+设备表格上方添加搜索框，按名称/分类过滤
9. **状态栏增强** — 永久项目路径标签 + 选中任务信息 + 操作状态提示
10. **空列表引导** — 5 个视图 (甘特图/Issue/资源/看板/拖拽) 空状态时居中引导文字
11. **错误提示友好化** — 6 处 str(e) 替换为 _friendly_error_msg (区分 FileNotFoundError/PermissionError 等)
12. **批量操作扩展** — 右键菜单新增"批量修改分类"+"批量修改优先级"
13. **数据联动** — Issue 表格双击跳转甘特图、Dashboard 任务双击跳转甘特图
14. **甘特图英文搜索** — _apply_filter 支持 name_en 匹配

### 修改文件 (易用性)

```
src/views/main_window.py      — tooltip/快捷键/撤销按钮/状态栏/错误提示/数据联动/QLabel+QInputDialog导入
src/views/gantt_view.py        — 工期拖拽/表格排序/英文搜索/空状态/批量操作(分类+优先级)/选中信号
src/views/resource_view.py     — 搜索框/表格排序/空状态/表单验证
src/widgets/task_editor.py     — 实时验证
src/widgets/section_manager.py — key唯一性验证 + QWidget导入修复
src/widgets/issue_tracker.py   — 表格排序/空状态/双击跳转
src/widgets/dashboard.py       — 空状态/双击跳转
src/widgets/resource_drag_view.py — 空状态
src/widgets/scheduler_dialog.py — 排程进度条
src/widgets/excel_import_dialog.py — 导入进度条
src/widgets/template_library.py — @property→普通方法修复
```

## 待办事项 (按优先级)

### P1 — 建议尽快处理

- [ ] **排程异步化** — 当前 scheduler 在主线程运行，100+ 任务时卡 UI，需 QThread 重构
- [ ] **主题系统迁移** — colors.py 已建但仅 3/12 文件迁移，剩余 widget 仍硬编码颜色

### P2 — 可选改进

- [ ] **Dashboard 查询优化** — 5 个 chart 可共享 DB 查询结果，减少重复 IO
- [ ] **模板数据外置** — default_data.py 500 行硬编码，可抽 JSON
- [ ] **ScheduleMode.DEADLINE** — ResourceView 有枚举但无输入框

### P3 — 长期

- [ ] **GUI 集成测试** — 当前只测后端逻辑，未测 widget 交互（需 xvfb）
- [ ] **覆盖率提升** — `auto_save.py` 76%、`scheduler.py` 80% 可继续补

---

## 关键技术备忘

- **apsw backup() 正确用法**: `destination_connection.backup("main", source_connection, "main")`
- **Section 枚举值小写**: `Section.ENV.value == "env"`
- **Task/Resource 需要 id**: `Task(id=0, num="1", ...)`
- **Database 关闭**: 无 `close()` 方法，用 `db.conn.close()`
- **快照文件名**: `kekaoxing_snapshot_YYYYMMDD_HHMMSS_XXXXXX.db`（6 位微秒）
- **offscreen 测试**: `QT_QPA_PLATFORM=offscreen` 必须在 `import PySide6` 前设置

---

## 功能清单 (完整)

- 7 张数据库表: tasks, resources, test_results, sections, issues, snapshots, schedule_log
- 5 个主 Tab: 甘特图 / 资源池 / 仪表盘 / 问题跟踪 / 统计
- 17 个工具栏按钮
- 6 种导入导出: Excel / CSV / JSON / PDF / 打印 / 快照
- 3 阶段排程算法: 拓扑排序 → 贪心放置 → 左移压缩
