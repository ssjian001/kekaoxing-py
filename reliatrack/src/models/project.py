"""项目模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProjectStatus(str, Enum):
    """项目状态。"""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


@dataclass
class Project:
    """项目 — 顶层实体，所有数据均挂在项目下。"""
    id: Optional[int] = None
    name: str = ""
    product: str = ""
    customer: str = ""
    description: str = ""
    status: str = ProjectStatus.ACTIVE.value
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        # 防御性验证：不 raise，只修正和警告
        if isinstance(self.name, str) and not self.name:
            import warnings
            warnings.warn("Project.name is empty string")
        _valid_status = {s.value for s in ProjectStatus}
        if self.status not in _valid_status:
            import warnings
            warnings.warn(f"Unknown Project.status: {self.status!r}")
