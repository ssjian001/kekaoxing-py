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


class TestTaskStatus(str, Enum):
    """测试任务状态。"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


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
    id: Optional[int] = None
    project_id: int = 0
    name: str = ""
    test_standard: str = ""   # MIL-STD-810H / IEC 60068 / 企业内测
    start_date: str = ""
    end_date: str = ""
    status: str = TestPlanStatus.DRAFT.value
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TestTask:
    """测试任务 — 计划下的单个测试项。"""
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
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TestResult:
    """测试结果 — 任务 × 样品的测试结论。"""
    id: Optional[int] = None
    task_id: int = 0
    sample_id: Optional[int] = None
    result: str = TestResultStatus.PENDING.value
    test_date: str = ""
    tester_id: Optional[int] = None
    environment: str = "{}"
    notes: str = ""
    attachments: str = "[]"   # JSON: [file_path, ...]
    created_at: str = ""
