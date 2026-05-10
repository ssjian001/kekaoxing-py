"""应用主控制器 — 初始化所有 Service，提供统一入口。

AppController 是整个应用的"大脑"，持有：
  - 所有 Repository 实例（单一连接）
  - 所有 Service 实例
  - UndoManager
  - 数据变更通知（通过信号或回调）

UI 层通过 AppController 访问所有业务逻辑。
"""

from __future__ import annotations

import datetime
import logging
import shutil
from pathlib import Path
from typing import Callable

import apsw

from src.db.connection import get_connection, close_all_connections
from src.db.connection import DEFAULT_ATTACHMENTS_DIR, DEFAULT_BACKUPS_DIR
from src.db.schema import init_schema
from src.db.repositories import (
    ProjectRepository,
    EquipmentRepository,
    TechnicianRepository,
    SampleRepository,
    TestPlanRepository,
    TestTaskRepository,
    TestResultRepository,
    IssueRepository,
    SettingsRepository,
    KnowledgeRepository,
)
from src.services import (
    ProjectService,
    EquipmentService,
    SampleService,
    TestPlanService,
    IssueService,
    SettingsService,
    SchedulerService,
    KnowledgeService,
    TechnicianService,
    ExportService,
)
from src.services.holiday_service import HolidayService
from src.services.undo_manager import UndoManager

logger = logging.getLogger(__name__)


class AppController:
    """应用主控制器 — 所有业务逻辑的统一入口。"""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = db_path
        self._conn: apsw.Connection | None = None

        # Repositories
        self.projects: ProjectRepository | None = None
        self.equipment: EquipmentRepository | None = None
        self.technicians: TechnicianRepository | None = None
        self.samples: SampleRepository | None = None
        self.test_plans: TestPlanRepository | None = None
        self.test_tasks: TestTaskRepository | None = None
        self.test_results: TestResultRepository | None = None
        self.issues: IssueRepository | None = None
        self.settings: SettingsRepository | None = None
        self.knowledge: KnowledgeRepository | None = None

        # Services
        self.project_service: ProjectService | None = None
        self.equipment_service: EquipmentService | None = None
        self.sample_service: SampleService | None = None
        self.test_plan_service: TestPlanService | None = None
        self.issue_service: IssueService | None = None
        self.settings_service: SettingsService | None = None
        self.scheduler_service: SchedulerService | None = None
        self.knowledge_service: KnowledgeService | None = None
        self.technician_service: TechnicianService | None = None
        self.export_service: ExportService | None = None

        # Undo/Redo
        self.undo_manager = UndoManager(max_history=50)

        # 数据变更回调
        self._on_data_changed: list[Callable[[str], None]] = []

    # ── 初始化 ──

    def initialize(self) -> None:
        """初始化数据库连接、schema 和所有 Repository/Service。"""
        import sys
        import logging
        logger = logging.getLogger("app_ctrl")
        logger.warning("[DEBUG AppController.initialize] db_path=%s", self._db_path)
        self._conn = get_connection(self._db_path)
        logger.warning("[DEBUG AppController.initialize] conn_id=%d", id(self._conn))
        init_schema(self._conn)
        tables = [r[0] for r in self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        logger.warning("[DEBUG AppController.initialize] tables after init_schema: %s (count=%d)", tables, len(tables))
        # 启动时自动备份
        self._startup_backup()
        logger.info("Database initialized: %s", self._db_path)

        # Repositories
        self.projects = ProjectRepository(self._conn)
        self.equipment = EquipmentRepository(self._conn)
        self.technicians = TechnicianRepository(self._conn)
        self.samples = SampleRepository(self._conn)
        self.test_plans = TestPlanRepository(self._conn)
        self.test_tasks = TestTaskRepository(self._conn)
        self.test_results = TestResultRepository(self._conn)
        self.issues = IssueRepository(self._conn)
        self.settings = SettingsRepository(self._conn)
        self.knowledge = KnowledgeRepository(self._conn)

        # Services
        self.project_service = ProjectService(
            self.projects, self.test_plans, self.test_tasks, self.samples, self.issues
        )
        self.equipment_service = EquipmentService(self.equipment)
        self.sample_service = SampleService(self.samples, self.test_results, self.issues)
        self.test_plan_service = TestPlanService(self.test_plans, self.test_tasks, self.test_results)
        self.issue_service = IssueService(self.issues, conn=self._conn)
        self.settings_service = SettingsService(self.settings)
        self.holiday_service = HolidayService(self._conn)
        self.scheduler_service = SchedulerService(
            self.test_tasks, self.equipment, self.test_plans,
            holiday_service=self.holiday_service,
        )
        self.knowledge_service = KnowledgeService(self.knowledge)
        self.technician_service = TechnicianService(self.technicians, self.test_tasks, self.issues)
        self.export_service = ExportService()

        logger.info("All services initialized")

    def _startup_backup(self) -> None:
        """启动时自动备份数据库（每日一次，使用 apsw Backup API 保证一致性）。"""
        db_path = Path(self._conn.db_filename("main") or self._db_path)
        DEFAULT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.date.today().strftime("%Y%m%d")
        backup_path = DEFAULT_BACKUPS_DIR / f"reliatrack_{date_str}.db"
        # 同一天只备份一次
        if not backup_path.exists():
            try:
                dest = apsw.Connection(str(backup_path))
                with self._conn.backup("main", dest, "main") as backup:
                    backup.step()
                dest.close()
                logger.info("Backup created: %s", backup_path)
            except Exception:
                logger.exception("Backup failed")
        # 清理超过30天的旧备份
        for old in sorted(DEFAULT_BACKUPS_DIR.glob("reliatrack_*.db"))[:-30]:
            old.unlink(missing_ok=True)

    # ── 变更通知 ──

    def register_on_data_changed(self, callback: Callable[[str], None]) -> None:
        """注册数据变更回调（UI 层用来刷新显示）。"""
        self._on_data_changed.append(callback)

    def notify_data_changed(
        self, entity_type: str = "all"
    ) -> None:
        """通知所有监听者数据已变更。

        Args:
            entity_type: 变更的实体类型，用于按需刷新。
                'all' | 'project' | 'sample' | 'task' | 'issue' |
                'equipment' | 'technician' | 'knowledge' | 'plan' | 'undo'
        """
        for cb in self._on_data_changed:
            try:
                cb(entity_type)
            except Exception:
                logger.exception("Error in data changed callback")

    # ── 生命周期 ──

    def shutdown(self) -> None:
        """关闭数据库连接（附件扫描 + WAL checkpoint + close）。"""
        # 附件完整性扫描（仅记录日志，不阻塞关闭）
        if self.issue_service:
            try:
                scan = self.issue_service.scan_attachment_integrity()
                missing = scan.get("missing_files", [])
                orphan = scan.get("orphan_files", [])
                if missing:
                    logger.warning("附件引用扫描: %d 个文件缺失: %s", len(missing), missing[:5])
                if orphan:
                    logger.info("附件引用扫描: %d 个孤立文件: %s", len(orphan), orphan[:5])
                if not missing and not orphan:
                    logger.info("附件引用扫描: 全部正常")
            except Exception:
                logger.debug("附件扫描跳过（无数据或异常）")

        if self._conn:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("WAL checkpoint completed")
            except Exception:
                logger.exception("WAL checkpoint failed")
        close_all_connections()
        self._conn = None
        logger.info("Database connection closed")
