# 可靠性测试甘特图 - Python 桌面应用

PySide6 + SQLite 桌面工具，用于消费电子产品可靠性测试排程管理。

## 快速启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 项目结构

```
kekaoxing-py/
├── main.py                 # 入口
├── src/
│   ├── models/             # 数据模型 (Task, Resource, ScheduleConfig)
│   ├── core/               # 排程引擎 + 默认数据
│   ├── views/              # 主视图 (甘特图 / 资源配置)
│   ├── widgets/            # 自定义组件 (甘特条, 弹窗, 时间线)
│   ├── db/                 # SQLite 数据库层
│   └── styles/             # QSS 样式表
├── requirements.txt
└── README.md
```
