"""Repository 包 — 数据访问层。"""

from src.db.repositories.base import BaseRepository
from src.db.repositories.project_repo import ProjectRepository
from src.db.repositories.equipment_repo import EquipmentRepository
from src.db.repositories.technician_repo import TechnicianRepository
from src.db.repositories.sample_repo import SampleRepository
from src.db.repositories.test_plan_repo import TestPlanRepository
from src.db.repositories.test_task_repo import TestTaskRepository
from src.db.repositories.issue_repo import IssueRepository
from src.db.repositories.issue_repo import FARecordRepository, CAPARecordRepository
from src.db.repositories.issue_repo import (
    IssueCommentRepository, IssueActivityLogRepository, IssueLinkRepository,
)
from src.db.repositories.settings_repo import SettingsRepository
from src.db.repositories.knowledge_repo import KnowledgeRepository
from src.db.repositories.test_result_repo import TestResultRepository

__all__ = [
    "BaseRepository",
    "ProjectRepository",
    "EquipmentRepository",
    "TechnicianRepository",
    "SampleRepository",
    "TestPlanRepository",
    "TestTaskRepository",
    "IssueRepository",
    "FARecordRepository",
    "CAPARecordRepository",
    "IssueCommentRepository",
    "IssueActivityLogRepository",
    "IssueLinkRepository",
    "SettingsRepository",
    "KnowledgeRepository",
    "TestResultRepository",
]
