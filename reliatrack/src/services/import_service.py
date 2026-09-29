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


def _cell_text(value: object) -> str:
    """把 Excel 单元格值规整为去空白的 str（永不抛异常）。

    Excel 数字单元格是 float/int，None 则来自空单元格。旧实现直接
    `row.get("name", "").strip()`，遇到数字单元格抛 AttributeError ——
    且该语句在行级 try 之外，异常被外层吞掉后整批回滚、errors 里却
    一条原因都没有（审计 P2-7）。这里做全类型兜底。
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def import_equipment(
    rows: list[dict],
    service: EquipmentService,
) -> ImportResult:
    """批量导入设备（事务包裹：任一行写入失败整体回滚）。

    Args:
        rows: [{field: value, ...}, ...]
        service: EquipmentService 实例

    Returns:
        ImportResult — 含成功数、跳过数和每条跳过的原因。
    """
    existing = {eq.name for eq in service.list_all()}
    seen_this_batch: set[str] = set()
    result = ImportResult()

    try:
        with service.transaction():
            for idx, row in enumerate(rows, 1):
                name = _cell_text(row.get("name"))
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
                    # 审计 #16：Excel 数字单元格可能是 float（6.0）或文本，
                    # 直接 int()/strip() 会炸整批。先做类型规整 + 行级校验。
                    # None/空串回落默认 12（与旧行为一致）。
                    raw_interval = row.get("calibration_interval_months", 12)
                    if raw_interval is None or str(raw_interval).strip() == "":
                        interval = 12
                    else:
                        try:
                            interval = int(float(str(raw_interval).strip()))
                        except (ValueError, TypeError):
                            result.skipped += 1
                            result.errors.append(
                                f"第 {idx} 行: 设备「{name}」校准间隔不是有效数字: {raw_interval!r}"
                            )
                            continue

                    def _cell_str(key: str) -> str:
                        return _cell_text(row.get(key))

                    service.create(
                        name=name,
                        type=_cell_str("type"),
                        model=_cell_str("model"),
                        location=_cell_str("location"),
                        status=_cell_str("status") or "available",
                        asset_no=_cell_str("asset_no"),
                        manufacturer=_cell_str("manufacturer"),
                        accuracy=_cell_str("accuracy"),
                        calibration_date=_cell_str("calibration_date"),
                        next_calibration_date=_cell_str("next_calibration_date"),
                        calibration_interval_months=interval,
                    )
                    seen_this_batch.add(name)
                    result.success += 1
                except Exception as e:
                    logger.exception("Error in import_service")
                    result.errors.append(f"第 {idx} 行: 设备「{name}」导入失败 — {e}")
                    raise  # 触发事务回滚
    except Exception:
        logger.exception("Error in import_service")
        # 事务已回滚，success 计数无效
        result.success = 0
    return result


def import_technicians(
    rows: list[dict],
    service: TechnicianService,
) -> ImportResult:
    """批量导入技术员（事务包裹：任一行写入失败整体回滚）。"""
    existing = {(t.name, t.employee_id) for t in service.list_all()}
    seen_this_batch: set[tuple[str, str]] = set()
    result = ImportResult()

    try:
        with service.transaction():
            for idx, row in enumerate(rows, 1):
                name = _cell_text(row.get("name"))
                if not name:
                    result.skipped += 1
                    result.errors.append(f"第 {idx} 行: 技术员名称为空")
                    continue
                emp_id = _cell_text(row.get("employee_id"))
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
                        role=_cell_text(row.get("role")),
                        department=_cell_text(row.get("department")),
                        phone=_cell_text(row.get("phone")),
                        email=_cell_text(row.get("email")),
                    )
                    seen_this_batch.add(key)
                    result.success += 1
                except Exception as e:
                    logger.exception("Error in import_service")
                    result.errors.append(f"第 {idx} 行: 技术员「{name}」导入失败 — {e}")
                    raise  # 触发事务回滚
    except Exception:
        logger.exception("Error in import_service")
        # 事务已回滚，success 计数无效
        result.success = 0
    return result
