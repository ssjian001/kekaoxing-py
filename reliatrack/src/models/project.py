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
