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

- **仪表盘** — SaaS 风格 v2: Header + 健康度卡片(评分0-100) + 左右两栏(4KPI+环形图 / 3KPI+独立进度环卡片), QPainter 自绘
- **项目管理** — 创建/管理可靠性测试项目
- **样品追踪** — 全生命周期样品状态跟踪 + Excel 批量导入
- **测试计划** — 定义测试任务（13列含预计日期）、自动排程（3阶段算法）、甘特图可视化（预计/实际切换+设备颜色编码）、结果矩阵（3种显示模式+Tooltip）、失效模式分析Tab（类别统计+失效TopN+未关联Issue警告）、今日摘要栏、一键总结报告按钮、导出按项目筛选、依赖弹出式选择
- **Issue 跟踪** — FA 分析步骤 + CAPA 纠正预防（自由文本负责人）+ 8D PDF/Word 报告导出 + 状态/严重度/类别筛选（状态多选）
- **设备管理** — 测试设备台账（资产编号、制造商、精度、校准信息）+ 技术员管理
- **知识库** — 失效模式经验沉淀

## 7 个 Tab

| 索引 | Tab | 核心功能 |
|-----|-----|---------|
| 0 | 仪表盘 | 健康度卡片(评分0-100) + 左右两栏(4KPI+环形图 / 3KPI+独立进度环卡片) |
| 1 | 项目管理 | 项目 CRUD + 搜索 |
| 2 | 样品管理 | 样品池 + 出入库 + 批量导入 |
| 3 | 测试计划 | 任务 CRUD + 自动排程 + 甘特图（序号标签+预计/实际切换）+ 结果矩阵（3种模式+Tooltip）+ 失效分析Tab + 今日摘要 + 一键总结报告 + 依赖弹出选择 |
| 4 | Issue 追踪 | Issue(9列含DRI+解决方案) + FA/CAPA 左右排列 + 双向联动 + 8D 导出 + 筛选 |
| 5 | 设备管理 | 设备 + 校准 + 技术员（子 Tab） |
| 6 | 知识库 | 失效模式 CRUD |

## 架构

```
main.py              # 入口（MainWindow, 7个Tab, 快捷键分发）
src/
├── constants.py     # 全局常量
├── controllers/     # 页面控制器（AppController）
├── db/
│   ├── connection.py
│   └── schema.py        # SQLite schema（v21）
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
├── handlers/        # 信号处理（11个Handler类，含export_handlers、backup_handlers）
│   ├── project_handlers.py
│   ├── sample_handlers.py
│   ├── plan_handlers.py
│   ├── issue_handlers.py
│   ├── equipment_handlers.py
│   ├── knowledge_handlers.py
│   ├── export_handlers.py
│   ├── refresh_handlers.py
│   └── technician_handlers.py
├── models/          # 数据模型
├── services/        # 业务逻辑层
│   ├── scheduler.py          # 3阶段排程引擎（607行）
│   ├── scheduler_service.py  # 排程服务（DB 读写）
│   ├── export_service.py     # 8D/计划导出（reportlab + python-docx）
│   ├── import_service.py     # Excel 批量导入
│   ├── holiday_service.py    # 节假日管理
│   ├── issue_service.py      # Issue + FA + CAPA
│   ├── undo_manager.py       # 撤销操作管理
│   └── ...
├── styles/          # QSS 样式（Catppuccin Latte 明亮主题）
└── views/           # Qt 视图
    ├── dashboard_view.py      # SaaS v2: 健康度+环形图+独立进度环卡片, QPainter
    ├── project_view.py
    ├── sample_view.py
    ├── test_plan_view.py      # 任务表 + 甘特图 + 结果矩阵 + 失效分析 + 一键报告
    ├── issue_view.py          # Issue + FA + CAPA + 筛选
    ├── equipment_view.py      # 设备 + 技术员子Tab
    ├── knowledge_view.py
    ├── widgets/               # 可复用组件
    │   ├── task_table.py      # 任务表格
    │   ├── gantt_widget.py    # 甘特图
    │   ├── result_matrix.py   # 结果矩阵（3种显示模式）
    │   └── analysis_widget.py # 失效模式分析（类别统计+TopN）
    └── dialogs/
        ├── schedule_config_dialog.py  # 排程参数配置
        ├── schedule_report_dialog.py  # 排程报告（利用率图表）
        ├── fa_record_dialog.py        # FA 分析步骤
        └── ...
```

## 测试

```bash
.venv/bin/python -m pytest tests/ -v
```

E2E 测试需 offscreen 模式：`QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_e2e_full.py`。274 → 289 个 pytest 测试全通过（另有 test_boundary 7 项 CI-only 跳过）。

## CI/CD

- **CI**：GitHub Actions，Python 3.11/3.12 matrix，自动测试
- **Release**：推送 `v*` tag 触发 PyInstaller 打包，自动生成 Linux/Windows 独立可运行版本

## 技术栈

- Python 3.11 + PySide6 + apsw (SQLite)
- 分层架构：View → Handler → Service → Repo
- Schema v21：Issue 责任类别(ME/EE/AE/SW/NPI/QE/Other)+状态多选筛选+CheckBox QProxyStyle；v20 任务编号前缀；v17 Issue 软删除；v16 Issue DRI + CAPA 验证人 + fail→自动创建 Issue，显式列名（无 SELECT *），QPainter 自绘图表
- Issue 跟踪：[bd (beads)](https://github.com/Ironlung968/beads) — Dolt-backed graph tracker

## 许可

私有项目
