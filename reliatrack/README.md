# ReliaTrack

可靠性测试全生命周期管理系统 — PySide6 + SQLite

## 快速开始

```bash
cd ~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 main.py
```

数据库自动创建在 `data/reliatrack.db`。

## 功能

- **项目管理** — 创建/管理可靠性测试项目
- **测试计划** — 定义测试任务、分配样品
- **样品追踪** — 全生命周期样品状态跟踪
- **设备管理** — 测试设备台账（资产编号、校准信息）
- **人员管理** — 技术员分配与工作量
- **甘特图** — 测试任务时间线可视化
- **Issue 跟踪** — bd (beads) 图谱化 issue 管理
- **知识库** — 经验教训沉淀
- **Dashboard** — 项目概览与统计

## 架构

```
main.py              # 入口
src/
├── configs/         # 页面配置
├── constants.py     # 全局常量
├── controllers/     # 页面控制器
├── db/
│   ├── connection.py
│   ├── schema.py        # SQLite schema（v13）
│   └── repositories/    # 数据访问层（repo 模式）
│       ├── base.py
│       ├── project_repo.py
│       ├── sample_repo.py
│       ├── test_task_repo.py
│       ├── test_plan_repo.py
│       ├── test_result_repo.py
│       ├── equipment_repo.py
│       ├── technician_repo.py
│       ├── issue_repo.py
│       ├── knowledge_repo.py
│       └── settings_repo.py
├── handlers/        # 全局信号处理
├── models/          # Pydantic 模型
├── services/        # 业务逻辑层
│   ├── project_service.py
│   ├── sample_service.py
│   ├── scheduler_service.py
│   ├── export_service.py
│   ├── import_service.py
│   └── ...
├── styles/          # QSS 样式（Catppuccin Latte 明亮主题）
└── views/           # Qt 视图
    ├── dashboard_view.py
    ├── project_view.py
    ├── sample_view.py
    ├── equipment_view.py
    ├── issue_view.py
    ├── dialogs/     # 对话框
    └── ...
```

## 测试

```bash
.venv/bin/python -m pytest tests/ -v
```

70 个测试覆盖 repo 层和 service 层。

## 技术栈

- Python 3.11 + PySide6 + apsw (SQLite)
- Repo 模式：数据访问经由 `src/db/repositories/`，禁止在 services/controllers 直接操作 cursor
- Schema v13：FK ON DELETE SET NULL，显式列名（无 SELECT *）
- Issue 跟踪：[bd (beads)](https://github.com/Ironlung968/beads) — Dolt-backed graph tracker

## 许可

私有项目
