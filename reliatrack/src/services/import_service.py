"""导入服务 — 设备、技术员 Excel 批量导入逻辑。

返回 ImportResult 命名元组，包含成功数、跳过数和跳过原因详情。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.services.equipment_service import EquipmentService
from src.services.technician_service import TechnicianService

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """批量导入结果。"""
    success: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def import_equipment(
    rows: list[dict],
    service: EquipmentService,
) -> ImportResult:
    """批量导入设备。

    Args:
        rows: [{field: value, ...}, ...]
        service: EquipmentService 实例

    Returns:
        ImportResult — 含成功数、跳过数和每条跳过的原因。
    """
    existing = {eq.name for eq in service.list_all()}
    seen_this_batch: set[str] = set()
    result = ImportResult()
    for idx, row in enumerate(rows, 1):
        name = row.get("name", "").strip()
        if not name:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 设备名称为空")
            continue
        if name in existing:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 设备「{name}」已存在")
            continue
        if name in seen_this_batch:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 设备「{name}」与本批次重复")
            continue
        try:
            service.create(
                name=name,
                type=row.get("type", "").strip(),
                model=row.get("model", "").strip(),
                location=row.get("location", "").strip(),
                status=row.get("status", "available").strip(),
                calibration_date=row.get("calibration_date", "").strip(),
                next_calibration_date=row.get("next_calibration_date", "").strip(),
            )
            seen_this_batch.add(name)
            result.success += 1
        except Exception as e:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 设备「{name}」导入失败 — {e}")
    return result


def import_technicians(
    rows: list[dict],
    service: TechnicianService,
) -> ImportResult:
    """批量导入技术员。

    Args:
        rows: [{field: value, ...}, ...]
        service: TechnicianService 实例

    Returns:
        ImportResult — 含成功数、跳过数和每条跳过的原因。
    """
    existing = {(t.name, t.employee_id) for t in service.list_all()}
    seen_this_batch: set[tuple[str, str]] = set()
    result = ImportResult()
    for idx, row in enumerate(rows, 1):
        name = row.get("name", "").strip()
        if not name:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 技术员名称为空")
            continue
        emp_id = row.get("employee_id", "").strip()
        key = (name, emp_id)
        if key in existing:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 技术员「{name}({emp_id})」已存在")
            continue
        if key in seen_this_batch:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 技术员「{name}({emp_id})」与本批次重复")
            continue
        try:
            service.create(
                name=name,
                employee_id=emp_id,
                role=row.get("role", "").strip(),
                department=row.get("department", "").strip(),
                phone=row.get("phone", "").strip(),
                email=row.get("email", "").strip(),
            )
            seen_this_batch.add(key)
            result.success += 1
        except Exception as e:
            result.skipped += 1
            result.errors.append(f"第 {idx} 行: 技术员「{name}」导入失败 — {e}")
    return result
