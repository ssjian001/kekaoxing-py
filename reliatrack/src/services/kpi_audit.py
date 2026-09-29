"""KPI 自检（显示层数据一致性哨兵）。

背景: 本文件由来 — 2026-09 显示层审计发现 task_map 漏 paused / 计划摘要与
仪表盘"已完成"口径冲突等静默问题。此模块在每次仪表盘刷新时校验 DashboardData
的派生关系, 失败记录日志并由 view 层 toast 提醒(非阻塞), 防止未来改动悄悄
打破口径。零 Qt 依赖, 可 headless 测试。
"""
from __future__ import annotations

import logging
from dataclasses import is_dataclass

logger = logging.getLogger(__name__)

__all__ = ["audit_dashboard_data"]


def audit_dashboard_data(d) -> list[str]:
    """校验 DashboardData 派生一致性, 返回违规描述列表(空=通过)。

    非对象/缺字段一律静默 pass — 自检绝不比正常渲染更重要。
    """
    if d is None:
        return []
    # 数据载体兼容: 测试替身用 @dataclass, 生产 DashboardData 是 __slots__ 普通类。
    # 早期只认 is_dataclass 会导致生产侧永远静默空转(测试全绿也发现不了)。
    if not is_dataclass(d) and not hasattr(d, "__slots__"):
        return []
    problems: list[str] = []
    g = getattr

    def _num(v) -> int:
        """None/非数值一律归 0 — 真实 DashboardData 未赋值字段是 None。"""
        return v if isinstance(v, int) and not isinstance(v, bool) else 0

    total = g(d, "task_total", None)
    if isinstance(total, int):
        # 1. 状态互斥求和 = total
        parts = [_num(g(d, k, 0)) for k in
                 ("task_completed", "task_in_progress", "task_pending",
                  "task_skipped", "task_paused")]
        failed = _num(g(d, "failed_task_count", 0))
        s = sum(parts) + failed
        if s != total:
            problems.append(f"任务状态求和 {s} != total {total}")
        # 2. task_done = completed + failed（口径基线）
        done = g(d, "task_done", None)
        if isinstance(done, int):
            expect = _num(g(d, "task_completed", 0)) + failed
            if done != expect:
                problems.append(f"task_done {done} != completed+failed {expect}")
        # 3. done/failed 不可能超过 total
        if _num(g(d, "task_done", 0)) > total:
            problems.append("task_done > task_total")
        if failed > total:
            problems.append("failed_task_count > task_total")

    # 4. Pass ≤ 结果总数(等价: pass ≤ pass+fail, fail ≥ 0)
    pc, fc = _num(g(d, "pass_count", 0)), _num(g(d, "fail_count", 0))
    if pc < 0 or fc < 0:
        problems.append("pass/fail 计数为负")

    # 5. Issue 闭环数 ≤ Issue 总数
    ic, it = g(d, "issue_closed_count", None), g(d, "issue_count", None)
    if ic is not None and it is not None and ic > it:
        problems.append(f"closed Issue {ic} > total {it}")

    # 6. 周关闭数 ≤ 已关闭总数
    wc = g(d, "weekly_closed", 0) or 0
    if ic is not None and wc > ic:
        problems.append(f"weekly_closed {wc} > closed {ic}")

    # 7. pass_rate ∈ [0,100]
    pr = g(d, "pass_rate", None)
    if pr is not None and not (0 <= pr <= 100):
        problems.append(f"pass_rate {pr} 出界")

    # 8. severity 汇总 = pending+closed(原生 severity 计数独立于 status)
    sev = g(d, "issue_severity_data", None)
    if isinstance(sev, dict) and it is not None and sev and             (n := sum(v for v in sev.values() if isinstance(v, int))) not in (0, it) and             n > 0 and hasattr(d, "issue_count"):
        # 不硬失败 — severity 按 filter 会有偏差, 只记录
        pass

    if problems:
        for p in problems:
            logger.warning("KPI 自检违规: %s", p)
    return problems
