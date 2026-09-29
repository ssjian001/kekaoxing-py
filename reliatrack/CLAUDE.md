# CLAUDE.md — ReliaTrack（代码目录）

> ⚠️ **权威项目文档在仓库根：`../CLAUDE.md`**（`kekaoxing-py/reliatrack/CLAUDE.md`）。
>
> 本文件与根副本曾各自演进（本份最后更新 2026-08-22，根副本 2026-08-30），
> 2026-09-29 已做并集合并：根副本 = 两份的并集（含本份原有的全部 Qt 坑、
> 结构树细节 + 更新的 CI 状态 + `ReliaTrack.spec` 打包命令）。
> **不要再在本文件追加知识** —— 一律写进根 `../CLAUDE.md`，避免再次分叉。

## 本目录特有：cwd 与解释器

```
cwd      = reliatrack/reliatrack/   # main.py / src / tests / progress / feature_list.json 所在
venv     = ../.venv                 # 在仓库根，不在本目录（本文件曾写 .venv/… 全部不可执行）
```

启动 / 测试 / 打包命令、项目结构、业务规则、已知 Qt 坑、DoD、范围规则 → 见 **`../CLAUDE.md`**。

## 本目录内的关键路径

| 用途 | 路径（相对本目录） |
|---|---|
| 入口 | `main.py` |
| 数据库迁移 | `migrate.py` |
| schema 定义 | `src/db/schema.py`（`SCHEMA_VERSION`，当前 v28 / 20 张表） |
| 上次进度 | `progress/current.md` ← 会话开始必读 |
| 功能清单 | `feature_list.json`（dict 格式，**权威且唯一**；仓库根旧 list 副本已于 2026-09-29 删除，`git checkout 4d6b532 -- feature_list.json` 可恢复） |
| 测试套件 | `tests/`（1111 用例，2026-09-29 全量通过） |
| 环境自检 | `../init.sh` |
| 构建配置 | `ReliaTrack.spec` |

## 质量红线（与会话结束相关）

- 判"测试全绿"必须跑**不带 `-x`** 的全量：`cd reliatrack && ../.venv/bin/python -m pytest tests/ -q`（`-x` 首个失败即停，会隐藏后续失败）
- 会话结束必须 `git push` 成功（详见 `AGENTS.md`）
- 环境变量/依赖缺失时用 `../.venv/bin/pip install -r requirements.txt`
