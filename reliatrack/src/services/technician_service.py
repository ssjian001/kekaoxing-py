"""技术员 Service — 技术员 CRUD。"""

from __future__ import annotations

from src.db.repositories import TechnicianRepository
from src.models.common import Technician


class TechnicianService:
    """技术员业务逻辑。"""

    def __init__(self, repo: TechnicianRepository) -> None:
        self._repo = repo

    def create(self, name: str, **kwargs: object) -> int:
        return self._repo.insert(name=name, **kwargs)

    def get(self, technician_id: int) -> Technician | None:
        return self._repo.get_by_id(technician_id)

    def update(self, technician_id: int, **kwargs: object) -> None:
        self._repo.update(technician_id, **kwargs)

    def delete(self, technician_id: int) -> None:
        self._repo.delete(technician_id)

    def list_all(self) -> list[Technician]:
        return self._repo.list_all()
