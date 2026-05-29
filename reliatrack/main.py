"""ReliaTrack — 可靠性测试全生命周期管理系统。

主入口：创建 QApplication，初始化 AppController，显示主窗口。
"""

from __future__ import annotations

import sys
import os

# 开发模式：将 reliatrack/ 的父目录加入 sys.path，使 from src.xxx 可用
# PyInstaller 打包模式（sys.frozen）下跳过，因为依赖已内嵌
if not getattr(sys, 'frozen', False):
    _PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    _parent_dir = os.path.dirname(_PROJECT_ROOT)
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QMessageBox,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from src.styles.theme import get_stylesheet, set_theme, current_theme, theme_host
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
    BackupHandlers,
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
        self._backup_handlers = BackupHandlers(self)

        # 跨 handler 引用
        self._refresh_handlers._sample_handlers = self._sample_handlers

        self._setup_central_widget()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_status_bar()

        # Connect all handler signals
        self._project_handlers.connect_signals()
        self._sample_handlers.connect_signals()
        self._plan_handlers.connect_signals()
        self._issue_handlers.connect_signals()
        self._equipment_handlers.connect_signals()
        self._technician_handlers.connect_signals()
        self._knowledge_handlers.connect_signals()

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

        # Tab 0: 仪表盘（首页）
        self._dashboard = DashboardView()
        self._tab_widget.addTab(self._dashboard, "仪表盘")
        self._dashboard.card_clicked.connect(self._tab_widget.setCurrentIndex)

        # Tab 1: 项目管理
        self._project_view = ProjectView()
        self._tab_widget.addTab(self._project_view, "项目管理")

        # Tab 2: 样品管理
        self._sample_view = SampleView()
        self._tab_widget.addTab(self._sample_view, "样品管理")

        # Tab 3: 测试计划
        self._test_plan_view = TestPlanView()
        self._tab_widget.addTab(self._test_plan_view, "测试计划")

        # Tab 4: Issue 追踪
        self._issue_view = IssueView()
        self._tab_widget.addTab(self._issue_view, "Issue 追踪")

        # Tab 5: 设备 & 技术员管理（内部双 tab）
        self._equip_tech_tabs = QTabWidget()
        self._equipment_view = EquipmentView()
        self._equip_tech_tabs.addTab(self._equipment_view, "设备")
        self._technician_view = TechnicianView()
        self._equip_tech_tabs.addTab(self._technician_view, "技术员")
        self._tab_widget.addTab(self._equip_tech_tabs, "设备管理")

        # Tab 6: 知识库
        self._knowledge_view = KnowledgeView()
        self._tab_widget.addTab(self._knowledge_view, "知识库")

        # 恢复上次选中的 Tab
        settings = QSettings()
        try:
            last_tab = int(settings.value("ReliaTrack/last_tab_index", 0))
        except (ValueError, TypeError):
            last_tab = 0
        if 0 <= last_tab < self._tab_widget.count():
            self._tab_widget.setCurrentIndex(last_tab)
        # Tab 切换时保存
        self._tab_widget.currentChanged.connect(
            lambda idx: QSettings().setValue("ReliaTrack/last_tab_index", idx)
        )

        layout.addWidget(self._tab_widget)
        self.setCentralWidget(central)

        # 全局项目筛选器 — 在 tab_widget 之前插入
        self._create_filter_bar(layout)

    def _create_filter_bar(self, layout: QVBoxLayout) -> None:
        """创建项目/计划筛选栏（注入到 layout 顶部）。"""
        filter_bar = QHBoxLayout()
        self._filter_label = QLabel("项目筛选:")
        self._filter_label.setProperty("class", "filter-label")
        self._project_filter_combo = QComboBox()
        self._project_filter_combo.setMinimumWidth(200)
        self._project_filter_combo.setProperty("class", "filter-combo")
        self._project_filter_combo.addItem("全部项目", None)

        self._plan_filter_label = QLabel("计划:")
        self._plan_filter_label.setProperty("class", "filter-label")
        self._plan_filter_combo = QComboBox()
        self._plan_filter_combo.setMinimumWidth(180)
        self._plan_filter_combo.setProperty("class", "filter-combo")
        self._plan_filter_combo.addItem("全部计划", None)
        self._plan_filter_combo.setEnabled(False)

        filter_bar.addWidget(self._filter_label)
        filter_bar.addWidget(self._project_filter_combo)
        filter_bar.addWidget(self._plan_filter_label)
        filter_bar.addWidget(self._plan_filter_combo)
        filter_bar.addStretch()
        self._filter_layout = QWidget()
        self._filter_layout.setLayout(filter_bar)
        self._filter_layout.setProperty("class", "filter-bar")
        layout.insertWidget(0, self._filter_layout)
        self._project_filter_combo.currentIndexChanged.connect(self._on_project_filter_changed)
        self._plan_filter_combo.currentIndexChanged.connect(self._on_plan_filter_changed)

    def _setup_menubar(self) -> None:
        """创建菜单栏。"""
        menubar = self.menuBar()

        # 操作菜单
        op_menu = menubar.addMenu("操作(&O)")

        act_refresh = QAction("刷新(&R)", self)
        act_refresh.setShortcut("F5")
        act_refresh.setToolTip("刷新所有数据 (F5)")
        act_refresh.triggered.connect(self._refresh_all)
        op_menu.addAction(act_refresh)

        act_export = QAction("导出(&E)…", self)
        act_export.setShortcut("Ctrl+E")
        act_export.setToolTip("导出报告 (Ctrl+E)")
        act_export.triggered.connect(self._export_handlers._on_export)
        op_menu.addAction(act_export)

        op_menu.addSeparator()

        act_backup = QAction("数据管理(&B)…", self)
        act_backup.setToolTip("数据库备份与恢复")
        act_backup.triggered.connect(self._backup_handlers._on_data_manage)
        op_menu.addAction(act_backup)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")

        # 暗色主题 Toggle
        self._act_dark_theme = QAction("暗色主题(&D)", self)
        self._act_dark_theme.setCheckable(True)
        self._act_dark_theme.setChecked(current_theme() == "dark")
        self._act_dark_theme.setToolTip("切换暗色/明亮主题")
        self._act_dark_theme.toggled.connect(self._on_toggle_dark_theme)
        view_menu.addAction(self._act_dark_theme)

        # 订阅主题变化（外部调用 set_theme 时同步菜单状态）
        theme_host.theme_changed.connect(self._on_theme_changed)

    def _on_toggle_dark_theme(self, checked: bool) -> None:
        """菜单 Toggle 回调 — 切换主题并持久化。"""
        from PySide6.QtWidgets import QApplication
        name = "dark" if checked else "light"
        set_theme(name)
        QApplication.instance().setStyleSheet(get_stylesheet())
        QSettings().setValue("ReliaTrack/theme", name)

    def _on_theme_changed(self, name: str) -> None:
        """外部主题切换时同步菜单 checkbox 状态（唯一 theme_changed 监听器）。"""
        self._act_dark_theme.blockSignals(True)
        self._act_dark_theme.setChecked(name == "dark")
        self._act_dark_theme.blockSignals(False)
        # 内联样式已全部迁移到 QSS 类选择器，不再需要逐控件刷新

    def _setup_toolbar(self) -> None:
        """快捷键注册（无可见工具栏）。"""
        # 全局快捷键
        self._shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self._shortcut_new.activated.connect(self._on_shortcut_new)
        self._shortcut_delete = QShortcut(QKeySequence("Delete"), self)
        self._shortcut_delete.activated.connect(self._on_shortcut_delete)
        self._shortcut_edit = QShortcut(QKeySequence("F2"), self)
        self._shortcut_edit.activated.connect(self._on_shortcut_edit)
        self._shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self._shortcut_find.activated.connect(self._on_shortcut_find)

        # 撤销 / 重做（隐藏快捷键，无 UI 按钮）
        self._shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._shortcut_undo.activated.connect(self._on_undo)
        self._shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._shortcut_redo.activated.connect(self._on_redo)

    def _setup_status_bar(self) -> None:
        """创建状态栏。"""
        status_bar: QStatusBar = self.statusBar()
        status_bar.showMessage("ReliaTrack v2.0.0 — 就绪")

    # ── 快捷键分发 ──

    def _on_shortcut_new(self) -> None:
        """Ctrl+N: 根据当前 Tab 新建。"""
        idx = self._tab_widget.currentIndex()
        if idx == 1:
            self._project_handlers._on_project_add()
        elif idx == 2:
            self._sample_handlers._on_sample_checkin()
        elif idx == 3:
            self._plan_handlers._on_task_add()
        elif idx == 4:
            self._issue_view._btn_add.click()
        elif idx == 5:
            self._equipment_view.btn_add.click()
        elif idx == 6:
            self._knowledge_view.btn_add.click()

    def _on_shortcut_delete(self) -> None:
        """Delete: 删除当前 Tab 的选中项。"""
        idx = self._tab_widget.currentIndex()
        if idx == 1:
            self._project_handlers._on_project_delete()
        elif idx == 3:
            self._plan_handlers._on_task_delete_menu()
        elif idx == 5:
            self._equipment_handlers._on_equipment_delete()
        elif idx == 6:
            self._knowledge_handlers._on_knowledge_delete()

    def _on_shortcut_edit(self) -> None:
        """F2: 编辑当前 Tab 的选中项。"""
        idx = self._tab_widget.currentIndex()
        if idx == 1:
            self._project_handlers._on_project_edit()
        elif idx == 3:
            self._plan_handlers._on_task_edit_menu()
        elif idx == 5:
            self._equipment_handlers._on_equipment_edit()
        elif idx == 6:
            self._knowledge_handlers._on_knowledge_edit()

    def _on_shortcut_find(self) -> None:
        """Ctrl+F: 聚焦当前 Tab 的搜索框。"""
        search_map = {
            1: lambda: self._project_view.search_input,
            2: lambda: self._sample_view.pool_tab.search_input,
            3: lambda: self._test_plan_view._search_edit,
            4: lambda: self._issue_view._search_input,
            5: lambda: self._equipment_view._search_edit,
            6: lambda: self._knowledge_view._search_edit,
        }
        idx = self._tab_widget.currentIndex()
        getter = search_map.get(idx)
        if getter:
            widget = getter()
            widget.setFocus()
            widget.selectAll()

    # ── 刷新/撤销快捷入口（委托给 handler） ──

    def _refresh_all(self) -> None:
        self._refresh_handlers._refresh_all()

    def _schedule_refresh(self, entity_type: str = "all") -> None:
        self._refresh_handlers._schedule_refresh(entity_type)

    # ── 公共方法：供 Handler 访问（替代直接访问私有属性） ──────────

    def get_project_filter_id(self) -> int | None:
        """获取当前项目筛选 combo 的 currentData（None = 全部项目）。"""
        return self._project_filter_combo.currentData()

    def get_plan_filter_id(self) -> int | None:
        """获取当前计划筛选 combo 的 currentData（None = 全部计划）。

        若 combo 禁用则返回 None。
        """
        if not self._plan_filter_combo.isEnabled():
            return None
        return self._plan_filter_combo.currentData()

    def refresh_project_filter(self, projects: list, current_id: int | None = None) -> None:
        """刷新项目筛选 combo 选项（不触发信号）。

        Args:
            projects: 项目列表（需有 .name 和 .id 属性）
            current_id: 之前选中的项目 ID，用于恢复
        """
        combo = self._project_filter_combo
        combo.blockSignals(True)
        _current = current_id if current_id is not None else combo.currentData()
        combo.clear()
        combo.addItem("全部项目", None)
        for p in projects:
            combo.addItem(p.name, p.id)
        # 恢复之前选中的筛选项
        for i in range(combo.count()):
            if combo.itemData(i) == _current:
                combo.setCurrentIndex(i)
                break
        combo.blockSignals(False)

    def schedule_throttled_refresh(self, entity_type: str = "all") -> None:
        """节流刷新：合并短时间内的多次变更，100ms 后统一刷新。

        供 handler 调用，替代直接操作 _pending_entity_types + _refresh_timer。
        """
        if entity_type == "all":
            self._pending_entity_types.clear()
        else:
            self._pending_entity_types.add(entity_type)
            # plan 变更也影响 dashboard
            self._pending_entity_types.add("plan")
        self._refresh_timer.start()

    def get_pending_entity_types(self) -> set[str]:
        """获取当前待刷新的实体类型集合。"""
        return self._pending_entity_types

    def clear_pending_entities(self) -> None:
        """清空待刷新实体类型集合。"""
        self._pending_entity_types.clear()

    def update_undo_redo(
        self,
        can_undo: bool = False,
        can_redo: bool = False,
        undo_desc: str = "",
        redo_desc: str = "",
    ) -> None:
        """更新撤销/重做状态（保留接口兼容，无可见 UI）。"""

    # ── 公共属性（Handler 通过 .ctrl 访问，替代直接操作 _ctrl） ──────

    @property
    def ctrl(self) -> AppController:
        """获取应用控制器。"""
        return self._ctrl

    @property
    def test_plan_view(self) -> TestPlanView:
        return self._test_plan_view

    @property
    def issue_view(self) -> IssueView:
        return self._issue_view

    @property
    def sample_view(self) -> SampleView:
        return self._sample_view

    @property
    def project_view(self) -> ProjectView:
        return self._project_view

    @property
    def equipment_view(self) -> EquipmentView:
        return self._equipment_view

    @property
    def technician_view(self) -> TechnicianView:
        return self._technician_view

    @property
    def knowledge_view(self) -> KnowledgeView:
        return self._knowledge_view

    @property
    def dashboard(self) -> DashboardView:
        return self._dashboard

    def _on_project_filter_changed(self, index: int) -> None:
        """项目筛选变化时：更新计划 combo + 刷新所有视图。"""
        # 更新计划 combo
        self._refresh_plan_combo()
        self._refresh_all()

    def _on_plan_filter_changed(self, index: int) -> None:
        """计划筛选变化时刷新仪表盘。"""
        self._refresh_all()

    def _refresh_plan_combo(self) -> None:
        """根据当前选中的项目更新计划筛选 combo（保留之前选中项）。"""
        project_id = self._project_filter_combo.currentData()
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            self._plan_filter_combo.setEnabled(False)
            return

        # 记住当前选中
        _current_plan_id = self._plan_filter_combo.currentData()

        self._plan_filter_combo.blockSignals(True)
        self._plan_filter_combo.clear()
        self._plan_filter_combo.addItem("全部计划", None)

        if project_id is None:
            # 全部项目 → 禁用计划筛选
            self._plan_filter_combo.setEnabled(False)
        else:
            # 选了项目 → 填充该项目的计划列表
            plans = ctrl.test_plan_service.get_plans_by_project(project_id)
            for p in plans:
                self._plan_filter_combo.addItem(p.name, p.id)
            self._plan_filter_combo.setEnabled(True)

            # 恢复之前选中的计划
            for i in range(self._plan_filter_combo.count()):
                if self._plan_filter_combo.itemData(i) == _current_plan_id:
                    self._plan_filter_combo.setCurrentIndex(i)
                    break

        self._plan_filter_combo.blockSignals(False)

    def _on_undo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        cmd = um.peek_undo()
        desc = um.undo()
        if desc:
            self.statusBar().showMessage(f"已撤销: {desc}", 3000)
            self._ctrl.notify_data_changed("issue")
            # FA/CAPA 删除撤销后需要 re-sync Issue
            self._replay_sync_after_undo_redo(cmd)

    def _on_redo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        cmd = um.peek_redo()
        desc = um.redo()
        if desc:
            self.statusBar().showMessage(f"已重做: {desc}", 3000)
            self._ctrl.notify_data_changed("issue")
            self._replay_sync_after_undo_redo(cmd)

    def _replay_sync_after_undo_redo(self, cmd: object) -> None:
        """Undo/Redo FA/CAPA 删除后重新同步 Issue 关联字段。

        DeleteEntityCommand.undo() 恢复 DB 记录但不触发业务 sync，
        需要在这里手动调用 _sync_issue_from_capa / _sync_issue_from_fa。
        """
        from src.services.undo_manager import DeleteEntityCommand
        if not isinstance(cmd, DeleteEntityCommand):
            return
        table = getattr(cmd._repo, "_table", "")
        issue_id = cmd._saved_data.get("issue_id")
        if not issue_id:
            return
        ih = self._issue_handlers
        if table == "capa_records":
            ih._sync_issue_from_capa(issue_id)
        elif table == "fa_records":
            ih._sync_issue_from_fa(issue_id)

    def toast(self, message: str, level: str = "success") -> None:
        """显示 Toast 提示（替代 statusBar 的成功/警告消息）。"""
        from src.styles.toast import ToastWidget
        ToastWidget.show_toast(self, message, level)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """处理窗口关闭事件 — 检查打开的 dialog 和未撤销操作。"""
        # 检查是否有正在编辑的 dialog（排除 QMenu/QToolTip 等瞬时窗口）
        from PySide6.QtWidgets import QDialog
        from PySide6.QtCore import Qt
        open_dialogs = [
            w for w in QApplication.topLevelWidgets()
            if isinstance(w, QDialog) and w.isVisible()
            and w.windowModality() != Qt.WindowModality.NonModal
        ]
        if open_dialogs:
            reply = QMessageBox.question(
                self,
                "确认关闭",
                f"有 {len(open_dialogs)} 个窗口正在编辑中，关闭后未保存的内容将丢失。\n确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        um = self._ctrl.undo_manager
        if um and um.can_undo():
            reply = QMessageBox.question(
                self,
                "确认关闭",
                "有尚未保存的撤销历史，关闭后将无法恢复。\n确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        self._ctrl.shutdown()
        event.accept()


def main() -> int:
    """应用程序入口。"""
    # HiDPI 支持（Qt6 默认启用，显式声明确保一致性）
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "RoundPreferFloor")
    # 避免 Wayland 下 Qt 的部分渲染问题，优先使用 XCB
    if sys.platform == "linux" and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    import logging
    import logging.handlers
    from pathlib import Path as _P

    log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_datefmt = "%H:%M:%S"
    logging.basicConfig(level=logging.INFO, format=log_fmt, datefmt=log_datefmt)

    # 持久化日志 — RotatingFileHandler（5×1MB）
    from src.db.connection import DEFAULT_BACKUPS_DIR, DEFAULT_LOGS_DIR
    DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _fh = logging.handlers.RotatingFileHandler(
        DEFAULT_LOGS_DIR / "reliatrack.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    _fh.setFormatter(logging.Formatter(log_fmt, datefmt=log_datefmt))
    logging.getLogger().addHandler(_fh)

    app = QApplication(sys.argv)
    app.setApplicationName("ReliaTrack")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("ReliaTrack")

    # 自定义 CheckBox / RadioButton indicator 绘制
    from src.styles.proxy_style import CheckboxProxyStyle
    app.setStyle(CheckboxProxyStyle())

    app.setStyleSheet(get_stylesheet())

    # 恢复主题偏好（QSettings，controller 初始化前即可用）
    _settings = QSettings()
    _saved_theme = _settings.value("ReliaTrack/theme", "light")
    if _saved_theme in ("light", "dark") and _saved_theme != "light":
        set_theme(_saved_theme)
        app.setStyleSheet(get_stylesheet())

    # 全局异常兜底 — 未捕获异常记日志 + 友好弹窗
    _log = logging.getLogger("reliatrack")
    _orig_excepthook = sys.excepthook

    def _global_excepthook(exc_type, exc_val, exc_tb):
        _log.critical("Uncaught exception", exc_info=(exc_type, exc_val, exc_tb))
        try:
            from PySide6.QtWidgets import QMessageBox as _MB
            _MB.critical(
                None, "意外错误",
                f"程序发生未预期的错误：\n{exc_val}\n\n"
                "详细信息已记录到日志。请尝试重启程序。",
            )
        except Exception:
            pass  # 弹窗也失败时 fallback 到原始 hook
        _orig_excepthook(exc_type, exc_val, exc_tb)

    sys.excepthook = _global_excepthook

    # 捕获 Qt C++ 层的致命错误（段错误、paint 崩溃等）
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    _log = logging.getLogger("reliatrack")

    def _qt_message_handler(msg_type, context, message):
        if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            _log.critical(
                "Qt fatal: %s (file=%s, line=%d, func=%s)",
                message, context.file, context.line, context.function,
            )

    qInstallMessageHandler(_qt_message_handler)

    # 单实例互斥 — 防止两个进程同时写同一 DB
    from PySide6.QtCore import QLockFile
    _lock = QLockFile(str(DEFAULT_BACKUPS_DIR.parent / ".reliatrack.lock"))
    if hasattr(_lock, 'setStaleLockTime'):
        _lock.setStaleLockTime(30000)  # 30 秒过期，防止崩溃后锁文件永久残留
    else:
        _lock.setStaleLockTimeout(30000)
    if not _lock.tryLock(100):
        from PySide6.QtWidgets import QMessageBox as _MB
        _MB.critical(None, "已运行", "ReliaTrack 已在运行中，请勿重复启动。")
        _lock.unlock()
        _lock_path = _P(str(DEFAULT_BACKUPS_DIR.parent / ".reliatrack.lock"))
        _lock_path.unlink(missing_ok=True)
        return 1

    # 数据库路径：开发模式优先用项目下 data/reliatrack.db
    # PyInstaller 打包模式（sys.frozen）用默认 ~/.reliatrack/reliatrack.db
    _db_path = ""
    if not getattr(sys, 'frozen', False):
        _local_db = _P(__file__).parent / "data" / "reliatrack.db"
        if _local_db.exists():
            _db_path = str(_local_db)

    # 初始化 Controller（数据库 + 服务）
    controller = AppController(_db_path)
    controller.initialize()

    # 启动主窗口
    window = MainWindow(controller)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
