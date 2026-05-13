"""ReliaTrack handler modules — extracted from MainWindow for maintainability."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # MainWindow is not imported here to avoid circular imports

from src.handlers.project_handlers import ProjectHandlers
from src.handlers.sample_handlers import SampleHandlers
from src.handlers.plan_handlers import PlanHandlers
from src.handlers.issue_handlers import IssueHandlers
from src.handlers.equipment_handlers import EquipmentHandlers
from src.handlers.technician_handlers import TechnicianHandlers
from src.handlers.knowledge_handlers import KnowledgeHandlers
from src.handlers.export_handlers import ExportHandlers
from src.handlers.refresh_handlers import RefreshHandlers
from src.handlers.backup_handlers import BackupHandlers

__all__ = [
    "ProjectHandlers",
    "SampleHandlers",
    "PlanHandlers",
    "IssueHandlers",
    "EquipmentHandlers",
    "TechnicianHandlers",
    "KnowledgeHandlers",
    "ExportHandlers",
    "RefreshHandlers",
    "BackupHandlers",
]
