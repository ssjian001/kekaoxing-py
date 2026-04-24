"""样品与出入库记录模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
#  Status Enums
# ═══════════════════════════════════════════════════════════════════

class SampleStatus(str, Enum):
    """样品状态。"""
    IN_STOCK = "in_stock"
    CHECKED_OUT = "checked_out"
    IN_TEST = "in_test"
    SUSPENDED = "suspended"
    SCRAPPED = "scrapped"
    RETURNED = "returned"


class TransactionType(str, Enum):
    """出入库类型。"""
    CHECK_OUT = "check_out"
    CHECK_IN = "check_in"
    TRANSFER = "transfer"


# ═══════════════════════════════════════════════════════════════════
#  Dataclass Models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Sample:
    """样品 — 实验室核心实体，SN 为唯一标识。"""
    id: Optional[int] = None
    sn: str = ""              # 序列号/唯一标识
    batch_no: str = ""        # 批次号
    spec: str = ""            # 规格型号
    project_id: Optional[int] = None
    status: str = SampleStatus.IN_STOCK.value
    location: str = ""
    qr_code: str = ""         # 本地二维码路径（可选）
    created_at: str = ""
    updated_at: str = ""


@dataclass
class SampleTransaction:
    """样品出入库记录 — 完整的历史流水。"""
    id: Optional[int] = None
    sample_id: int = 0
    type: str = TransactionType.CHECK_OUT.value
    operator_id: Optional[int] = None
    purpose: str = ""         # 测试/拆解/对比分析/...
    related_task_id: Optional[int] = None
    expected_return: str = "" # 预计归还日期
    actual_return: str = ""   # 实际归还日期
    notes: str = ""
    created_at: str = ""
