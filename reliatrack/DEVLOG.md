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
- [x] 二维码生成（PRD 标注可选，DB 有 `qr_code` 字段）
- [x] Word 导出（当前只有 Excel + PDF）

## 2026-04-28 (晚) — 用户实测反馈修复

> 用户实际测试后提出 4 项改进需求，全部完成。

### 1. 二维码生成修复
- **问题**: QR 按钮仅在"样品池" Tab，"样品台账"无 QR 按钮；未选样品时状态栏提示被忽略
- **修复**:
  - `_SampleLedgerTab` 新增完整工具栏 + "🔲 生成二维码"按钮
  - `main.py` 新增 `_on_ledger_generate_qr` 回调
  - 未选样品/无 SN 时改用 `QMessageBox.warning()` 弹窗提醒（替代易被忽略的状态栏消息）
- **新文件**: 无

### 2. 样品信息可编辑
- **新增**: `src/views/dialogs/sample_edit_dialog.py` — `SampleEditDialog`
  - 字段: SN, 批次号, 规格, 项目ID, 状态(下拉), 位置, 备注
  - 支持新建/编辑模式，编辑模式预填数据
- **修改**:
  - `_SamplePoolTab` + `_SampleLedgerTab` 各新增 "✏️ 编辑" 按钮
  - `main.py` 新增 `_on_sample_edit` + `_on_ledger_edit` 回调

### 3. 移除技术员管理
- **删除**: UI 层 Tab（main.py 中移除 `TechnicianView` 创建及信号连接）
- **清理**:
  - `main.py`: 3 处 `ctrl.technicians` 引用 → `[]`（TaskEditDialog/SampleCheckoutDialog）
  - `task_dialog.py`: 补充 `self._technician_list = technician_list or []`（之前漏赋值）
  - `test_e2e_full.py`: Tab 数 7→6, 移除"技术员管理" Tab 名和 `_technician_view` 检查
  - `test_boundary.py`: 移除 TechnicianEditDialog 测试, 移除 `t1` 引用, `operator_id=t1` → 删除参数
- **保留**: DB schema 中 `technicians` 表（向后兼容）、Repository/Service/Model 文件

### 4. 项目管理功能
- **新增**:
  - `src/views/project_view.py` — `ProjectView`（搜索+新建+编辑+删除，状态着色，空状态）
  - `src/views/dialogs/project_edit_dialog.py` — `ProjectEditDialog`（名称/产品/客户/描述/状态）
- **修改**:
  - `main.py`: 项目 Tab 作为第一个 Tab（index 0），新增 3 个 CRUD 回调
  - `src/views/dialogs/__init__.py`: 添加 ProjectEditDialog 导入
- **Note**: 其他功能（样品/计划/Issue）关联 `project_id` 的筛选机制尚未实现，后续迭代添加

### 测试结果
| 测试 | 结果 |
|---|---|
| E2E | 58/58 PASS |
| Boundary | 42/42 PASS |

### 修改文件汇总 (本轮)
| 操作 | 文件 |
|---|---|
| 新建 | `src/views/dialogs/sample_edit_dialog.py` |
| 新建 | `src/views/dialogs/project_edit_dialog.py` |
| 新建 | `src/views/project_view.py` |
| 修改 | `src/views/sample_view.py` (台账工具栏 + 编辑按钮) |
| 修改 | `src/views/dialogs/__init__.py` |
| 修改 | `src/views/dialogs/task_dialog.py` (_technician_list 赋值) |
| 修改 | `main.py` (QR/编辑/项目管理/移除技术员) |
| 修改 | `tests/test_e2e_full.py` (Tab 数/名) |
| 修改 | `tests/test_boundary.py` (移除技术员/新增项目) |

## 2026-04-29 — 全局项目筛选器

> 在 Tab 栏上方添加项目选择器，切换项目后所有关联数据自动筛选。

