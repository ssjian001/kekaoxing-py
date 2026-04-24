"""通用实体模型：Technician, Equipment, Settings。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
#  Status Enums
# ═══════════════════════════════════════════════════════════════════

class EquipmentStatus(str, Enum):
    """设备状态。"""
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


# ═══════════════════════════════════════════════════════════════════
#  Dataclass Models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Technician:
    """技术员 / 测试人员。"""
    id: Optional[int] = None
    name: str = ""
    role: str = ""        # DQE / QE / 测试员 / ...
    department: str = ""
    created_at: str = ""


@dataclass
class Equipment:
    """测试设备。"""
    id: Optional[int] = None
    name: str = ""
    type: str = ""        # 高低温箱 / 跌落机 / 振动台 / ...
    model: str = ""
    location: str = ""
    status: str = EquipmentStatus.AVAILABLE.value
    created_at: str = ""


@dataclass
class Settings:
    """系统设置（键值对）。"""
    key: str = ""
    value: str = ""
    updated_at: str = ""
