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

    def create_with_ledger(self, sn: str, **kwargs: object) -> int:
        """创建样品并写入入库台账（单事务原子化）。

        台账写入失败时整体回滚——不会出现"样品已创建但无流水记录"
        的不一致状态（2026-08-21 审计 #2）。
        """
        with self._repo.transaction():
            sample_id = self._repo.insert(sn=sn, **kwargs)
            # 状态联动由 create 的 status="in_stock" 完成，
            # 此处直接写台账行，不再走 add_transaction 的冗余 update_status
            self._repo.add_transaction(sample_id, "check_in")
        return sample_id

    def count_by_status(self, project_id: int | None = None) -> dict[str, int]:
        """按状态分组计数（委托给 repo）。

        注意：生产走 ctrl.test_tasks.count_by_status（refresh_handlers），
        此方法为样品侧对称 API，暂无调用方。
        """
        return self._repo.count_by_status(project_id=project_id)


    def get(self, sample_id: int) -> Sample | None:
        return self._repo.get_by_id(sample_id)

    def get_by_sn(self, sn: str) -> Sample | None:
        return self._repo.get_by_sn(sn)

    def get_by_project(self, project_id: int) -> list[Sample]:
        return self._repo.get_by_project(project_id)

    def update(self, sample_id: int, **kwargs: object) -> None:
        self._repo.update(sample_id, **kwargs)

    def update_status(self, sample_id: int, status: str) -> None:
        self._repo.update_status(sample_id, status)

    def _check_references(self, sample_id: int) -> None:
        """检查样品是否被其他实体引用，有引用则抛 ValueError。"""
        reasons: list[str] = []

        if self._test_result_repo is not None:
            result_count = self._test_result_repo.count_by_sample(sample_id)
            if result_count > 0:
                reasons.append(f"{result_count} 条测试结果")

        if self._issue_repo is not None:
            issue_count = self._issue_repo.count_by_sample(sample_id)
            if issue_count > 0:
                reasons.append(f"{issue_count} 个 Issue")
            # 软删 Issue 仍持有 sample_id 外键，删除样品会触发
            # FK ON DELETE CASCADE 物理清除它们（含 FA/CAPA/评论）。
            # 必须阻止，软删 Issue 是保底可恢复数据。
            soft_deleted = self._issue_repo.count_by_sample_all(sample_id) - issue_count
            if soft_deleted > 0:
                reasons.append(f"{soft_deleted} 个已删除 Issue（需先恢复或解除关联）")

        if reasons:
            detail = "、".join(reasons)
            raise ValueError(
                f"样品 #{sample_id} 仍被 {detail} 引用，请先解除关联"
            )

    def delete(self, sample_id: int) -> None:
        """删除样品，有引用时拒绝删除。"""
        with self._repo.transaction():
            self._check_references(sample_id)
            # 1. 清理 test_tasks.sample_ids JSON 中的悬空引用
            self._repo.remove_from_task_sample_ids(sample_id)
            # 2. 删出入库记录（子表），再删样品（父表）
            self._repo.delete_transactions(sample_id)
            self._repo.delete(sample_id)

    def list_all(self) -> list[Sample]:
        return self._repo.list_all()
    def add_transaction(self, sample_id: int, txn_type: str, **kwargs: object) -> int:
        """添加出入库记录，并自动联动样品状态。

        映射: check_out → checked_out, return/check_in → in_stock
        """
        txn_id = self._repo.add_transaction(sample_id, txn_type, **kwargs)

        # 自动联动样品状态
        _STATUS_MAP = {
            "check_out": "checked_out",
            "return": "in_stock",
            "check_in": "in_stock",
        }
        new_status = _STATUS_MAP.get(txn_type)
        if new_status:
            self._repo.update_status(sample_id, new_status)

        return txn_id
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
