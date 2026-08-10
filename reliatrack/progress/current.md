# ReliaTrack 当前进度

**最后更新**: 2026-08-10
**Schema 版本**: v28 (20 张表)
**测试**: 668+（全量回归待确认）
**Widgets**: 42 | **Dialogs**: 28

## 当前状态

2026-08-10 六维度全量审计修复完成（P0×2 + P1×14 全部处理，R3-P2 死代码清理中）。

### 最近完成（2026-08-10 审计修复批次，8 commits 待 push）

- **P0 类别值域统一 (ca9d8ce)**: schema v28 迁移（环境→环境试验/力学→机械试验/电测→其他），
  实测 12 条任务转换；combo findText 失败保留原值不再静默改写；undo/redo 按命令实体分发刷新
- **P1 修复批次 (b0386b8)**: 设备/技术员删除静默失败弹窗提示；样品删除阻止物理级联清除软删
  Issue（count_by_sample_all）；CAPA 全局 KPI 过滤 is_deleted；热力图去掉 random 假数据改
  接真实任务引用数；排程 max_scan 超限返回 None 不再静默违反约束
- **undo 异常安全 (498ab96)**: undo/redo 失败命令不丢失压回原栈；批量操作改走
  MacroCommand+UpdateFieldCommand 一次入栈整体撤销；+3 行为测试
- **Issue 回收站 UI (8f11d6a)**: 更多菜单→回收站，list_deleted/restore/delete 接线，
  软删 Issue 不再永久不可见
- **备份恢复加固 (6b4ba8c)**: validate_backup 加 integrity_check + 17 核心表校验；
  恢复前安全备份失败改为中止恢复（保护生产库）；安全备份文件名加毫秒防碰撞
- **看板↔列表筛选双向同步 (835682e)**: set_filters 真正应用入参 + filter_changed emit
- **搜索历史 chips 接线 (131fb4c)**: save_search_keyword 接入 _on_task_search
- **R3-P2 死代码清理 (dc77b59)**: 4 视图死信号 + todo toggle 死链路删除；
  _on_batch_value 对非真实 UndoManager 直接执行（修 test_handlers 回归）

### 待办

- [ ] (可选) restore_sort_state 刷新重放 — 幂等冗余保留(改动风险>收益)
- [ ] (可选) 批量导入非原子 — best-effort 设计保留, 汇总已显示
- [x] 已接线: Issue 关联 UI(detail_dialog 6 Tab) + 待办提醒(60s 轮询)
      + 校准提醒(启动检查) + 技术员容量配置 + equipment location 列

### 最近完成

- **测试升级 (2026-08-10, 2deed84)**: tests/test_reminders.py 27 个测试覆盖
  Issue 关联 UI(交互/异常/软删/自引用) + 待办提醒(触发/去重/异常)
  + 校准提醒(边界/排序/一天一次/文案截断)。全量 666 passed。
  顺带修复 detail_dialog._load_links 用错 API(get_by_id→get, 真实运行时 bug)。
- **样品表格空状态提示 (2026-08-09, c961c94)**: 无数据时居中显示"暂无样品数据"（empty-label class），覆盖样品池/台账两 tab，+2 测试
- **todo_view 死信号清理 (2026-08-09, c6c4235)**: 删除从未 emit/connect 的 archive_requested（归档功能走 btn_archive.clicked，不受影响）
- **窗口几何记忆 (2026-08-09, fa34bd8)**: 重启恢复上次窗口大小/位置/工具栏状态（QSettings），+3 测试

### 最近完成

- **浮动批量操作栏死信号修复 (2026-08-09, 55892fe)**: UX 审计发现 BatchActionBar 3 个核心信号（批量改状态/指派技术员/导出）从未连接——UI 存在但功能静默失效。
  - task_table 新增 get_selected_task_ids()（排序安全）
  - plan_handlers 连接 status_selected/tech_selected/export_clicked 到新 handler
  - 批量状态选项 fail→failed 统一
  - 新增 4 行为测试，663 passed

### 最近完成

- **任务失败状态统一 + 就地编辑残留修复补完 (2026-08-09, bf52aa6)**: 代码审查发现上次就地编辑修复漏了 progress/priority 两列 + 三个 combo 无 focusOut 兜底 + 任务状态 "fail"/"failed" 双值不一致。
  - P1-1: progress(6)/priority(7) 就地编辑改用 _finish_inline_edit 统一路径
  - P1-2: category/status/technician/priority 四个 combo 编辑器补 focusOut 兜底
  - P1-3: 右键菜单状态值 fail→failed 统一；TASK_STATUS_LABELS/COLORS 补 failed（红色）；dashboard 统计合并 fail+failed；筛选栏补失败选项；表格渲染/状态定位兼容历史 fail
  - P2: progress _commit 加值变化判断；状态定位 initial_idx 保护防误改
  - 测试重构为行为测试（枚举/渲染/状态定位/提交路径），659 passed

