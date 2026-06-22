# ReliaTrack 当前进度

**最后更新**: 2026-06-22
**Schema 版本**: v23
**测试**: 380 passed

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

### 未完成 / 待处理

- **P1-2**：导出/导入主线程阻塞 → 需 QThread 异步化（ExportService 零 Qt 依赖，改造简单）
- **测试覆盖**：backup_service.py + import_service.py 无测试；FK 行为无测试验证
- **导出防御性检查**：低优先级，UI 层已隔离归档计划，导出层可后续加 plan.status 检查

## 阻塞

无。

## 下一步

启动应用验证仪表盘 + 归档隔离效果。
