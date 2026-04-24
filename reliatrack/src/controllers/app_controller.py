"""应用主控制器 — 初始化所有 Service，提供统一入口。

AppController 是整个应用的"大脑"，持有：
  - 所有 Repository 实例（单一连接）
  - 所有 Service 实例
  - UndoManager
  - 数据变更通知（通过信号或回调）

UI 层通过 AppController 访问所有业务逻辑。
"""

from __future__ import annotations

import logging
from typing import Callable

import apsw

from src.db.connection import get_connection, close_all_connections
from src.db.schema import init_schema
from src.db.repositories import (
    ProjectRepository,
    EquipmentRepository,
    TechnicianRepository,
    SampleRepository,
    TestPlanRepository,
    TestTaskRepository,
    IssueRepository,
    SettingsRepository,
)
from src.services import (
    ProjectService,
    EquipmentService,
    SampleService,
    TestPlanService,
    IssueService,
    SettingsService,
    SchedulerService,
)
from src.services.undo_manager import UndoManager

logger = logging.getLogger(__name__)


class AppController:
    """应用主控制器 — 所有业务逻辑的统一入口。"""

    def __init__(self, db_path: str = "data/reliatrack.db") -> None:
        self._db_path = db_path
        self._conn: apsw.Connection | None = None

        # Repositories
        self.projects: ProjectRepository | None = None
        self.equipment: EquipmentRepository | None = None
        self.technicians: TechnicianRepository | None = None
        self.samples: SampleRepository | None = None
        self.test_plans: TestPlanRepository | None = None
        self.test_tasks: TestTaskRepository | None = None
        self.issues: IssueRepository | None = None
        self.settings: SettingsRepository | None = None

        # Services
        self.project_service: ProjectService | None = None
        self.equipment_service: EquipmentService | None = None
        self.sample_service: SampleService | None = None
        self.test_plan_service: TestPlanService | None = None
        self.issue_service: IssueService | None = None
        self.settings_service: SettingsService | None = None
        self.scheduler_service: SchedulerService | None = None

        # Undo/Redo
        self.undo_manager = UndoManager(max_history=50)

        # 数据变更回调
        self._on_data_changed: list[Callable[[], None]] = []

    # ── 初始化 ──

    def initialize(self) -> None:
        """初始化数据库连接、schema 和所有 Repository/Service。"""
        self._conn = get_connection(self._db_path)
        init_schema(self._conn)
        logger.info("Database initialized: %s", self._db_path)

        # Repositories
        self.projects = ProjectRepository(self._conn)
        self.equipment = EquipmentRepository(self._conn)
        self.technicians = TechnicianRepository(self._conn)
        self.samples = SampleRepository(self._conn)
        self.test_plans = TestPlanRepository(self._conn)
        self.test_tasks = TestTaskRepository(self._conn)
        self.issues = IssueRepository(self._conn)
        self.settings = SettingsRepository(self._conn)

        # Services
        self.project_service = ProjectService(
            self.projects, self.test_plans, self.test_tasks, self.samples, self.issues
        )
        self.equipment_service = EquipmentService(self.equipment)
        self.sample_service = SampleService(self.samples)
        self.test_plan_service = TestPlanService(self.test_plans, self.test_tasks)
        self.issue_service = IssueService(self.issues)
        self.settings_service = SettingsService(self.settings)
        self.scheduler_service = SchedulerService(
            self.test_tasks, self.equipment, self.test_plans,
        )

        logger.info("All services initialized")

    # ── 变更通知 ──

    def register_on_data_changed(self, callback: Callable[[], None]) -> None:
        """注册数据变更回调（UI 层用来刷新显示）。"""
        self._on_data_changed.append(callback)

    def notify_data_changed(self) -> None:
        """通知所有监听者数据已变更。"""
        for cb in self._on_data_changed:
            try:
                cb()
            except Exception:
                logger.exception("Error in data changed callback")

    # ── 生命周期 ──

    def shutdown(self) -> None:
        """关闭数据库连接。"""
        close_all_connections()
        self._conn = None
        logger.info("Database connection closed")
