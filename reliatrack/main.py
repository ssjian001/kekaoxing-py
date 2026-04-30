"""ReliaTrack — 可靠性测试全生命周期管理系统。

主入口：创建 QApplication，初始化 AppController，显示主窗口。
"""

from __future__ import annotations

import sys
import os

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, os.path.dirname(_PROJECT_ROOT))

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QToolBar,
    QMessageBox,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from src.styles.theme import get_stylesheet, TEXT, SURFACE0, SURFACE1, MANTLE
from src.controllers import AppController
from src.views.dashboard_view import DashboardView
from src.views.sample_view import SampleView
from src.views.test_plan_view import TestPlanView
from src.views.issue_view import IssueView
from src.views.equipment_view import EquipmentView
from src.views.technician_view import TechnicianView
from src.views.project_view import ProjectView
from src.views.knowledge_view import KnowledgeView

# Handler modules
from src.handlers import (
    ProjectHandlers,
    SampleHandlers,
    PlanHandlers,
    IssueHandlers,
    EquipmentHandlers,
    TechnicianHandlers,
    KnowledgeHandlers,
    ExportHandlers,
    RefreshHandlers,
)


class MainWindow(QMainWindow):
    """ReliaTrack 主窗口。"""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._ctrl = controller
        self.setWindowTitle("ReliaTrack — 可靠性测试管理")
        self.setMinimumSize(800, 600)
        self.resize(1100, 700)

        # 初始化 handler 模块
        self._project_handlers = ProjectHandlers(self)
        self._sample_handlers = SampleHandlers(self)
        self._plan_handlers = PlanHandlers(self)
        self._issue_handlers = IssueHandlers(self)
        self._equipment_handlers = EquipmentHandlers(self)
        self._technician_handlers = TechnicianHandlers(self)
        self._knowledge_handlers = KnowledgeHandlers(self)
        self._export_handlers = ExportHandlers(self)
        self._refresh_handlers = RefreshHandlers(self)

        # 跨 handler 引用
        self._refresh_handlers._sample_handlers = self._sample_handlers

        self._setup_central_widget()
        self._setup_toolbar()
        self._setup_status_bar()

        # Issue 追踪信号连接
        self._issue_view.issue_saved.connect(self._issue_handlers._handle_issue_saved)
        self._issue_view.issue_deleted.connect(self._issue_handlers._handle_issue_deleted)
        self._issue_view.issue_selected.connect(self._issue_handlers._handle_issue_selected)
        self._issue_view.fa_record_added.connect(self._issue_handlers._handle_fa_record_added)

        # Debounce 刷新定时器
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(100)  # 100ms debounce
        self._refresh_timer.timeout.connect(self._refresh_handlers._do_refresh_all)
        self._pending_entity_types: set[str] = set()

        # 初始数据加载
        self._refresh_all()

        # 监听数据变更
        controller.register_on_data_changed(self._schedule_refresh)

    def _setup_central_widget(self) -> None:
        """创建中央 Tab Widget。"""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()

        # Tab 0: 项目管理
        self._project_view = ProjectView()
        self._tab_widget.addTab(self._project_view, "📁 项目管理")
        self._project_view.btn_add.clicked.connect(self._project_handlers._on_project_add)
        self._project_view.btn_edit.clicked.connect(self._project_handlers._on_project_edit)
        self._project_view.btn_delete.clicked.connect(self._project_handlers._on_project_delete)

        # Tab 1: 仪表盘
        self._dashboard = DashboardView()
        self._tab_widget.addTab(self._dashboard, "📊 仪表盘")
        self._dashboard.card_clicked.connect(self._tab_widget.setCurrentIndex)

        # Tab 2: 样品管理
        self._sample_view = SampleView()
        self._tab_widget.addTab(self._sample_view, "📦 样品管理")
        self._sample_view.pool_tab.btn_add.clicked.connect(self._sample_handlers._on_sample_checkin)
        self._sample_view.pool_tab.btn_out.clicked.connect(self._sample_handlers._on_sample_checkout)
        self._sample_view.pool_tab.btn_batch_import.clicked.connect(self._sample_handlers._on_sample_batch_import)
        self._sample_view.pool_tab.btn_edit.clicked.connect(self._sample_handlers._on_sample_edit)
        self._sample_view.ledger_tab.btn_edit.clicked.connect(self._sample_handlers._on_ledger_edit)
        self._sample_view.usage_tab.set_refresh_callback(self._sample_handlers._refresh_sample_usage)

        # Tab 3: 测试计划
        self._test_plan_view = TestPlanView()
        self._tab_widget.addTab(self._test_plan_view, "📋 测试计划")
        self._test_plan_view.btn_schedule.clicked.connect(self._plan_handlers._on_auto_schedule)
        self._test_plan_view.task_moved.connect(self._plan_handlers._on_gantt_task_moved)
        self._test_plan_view.btn_add_plan.clicked.connect(self._plan_handlers._on_plan_add)
        self._test_plan_view.btn_edit_plan.clicked.connect(self._plan_handlers._on_plan_edit)
        self._test_plan_view._plan_combo.currentIndexChanged.connect(
            self._plan_handlers._on_plan_changed
        )
        self._test_plan_view.btn_import_tasks.clicked.connect(
            self._plan_handlers._on_task_batch_import
        )
        self._test_plan_view.btn_record_result.clicked.connect(
            self._plan_handlers._on_record_result
        )
        self._test_plan_view.setup_task_callbacks(
            on_add=self._plan_handlers._on_task_add,
            on_edit=self._plan_handlers._on_task_edit,
            on_delete=self._plan_handlers._on_task_delete,
            on_status_advance=self._plan_handlers._on_task_status_advance,
        )

        # Tab 4: Issue 追踪
        self._issue_view = IssueView()
        self._tab_widget.addTab(self._issue_view, "🐛 Issue 追踪")
        self._issue_view.btn_attachments.clicked.connect(self._issue_handlers._on_issue_attachments)

        # Tab 5: 设备 & 技术员管理（内部双 tab）
        self._equip_tech_tabs = QTabWidget()
        self._equipment_view = EquipmentView()
        self._equip_tech_tabs.addTab(self._equipment_view, "设备")
        self._technician_view = TechnicianView()
        self._equip_tech_tabs.addTab(self._technician_view, "技术员")
        self._tab_widget.addTab(self._equip_tech_tabs, "🔧 设备管理")
        self._equipment_view.btn_add.clicked.connect(self._equipment_handlers._on_equipment_add)
        self._equipment_view.btn_edit.clicked.connect(self._equipment_handlers._on_equipment_edit)
        self._equipment_view.btn_delete.clicked.connect(self._equipment_handlers._on_equipment_delete)
        self._technician_view.btn_add.clicked.connect(self._technician_handlers._on_technician_add)
        self._technician_view.btn_edit.clicked.connect(self._technician_handlers._on_technician_edit)
        self._technician_view.btn_delete.clicked.connect(self._technician_handlers._on_technician_delete)

        # Tab 6: 知识库
        self._knowledge_view = KnowledgeView()
        self._tab_widget.addTab(self._knowledge_view, "📚 知识库")
        self._knowledge_view.btn_add.clicked.connect(self._knowledge_handlers._on_knowledge_add)
        self._knowledge_view.btn_edit.clicked.connect(self._knowledge_handlers._on_knowledge_edit)
        self._knowledge_view.btn_delete.clicked.connect(self._knowledge_handlers._on_knowledge_delete)

        layout.addWidget(self._tab_widget)
        self.setCentralWidget(central)

        # 全局项目筛选器 — 在 tab_widget 之前插入
        filter_bar = QHBoxLayout()
        filter_label = QLabel("📁 项目筛选:")
        filter_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        self._project_filter_combo = QComboBox()
        self._project_filter_combo.setMinimumWidth(200)
        self._project_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {SURFACE0};
                color: {TEXT};
                border: 1px solid {SURFACE1};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                min-height: 26px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {SURFACE0};
                color: {TEXT};
                selection-background-color: {SURFACE1};
            }}
        """)
        self._project_filter_combo.addItem("📋 全部项目", None)  # data=None means all
        filter_bar.addWidget(filter_label)
        filter_bar.addWidget(self._project_filter_combo)
        filter_bar.addStretch()
        filter_layout = QWidget()
        filter_layout.setLayout(filter_bar)
        filter_layout.setStyleSheet(f"background-color: {MANTLE}; padding: 3px 16px;")
        layout.insertWidget(0, filter_layout)
        self._project_filter_combo.currentIndexChanged.connect(self._on_project_filter_changed)

    def _setup_toolbar(self) -> None:
        """创建工具栏。"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 全局快捷键
        self._shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self._shortcut_new.activated.connect(self._on_shortcut_new)
        self._shortcut_delete = QShortcut(QKeySequence("Delete"), self)
        self._shortcut_delete.activated.connect(self._on_shortcut_delete)
        self._shortcut_edit = QShortcut(QKeySequence("F2"), self)
        self._shortcut_edit.activated.connect(self._on_shortcut_edit)

        # 撤销 / 重做
        self._act_undo = QAction("↩ 撤销", self)
        self._act_undo.setEnabled(False)
        self._act_undo.setShortcut("Ctrl+Z")
        self._act_undo.triggered.connect(self._on_undo)
        toolbar.addAction(self._act_undo)

        self._act_redo = QAction("↪ 重做", self)
        self._act_redo.setEnabled(False)
        self._act_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self._act_redo.triggered.connect(self._on_redo)
        toolbar.addAction(self._act_redo)

        toolbar.addSeparator()

        # 刷新
        act_refresh = QAction("🔄 刷新", self)
        act_refresh.triggered.connect(self._refresh_all)
        toolbar.addAction(act_refresh)

        # 导出
        act_export = QAction("📤 导出", self)
        act_export.triggered.connect(self._export_handlers._on_export)
        toolbar.addAction(act_export)

    def _setup_status_bar(self) -> None:
        """创建状态栏。"""
        status_bar: QStatusBar = self.statusBar()
        status_bar.showMessage("ReliaTrack v2.0.0 — 就绪")

    # ── 快捷键分发 ──

    def _on_shortcut_new(self) -> None:
        """Ctrl+N: 根据当前 Tab 新建。"""
        idx = self._tab_widget.currentIndex()
        if idx == 0:
            self._project_handlers._on_project_add()
        elif idx == 2:
            self._sample_handlers._on_sample_checkin()
        elif idx == 3:
            self._test_plan_view._btn_add_task.click()
        elif idx == 4:
            self._issue_view._btn_add.click()
        elif idx == 5:
            self._equipment_view.btn_add.click()
        elif idx == 6:
            self._technician_view.btn_add.click()
        elif idx == 7:
            self._knowledge_view.btn_add.click()

    def _on_shortcut_delete(self) -> None:
        """Delete: 删除当前 Tab 的选中项。"""
        idx = self._tab_widget.currentIndex()
        if idx == 0:
            self._project_handlers._on_project_delete()
        elif idx == 3:
            self._test_plan_view._btn_delete_task.click()
        elif idx == 5:
            self._equipment_handlers._on_equipment_delete()
        elif idx == 6:
            self._technician_handlers._on_technician_delete()
        elif idx == 7:
            self._knowledge_handlers._on_knowledge_delete()

    def _on_shortcut_edit(self) -> None:
        """F2: 编辑当前 Tab 的选中项。"""
        idx = self._tab_widget.currentIndex()
        if idx == 0:
            self._project_handlers._on_project_edit()
        elif idx == 3:
            self._test_plan_view._btn_edit_task.click()
        elif idx == 5:
            self._equipment_handlers._on_equipment_edit()
        elif idx == 6:
            self._technician_handlers._on_technician_edit()
        elif idx == 7:
            self._knowledge_handlers._on_knowledge_edit()

    # ── 刷新/撤销快捷入口（委托给 handler） ──

    def _refresh_all(self) -> None:
        self._refresh_handlers._refresh_all()

    def _schedule_refresh(self, entity_type: str = "all") -> None:
        self._refresh_handlers._schedule_refresh(entity_type)

    def _on_project_filter_changed(self, index: int) -> None:
        """项目筛选变化时刷新所有视图。"""
        self._refresh_all()

    def _on_undo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        desc = um.undo()
        if desc:
            self.statusBar().showMessage(f"已撤销: {desc}", 3000)
            self._ctrl.notify_data_changed("undo")

    def _on_redo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        desc = um.redo()
        if desc:
            self.statusBar().showMessage(f"已重做: {desc}", 3000)
            self._ctrl.notify_data_changed("undo")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """处理窗口关闭事件 — 清理资源。"""
        self._ctrl.shutdown()
        event.accept()


def main() -> int:
    """应用程序入口。"""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("ReliaTrack")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("ReliaTrack")
    app.setStyleSheet(get_stylesheet())

    # 初始化 Controller（数据库 + 服务）
    controller = AppController()
    controller.initialize()

    # 启动主窗口
    window = MainWindow(controller)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
