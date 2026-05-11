# 架构说明

## 概述

ReliaTrack 是一个面向可靠性测试实验室的全生命周期管理工具，核心功能围绕「项目 → 测试计划 → 任务 → 样品 → 结果」这条主链展开。

## 数据模型

### 核心实体关系

```
Project ──< TestPlan ──< TestTask >── Sample
   │                          │
   ├──< Equipment             └──< TestResult
   ├──< Technician
   ├──< Issue ──< FARecord
   │         ──< CAPARecord
   │         ──< IssueAttachment
   └──< Knowledge
```

### Schema 版本：v17

- **v16**：Issue 加 `dri_name`（DRI 责任人）；CAPA 加 `verifier_name`（验证人）；测试结果保存时可自动创建 Issue
- **v17**：Issue 软删除试点（`is_deleted`/`deleted_at` 列，`list_all` 过滤）
- **v15**：CAPA PDCA 扩展 — capa_records 加 `root_cause`/`effectiveness`/`follow_up`；CAPA 编辑/删除 UI；`count_capa_done` bug 修复
- **v14**：capa_records 加 assignee_name（责任人自由文本，与 assignee_id 并存）；test_tasks 安全补列
- **FK 策略**：核心关联表（issues/fa_records/capa_records/attachments）使用 `ON DELETE CASCADE`，级联删除由 DB 层保证一致性；保留孤立记录的字段（如 assignee_id）使用 `ON DELETE SET NULL`
- **显式列名**：所有 SELECT 使用具体列名，禁止 `SELECT *`
- **迁移**：通过 `migrate.py` 管理，schema 版本记录在 `schema_version` 表

## 分层架构

```
View (Qt UI)
  ↓ Signal
Handler (信号处理器, 10个类)
  ↓ 调用
Service (业务逻辑)
  ↓ 调用
Repository (数据访问)
  ↓ SQL
SQLite (apsw)
```

- **Views**：纯 UI 绑定，不做业务判断
- **Handlers**：连接 View 信号到 Service 调用，处理用户交互反馈
- **Services**：业务规则（调度、导入导出、统计计算）
- **Repositories**：单表 CRUD，封装 SQL 细节

## 7 个 Tab

| 索引 | Tab | 核心组件 |
|-----|-----|---------|
| 0 | 📊 仪表盘 | SaaS v2: Header + 测试进度堆叠条卡片(_StackedBar) + 左栏(3KPI+环形图) + 右栏(4KPI+进度环+严重度条), QPainter |
| 1 | 📁 项目管理 | 项目 CRUD + 搜索过滤 |
| 2 | 📦 样品管理 | 样品池 + 出入库记录 + Excel 批量导入 |
| 3 | 📋 测试计划 | 任务表（13列含预计日期）+ 甘特图（预计/实际切换+设备颜色编码）+ 自动排程 + 结果矩阵（3种显示模式+Tooltip+行列统计）+ 失效模式分析Tab（类别统计+TopN+未关联Issue警告）+ 今日摘要栏 + 一键总结报告 + 导出按项目筛选 + 依赖弹出选择 |
| 4 | 🐛 Issue 追踪 | Issue CRUD(9列含DRI) + FA 分析 + CAPA 措施（负责人+验证人自由输入）+ FA/CAPA↔Issue 双向联动 + 自动创建 Issue(fail→Issue) + 8D PDF/Word 导出 + 状态/严重度筛选 |
| 5 | 🔧 设备管理 | 设备 CRUD + 校准管理 + 技术员管理（内部子 Tab） |
| 6 | 📚 知识库 | 失效模式 CRUD + 关键词搜索 |

## 排程引擎

3 阶段自动排程（`scheduler.py`）：

1. **Greedy Placement** — 按拓扑序+优先级贪心放置，锁任务优先
2. **Left-Shift Compression** — 尝试把任务左移填补空闲
3. **Report Generation** — 计算总工期、设备利用率、瓶颈、建议

支持：跳过周末/节假日、设备并行数约束、锁定已有排期、循环依赖检测、任务依赖（拓扑排序+约束计算）。

## 依赖编辑

任务依赖通过弹出式多选对话框配置：
- 列表按排程排序，显示天数区间（如 D0~D5）
- 编辑模式下插入蓝色「当前任务」参照行
- 保存时校验：自依赖检测、ID 有效性验证
- 排程引擎完整支持：Kahn 拓扑排序、依赖约束计算（取前置任务结束日最大值）

## 关键设计决策

| 决策 | 原因 |
|---|---|
| Repo 模式而非 ORM | SQLite 单文件场景，ORM 过重；repo 提供足够抽象同时保持 SQL 可控性 |
| apsw 而非 sqlite3 | 支持 WAL 模式、更好的并发控制 |
| FK ON DELETE CASCADE（关联表）+ SET NULL（引用字段） | 核心关联数据随父记录级联删除保证一致性；引用字段（如 assignee_id）设 NULL 保留记录 |
| Handler 层分离 | 解耦 View 和 Service，信号处理可独立测试 |
| QSS 样式独立 | 主题切换需求（Catppuccin Latte 明亮主题） |
