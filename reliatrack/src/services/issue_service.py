"""Issue Service — Issue CRUD + FA 记录管理。"""

from __future__ import annotations

import logging

from src.db.repositories import IssueRepository
from src.db.connection import DEFAULT_ATTACHMENTS_DIR
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

    def update_fa_record(self, fa_id: int, **kwargs: object) -> None:
        return self._repo.update_fa_record(fa_id, **kwargs)

    def delete_fa_record(self, fa_id: int) -> None:
        return self._repo.delete_fa_record(fa_id)

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

    def update_capa_record(self, capa_id: int, **kwargs: object) -> bool:
        """更新 CAPA 记录。返回 True 表示成功。"""
        self._repo.update_capa_record(capa_id, **kwargs)
        return True

    def delete_capa_record(self, capa_id: int) -> bool:
        """删除单条 CAPA 记录。返回 True 表示成功。"""
        self._repo.delete_capa_record(capa_id)
        return True

    def count_capa_all(self, project_id: int | None = None) -> int:
        """CAPA 记录总数（可按项目筛选）。"""
        return self._repo.count_capa_all(project_id)

    def count_capa_done(self, project_id: int | None = None) -> int:
        """已完成/已验证的 CAPA 记录数。"""
        return self._repo.count_capa_done(project_id)

    def scan_attachment_integrity(self) -> dict[str, list[str]]:
        """扫描附件引用完整性。返回 {'missing_files': [...], 'orphan_files': [...]}。"""
        from pathlib import Path
        result: dict[str, list[str]] = {"missing_files": [], "orphan_files": []}

        # 1. DB 记录指向不存在的文件
        all_issues = self._repo.list_all()
        for issue in all_issues:
            if issue.id is None:
                continue
            for att in self._repo.get_attachments(issue.id):
                if att.file_path and not Path(att.file_path).is_file():
                    result["missing_files"].append(
                        f"Issue#{issue.id} 附件#{att.id}: {att.file_path}"
                    )

        # 2. 磁盘文件无 DB 记录
        attach_dir = DEFAULT_ATTACHMENTS_DIR
        if attach_dir.is_dir():
            db_paths = set()
            for issue in all_issues:
                if issue.id is None:
                    continue
                for att in self._repo.get_attachments(issue.id):
                    if att.file_path:
                        db_paths.add(att.file_path)
            for fp in attach_dir.rglob("*"):
                if fp.is_file() and str(fp) not in db_paths:
                    result["orphan_files"].append(str(fp))

        return result
