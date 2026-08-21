# ReliaTrack 进度 — 2026-08-21（晚）

## 今日完成
1. **全面体检** → CI 6 连红修绿，挖出 ESCAPE SQL bug
2. **全量对抗审计**（15 单元 + 排程补审）：~66 条有效 bug → `progress/audit-20260821.md`
3. **修复 29 项**（P1 全部 7 + P2 22）：详见审计报告"修复状态"节
   - 数据破坏类：单实例锁/入库原子化/矩阵 upsert/双击真值/就地编辑守卫/校准日期/级联软删
   - 功能类：ESCAPE/tech_name/文件名 sanitize/半成品清理/Word 换行/列宽/重复表头/heatmap×2/枚举/双定时器/锁守卫/overflow 菜单等
   - UX/数据真实性：假履历换真数据、必填校验、KPI 死勾选、任务日期死守卫复活
4. reportlab 4.5.1→5.0.1 升级评估并实装

## 待办（下次继续）
- #22 plan_summary off-by-one（需确认统计口径）
- P3 批次：死代码集群 ~12 处一次性清理（update_status/purge_old/theme_palette_dialog/toast_stack/4 个零调用 service 方法等）
- 契约假死：4 个 repo 的 getrowcount 恒 0（改 SELECT changes()）
- gantt B3 主题快照/B4 关键路径未沿依赖链（低危）

## 测试基线
735 passed（新增 21 个审计回归测试 test_audit_fixes_20260821.py）+ E2E 57 PASS
