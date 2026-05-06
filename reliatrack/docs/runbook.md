# 运维手册

## 启动

```bash
cd ~/Desktop/AI/xiangmu/kekaoxing-py/reliatrack
.venv/bin/python3 main.py
```

## 数据库

- **位置**：`data/reliatrack.db`（自动创建）
- **Schema 版本**：v13
- **备份**：`backups/` 目录下自动/手动备份
- **迁移**：`.venv/bin/python3 migrate.py`（运行 pending migrations）

## 备份

应用内提供手动备份功能（文件 → 备份），备份文件存放在 `backups/` 目录。

手动备份：
```bash
cp data/reliatrack.db "backups/reliatrack_$(date +%Y%m%d_%H%M%S).db"
```

## 测试

```bash
# E2E 测试（56 项，需 offscreen 模式）
QT_QPA_PLATFORM=offscreen .venv/bin/python3 tests/test_e2e_full.py

# 单元测试
.venv/bin/python -m pytest tests/ -v

# 单模块
.venv/bin/python -m pytest tests/test_sample_repo.py -v
```

## 故障排查

| 问题 | 解决 |
|---|---|
| 启动报错 `No module named 'apsw'` | `.venv/bin/pip install apsw` |
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
