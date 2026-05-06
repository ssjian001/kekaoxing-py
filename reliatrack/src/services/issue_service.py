"""Issue Service — Issue CRUD + FA 记录管理。"""

from __future__ import annotations

import logging

from src.db.repositories import IssueRepository
from src.models.issue import Issue, FARecord, IssueAttachment, CAPARecord

logger = logging.getLogger(__name__)


class IssueService:
    """Issue / FA 业务逻辑。"""

    def __init__(self, repo: IssueRepository) -> None:
        self._repo = repo

    # ── Issue CRUD ──

    def create(self, title: str, **kwargs: object) -> int:
        return self._repo.insert(title=title, **kwargs)

    def get(self, issue_id: int) -> Issue | None:
        return self._repo.get_by_id(issue_id)

    def get_by_project(self, project_id: int) -> list[Issue]:
        return self._repo.get_by_project(project_id)

    def get_by_status(self, status: str) -> list[Issue]:
        return self._repo.get_by_status(status)

    def get_by_task(self, task_id: int) -> list[Issue]:
        return self._repo.get_by_task(task_id)

    def update(self, issue_id: int, **kwargs: object) -> None:
        self._repo.update(issue_id, **kwargs)

    def update_status(self, issue_id: int, status: str) -> None:
        self._repo.update_status(issue_id, status)

    def delete(self, issue_id: int) -> None:
        with self._repo.transaction():
            # 先删子表，再删 Issue（父表）
            self._repo.delete_fa_records(issue_id)
            self._repo.delete_capa_records(issue_id)
            self._repo.delete_attachments(issue_id)
            self._repo.delete(issue_id)

    def list_all(self) -> list[Issue]:
        return self._repo.list_all()

    # ── FA 记录 ──

    def add_fa_record(self, issue_id: int, **kwargs: object) -> int:
        return self._repo.add_fa_record(issue_id, **kwargs)

    def get_fa_records(self, issue_id: int) -> list[FARecord]:
        return self._repo.get_fa_records(issue_id)

    # ── 附件 ──

    def add_attachment(self, issue_id: int, **kwargs: object) -> int:
        return self._repo.add_attachment(issue_id, **kwargs)

    def get_attachments(self, issue_id: int) -> list[IssueAttachment]:
        return self._repo.get_attachments(issue_id)

    def delete_attachment(self, attachment_id: int) -> None:  # attachment management
        """删除单条附件。"""
        self._repo.delete_attachment(attachment_id)

    # ── CAPA 记录 ──

    def add_capa_record(self, issue_id: int, **kwargs: object) -> int:
        return self._repo.add_capa_record(issue_id, **kwargs)

    def get_capa_records(self, issue_id: int) -> list[CAPARecord]:
        return self._repo.get_capa_records(issue_id)

    def count_capa_all(self, project_id: int | None = None) -> int:
        """CAPA 记录总数（可按项目筛选）。"""
        return self._repo.count_capa_all(project_id)

    def count_capa_done(self, project_id: int | None = None) -> int:
        """已完成/已验证的 CAPA 记录数。"""
        return self._repo.count_capa_done(project_id)
