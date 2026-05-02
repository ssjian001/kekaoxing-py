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
    employee_id: str = ""   # 工号
    role: str = ""           # 职位: DQE / QE / 测试员 / ...
    department: str = ""     # 部门: 测试部/研发部/质量部/其他
    phone: str = ""          # 联系方式
    email: str = ""          # 邮箱
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
    calibration_date: str = ""
    next_calibration_date: str = ""
    calibration_interval_months: int = 12
    asset_no: str = ""       # 资产编号
    manufacturer: str = ""   # 制造商
    accuracy: str = ""       # 精度/不确定度
    created_at: str = ""


@dataclass
class Settings:
    """系统设置（键值对）。"""
    key: str = ""
    value: str = ""
    updated_at: str = ""
