# ReliaTrack Local

可靠性测试全生命周期管理系统

基于 PySide6 + SQLite 的桌面应用，用于：
- 项目管理
- 测试计划与任务排程（甘特图）
- 样品管理（入库/出库/流转）
- Issue 与 FA 记录跟踪
- 数据导出（Excel/PDF）

## 快速开始

```bash
cd reliatrack
pip install -r requirements.txt
python main.py
```

## 技术栈

- Python 3.10+
- PySide6 (Qt)
- apsw (SQLite)
- openpyxl / fpdf2 (导出)
