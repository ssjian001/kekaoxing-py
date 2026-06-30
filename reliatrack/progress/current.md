# ReliaTrack 当前进度

**最后更新**: 2026-06-29
**Schema 版本**: v25 (20 张表，含 todos)
**测试**: 381 passed

## 当前状态

项目功能开发基本完成，处于稳定维护阶段。

### 最近完成

- **仪表盘 Bug 修复** (2026-06-22):
  - `pending_count` 变量覆写修复（待开始 = 任务 pending，非 Issue pending）
  - `_card_fail` 改用 `failed_task_count`（任务状态层面），与已完成/进行中/待开始同源
  - `count_by_status` 边界 case：项目无计划时返回空集，不扫描全量
  - 左侧 section context 小字提示（项目/计划归属清晰）

- **删除计划 → 归档** (2026-06-22):
  - 计划管理菜单「删除计划」改为「归档」，任何状态可归档
  - 归档不改任何级联数据（Issue/任务/FA/CAPA/样品全部保留）
  - 归案后可取消归档恢复

- **归档计划数据全面隔离** (2026-06-22):
  - `issue_repo.get_by_project` → LEFT JOIN test_plans 排除历史计划 Issue
  - `issue_repo.count_by_severity/status` → 同上 JOIN
  - `issue_repo.count_capa_all/done` → 同上 JOIN
  - `test_task_repo.count_by_status` → `AND status != 'archived'`
  - Issue 列表/看板/仪表盘/导出/全部数据源已审计，无泄漏
  - commit: `1c5245a`, `86e3309`, `5eeb62b`, `ecaafd6`

- **导出异步化** (2026-06-29): export_handlers 新增 ExportWorker(QThread) + QProgressDialog，大型导出不再冻结 UI
- **N+1 查询优化** (2026-06-29): `_export_issues` 改用批量接口 `get_fa_records_by_issue_ids` + `get_capa_records_by_issue_ids`（issue_repo / issue_service 新增，handler 调用）
- **issue_activity_log 加 project_id** (2026-06-29): v24 schema 迁移，仪表盘 weekly_closed 按项目筛选
- **看板拖拽可撤销** (2026-06-29): 新增 TransitionIssueStatusCommand + UndoManager.record() 方法
- **批量操作用 record()** (2026-06-29): list_view 直接 push _undo_stack 改为 record()，清理 redo_stack
- **get_by_task/get_by_sample 加 archive 过滤** (2026-06-29): 同步 get_by_project 的 archive plan 排除逻辑
- **PDF/Word 列顺序一致** (2026-06-29): docx 任务表 "进度→状态" 与 PDF 对齐

### 未完成 / 待处理

- **备份/导入 测试覆盖**：backup_service.py + import_service.py 无测试

## 阻塞

无。

## 下一步

启动应用验证仪表盘 + 归档隔离效果。
