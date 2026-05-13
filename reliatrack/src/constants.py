"""集中管理状态标签和枚举映射 — 全局唯一来源。

所有 UI 组件和导出功能统一从此模块导入标签映射，
避免各处重复定义导致不一致。
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════
#  任务状态
# ═══════════════════════════════════════════════════════════════════

TASK_STATUS_LABELS: dict[str, str] = {
    "pending": "待开始",
    "in_progress": "进行中",
    "completed": "已完成",
    "skipped": "已跳过",
}

# ═══════════════════════════════════════════════════════════════════
#  计划状态
# ═══════════════════════════════════════════════════════════════════

PLAN_STATUS_OPTIONS: list[tuple[str, str]] = [
    ("draft", "草稿"),
    ("in_progress", "进行中"),
    ("completed", "已完成"),
    ("paused", "已暂停"),
]

# ═══════════════════════════════════════════════════════════════════
#  测试结果
# ═══════════════════════════════════════════════════════════════════

RESULT_OPTIONS: list[tuple[str, str]] = [
    ("通过", "pass"),
    ("不通过", "fail"),
    ("条件通过", "conditional"),
    ("待定", "pending"),
    ("跳过", "skip"),
]

# ═══════════════════════════════════════════════════════════════════
#  优先级
# ═══════════════════════════════════════════════════════════════════

PRIORITY_LABELS: dict[int, str] = {
    1: "P1", 2: "P2", 3: "P3", 4: "P4", 5: "P5",
}

# ═══════════════════════════════════════════════════════════════════
#  Issue 严重度
# ═══════════════════════════════════════════════════════════════════

SEVERITY_OPTIONS: list[tuple[str, str]] = [
    ("严重", "critical"),
    ("主要", "major"),
    ("次要", "minor"),
    ("外观", "cosmetic"),
]

# dict 形式: {english_value: chinese_label}
SEVERITY_LABELS: dict[str, str] = {v: k for k, v in SEVERITY_OPTIONS}

# ═══════════════════════════════════════════════════════════════════
#  Issue 状态
# ═══════════════════════════════════════════════════════════════════

ISSUE_STATUS_LABELS: dict[str, str] = {
    "open": "待处理",
    "analyzing": "分析中",
    "verified": "已验证",
    "closed": "已关闭",
}

# ═══════════════════════════════════════════════════════════════════
#  Issue 责任类别 (Jira-style component/team)
# ═══════════════════════════════════════════════════════════════════

ISSUE_CATEGORY_OPTIONS: list[tuple[str, str]] = [
    ("ME", "ME — 机械工程"),
    ("EE", "EE — 电子工程"),
    ("AE", "AE — 声学/天线工程"),
    ("SW", "SW — 软件工程"),
    ("NPI", "NPI — 新产品导入"),
    ("QE", "QE — 质量工程"),
    ("Other", "其他"),
]

ISSUE_CATEGORY_LABELS: dict[str, str] = {v: k for k, v in ISSUE_CATEGORY_OPTIONS}

# ═══════════════════════════════════════════════════════════════════
#  样品状态
# ═══════════════════════════════════════════════════════════════════

SAMPLE_STATUS_LABELS: dict[str, str] = {
    "in_stock": "在库",
    "in_test": "测试中",
    "checked_out": "已出库",
    "returned": "已归还",
    "scrapped": "已报废",
}

SAMPLE_STATUS_OPTIONS = ["在库", "测试中", "已归还", "已报废"]
SAMPLE_STATUS_MAP: dict[str, str] = {
    "在库": "in_stock",
    "测试中": "in_test",
    "已归还": "returned",
    "已报废": "scrapped",
}
SAMPLE_STATUS_REVERSE: dict[str, str] = {v: k for k, v in SAMPLE_STATUS_MAP.items()}

# ═══════════════════════════════════════════════════════════════════
#  项目状态
# ═══════════════════════════════════════════════════════════════════

PROJECT_STATUS_OPTIONS = ["进行中", "暂停", "已关闭"]
PROJECT_STATUS_MAP: dict[str, str] = {
    "进行中": "active",
    "暂停": "paused",
    "已关闭": "closed",
}
PROJECT_STATUS_REVERSE: dict[str, str] = {v: k for k, v in PROJECT_STATUS_MAP.items()}

# ═══════════════════════════════════════════════════════════════════
#  Issue 解决结果
# ═══════════════════════════════════════════════════════════════════

RESOLUTION_OPTIONS: list[tuple[str, str]] = [
    ("未解决", ""),
    ("已修复", "fixed"),
    ("不修复", "wont_fix"),
    ("重复", "duplicate"),
    ("无法复现", "cannot_reproduce"),
    ("非问题", "not_an_issue"),
]

RESOLUTION_LABELS: dict[str, str] = {v: k for k, v in RESOLUTION_OPTIONS}

# ═══════════════════════════════════════════════════════════════════
#  Issue 状态转换规则
# ═══════════════════════════════════════════════════════════════════

ISSUE_TRANSITIONS: dict[str, set[str]] = {
    "open": {"analyzing", "closed"},
    "analyzing": {"open", "verified", "closed"},
    "verified": {"open", "closed"},
    "closed": {"open"},
}
