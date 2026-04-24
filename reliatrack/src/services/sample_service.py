"""样品 Service — 样品 CRUD + 出入库。"""

from __future__ import annotations

from src.db.repositories import SampleRepository
from src.models.sample import Sample, SampleTransaction


class SampleService:
    """样品业务逻辑。"""

    def __init__(self, repo: SampleRepository) -> None:
        self._repo = repo

    def create(self, sn: str, **kwargs: object) -> int:
        return self._repo.insert(sn=sn, **kwargs)

    def get(self, sample_id: int) -> Sample | None:
        return self._repo.get_by_id(sample_id)

    def get_by_sn(self, sn: str) -> Sample | None:
        return self._repo.get_by_sn(sn)

    def get_by_project(self, project_id: int) -> list[Sample]:
        return self._repo.get_by_project(project_id)

    def get_by_status(self, status: str) -> list[Sample]:
        return self._repo.get_by_status(status)

    def update(self, sample_id: int, **kwargs: object) -> None:
        self._repo.update(sample_id, **kwargs)

    def update_status(self, sample_id: int, status: str) -> None:
        self._repo.update_status(sample_id, status)

    def delete(self, sample_id: int) -> None:
        # 先删出入库记录（子表），再删样品（父表）
        self._repo.delete_transactions(sample_id)
        self._repo.delete(sample_id)

    def list_all(self) -> list[Sample]:
        return self._repo.list_all()

    def get_transactions(self, sample_id: int) -> list[SampleTransaction]:
        return self._repo.get_transactions(sample_id)

    def add_transaction(self, sample_id: int, txn_type: str, **kwargs: object) -> int:
        """添加出入库记录。"""
        return self._repo.insert(sample_id=sample_id, type=txn_type, **kwargs)

    def delete_transactions(self, sample_id: int) -> None:
        """删除样品的所有出入库记录（级联删除子表）。"""
        return self._repo.delete_transactions(sample_id)