### 实现方案
- `main.py` `_setup_central_widget()`: Tab widget 上方插入 QComboBox 筛选栏
- `_refresh_all()`: 根据 `currentData()` 决定使用 `list_all()` 还是 `get_by_project(id)`
- 筛选范围: Dashboard KPI/图表、样品池/台账、测试计划、Issue 追踪
- 设备/知识库无 project_id，不参与筛选
- 筛选器选项随项目增删自动更新（`blockSignals` 防递归）

### 测试结果
| 测试 | 结果 |
|---|---|
| E2E | 58/58 PASS |
| Boundary | 42/42 PASS |

## 2026-04-29 (下午) — 功能增强 + UI 全面优化

> 以用户实测反馈为驱动，分 4 个方向完成 15 个 commit。

### 一、功能增强 (2 commits)

#### 1. 新数据自动关联当前项目 + Dashboard 增强
- 创建新数据（样品入库/Issue/测试计划）时自动将全局筛选器的项目预填到弹窗
- `SampleCheckInDialog` / `IssueEditDialog` / `PlanEditDialog` / `SampleEditDialog` 全部支持 `default_project_id` 参数
- Dashboard 新增「样品数」KPI 卡片（TEAL 配色）
- Dashboard 标题下方项目筛选指示器

#### 2. 技术员管理嵌入设备管理 Tab
- 设备管理 Tab 改为内部 QTabWidget（设备 | 技术员），不再是独立顶级 Tab
- 技术员 CRUD 回调完整实现， TechnicianRepository 用 BaseRepository.insert 方法

### 二、UI/UX 优化 (9 commits)

| Commit | 内容 |
|--------|------|
| `c35c857` | 小分辨率适配 — 去重复标题/emoji、缩小窗口和控件 |
| `3cf7ca9` | 收紧 UI 密度，甘特图改为上下堆叠 |
| `21c5a0b` | 全面优化 UI 布局适配低分辨率屏幕 |
| `985f9c3` | 所有弹窗支持自由调整大小（setSizeGripEnabled） |
| `9723e84` | 参照 Jira/TestRail 标准模式优化布局 |
| `01db1b9` | 明亮主题（Catppuccin Latte）+ Issue 布局改上下堆叠 |
| `2c7cb82` | 技术员管理嵌入设备管理 Tab |
| `3b8afca` | 移除样品二维码生成功能 |
| `c9ac3c1` | 替换 QDialogButtonBox 为自定义按钮 |

**主题变更**: Catppuccin Mocha 暗色 → Catppuccin Latte 明亮
**关键原则**: 去除 Tab 内重复页面标题、所有按钮去除 emoji、上下堆叠优先于左右并列、搜索框左对齐 → stretch → 按钮分组

### 三、代码质量 (1 commit)

#### mypy 类型注解全通过
- 从 130 errors 降至 0（66 source files）
- 修复模式：`assert x is not None`、`cast()`、`# type: ignore`、`if TYPE_CHECKING` 隔离循环导入
- `SampleEditDialog` 的 `project_id` 改为 QComboBox 下拉选择

### 四、导出重构 (2 commits)

| Commit | 内容 |
|--------|------|
| `4767513` | PDF 导出从 fpdf2 切换到 reportlab（更成熟的中文处理） |
| `4a7dcb5` | 跨平台字体检测 — Windows(msyh)/macOS(PingFang)/Linux(Droid) |

**技术细节**:
- reportlab 不支持 CFF/OTF outline，只能用 TrueType
- 字体注册名固定 "CJK"/"CJK-Bold"，用变量引用不硬编码
- 找不到字体时抛明确 FileNotFoundError

### 五、问题修复 (1 commit)

#### QDialogButtonBox 中文翻译 Bug
- Qt 中文翻译将 "OK" 错误翻译为"向上"
- `base_dialog.py` 改用自定义 `QPushButton("确定")/QPushButton("取消")`
- `batch_import_dialog.py` / `attachment_dialog.py` 按钮隐藏方式同步更新
- 导出失败从状态栏消息改为 `QMessageBox.critical()` 弹窗 + traceback

