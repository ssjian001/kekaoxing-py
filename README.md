# ReliaTrack

可靠性测试全生命周期管理系统 — 基于 PySide6 + SQLite 的桌面应用。

> **本文件只是仓库根的入口指引。** 完整介绍、功能清单、目录树与测试说明在 **[`reliatrack/README.md`](reliatrack/README.md)**；
> 项目约定与架构见 **[`CLAUDE.md`](CLAUDE.md)**。本文件不再重复那些内容（重复 = 两个数字迟早打架）。

## 目录结构（⚠️ 双层）

```
reliatrack/            # 仓库根：.venv / .github / init.sh / 本文件
└── reliatrack/        # 代码目录：main.py, src/, tests/, docs/, progress/, feature_list.json
```

## 快速开始

```bash
cd ~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack   # 仓库根
python3 -m venv .venv                              # 首次
.venv/bin/pip install -r reliatrack/requirements.txt

cd reliatrack                                      # 代码目录
../.venv/bin/python3 main.py                       # 启动
../.venv/bin/python -m pytest tests/            # 全量测试（1136 用例，实测 ~49s）
# ⚠️ 别再加 -q：pytest.ini 的 addopts 已含 -q，叠加成 -qq 会吞掉 summary 行
# ⚠️ 判"全绿"看最后一行 `N passed` + exit code，别用 `| tail -N` 管道（会挤掉 summary）
```

环境自检脚本：`bash init.sh`（语法 + schema + 测试 + feature_list 校验）。

## 功能速览

- 项目管理 / 测试计划与任务排程（甘特图）
- 样品管理（入库/出库/流转）与设备台账
- Issue 与 FA / CAPA 跟踪（看板 + 列表）
- 数据导出（Excel / PDF / Word）
- 双主题（Catppuccin Latte / Mocha）
