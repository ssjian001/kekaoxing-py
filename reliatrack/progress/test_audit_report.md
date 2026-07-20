# ReliaTrack 测试套件健康评估报告

**日期**: 2026-07-20
**环境**: Linux, Python 3.13, 553 passed (46 warnings)
**分支**: explore/ui-ux-enhancements

---

## 1. 覆盖率分析（全局 54%）

### 覆盖率最低的 5 个模块

| # | 模块 | 覆盖率 | 代码行数 | 未覆盖行区间 |
|---|------|--------|---------|-------------|
| 1 | `src/styles/proxy_style.py` | **0%** | 249 行 | 3-249 (整文件) |
| 2 | `src/views/dialogs/schedule_preview_dialog.py` | **0%** | 569 行 | 10-569 (整文件) |
| 3 | `src/views/dialogs/schedule_report_dialog.py` | **0%** | 202 行 | 3-202 (整文件) |
| 4 | `src/views/dialogs/sample_select_dialog.py` | **0%** | 248 行 | 3-248 (整文件) |
| 5 | `src/views/dialogs/holiday_manage_dialog.py` | **0%** | 197 行 | 3-197 (整文件) |

**其他 < 60% 的关键模块**: filter_row.py (0%), import_tasks_from_plan_dialog.py (0%), test_result_dialog.py (10%), quick_create.py (12%), batch_edit_sample_dialog.py (13%), fa_record_dialog.py (14%), fa_capa_panels.py (25%), column_persistence.py (26%), task_table.py (22%), result_matrix.py (29%), theme.py (34%), animation.py (60%), kanban_view.py (58%), dashboard_view.py (58%), quadrant_view.py (58%)

**注意**: `test_low_coverage_modules.py` (417 行) 已覆盖部分模块（test_result_repo, settings_service, holiday_service, knowledge_repo, scheduler_service），但大量 dialogs/widgets/styles 仍裸奔。

---

## 2. 重复/失效测试

### 被跳过的整文件

| 文件 | 行数 | 原因 | 影响 |
|------|------|------|------|
| `test_e2e_full.py` | 539 行 | `pytestmark = pytest.mark.skip("Script-based E2E")` | ⚠️ 最大的测试文件被完全跳过 |
| `test_performance.py` | 232 行 | `pytestmark = pytest.mark.skip("Performance benchmark")` | ⚠️ 性能基准不被运行 |

### 可合并的冗余测试文件对

| 对 | 重叠分析 | 建议 |
|---|---------|------|
| `test_services.py` (435行) ↔ `test_e2e_full.py` (539行, SKIPPED) | 两者都测试 service CRUD（project/equipment/sample/issue），`test_e2e_full.py` 顺序编排 + MainWindow 构造，重度重叠 | **合并**: 将 `test_e2e_full.py` 中未覆盖的服务场景并入 `test_services.py`，删除源文件 |
| `test_session_20260512.py` (245行) ↔ `test_services.py` (435行) | `test_session_20260512.py` 测试 `import_tasks_from_plan()` / `table_exists()` / `_validate_schema_integrity()`，都是 Service 层功能 | **迁移 + 删除**: 将 3 个测试类移至 `test_services.py` 或 `test_low_coverage_modules.py` |
| `test_new_features.py` (346行) ↔ 多个已有测试 | "新增功能测试"命名暗示这是临时文件，内容分散 | **归并到对应模块**: 按功能拆入 `test_services.py` / `test_scheduler.py` / `test_todo.py` 等 |
| `test_boundary.py` (263行) ↔ `test_e2e_full.py` (539行, SKIPPED) + `test_services.py` | dialog 构造测试 + 边界场景，与 e2e 的 MainWindow 测试有重叠 | **保留**但可清理与 test_services.py 重复的 fixture 设置模式 |

### 孤儿 pycache
- **无** — 所有 `__pycache__/*.pyc` 都有对应的 `.py` 源文件。

### 无 `@pytest.mark.skip` 或 `xfail` 装饰器测试
- 但有两个模块级的 `pytestmark = pytest.mark.skip(...)`（见上）。

### 无注释掉的测试函数
- 搜索 `#.*def test_` 未命中。

---

## 3. 性能分析 — 最慢的 10 个测试

| # | 耗时 | 测试 | 文件名 | 分析 |
|---|------|------|--------|------|
| 1 | **2.02s** | `test_gantt_paint_perf` | test_gantt_perf.py | 甘特图渲染性能基准，合理偏高 |
| 2 | **1.03s** | `test_parallel_reads_independent_connections` | test_concurrency.py | 并发连接测试，涉及多线程 |
| 3 | **0.41s** | `test_plan_edit_dialog` (setup) | test_boundary.py | `AppController(':memory:')` + `MainWindow()` 构造开销 |
| 4 | **0.37s** | `test_export_service_file_generation` | test_boundary.py | 实际生成 PDF + Word 文件 |
| 5 | **0.11s** | `test_create_dialog_new` (setup) | test_todo.py | Dialog 测试 fixture 构造 |
| 6 | **0.10s** | `test_parallel_read_write_independent_connections` | test_concurrency.py | 并发读写 |
| 7 | **0.07s** | `test_bulk_insert_and_query` | test_concurrency.py | 大量数据插入 |
| 8 | **0.07s** | `test_export_8d_docx` | test_export_smoke.py | DOCX 导出渲染 |
| 9 | **0.04s** | `test_export_to_word` | test_export_smoke.py | Word 导出 |
| 10 | **0.04s** | `test_independent_connections` | test_concurrency.py | 连接隔离测试 |