### 排程引擎验证
- 独立脚本验证全部排程逻辑：日历计算、依赖链、设备冲突/并行、优先级排序、循环依赖检测、锁定已有排程、跳过周末
- `start_day` 是日历天（可落在周末），实际工作日由 `_iterate_work_days` 自动跳过

### 测试结果
| 测试 | 结果 |
|---|---|
| E2E | 56/56 PASS (移除 QR 测试减少 2 项) |
| Boundary | 42/42 PASS |
| mypy | 66 files, 0 errors |

### 修改文件汇总
- 38 files changed, +1,076 / -894 lines
- 新增依赖: reportlab
- 移除: src/services/qr_service.py

---

## 当前状态 (2026-04-29)

### 质量指标
- E2E: 56/56 | Boundary: 42/42 | mypy: 0 errors
- 远程同步: `4a7dcb5` (main 分支, 22 commits)

### 已知限制（后续迭代方向）

| 项目 | 说明 |
|------|------|
| `start_day` 日历天语义 | 可落在周末，实际工作日自动跳过，排程结果正确但用户看到的日期可能显示周六/周日 |
| 排程参数固定 | `skip_weekends=True` 硬编码，`equipment_capacity` 默认 1，无 UI 配置入口 |
| `qr_code` 字段残留 | DB model 保留（避免迁移），功能已移除 |
| 设备利用率建议为空 | 复杂场景下 suggestions 列表为空 |
| 无撤销/重做 UI | 排程不可回退 |
| 单文件 SQLite | 无并发写入保护 |

---

## 2026-04-29 (晚) — 代码审查 & 优化修复

> 全量代码审查，分数据层 + UI 层两个子代理并行审查。

### 审查发现

#### 数据层 🔴 阻塞项 (3)
| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| D1 | `list_transactions` 列名遗漏 | `sample_repo.py:94-98` | `cols` 硬编码 11 项，`SELECT st.*` 返回 13 列，遗漏 `expected_return`, `actual_return`, `notes` |
| D2 | `init_schema` 无事务包裹 | `schema.py:349-385` | 迁移中途 crash 导致半迁移状态 |
| D3 | Service 直接访问 `_conn` | `equipment_service.py:32`, `test_plan_service.py:44-55` | 绕过 Repository 抽象 |

#### 数据层 🟡 建议项 (7)
- `sample_repo.py:83` LIKE 搜索未转义 `%`/`_`
- `begin_transaction()` 无嵌套保护
- `ProjectService.delete()` N+1 循环删除
- `KnowledgeRepository` 方法签名与基类不一致
- schema 迁移列名未用 `[{col}]` 括号
- `BaseRepository._columns()` 对异常表缺防护
- PDF 字体注册非线程安全（影响小）

#### UI 层 🔴 阻塞项 (4)
| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| U1 | `_refresh_all()` 全量刷新 180+ 行 | `main.py:245-426` | 任何数据变更触发所有 Tab 重建 |
| U2 | 无去重/节流机制 | `main.py:83` | 批量操作触发多次重复刷新 |
| U3 | IssueView 鸭子类型钩子注入 | `main.py:73-77` | 绕开 Qt 信号 + lambda 循环引用 |
| U4 | `_on_sample_edit` / `_on_ledger_edit` 重复 | `main.py:732-784` | 53×2 行完全相同 |

#### UI 层 🟡 建议项 (8)
- `main.py` 1247 行应拆分
- `DashboardView.refresh()` 13 个参数 → dataclass
- `constants.py` 暗色色值 + `theme.py` 亮色色值混用
- 项目下拉框用名称匹配而非 ID
- 空状态模式 8 处重复
- 4 个 CRUD 视图高度相似
- `_chart_sample_status` 重复 set_data
- 多处未使用 import
