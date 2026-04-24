"""设备 Service — 设备 CRUD。"""

from __future__ import annotations

from src.db.repositories import EquipmentRepository
from src.models.common import Equipment


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
        self._repo.delete(equipment_id)

    def list_all(self) -> list[Equipment]:
        return self._repo.list_all()
