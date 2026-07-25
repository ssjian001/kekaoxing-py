"""设备 Service — 设备 CRUD。"""

from __future__ import annotations

import logging

from src.db.repositories import EquipmentRepository
from src.models.common import Equipment

logger = logging.getLogger(__name__)


class EquipmentService:
    """设备业务逻辑。"""

    def __init__(self, repo: EquipmentRepository) -> None:
        self._repo = repo

    def create(self, name: str, **kwargs: object) -> int:
        return self._repo.insert(name=name, **kwargs)

    def get(self, equipment_id: int) -> Equipment | None:
        return self._repo.get_by_id(equipment_id)

    def get_available(self) -> list[Equipment]:
        return self._repo.get_available()

    def get_by_type(self, type: str) -> list[Equipment]:
        return self._repo.get_by_type(type)

    def update(self, equipment_id: int, **kwargs: object) -> None:
        self._repo.update(equipment_id, **kwargs)

    def delete(self, equipment_id: int) -> None:
        # 检查是否被 test_tasks 引用
        ref_count = self._repo.count_task_references(equipment_id)
        if ref_count > 0:
            raise ValueError(
                f"设备 #{equipment_id} 仍被 {ref_count} 个任务引用，请先解除分配"
            )
        self._repo.delete(equipment_id)

    def list_all(self) -> list[Equipment]:
        return self._repo.list_all()

    def create_delete_command(self, equipment_id: int):
        """创建删除命令（含前置校验）。"""
        from src.services.undo_manager import DeleteEntityCommand
        ref_count = self._repo.count_task_references(equipment_id)
        if ref_count > 0:
            raise ValueError(
                f"设备 #{equipment_id} 仍被 {ref_count} 个任务引用，请先解除分配"
            )
        return DeleteEntityCommand(self._repo, equipment_id, "设备")

    def transaction(self):
        """事务上下文管理器。"""
        return self._repo.transaction()

    def get_expiring_calibrations(self, days: int = 30) -> list[tuple[Equipment, int]]:
        """查找 N 天内即将到期或已过期的校准设备，返回 [(Equipment, remaining_days)]。"""
        from datetime import date
        today = date.today()
        expiring = []
        for eq in self.list_all():
            if not eq.next_calibration_date:
                continue
            try:
                cal_date = date.fromisoformat(eq.next_calibration_date)
                delta_days = (cal_date - today).days
                if delta_days <= days:
                    expiring.append((eq, delta_days))
            except ValueError:
                pass
        expiring.sort(key=lambda x: x[1])
        return expiring
