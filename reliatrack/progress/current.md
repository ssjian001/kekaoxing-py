# ReliaTrack 当前进度

**最后更新**: 2026-07-19
**Schema 版本**: v27 (20 张表)
**测试**: 553 passed (541 + 12 新增)
**覆盖率**: services 85% (+6pp)

## 当前状态

项目功能开发基本完成，进入稳定维护 + 性能优化阶段。

### 最近完成

- **测试计划工具栏重构** (2026-07-19):
  - 15 控件拆两行：管理+操作 / 搜索+筛选，逻辑分组 + 分隔线
  - 统一纯文字按钮风格，无图标/文字混搭
  - 摘要栏合并（今日工作摘要 + 任务统计合为一条）
  - 甘特图模式切换 QRadioButton → pills 按钮组

- **QSS 主题统一** (2026-07-19):
  - Tab 样式改为纯文字+底线条（Fluent 风格）
  - 表头加 hover 效果 + 排序箭头间距调整
  - 统一 sep-vline 分隔线 QSS class（5 tab 同步）
  - Pill 按钮组 QSS（甘特图模式、筛选模式等）
  - 空状态提示加 SVG 文档图标

- **效能 Profile** (2026-07-19): 1000 任务 + 5000 结果 profile 完成
  - DB 层最慢 ~19ms，Service 层 ~31ms
  - 唯一瓶颈 UI 渲染 `table.set_tasks(1000)` ~185ms，仍在无感范围
  - PRAGMA 配置完善：WAL + 64MB cache + NORMAL sync + 20 个索引

- **BackupService 测试补充** (2026-07-19): +4 个恢复场景测试
  - 配置文件不存在/损坏时的异常处理
  - 多表关联数据恢复完整性验证
  - 恢复失败时的安全回滚机制测试
  - 覆盖率 79% → 85%

- **ProjectService 级联删除测试** (2026-07-19): 新增独立测试文件 `test_project_cascade.py`
  - cascade_stats 准确统计（含空项目、不存在项目）
  - 级联删除正确清理 project → plan → task → result/sample/issue
  - 删除隔离性：A 项目不影响 B 项目数据
  - FK 级联 test_results 验证
  - 8 tests 全部通过

- **并发测试修复** (2026-07-19):
  - 修复多线程共享 Connection 的 ThreadingViolationError
  - 改为独立连接 + 临时文件 DB 的正确并发模式
  - 6 tests + --cov 全部稳定通过

### 已完成 (feature_list.json: 24/25 done)

- 25 个 feature 中 24 个 done，1 个 cancelled（国际化 i18n）
- 所有核心 CRUD + 导入导出 + 排程 + 撤销/重做

## 阻塞

无。

## 下一步

- 功能层：按需新增（待用户明确需求）
- 性能：当前 1000 行数据量无瓶颈，无需优化
- 稳定性：services 覆盖率 85%，export_utils(70%)/undo_manager(78%) 可考虑补充