**总运行时间**: 15.12s（553 passed）。若排除 test_boundary.py（0.78s 合计）和 test_concurrency.py 的并发测试（1.17s），核心测试在 **~13s** 内完成，可接受。

---

## 4. UI 重构覆盖缺口

### 检查结果：现有测试文件**未直接引用**被移除的 UI 属性

搜索了以下旧模式在所有 31 个测试文件中的引用：

| 被移除的旧 API | 测试文件中引用 | 风险 |
|----------------|---------------|------|
| `btn_add` | **0 处** — 但 src/handlers 中多处仍用 `btn_add.clicked.connect()` | 低风险 — `btn_add` 在 sample_view/todo_view 等中未移除 |
| `_filter_panel` / `DynamicFilterPanel` | **0 处** — `FilterPanel` 类本身仍存在且被 test_ui_integration.py 直接测试 | ✅ 无风险 |
| `btn_batch_import.clicked` / `btn_batch_edit.clicked` | **0 处** — 旧 `QPushButton` → 新 `QAction` 通过同名 property 兼容 | ✅ 向后兼容 |
| `_btn_archived` | **0 处** | ✅ 无风险 |
| `issue_view` (已合并) | **1 处** — `test_export_regression.py:176` Mock `_bug_tracker_view`，验证了旧路径重定向 | ✅ 已有回归测试 |

### 新 API 覆盖缺口

| 新增/重构的 API | 对应源文件 | 是否有测试覆盖 |
|----------------|-----------|-------------|
| `list_view._build_filter_row()` | bug_tracker/list_view.py | ❌ 无 |
| `list_view._clear_filters()` | bug_tracker/list_view.py | ❌ 无（test_ui_integration 测试的是 `FilterPanel._clear_filters`，不是 list_view 版本） |
| `list_view._apply_filters()` | bug_tracker/list_view.py | ❌ 无 |
| `todo_view._build_filter_row()` | todo_view.py | ❌ 无 |
| `todo_view._build_action_row()` | todo_view.py | ❌ 无 |
| `sample_view._btn_more` / `_more_menu` | sample_view.py | ❌ 无 |
| `test_plan_view._act_toggle_archived` | test_plan_view.py | ❌ 无 |

---

## 5. CI 失败测试

**test_boundary.py** — CLAUDE.md 记录：

> 已知 CI-only bug：test_boundary.py 在 CI 上 init_schema 返回空表，本地无法复现，CI 中 `--ignore` 跳过

- 当前本地运行 **通过** (553 passed)
- CI 中通过 `--ignore=tests/test_boundary.py` 规避
- **根本原因未修复** — 可能是 CI runner 环境差异（文件系统/权限/APSW 版本兼容性）

---

## 6. 按优先级排序的行动清单

### 🔴 P0 — 必须修复

1. **修复 test_boundary.py CI bug** — 这是唯一影响 CI 通道的问题。排查 CI 上 `init_schema` 空表原因（可能是 `scope="module"` fixture 在 CI 并行模式下被多个进程污染）。修复后移除 `--ignore` 标记。

2. **为 filter_row.py、filter_panel.py 等 widget 模块编写测试** — `filter_row.py` (0%) 是新 UI 重构的核心产出，无测试覆盖。`FilterPanel` 在 `test_ui_integration.py` 中有测试，但新增的 `_build_filter_row` / `_clear_filters` / `_apply_filters` 方法在 list_view.py 中未被测试。

### 🟡 P1 — 高优先级

3. **删除 test_e2e_full.py 和 test_performance.py 的 skip 标记或替换为可运行测试** — 539 行 + 232 行被永久跳过是测试债务。将 test_e2e_full.py 中仍有效的 service 测试合并到 test_services.py，然后删除文件。

4. **整合 session 临时测试** — 将 `test_session_20260512.py` (245行) 和 `test_new_features.py` (346行) 中的测试按功能归并到对应模块文件后删除。临时文件不应停留在主分支。

5. **为 0% 覆盖率的关键 dialog 编写 smoke 测试** — `holiday_manage_dialog.py`, `import_tasks_from_plan_dialog.py`, `sample_select_dialog.py`, `schedule_preview_dialog.py`, `schedule_report_dialog.py` 完全无覆盖。至少确保构造不崩溃。

### 🔵 P2 — 中优先级

6. **补充新增 UI API 的测试** — `list_view._build_filter_row()`、`todo_view._build_filter_row()` / `_build_action_row()`、`sample_view._btn_more` / `_more_menu`、`test_plan_view._act_toggle_archived` 均无测试覆盖。在 `test_ui_integration.py` 或新建文件中添加。

7. **提升 proxy_style.py (0%) → 至少 70%** — 这个文件负责 Qt proxy style 的自定义绘制，是主题系统核心。缺少覆盖意味着主题修改容易无声退化。

### 🟢 P3 — 低优先级

8. **清理重复 fixture 定义** — 多个测试文件（test_services.py, test_boundary.py, test_todo.py 等）各自定义了 `db_conn` / `issue_svc` / `sample_issue` fixture。共享到 `conftest.py` 可减少模板代码和设置时间。

9. **优化慢测试** — `test_gantt_paint_perf` (2.02s) 和 `test_boundary.py` 的 setup 阶段 (0.41s) 最耗时。考虑将 `AppController(':memory:')` 和 `MainWindow()` 的 `scope="module"` fixture 改为 `scope="session"` 以复用。

10. **建立测试覆盖率门槛** — 全局 54% 偏低。建议在 CI 中设置 `--cov-fail-under=60` 作为最低门禁，逐步提升到 70%。
