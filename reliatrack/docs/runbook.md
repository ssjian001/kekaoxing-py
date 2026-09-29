# 运维手册

## 启动

```bash
cd ~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/reliatrack   # 代码目录（main.py/src/tests 所在）
../.venv/bin/python3 main.py
```

> ⚠️ **venv 在仓库根**（`~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/.venv`），不在代码目录 —— 从代码目录执行命令一律用 `../.venv/bin/python`。

## 数据库

- **位置**：`data/reliatrack.db`（自动创建）
- **Schema 版本**：v28（20 张表）
- **备份**：`data/backups/` 目录下自动/手动备份
- **迁移**：`../.venv/bin/python3 migrate.py`（运行 pending migrations）

## 备份

应用内提供手动备份功能（文件 → 备份），备份文件存放在 `data/backups/` 目录。

手动备份：
```bash
cp data/reliatrack.db "data/backups/reliatrack_$(date +%Y%m%d_%H%M%S).db"
```

## 测试

```bash
# 单元测试（1111 项，2026-09-29 全量通过）
../.venv/bin/python -m pytest tests/ -v

# E2E 测试（脚本式，需 offscreen 模式；53 项断言）
QT_QPA_PLATFORM=offscreen ../.venv/bin/python3 tests/manual/test_e2e_full.py
```

## 故障排查

| 问题 | 解决 |
|---|---|
| 启动报错 `No module named 'apsw'` | `../.venv/bin/pip install apsw` |
| 数据库锁定 | 检查是否有其他实例在运行，或删除 `data/reliatrack.db-wal` |
| 样品/任务数据异常 | 检查 FK 是否正确（`SELECT * FROM pragma_foreign_key_check`） |
| 排程结果异常 | 检查任务依赖是否有循环（排程报告会提示） |

## Issue 管理

使用 bd (beads) 图谱化 issue 跟踪：

```bash
bd ready              # 查看可用任务
bd show <id>          # 查看详情
bd update <id> --claim # 认领
bd close <id>         # 完成
bd dolt push          # 推送到远程
```

> ⚠️ **Linux 侧未安装 bd**（`.beads/` 数据由 Windows 端维护）。Linux 会话跳过全部 `bd *` 步骤，issue/任务状态以 `progress/current.md` + `feature_list.json` 为准。
