# ReliaTrack Local — 开发日志

> 项目路径: `/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/`
> 技术栈: PySide6 + SQLite (apsw)
> 运行: `cd reliatrack && ../.venv/bin/python main.py`
> Issue 跟踪: `bd` (beads, `.beads/`)

---

## 2026-04-23 — 项目启动 & 架构设计

- **决策**: 放弃旧版 Electron+Vue3 的 kekaoxing-app，用 PySide6 + SQLite 从头构建
- **架构**: View → Controller → Service → Repository → Database (5 层)
- **数据库**: 14 张表，apsw 驱动，WAL 模式，FK CASCADE
- **模型**: 12 个 dataclass
- **计划**: 7 天 6 阶段（骨架→DB→Service→Controller→UI→导出）

## 2026-04-24 — 核心功能实现 (s1-s6)

### s1 排程算法适配
- 重写 `scheduler.py` + `scheduler_service.py`
- 3 阶段算法：拓扑排序→贪心放置→左移压缩→报告生成
- 设备并行容量约束 + 依赖关系处理

### s2 样品出入库弹窗
- `SampleCheckInDialog` — 手动录入 SN/批次/规格/项目/位置
- `SampleCheckoutDialog` — 操作人选择/关联任务/预计归还
- `main.py` 回调连接，信号→槽→Service→刷新

### s3 Issue/FA 增删改弹窗
- `IssueEditDialog` — 失效模式/阶段/严重度/状态/根因/解决方案
- `FARecordDialog` — 步骤号/方法/标题/描述/发现
- `IssueView` 右键菜单 + FA 面板（卡片式展示）+ 5 个钩子方法

### s4 测试任务增删改弹窗
- `TaskEditDialog` — 名称/类别/标准/工期/设备/技术员/依赖
- `TestPlanView.setup_task_callbacks()` 注入模式

### s5 自动排程按钮连接
- `btn_schedule` → `_on_auto_schedule` → `scheduler_service.auto_schedule`
- 甘特图 `paintEvent` 自绘实现（类别着色+进度条+天数标尺）

### s6 导出功能
- `ExportService`: 4 种导出（任务/Issue/样品 Excel + 综合 PDF）
- `ExportDialog`: 内容+格式选择器
- PDF 中文支持: NotoSansCJK (fpdf2 2.8.7 + .ttc)

## 2026-04-28 — Bug 修复 & 需求审计

### Bug 修复 (4 个)
| ID | Bug | 文件 | 修复 |
|---|---|---|---|
| `reliatrack-89e` | `ctrl.technician_service` 属性不存在 | `main.py:406` | → `ctrl.technicians` |
| `reliatrack-bu4` | `_add_combo_field` 缺 `placeholder` 参数 | `base_dialog.py` | 添加参数 |
| `reliatrack-3vy` | PDF 导出中文崩溃 (Helvetica) | `export_service.py` | 注册 NotoSansCJK |
| `reliatrack-xxl` | 搜索框 `textChanged` 未连接过滤 | `sample_view.py` | 缓存全量+过滤方法 |

### PRD 需求审计结果
| 模块 | 完成度 | 后端 | UI |
|---|---|---|---|
| 样品管理 | ~75% | ✅ | ❌ 缺批量导入 Excel |
| 测试管理 | ~65% | ✅ | ❌ 缺计划创建 UI、设备/技术员管理 UI、环境参数输入 |
| Issue/FA | ~85% | ✅ | ❌ 缺附件上传 UI、知识库 UI |
| 非功能需求 | ~90% | — | ❌ 缺 Word 导出 |

**后端完成度 ~90%，主要差距在 UI 层。**

### 其他
- 初始化 `bd` (beads) issue tracker
- 创建 `CLAUDE.md` + `AGENTS.md`
- 加载 `kekaoxing-reliatrack` skill

## 2026-04-28 (续) — PRD 功能补齐

> 上午需求审计发现 11 项 UI 缺口，下午全部补齐。

### 新建文件 (12 个)
| 文件 | 说明 |
|---|---|
| `src/views/dialogs/plan_edit_dialog.py` | 测试计划创建/编辑弹窗 |
| `src/views/dialogs/equipment_edit_dialog.py` | 设备编辑弹窗 |
| `src/views/dialogs/technician_edit_dialog.py` | 技术员编辑弹窗 |
| `src/views/dialogs/batch_import_dialog.py` | Excel 批量导入弹窗（openpyxl） |
| `src/views/dialogs/attachment_dialog.py` | 附件管理弹窗 |
| `src/views/dialogs/knowledge_edit_dialog.py` | 知识库编辑弹窗 |
| `src/views/equipment_view.py` | 设备管理 Tab |
| `src/views/technician_view.py` | 技术员管理 Tab |
| `src/views/knowledge_view.py` | 知识库 Tab |
| `src/db/repositories/knowledge_repo.py` | 知识库 Repo |
| `src/services/knowledge_service.py` | 知识库 Service |
| `src/models/knowledge.py` | KnowledgeEntry dataclass |

### 修改文件 (14 个)
| 文件 | 变更 |
|---|---|
| `main.py` | 新增 Tab(设备/技术员/知识库)、所有 CRUD 回调、Ctrl+Z/Y 快捷键、Dashboard 图表数据聚合 |
| `src/db/schema.py` | Schema v1→v5 迁移（设备校准日期、技术员工号/电话/邮箱、任务温湿度、知识库字段） |
| `src/models/common.py` | Equipment/Technician 新字段 |
| `src/models/test_plan.py` | TestTask 新增 temperature/humidity 字段 |
| `src/views/test_plan_view.py` | 新建/编辑计划按钮 |
| `src/views/sample_view.py` | 批量导入按钮、`_SampleUsageTab` 从占位符替换为完整实现 |
| `src/views/issue_view.py` | 附件按钮 |
| `src/views/dashboard_view.py` | QPainter 自绘条形图（任务/样品/Issue 状态分布） |
| `src/views/dialogs/task_dialog.py` | 环境参数输入 + 日志文件选择器 |
| `src/services/sample_service.py` | `list_transactions` 方法 |
| `src/services/issue_service.py` | `delete_attachment` 方法 |
| `src/db/repositories/sample_repo.py` | `list_transactions` 方法 |
| `src/db/repositories/issue_repo.py` | `delete_attachment` 方法 |
| `src/controllers/app_controller.py` | 注册 KnowledgeRepository/Service |

### Bug 修复
- **apsw 空结果集 `getdescription()` 崩溃** → 硬编码列名兜底
- **schema 迁移幂等性** → `PRAGMA table_info` 检查避免重复 `ALTER TABLE`

---

## 待办 (TODO)

- [x] PlanEditDialog — 测试计划创建/编辑 UI
- [x] 设备管理 Tab — CRUD 界面
- [x] 技术员管理 Tab — CRUD 界面
- [x] 样品批量导入 — Excel 解析
- [x] 附件上传 UI — 文件选择器
- [x] 知识库 UI — 失效模式检索
- [x] TaskEditDialog 环境参数输入
- [x] TaskEditDialog Log 文件选择器
- [x] UndoManager 实际接入业务操作
- [x] Dashboard 增强 — 图表可视化
- [x] 样品占用 Tab 替换占位符
- [ ] 二维码生成（PRD 标注可选，DB 有 `qr_code` 字段）
- [ ] Word 导出（当前只有 Excel + PDF）