### 最近完成

- **仪表盘进度条修复 (2026-08-06)**: 用户报告已完成任务被算进"待开始"。根因: 进度条混用结果数(pass_count)和任务数, completed 无 pass 结果的任务落入灰段; paused/skipped 无归属。修复: 进度条改用任务状态计数(6分类显式覆盖), 跳过=蓝/暂停=紫。

- **就地编辑残留修复 (2026-08-06, task_table)**: 用户报告双击编辑名称/类别/状态/技术员后控件残留。
  根因: combo 用 currentIndexChanged(选当前值不触发) + editingFinished(部分焦点路径不触发)。
  修复: combo 改 activated 信号 + QLineEdit/QSpinBox 加 focusOut eventFilter + QTimer 延迟销毁。

- **代码审查修复 (2026-08-06, branch-diff-review 8轮 + P1/P2/P3 修复)**:
  - P1.1: theme.py 新增 cell-edit QSS 规则(就地编辑器暗色主题修复)
  - P1.2: TASK_CATEGORIES 常量统一(3处去重 + plan_filter_bar 补齐3个缺失类别)
  - P2.1: ReportBundleDialog issues fallback 从 list_all(全库) 改为按 project_id 精确筛选
  - P2.2: fmt_combo 删掉无引擎支持的 csv/html 选项(原会生成损坏文件), 新增 docx/pdf
  - P2.3: @staticmethod 改实例方法 + 删除混乱 fmt_map
  - P3.1: 清理 4 文件未使用导入(main/export_handlers/plan_handlers/task_table)
  - P3.2: 删除 _COL_BATCHABLE 死代码

- **流程打通审计修复 (2026-08-01, 6 个断点)**:
  - P0: ReportBundleDialog 接入真实 ExportService 引擎（原输出硬编码假数据）
  - P1.1: Ctrl+K 命令面板双重绑定冲突 — 删旧版统一到 widgets 版
  - P1.2: 命令面板 Tab 跳转索引错位（设备/待办/技术员）
  - P1.3: 矩阵就地编辑不更新任务状态 — 补齐 _auto_update_task_progress + notify
  - P1.4: Issue 详情弹窗 CAPA/FA 面板死按钮 — 连接信号 + 添加编辑/删除回调
  - P2: 仪表盘 Issue 卡片筛选属性名 _status_combo → _filter_status

- **UI/UX 大改造 (2026-07-26, 23 commits merge)**:
  - Ctrl+K 全局命令面板 (command_palette_dialog.py)
  - 设备负载热力图 (equipment_heatmap_widget.py)
  - 样品生命周期时间轴 (sample_lifecycle_dialog.py)
  - 主题设置中心 + QSettings 持久化 (view_theme_settings_dialog.py + theme_palette_dialog.py)
  - 报告打包导出 (report_bundle_dialog.py)
  - 键盘快捷键说明 (keyboard_shortcuts_dialog.py, 按 ?)
  - Toast 通知堆叠 (toast_stack.py)
  - 批量操作浮层 (batch_action_bar.py)
  - 搜索历史 chips (search_history_chips.py)
  - 列显隐菜单+持久化 (column_visibility_menu.py)
  - 灯箱图片预览 (lightbox_viewer_dialog.py)
  - 甘特图缩放+日/周/月视图切换
  - KPI 钻取+环形图点击跳转
  - 亮暗双主题 QSettings 持久化

- **8D 质量报告可视化预览弹窗 (EightDReportDialog)**:
  - 结构化渲染 D1~D8 8大卡片（团队/描述/围堵/根因/对策/验证/预防/结案）
  - 支持弹窗中一键导出 PDF/Word 报告及复制纯文本摘要

- **甘特图高阶特性升级 (gantt_widget.py & plan_gantt_tab.py)**:
  - **任务依赖矢线与箭头**: 自动解析 `task.dependencies`，绘制折线与指向箭头
  - **冲突实时检测与告警**: 自动判定设备同一时间窗口重叠与依赖倒退冲突，绘制 `⚠️ 冲突` 角标与红色告警框
  - **关键路径 (Critical Path) 计算**: 最长路径算法推算，突出高亮关键路径节点
  - **里程碑节点渲染**: 支持 0 工期 / 里程碑菱形节点渲染

### 已知遗留

- `constants.py` 的 `PROJECT_STATUS_LABELS` 含 `completed/archived` 但 `ProjectStatus` Enum 只有 `{active,paused,closed}`，历史不一致（非阻塞，model validate 只 warn）

### 未完成 / 待处理

- 远期优化项：Weibull 寿命预测、加速寿命 (ALT) 计算面板

## 阻塞

无。

## 下一步

根据需求继续拓展 Reliability 分析面板与数据计算。
