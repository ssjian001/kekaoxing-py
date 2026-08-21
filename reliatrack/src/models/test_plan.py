"""测试计划、测试任务、测试结果模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
#  Status Enums
# ═══════════════════════════════════════════════════════════════════

class TestPlanStatus(str, Enum):
    """测试计划状态。"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
    ARCHIVED = "archived"


class PlanType(str, Enum):
    """测试计划类型。"""
    STANDARD = "standard"
    QUICK = "quick"
    FULL = "full"
    REGRESSION = "regression"
    OTHER = "other"


class TestTaskStatus(str, Enum):
    """测试任务状态。"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    # 审计 #9：handlers/styles/constants 均在用 failed（task_table 右键、
    # TASK_STATUS_LABELS、颜色映射），枚举作为值权威必须收编
    FAILED = "failed"


class TestResultStatus(str, Enum):
    """测试结果状态。"""
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"
    PENDING = "pending"
    SKIP = "skip"


# ═══════════════════════════════════════════════════════════════════
#  Dataclass Models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TestPlan:
    """测试计划 — 项目下的测试批次。"""
    __test__ = False
    id: Optional[int] = None
    project_id: int = 0
    name: str = ""
    test_standard: str = ""   # MIL-STD-810H / IEC 60068 / 企业内测
    start_date: str = ""
    end_date: str = ""
    status: str = TestPlanStatus.DRAFT.value
    plan_type: str = PlanType.STANDARD.value  # 计划类型
    apqp_phase: str = ""       # APQP 阶段: P1/P2/P3/P4/P5
    task_prefix: str = ""      # 任务编号前缀 (如 "HTG" → HTG-001)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        # 防御性默认值修正
        if self.status is None:
            self.status = "planning"
        if self.plan_type is None:
            self.plan_type = PlanType.STANDARD.value


@dataclass
class TestTask:
    """测试任务 — 计划下的单个测试项。"""
    __test__ = False
    id: Optional[int] = None
    plan_id: int = 0
    name: str = ""
    category: str = ""        # 环境试验/机械试验/表面处理/包装
    test_standard: str = ""   # 具体测试项标准条款
    technician_id: Optional[int] = None
    equipment_id: Optional[int] = None
    sample_ids: str = "[]"    # JSON: [sample_id, ...]
    duration: int = 1         # 工期（工作日）
    start_day: int = 0
    progress: float = 0.0
    status: str = TestTaskStatus.PENDING.value
    priority: int = 3
    environment: str = "{}"   # JSON: {"temp":"85C", "humidity":"85%RH"}
    log_file: str = ""        # 设备原始 Log 文件路径
    dependencies: str = "[]"  # JSON: [task_id, ...]
    notes: str = ""
    temperature: str = ""     # 例: "-40°C ~ 85°C"
    humidity: str = ""        # 例: "85%RH"
    accept_criteria: str = "" # 判定准则 JSON 或描述
    actual_start_date: str = ""
    actual_end_date: str = ""
    sort_order: int = 0
    manual_scheduled: int = 0  # 1=手动排程，自动排程时跳过
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if self.duration < 0:
            raise ValueError(f"工期不能为负数: {self.duration}")
        if not 0 <= self.progress <= 100:
            raise ValueError(f"进度必须在 0-100 之间: {self.progress}")
        # 0 = legacy invalid value (DB prior to schema default), treat as 3
        if self.priority == 0:
            self.priority = 3
        if self.priority < 1 or self.priority > 5:
            raise ValueError(f"优先级必须在 1-5 之间: {self.priority}")


@dataclass
class TestResult:
    """测试结果 — 任务 × 样品的测试结论。"""
    __test__ = False
    id: Optional[int] = None
    task_id: int = 0
    sample_id: Optional[int] = None
    result: str = TestResultStatus.PENDING.value
    test_date: str = ""
    tester_id: Optional[int] = None
    environment: str = "{}"
    notes: str = ""
    attachments: str = "[]"   # JSON: [file_path, ...]
    measured_value: str = ""
    created_at: str = ""
