"""样品 Service — 样品 CRUD + 出入库。"""

from __future__ import annotations

import logging

from src.db.repositories import SampleRepository
from src.db.repositories.test_result_repo import TestResultRepository
from src.db.repositories.issue_repo import IssueRepository
from src.models.sample import Sample, SampleTransaction

logger = logging.getLogger(__name__)


class SampleService:
    """样品业务逻辑。"""

    def __init__(
        self,
        repo: SampleRepository,
        test_result_repo: TestResultRepository | None = None,
        issue_repo: IssueRepository | None = None,
    ) -> None:
        self._repo = repo
        self._test_result_repo = test_result_repo
        self._issue_repo = issue_repo

    def create(self, sn: str, **kwargs: object) -> int:
        return self._repo.insert(sn=sn, **kwargs)

    def count_by_status(self, project_id: int | None = None) -> dict[str, int]:
        """按状态分组计数（委托给 repo）。"""
        return self._repo.count_by_status(project_id=project_id)


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
        """删除样品，有引用时拒绝删除。"""
        reasons: list[str] = []

        if self._test_result_repo is not None:
            result_count = self._test_result_repo.count_by_sample(sample_id)
            if result_count > 0:
                reasons.append(f"{result_count} 条测试结果")

        if self._issue_repo is not None:
            issue_count = self._issue_repo.count_by_sample(sample_id)
            if issue_count > 0:
                reasons.append(f"{issue_count} 个 Issue")

        if reasons:
            detail = "、".join(reasons)
            raise ValueError(
                f"样品 #{sample_id} 仍被 {detail} 引用，请先解除关联"
            )

        with self._repo.transaction():
            # 先删出入库记录（子表），再删样品（父表）
            self._repo.delete_transactions(sample_id)
            self._repo.delete(sample_id)

    def list_all(self) -> list[Sample]:
        return self._repo.list_all()

    def get_transactions(self, sample_id: int) -> list[SampleTransaction]:
        return self._repo.get_transactions(sample_id)

    def add_transaction(self, sample_id: int, txn_type: str, **kwargs: object) -> int:
        """添加出入库记录。"""
        return self._repo.add_transaction(sample_id, txn_type, **kwargs)

    def delete_transactions(self, sample_id: int) -> None:
        """删除样品的所有出入库记录（级联删除子表）。"""
        return self._repo.delete_transactions(sample_id)

    def list_transactions(
        self, filter_sn: str = "", filter_type: str = ""
    ) -> list[dict]:
        """查询所有出入库记录（含 JOIN 信息）。

        Args:
            filter_sn: 可选 SN 模糊搜索。
            filter_type: 可选操作类型精确过滤。

        Returns:
            字典列表，每个字典包含 sample_sn, batch_no, operator_name 等字段。
        """
        return self._repo.list_transactions(filter_sn, filter_type)

    def transaction(self):
        """事务上下文管理器。"""
        return self._repo.transaction()
