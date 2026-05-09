"""Issue / 失效追踪、FA 分析记录、Issue 附件模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
#  Status Enums
# ═══════════════════════════════════════════════════════════════════

class IssueStatus(str, Enum):
    """Issue 状态。"""
    OPEN = "open"
    ANALYZING = "analyzing"
    VERIFIED = "verified"
    CLOSED = "closed"


class IssueSeverity(str, Enum):
    """Issue 严重度。"""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    COSMETIC = "cosmetic"


class AttachmentType(str, Enum):
    """附件类型。"""
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    OTHER = "other"


# ═══════════════════════════════════════════════════════════════════
#  Dataclass Models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Issue:
    """Issue / 失效追踪 — 测试中发现的问题。"""
    id: Optional[int] = None
    project_id: Optional[int] = None
    plan_id: Optional[int] = None
    task_id: Optional[int] = None
    sample_id: Optional[int] = None
    title: str = ""
    failure_mode: str = ""    # 失效模式关键词
    failure_stage: str = ""   # "48h 高温失效" / "跌落第3次"
    description: str = ""
    severity: str = IssueSeverity.MAJOR.value
    status: str = IssueStatus.OPEN.value
    priority: int = 3
    assignee_id: Optional[int] = None
    dri_name: str = ""              # DRI 责任人（自由输入）
    root_cause: str = ""
    resolution: str = ""
    failure_code: str = ""      # 失效代码 (如 GJB/Z 1391 编码)
    occurrence_count: int = 1   # 发生次数
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        # 防御性类型转换：从 DB 或调用方可能传入 str
        if isinstance(self.priority, str):
            try:
                self.priority = int(self.priority)
            except (ValueError, TypeError):
                self.priority = 3  # 回退到默认值
        if isinstance(self.occurrence_count, str):
            try:
                self.occurrence_count = int(self.occurrence_count)
            except (ValueError, TypeError):
                self.occurrence_count = 1
        if self.occurrence_count < 1:
            raise ValueError(f"发生次数必须≥1: {self.occurrence_count}")
        if not isinstance(self.priority, int) or self.priority < 1 or self.priority > 5:
            raise ValueError(f"优先级必须在 1-5 之间: {self.priority}")


@dataclass
class FARecord:
    """FA 分析记录 — Issue 的多步骤分析过程。"""
    id: Optional[int] = None
    issue_id: int = 0
    step_no: int = 1
    step_title: str = ""
    description: str = ""
    method: str = ""          # 外观检查/切片分析/CT扫描/SEM/...
    findings: str = ""
    possible_cause: str = ""  # 可能原因
    cause_category: str = ""  # 鱼骨图分类: 人/机/料/法/环/测
    failure_mechanism: str = ""  # 失效机理分类
    confirmed: int = 0        # 是否确认: 0=待定, 1=确认, 2=排除
    analyst_id: Optional[int] = None
    attachments: str = "[]"   # JSON
    created_at: str = ""


@dataclass
class IssueAttachment:
    """Issue 附件 — 关联到 Issue 的文件。"""
    id: Optional[int] = None
    issue_id: int = 0
    file_path: str = ""
    file_type: str = AttachmentType.IMAGE.value
    description: str = ""
    created_at: str = ""


class CAPAStatus(str, Enum):
    """CAPA 状态。"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"


@dataclass
class CAPARecord:
    """CAPA 纠正预防措施 — Issue 关联的改进行动。"""
    id: Optional[int] = None
    issue_id: int = 0
    action: str = ""           # 纠正/预防措施描述
    assignee_id: Optional[int] = None
    assignee_name: str = ""       # 责任人自由文本
    due_date: str = ""         # 截止日期
    status: str = CAPAStatus.PENDING.value
    verification_result: str = ""  # 验证结果
    verified_by: Optional[int] = None
    verifier_name: str = ""       # 验证人自由文本
    root_cause: str = ""       # PDCA Plan: 根因分析
    effectiveness: str = ""    # PDCA Check: 效果验证
    follow_up: str = ""        # PDCA Act: 改善追踪
    created_at: str = ""
    updated_at: str = ""
