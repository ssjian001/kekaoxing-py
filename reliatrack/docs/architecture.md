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
   ├──< Issue
   └──< Knowledge
```

### Schema 版本：v13

- **FK 策略**：所有外键 `ON DELETE SET NULL`，级联删除由业务逻辑手动处理
- **显式列名**：所有 SELECT 使用具体列名，禁止 `SELECT *`
- **迁移**：通过 `migrate.py` 管理，schema 版本记录在 `schema_meta` 表

## 分层架构

```
Views (Qt UI)
  ↓ 信号/槽
Controllers (页面协调)
  ↓ 调用
Services (业务逻辑)
  ↓ 调用
Repositories (数据访问)
  ↓ SQL
SQLite (apsw)
```

- **Views**：纯 UI 绑定，不做业务判断
- **Controllers**：页面级协调，处理信号流转
- **Services**：业务规则（调度、导入导出、统计计算）
- **Repositories**：单表 CRUD，封装 SQL 细节

## 关键设计决策

| 决策 | 原因 |
|---|---|
| Repo 模式而非 ORM | SQLite 单文件场景，ORM 过重；repo 提供足够抽象同时保持 SQL 可控性 |
| apsw 而非 sqlite3 | 支持 WAL 模式、更好的并发控制 |
| FK ON DELETE SET NULL | 防止级联删除误伤关联数据，由 service 层决定是否级联 |
| QSS 样式独立 | 主题切换需求（Catppuccin Latte 明亮主题） |
