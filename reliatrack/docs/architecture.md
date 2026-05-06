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

### Schema 版本：v13

- **FK 策略**：所有外键 `ON DELETE SET NULL`，级联删除由业务逻辑手动处理
- **显式列名**：所有 SELECT 使用具体列名，禁止 `SELECT *`
- **迁移**：通过 `migrate.py` 管理，schema 版本记录在 `schema_meta` 表

## 分层架构

```
View (Qt UI)
  ↓ Signal
Handler (信号处理器, 9个类)
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
| 0 | 📊 仪表盘 | 12 KPI 卡片 + 3 图表 + 校准预警列表 |
| 1 | 📁 项目管理 | 项目 CRUD + 搜索过滤 |
| 2 | 📦 样品管理 | 样品池 + 出入库记录 + Excel 批量导入 |
| 3 | 📋 测试计划 | 任务表 + 甘特图（设备颜色编码）+ 自动排程 + 结果矩阵 |
| 4 | 🐛 Issue 追踪 | Issue CRUD + FA 分析 + CAPA 措施 + 8D 导出 + 状态/严重度筛选 |
| 5 | 🔧 设备管理 | 设备 CRUD + 校准管理 + 技术员管理（内部子 Tab） |
| 6 | 📚 知识库 | 失效模式 CRUD + 关键词搜索 |

## 排程引擎

3 阶段自动排程（`scheduler.py`）：

1. **Greedy Placement** — 按拓扑序+优先级贪心放置，锁任务优先
2. **Left-Shift Compression** — 尝试把任务左移填补空闲
3. **Report Generation** — 计算总工期、设备利用率、瓶颈、建议

支持：跳过周末/节假日、设备并行数约束、锁定已有排期、循环依赖检测。

## 关键设计决策

| 决策 | 原因 |
|---|---|
| Repo 模式而非 ORM | SQLite 单文件场景，ORM 过重；repo 提供足够抽象同时保持 SQL 可控性 |
| apsw 而非 sqlite3 | 支持 WAL 模式、更好的并发控制 |
| FK ON DELETE SET NULL | 防止级联删除误伤关联数据，由 service 层决定是否级联 |
| Handler 层分离 | 解耦 View 和 Service，信号处理可独立测试 |
| QSS 样式独立 | 主题切换需求（Catppuccin Latte 明亮主题） |
