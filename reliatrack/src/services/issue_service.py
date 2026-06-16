"""Issue Service — Issue CRUD + FA 记录管理 + Bug Tracker（评论/活动日志/关联）。"""

from __future__ import annotations

import logging

from src.db.repositories import IssueRepository
from src.db.repositories.issue_repo import (
    IssueCommentRepository,
    IssueActivityLogRepository,
    IssueLinkRepository,
)
from src.db.connection import DEFAULT_ATTACHMENTS_DIR
from src.models.issue import (
    Issue, FARecord, IssueAttachment, CAPARecord,
    IssueComment, IssueActivityLog, IssueLink,
)

logger = logging.getLogger(__name__)

# 活动日志追踪的字段（变更时自动记录）
_TRACKED_FIELDS = {
    "status", "severity", "assignee_id", "priority", "resolution", "category",
}


class IssueService:
    """Issue / FA / Bug Tracker 业务逻辑。"""

    def __init__(self, repo: IssueRepository, conn=None) -> None:
        self._repo = repo
        self._conn = conn or repo.conn
        # v23 新增 repo
        self._comment_repo = IssueCommentRepository(self._conn)
        self._activity_repo = IssueActivityLogRepository(self._conn)
        self._link_repo = IssueLinkRepository(self._conn)

    # ── 状态机（集中管理）──

    @staticmethod
    def can_transition(
        current_status: str, target_status: str, issue: Issue | None = None,
        has_fa_records: bool | None = None,
    ) -> tuple[bool, str]:
        """检查状态转换是否允许。返回 (是否允许, 原因)。

        约束：
        - open → analyzing: 允许
        - open/analyzing → verified: 需要有 FA 记录（has_fa_records 不为 None 时检查）
        - → closed: 需要有 resolution（issue 不为 None 时检查）
        - closed → open: reopen，允许
        - analyzing/verified → open: 回退，允许
        """
        if issue is None:
            raise ValueError("can_transition requires an issue object")
        from src.constants import ISSUE_TRANSITIONS

        if current_status == target_status:
            return True, ""

        allowed = ISSUE_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            return False, f"不允许从「{current_status}」转到「{target_status}」"

        # verified 前置条件：必须有 FA 记录
        if target_status == "verified" and has_fa_records is False:
            return False, "转入「已验证」前必须有 FA 分析记录"

        # closed 前置条件：必须有 resolution
        if target_status == "closed" and issue is not None:
            if not issue.resolution or issue.resolution == "":
                return False, "关闭前必须选择处理结果（Resolution）"

        return True, ""

    def transition_status(self, issue_id: int, target: str, operator: str = "") -> tuple[bool, str]:
        """执行状态转换（带校验 + 活动日志）。返回 (是否成功, 原因)。"""
        issue = self._repo.get_by_id(issue_id)
        if issue is None:
            return False, f"Issue #{issue_id} 不存在"

        fa_records = self._repo.get_fa_records(issue_id) if issue_id else []
        ok, reason = self.can_transition(
            issue.status, target, issue, has_fa_records=bool(fa_records),
        )
        if not ok:
            return False, reason

        old_status = issue.status
        kwargs: dict[str, object] = {"status": target}
        # reopen 时清空 resolution
        if target == "open" and old_status in ("closed", "verified"):
            kwargs["resolution"] = ""

        self._repo.update(issue_id, **kwargs)
        # 活动日志
        self._activity_repo.add(issue_id, "status", old_status, target, operator)
        if "resolution" in kwargs:
            self._activity_repo.add(
                issue_id, "resolution",
                issue.resolution or "", str(kwargs["resolution"]), operator,
            )
        return True, ""

    # ── Issue CRUD（带活动日志）──

    def create(self, title: str, **kwargs: object) -> int:
        return self._repo.insert(title=title, **kwargs)

    def get(self, issue_id: int) -> Issue | None:
        return self._repo.get_by_id(issue_id)

    def get_by_project(self, project_id: int) -> list[Issue]:
        return self._repo.get_by_project(project_id)

    def get_unassigned(self) -> list[Issue]:
        """返回未关联任何项目 (project_id IS NULL) 的 Issue。"""
        return self._repo.get_unassigned()

    def get_by_status(self, status: str) -> list[Issue]:
        return self._repo.get_by_status(status)

    def get_by_task(self, task_id: int) -> list[Issue]:
        return self._repo.get_by_task(task_id)

    def update(self, issue_id: int, operator: str = "", **kwargs: object) -> None:
        """更新 Issue，自动记录活动日志（6 个追踪字段）。

        状态转换不在此方法做校验（用 transition_status）。
        FA/CAPA 联动调用 update 不受状态机限制，仅记录日志。
        """
        # 获取旧值用于活动日志
        old_issue = self._repo.get_by_id(issue_id) if _TRACKED_FIELDS & set(kwargs.keys()) else None

        # reopen 时清空 resolution（兼容旧逻辑）
        new_status = kwargs.get("status")
        if new_status == "open" and old_issue and old_issue.status in ("closed", "verified"):
            kwargs.setdefault("resolution", "")

        # 非阻断状态转换 warning（兼容旧逻辑，正式校验用 transition_status）
        if new_status is not None and old_issue and old_issue.status != new_status:
            from src.constants import ISSUE_TRANSITIONS
            allowed = ISSUE_TRANSITIONS.get(old_issue.status, set())
            if new_status not in allowed:
                logger.warning(
                    "Status transition %s → %s not in allowed set %s "
                    "(use transition_status() for validated changes)",
                    old_issue.status, new_status, allowed,
                )

        self._repo.update(issue_id, **kwargs)

        # 自动记录活动日志
        if old_issue is not None:
            for field in _TRACKED_FIELDS:
                if field not in kwargs:
                    continue
                old_val = getattr(old_issue, field, "")
                new_val = kwargs[field]
                if str(old_val) != str(new_val):
                    self._activity_repo.add(
                        issue_id, field, str(old_val), str(new_val), operator,
                    )

    def update_status(self, issue_id: int, status: str) -> None:
        self._repo.update_status(issue_id, status)

    def delete(self, issue_id: int) -> None:
        with self._repo.transaction():
            # 先删子表，再删 Issue（父表）
            self._repo.delete_fa_records(issue_id)
            self._repo.delete_capa_records(issue_id)
            self._repo.delete_attachments(issue_id)
            self._repo.delete(issue_id)

    def soft_delete(self, issue_id: int) -> None:
        """软删除 Issue：标记为已删除但保留数据。"""
        self._repo.soft_delete(issue_id)

    def list_deleted(self) -> list[Issue]:
        """查询所有已软删除的 Issue。"""
        return self._repo.list_deleted()

    def restore(self, issue_id: int) -> None:
        """恢复已软删除的 Issue。"""
        self._repo.restore(issue_id)

    def purge_old(self, days: int = 30) -> int:
        """彻底删除已软删除超过 N 天的 Issue，返回删除行数。"""
        return self._repo.purge_old(days)

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

    # ── 评论（v23 新增）──

    def add_comment(self, issue_id: int, content: str, author_name: str = "") -> int:
        """添加评论，返回评论 ID。"""
        return self._comment_repo.insert(
            issue_id=issue_id, content=content, author_name=author_name,
        )

    def get_comments(self, issue_id: int) -> list[IssueComment]:
        """获取某 Issue 的所有评论（未删除，按时间升序）。"""
        return self._comment_repo.get_by_issue(issue_id)

    def delete_comment(self, comment_id: int) -> None:
        """软删除评论。"""
        self._comment_repo.soft_delete(comment_id)

    # ── 活动日志（v23 新增）──

    def get_activity_log(self, issue_id: int) -> list[IssueActivityLog]:
        """获取某 Issue 的活动日志（按时间升序）。"""
        return self._activity_repo.get_by_issue(issue_id)

    def get_activity_with_duration(self, issue_id: int) -> list[dict]:
        """获取活动日志 + 每条状态变更的停留时长。

        返回 list[dict]，每条含：field, old_value, new_value, operator,
        created_at (变更时间), stay_duration (在此状态的停留时长字符串)。
        """
        from datetime import datetime

        logs = self._activity_repo.get_by_issue(issue_id)
        if not logs:
            return []

        # 从 issue.updated_at 或 created_at 作为最后锚点
        issue = self._repo.get_by_id(issue_id)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result: list[dict] = []
        for i, log in enumerate(logs):
            # 下一条日志的时间作为结束点
            if i + 1 < len(logs):
                end_str = logs[i + 1].created_at or now_str
            else:
                end_str = now_str

            # 计算停留时长
            duration_str = ""
            if log.created_at and end_str:
                try:
                    fmt = "%Y-%m-%d %H:%M:%S"
                    start = datetime.strptime(log.created_at[:19], fmt)
                    end = datetime.strptime(end_str[:19], fmt)
                    delta = end - start
                    days = delta.days
                    hours = delta.seconds // 3600
                    if days > 0:
                        duration_str = f"{days}天{hours}小时"
                    elif hours > 0:
                        duration_str = f"{hours}小时"
                    else:
                        minutes = delta.seconds // 60
                        duration_str = f"{minutes}分钟"
                except (ValueError, TypeError):
                    pass

            result.append({
                "field": log.field,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "operator": log.operator,
                "created_at": log.created_at,
                "stay_duration": duration_str,
            })

        return result

    # ── Issue 关联（v23 新增）──

    def add_link(self, source_id: int, target_id: int, link_type: str = "relates_to") -> int:
        """创建 Issue 关联。自引用/重复会抛 ConstraintError。"""
        return self._link_repo.add(source_id, target_id, link_type)

    def get_links(self, issue_id: int) -> list[IssueLink]:
        """获取某 Issue 的所有关联（双向）。"""
        return self._link_repo.get_for_issue(issue_id)

    def delete_link(self, link_id: int) -> None:
        """删除关联。"""
        self._link_repo.delete(link_id)

    # ── Aging 计算 ──

    def get_aging_days(self, issue_id: int) -> int:
        """获取 Issue 在当前状态的停留天数。

        从活动日志最后一次 status 变更算起。
        无活动日志时用 updated_at，再不行用 created_at。
        """
        from datetime import datetime

        logs = self._activity_repo.get_by_issue(issue_id)
        status_changes = [l for l in logs if l.field == "status"]
        if status_changes:
            last_change = status_changes[-1].created_at
        else:
            issue = self._repo.get_by_id(issue_id)
            last_change = issue.updated_at or issue.created_at if issue else ""

        if not last_change:
            return 0

        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            start = datetime.strptime(last_change[:19], fmt)
            return (datetime.now() - start).days
        except (ValueError, TypeError):
            return 0

    # ── 附件完整性扫描 ──

    def scan_attachment_integrity(self) -> dict[str, list[str]]:
        """扫描附件引用完整性。返回 {'missing_files': [...], 'orphan_files': [...]}。"""
        from pathlib import Path
        result: dict[str, list[str]] = {"missing_files": [], "orphan_files": []}

        # 一次查询获取所有附件，按 issue_id 分组（消除 N+1）
        all_attachments = self._repo.get_all_attachments()
        issue_map: dict[int, int] = {}
        for att in all_attachments:
            issue_map[att.id] = att.issue_id

        # 1. DB 记录指向不存在的文件
        db_paths: set[str] = set()
        for att in all_attachments:
            if att.file_path:
                db_paths.add(att.file_path)
                if not Path(att.file_path).is_file():
                    result["missing_files"].append(
                        f"Issue#{att.issue_id} 附件#{att.id}: {att.file_path}"
                    )

        # 2. 磁盘文件无 DB 记录
        attach_dir = DEFAULT_ATTACHMENTS_DIR
        if attach_dir.is_dir():
            for fp in attach_dir.rglob("*"):
                if fp.is_file() and str(fp) not in db_paths:
                    result["orphan_files"].append(str(fp))

        return result

    # ── Delete Command 工厂 ──

    def create_delete_command(self, issue_id: int):
        """创建 Issue 软删除命令（可撤销）。"""
        from src.services.undo_manager import SoftDeleteCommand
        return SoftDeleteCommand(self._repo, issue_id, "Issue")

    def create_fa_delete_command(self, fa_id: int):
        """创建 FA 记录删除命令（可撤销）。"""
        from src.db.repositories.issue_repo import FARecordRepository
        from src.services.undo_manager import DeleteEntityCommand
        fa_repo = FARecordRepository(self._conn)
        return DeleteEntityCommand(fa_repo, fa_id, "FA 步骤")

    def create_capa_delete_command(self, capa_id: int):
        """创建 CAPA 记录删除命令（可撤销）。"""
        from src.db.repositories.issue_repo import CAPARecordRepository
        from src.services.undo_manager import DeleteEntityCommand
        capa_repo = CAPARecordRepository(self._conn)
        return DeleteEntityCommand(capa_repo, capa_id, "CAPA 措施")

    def create_status_change_command(self, issue_id: int, old_status: str, new_status: str):
        """创建状态变更命令（可撤销 — 看板拖拽用）。"""
        from src.services.undo_manager import UpdateFieldCommand
        return UpdateFieldCommand(
            self._repo, issue_id, "status", old_status, new_status, "Issue 状态",
        )
