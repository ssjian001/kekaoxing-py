# ReliaTrack Local — 任务状态

> 最后更新: 2026-04-24
> 项目路径: `/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/`
> 运行: `cd reliatrack && ../.venv/bin/python main.py`

---

## 总览

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| s1 | 排程算法适配 | ✅ 完成 | scheduler.py + scheduler_service.py 重写，3 阶段算法，集成测试通过 |
| s2 | 样品出入库弹窗 | ✅ 完成 | SampleCheckInDialog/SampleCheckoutDialog + main.py 回调已连接 |
| s3 | Issue/FA 增删改弹窗 | ✅ 完成 | IssueEditDialog/FARecordDialog + 5 个钩子已连接 |
| s4 | 测试任务增删改弹窗 | ✅ 完成 | TaskEditDialog + setup_task_callbacks 已连接 |
| s5 | 自动排程按钮连接 | ✅ 完成 | btn_schedule → _on_auto_schedule，甘特图刷新正常 |
| s6 | 导出功能 (Excel/PDF) | ✅ 完成 | ExportService (openpyxl + fpdf2) + ExportDialog + 工具栏按钮 |

---

## s6. 导出功能 — 实现细节

**新增文件：**
- `src/services/export_service.py` — ExportService 类
  - `export_tasks_excel(plan, tasks)` → 测试任务 Excel（带表头样式）
  - `export_issues_excel(issues, fa_map)` → Issue 列表 Excel
  - `export_samples_excel(samples)` → 样品台账 Excel
  - `export_report_pdf(plan, tasks, issues, samples)` → 综合测试报告 PDF（封面 + 概览 + 任务表 + Issue 表）
- `src/views/dialogs/export_dialog.py` — ExportDialog（选择导出内容 + 格式）

**修改文件：**
- `main.py` — 工具栏添加"📤 导出"按钮 + `_on_export` 槽方法
- `src/services/__init__.py` — 导出 ExportService

**依赖：** `openpyxl`, `fpdf2` (已安装到 venv)

---

## 关键约束

- **apsw** 无 `cursor.lastrowid`，必须用 `SELECT last_insert_rowid()`
- **theme.py** 没有 `FLAMINGO`，用 `PINK` 替代
- **单用户本地应用**，不做网络/二维码/条码
- Catppuccin Mocha 暗色主题，颜色常量在 `src/styles/theme.py`

## 新增文件清单 (本次迭代)

```
src/views/dialogs/__init__.py
src/views/dialogs/base_dialog.py
src/views/dialogs/sample_checkin_dialog.py
src/views/dialogs/sample_checkout_dialog.py
src/views/dialogs/issue_dialog.py
src/views/dialogs/fa_record_dialog.py
src/views/dialogs/task_dialog.py
src/views/dialogs/export_dialog.py
src/services/export_service.py
src/services/scheduler.py          (s1)
src/services/scheduler_service.py  (s1)
```

## 修改文件清单 (本次迭代)

```
main.py                           (s1-s6 全部连接)
src/controllers/app_controller.py (s1 scheduler_service 初始化)
src/services/__init__.py          (s1/s6 导出 SchedulerService + ExportService)
src/services/sample_service.py    (s2 新增 add_transaction)
src/views/sample_view.py          (s2 暴露按钮引用)
src/views/issue_view.py           (s3 右键菜单 + FA 按钮 + 钩子)
src/views/test_plan_view.py       (s4 任务增删改按钮 + 回调)
```
