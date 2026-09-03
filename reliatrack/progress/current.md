# ReliaTrack 进度 — 2026-09-03 (修复归档视图崩溃 + 本机环境重建)

## 本次完成

| commit | 内容 |
|---|---|
| `14dc65b` | fix: 补 TestPlanService.get_archived_plans_by_project，修复归档视图崩溃 |

## Bug 修复详情

**现象**：Windows 端勾选"显示归档计划"开关时 AttributeError:
`'TestPlanService' object has no attribute 'get_archived_plans_by_project'`

**根因**：main.py:832 调用 `get_archived_plans_by_project()`，但 service/repo 只实现了
`get_active_plans_by_project`（镜像方法缺失），属于"调用存在但实现缺失"的静默断点。

**修复**（3 文件，+60 行）：
- `src/db/repositories/test_plan_repo.py` — 新增 `get_archived_by_project`（SQL 层 `status='archived'` 过滤）
- `src/services/test_plan_service.py` — 新增 `get_archived_plans_by_project`（转发 repo）
- `tests/test_handlers.py` — 新增 `TestArchivedPlansByProject` 回归测试（2 用例：active/archived 互斥过滤 + 空归档不崩溃）

## 本机环境重建（Linux/ThinkPad X250）

- venv：`kekaoxing-py/.venv`（Python 3.11.16）
- 依赖：`requirements.lock.txt` + pytest + pytest-qt + pytest-cov（CI 同款组合）
- 注意：**必须装 pytest-qt**，否则 qapp fixture 缺失 → 部分 UI 测试 ERROR，
  且 Qt 状态异常引发 QProgressDialog 段错误（已踩坑确认因果）
- 必须设 `QT_QPA_PLATFORM=minimal`（X250 无显示输出；offscreen 平台在
  batch_import_dialog.py:387 QProgressDialog 处有段错误 bug，minimal 正常）

## 验证证据

- `pytest tests/ -q` 全量 938 tests，exit=0 全绿（minimal 平台，2026-09-03）
- `py_compile` 三文件通过
- 历史已对齐：本地 main = origin/main(d93b297) + 1 fix commit(14dc65b)，无分叉

## 待办 / 阻塞

- [ ] git push 需凭证：本机 SSH key 是 hermes-config 专用 deploy key（对
  kekaoxing-py 无权限）；需用户提供 GitHub PAT（写入 key.md）或把
  ~/.ssh/hermes_deploy.pub 加为账号级 SSH key
- [ ] Windows 端同步此修复（git pull 或手补三文件）
- [ ] 用户真机验证：勾选"显示归档计划"开关不再崩溃、归档计划正确过滤显示
