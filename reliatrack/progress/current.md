# ReliaTrack 进度 — 2026-08-23 (数据安全与体检)

## 当前分支：`explore/data-safety`（基于 explore/ui-polish @ a770ace）

## 数据安全与体检闭环（参考 Calibre / Vorta / TagStudio 模式）

| 模块 | 变更 | 说明 |
|---|---|---|
| 启动自检 | `src/services/health_service.py` | `check_db`：`PRAGMA quick_check` + `foreign_key_check`；失败抛 `DbCorruptError` |
| 损坏恢复引导 | `src/views/dialogs/db_corrupt_dialog.py` | 自检失败模态弹窗列出现有备份 → 用户选择 → 走 `restore_backup()`；闭环 Calibre `restore.py` 模式 |
| 启动链接入 | `main.py` + `app_controller.py` | `initialize()` 在 `init_schema` 前跑 `check_db`；`main()` 捕获 `DbCorruptError` 循环引导恢复 |
| 数据体检 | `health_service.py` + `data_health_dialog.py` | 扫描：缺失附件 / 孤儿文件 / 断链结果；支持勾选一键删除孤儿文件（安全约束：仅限附件目录内）；操作菜单加「数据体检(&H)…」入口 |
| 备份轮换修复 | `app_controller.py` | 按文件名时间戳正则解析排序，修复混合命名（`reliatrack_YYYYMMDD.db` 与 `_HHMMSS.db`）时的字符串混排问题 |
| 批量导入反馈 | `batch_import_dialog.py` | 加入 `QProgressDialog` 模态脉冲（300ms 门槛），保留同步处理（<500 行毫秒级完成，避免对 4 个调用方的异步侵入） |

## 测试基线
pytest **748 passed**（+10 new in `test_health_service.py`），50.19s 全绿；offscreen 冒烟通过。

---

# ReliaTrack 进度 — 2026-08-22

## 当前分支：`explore/ui-polish`（基于 main @ f510818，已推 GitHub）

## UI 美化 — 方案 A（保守精修现有 Catppuccin 风格，不动布局）

四轮全部完成，每轮均走完整验证链（offscreen 双主题截图 → 像素采样 → pytest 全绿 → commit+push）：

| 轮次 | commit | 内容 |
|---|---|---|
| 探索 | 0eaf339 | 双主题 18 张基线截图 + AI 视觉分析 + 三方向 HTML 原型（A 精修 / B Linear 深侧栏 / C 软卡片），用户选 A |
| R1 | 688a706 | 轻量表头（次要灰 12px+1px 细线）/ 侧栏胶囊选中态+3px accent 条 / KPI 卡 10px 圆角+hover 描边 |
| R2 | d73533a | Issue 色系收敛（8 色→4 色体系）/ MAUVE 暗色提亮 #8839ef→#a678e8 / 徽标 rgba QSS 修复 |
| R3 | 653eac9 | 测试计划主表 + 样品出入库表接入 RowHighlightDelegate（hover 灰底/选中浅蓝胶囊+左侧指示条）；result_matrix 有意跳过（逐格彩色网格不适用行级高亮） |
| R4 | 6197204 | 暗色语义色达 WCAG AA：RED #d20f39→#ea5a52 (3.0→4.75)、TEAL→#23b5bd (4.4→6.6)；constants.py 新增 resolve_status_color()+_DARK_ALIASES；set_theme() 同步刷新状态色表/CHART_COLORS/DASH_DANGER（往返幂等） |

关键坑（已写入 CLAUDE.md「已知 Qt 坑」）：
- constants.py 状态色表 import 时冻结 → 暗色适配走 set_theme() 就地刷新替身，不能单值提亮（会毁亮色主题：#ea5a52 白底仅 3.45:1）
- offscreen 像素采样须 strict(±3) 容差（抗锯齿边缘误报）；测试脚本必须走 set_theme+apply_palette+重挂 stylesheet 完整链路

## UI 偏好约束（docs/ui-explore/README.md，实装必须遵守）
明亮主题、紧凑布局、800×600 最小窗口适配、不用 emoji 按钮、不擅自移动/合并现有 UI 元素；双主题颜色改动亮暗各验证一次。

## 下一步（用户决策）
- 真机用几天攒感受，可选继续：斑马纹对比微调、间距节奏等边角项（边际收益低）
- 满意后：explore/ui-polish → main 合并（squash 或保留分轮 commit）
- 上次遗留：Windows 端同步 zip 后重装依赖（reportlab 5.0.1）

## 测试基线
pytest 全绿（738）；GUI 已在本机 DISPLAY=:0 运行验证

## 历史快照
2026-08-21（晚）：全面体检 + 全量对抗审计 ~66 bug 修复 29 项（progress/audit-20260821.md）+ reportlab 5.0.1
