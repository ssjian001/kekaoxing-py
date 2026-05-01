"""导入服务 — 设备、技术员 Excel 批量导入逻辑。"""

from __future__ import annotations

from src.models.common import Equipment, Technician
from src.services.equipment_service import EquipmentService
from src.services.technician_service import TechnicianService


def import_equipment(
    rows: list[dict],
    service: EquipmentService,
) -> tuple[int, int]:
    """批量导入设备。

    Args:
        rows: [{field: value, ...}, ...]
        service: EquipmentService 实例

    Returns:
        (成功数, 跳过数)
    """
    success = 0
    skipped = 0
    for row in rows:
        name = row.get("name", "").strip()
        if not name:
            skipped += 1
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
            success += 1
        except Exception:
            skipped += 1
    return success, skipped


def import_technicians(
    rows: list[dict],
    service: TechnicianService,
) -> tuple[int, int]:
    """批量导入技术员。

    Args:
        rows: [{field: value, ...}, ...]
        service: TechnicianService 实例

    Returns:
        (成功数, 跳过数)
    """
    success = 0
    skipped = 0
    for row in rows:
        name = row.get("name", "").strip()
        if not name:
            skipped += 1
            continue
        try:
            service.create(
                name=name,
                employee_id=row.get("employee_id", "").strip(),
                role=row.get("role", "").strip(),
                department=row.get("department", "").strip(),
                phone=row.get("phone", "").strip(),
                email=row.get("email", "").strip(),
            )
            success += 1
        except Exception:
            skipped += 1
    return success, skipped
