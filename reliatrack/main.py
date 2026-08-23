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
    QScrollArea,
    QStyle,
    QStyleOptionTab,
    QStylePainter,
    QTabBar,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QMessageBox,
    QComboBox,
    QPushButton,
    QToolButton,
)
from PySide6.QtCore import QTimer, QSettings, Qt, QSize, QRectF, QRect
from PySide6.QtGui import (
    QAction, QKeySequence, QShortcut,
    QColor, QPaintEvent, QPainterPath,
)

from src.styles.animation import TranslateYAnimation
from src.styles.icon import RI_REFRESH, RI_BACKUP, RI_EXPORT
import src.styles.theme as _t
from src.styles.theme import get_stylesheet, set_theme, theme_host, apply_palette
from src.styles.smooth_scroll import SmoothScroll
from src.controllers import AppController
from src.services.health_service import DbCorruptError
from src.views.dashboard_view import DashboardView
from src.views.sample_view import SampleView
from src.views.test_plan_view import TestPlanView
# IssueView 不再单独实例化（已合并到 BugTrackerView），import 保留供 test/ref 使用
from src.views.bug_tracker import BugTrackerView
from src.views.equipment_view import EquipmentView
from src.views.technician_view import TechnicianView
from src.views.project_view import ProjectView
from src.views.knowledge_view import KnowledgeView
from src.views.todo_view import TodoView

# Handler modules
from src.handlers import (
    ProjectHandlers,
    SampleHandlers,
    PlanHandlers,
    IssueHandlers,
    EquipmentHandlers,
    TechnicianHandlers,
    KnowledgeHandlers,
    TodoHandlers,
    ExportHandlers,
    RefreshHandlers,
    BackupHandlers,
)



class SidebarTabBar(QTabBar):
    """TabBar 置左時文字橫排，窄側欄樣式。"""
    def tabSizeHint(self, index: int) -> QSize:
        return QSize(72, 34)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QStylePainter(self)
        opt = QStyleOptionTab()
        for i in range(self.count()):
            self.initStyleOption(opt, i)
            # 精修: 选中态画圆角胶囊底 + 左侧 accent 条，替代原 drawControl 平铺
            # 坑: _t.SELECTION_BG 是 QSS rgba() 字符串, QColor() 解析为 INVALID→黑色。
            #     必须用 QColor(hex)+setAlpha 构造半透明色
            selected = bool(opt.state & QStyle.State_Selected)
            painter.save()
            rect = opt.rect.adjusted(3, 2, -3, -2)
            if selected:
                capsule = QColor(_t.ACCENT)
                capsule.setAlpha(28)
                path = QPainterPath()
                path.addRoundedRect(QRectF(rect), 8, 8)
                painter.fillPath(path, capsule)
            elif opt.state & QStyle.State_MouseOver:
                path = QPainterPath()
                path.addRoundedRect(QRectF(rect), 8, 8)
                painter.fillPath(path, QColor(_t.BG_HOVER))
            else:
                painter.drawControl(QStyle.CE_TabBarTabShape, opt)
            if selected:
                bar = QRect(rect.left() + 1, rect.top() + 7, 3, rect.height() - 14)
                path_bar = QPainterPath()
                path_bar.addRoundedRect(QRectF(bar), 1.5, 1.5)
                painter.fillPath(path_bar, QColor(_t.ACCENT))
            painter.restore()

            # 自繪文字（橫向）
            painter.save()
            rect = opt.rect.adjusted(4, 0, -4, 0)
            color = _t.FG_PRIMARY if opt.state & QStyle.State_Selected else _t.FG_SECONDARY
            painter.setPen(QColor(color))
            font = painter.font()
            font.setBold(bool(opt.state & QStyle.State_Selected))
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.tabText(i))
            painter.restore()


class MainWindow(QMainWindow):
    """ReliaTrack 主窗口。"""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._ctrl = controller
        self.setWindowTitle("ReliaTrack — 可靠性测试管理")
        self.setMinimumSize(800, 600)

        # 初始化 handler 模块
        self._project_handlers = ProjectHandlers(self)
        self._sample_handlers = SampleHandlers(self)
        self._plan_handlers = PlanHandlers(self)
        self._issue_handlers = IssueHandlers(self)
        self._equipment_handlers = EquipmentHandlers(self)
        self._technician_handlers = TechnicianHandlers(self)
        self._knowledge_handlers = KnowledgeHandlers(self)
        self._todo_handlers = TodoHandlers(self)
        self._export_handlers = ExportHandlers(self)
        self._refresh_handlers = RefreshHandlers(self)
        self._backup_handlers = BackupHandlers(self)

        # 跨 handler 引用
        self._refresh_handlers._sample_handlers = self._sample_handlers

        self._pending_entity_types: set[str] = set()

        self._setup_central_widget()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._restore_window_geometry()

        # Connect all handler signals
        self._project_handlers.connect_signals()
        self._sample_handlers.connect_signals()
        self._plan_handlers.connect_signals()
        self._issue_handlers.connect_signals()
        self._equipment_handlers.connect_signals()
        self._technician_handlers.connect_signals()
        self._knowledge_handlers.connect_signals()
        self._todo_handlers.connect_signals()

        # Debounce 刷新定时器
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(100)  # 100ms debounce
        self._refresh_timer.timeout.connect(self._refresh_handlers._do_refresh_all)

        # 初始数据加载
        self._refresh_all()

        # 监听数据变更
        controller.register_on_data_changed(self._schedule_refresh)

        # UX 增强：平滑滚动 + 动效
        self._install_ux_enhancements()

        # 待办提醒检查（启动 + 60s 轮询）
        self._start_reminder_check()

        # 设备校准到期提醒（启动检查一次）
        QTimer.singleShot(3000, self._check_calibration_reminders)

    def _setup_central_widget(self) -> None:
        """创建中央 Tab Widget。"""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # 全局项目/计划筛选栏（放在 TabWidget 上方，不依赖 corner widget）
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabBar(SidebarTabBar())
        self._tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self._tab_widget.setTabShape(QTabWidget.TabShape.Rounded)

        # Tab 0: 仪表盘（首页）
        self._dashboard = DashboardView()
        self._tab_widget.addTab(self._dashboard, "仪表盘")
        self._dashboard.card_clicked.connect(self._on_dashboard_card_clicked)

        # Tab 1: 项目管理
        self._project_view = ProjectView()
        self._tab_widget.addTab(self._project_view, "项目管理")

        # Tab 2: 样品管理
        self._sample_view = SampleView()
        self._tab_widget.addTab(self._sample_view, "样品管理")

        # Tab 3: 测试计划
        self._test_plan_view = TestPlanView()
        self._tab_widget.addTab(self._test_plan_view, "测试计划")

        # Tab 4: Issue 管理（看板/列表）
        assert self._ctrl.issue_service is not None, "IssueService must be initialized"
        self._bug_tracker_view = BugTrackerView(self._ctrl.issue_service, undo_manager=self._ctrl.undo_manager)
        self._tab_widget.addTab(self._bug_tracker_view, "Issue 管理")

        # Tab 5: 待办事项
        self._todo_view = TodoView()
        self._tab_widget.addTab(self._todo_view, "待办事项")

        # Tab 6: 设备 & 技术员管理（内部双 tab）
        self._equip_tech_tabs = QTabWidget()
        self._equipment_view = EquipmentView()
        self._equip_tech_tabs.addTab(self._equipment_view, "设备")
        self._technician_view = TechnicianView()
        self._equip_tech_tabs.addTab(self._technician_view, "技术员")
        self._tab_widget.addTab(self._equip_tech_tabs, "设备管理")

        # Tab 7: 知识库
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
        # Tab 切换时保存 + 自动刷新
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tab_widget)

        self.setCentralWidget(central)

        # ── 待办提醒定时器 ──
        # 审计 #8：原此处 30s 定时器与 _start_reminder_check 的 60s 定时器
        # 双路并行（同事件双 toast、两种错误处理）。统一走 _start_reminder_check。

    # ── Tab 切换自动刷新 ──

    def _on_tab_changed(self, index: int) -> None:
        """切换 Tab 时保存索引 + 自动刷新数据。"""
        QSettings().setValue("ReliaTrack/last_tab_index", index)

        # 淡入微动效已移除（2026-08-22）：QGraphicsOpacityEffect 强制整页离屏合成，
        # 在重页（测试计划：任务表+甘特图+筛选栏）上 X250 老显卡出现局部重绘乱序，
        # 表现为切换瞬间"小弹窗一闪而过"。直接切换无动画。

        # Tab 0 仪表盘 / Tab 3 测试计划 / Tab 4 Issue 管理
        if index == 0:
            self._schedule_refresh("dashboard")
        elif index == 3:
            self._schedule_refresh("test_plan")
        elif index == 4:
            self._schedule_refresh("issue")

    # ── 仪表盘卡片点击 ──

    def _on_dashboard_card_clicked(self, tab_index: int, jump_data: object = None) -> None:
        """点击仪表盘 KPI 卡片 → 跳转 Tab + 自动应用关联筛选条件。"""
        if 0 <= tab_index < self._tab_widget.count():
            self._tab_widget.setCurrentIndex(tab_index)

        if jump_data and isinstance(jump_data, dict):
            # 跳转至测试计划 Tab (Tab 3)
            if tab_index == 3 and hasattr(self, '_test_plan_view'):
                if "task_status" in jump_data:
                    status = jump_data["task_status"]
                    combo = getattr(self._test_plan_view, '_status_filter_combo', None)
                    if combo:
                        idx = combo.findData(status)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)

            # 跳转至 Issue 管理 Tab (Tab 4)
            elif tab_index == 4 and hasattr(self, '_bug_tracker_view'):
                if "issue_status" in jump_data:
                    status = jump_data["issue_status"]
                    bug_list = getattr(self._bug_tracker_view, '_list_view', None)
                    if bug_list and hasattr(bug_list, '_filter_status'):
                        idx = bug_list._filter_status.findData(status)
                        if idx >= 0:
                            bug_list._filter_status.setCurrentIndex(idx)


    def _create_filter_bar_content(self, parent: QWidget) -> None:
        """创建项目/计划筛选栏 + Ctrl+K 搜索按钮 — 菜单栏右上角。"""
        # combo parent 设为 self 避免 Windows setCornerWidget 销毁问题
        self._project_filter_combo = QComboBox(self)
        self._project_filter_combo.setMinimumWidth(150)
        self._project_filter_combo.setProperty("class", "filter-combo")
        self._project_filter_combo.addItem("全部项目", None)
        self._plan_filter_combo = QComboBox(self)
        self._plan_filter_combo.setMinimumWidth(130)
        self._plan_filter_combo.setProperty("class", "filter-combo")
        self._plan_filter_combo.addItem("全部计划", None)
        self._plan_filter_combo.setEnabled(False)
        self._project_filter_combo.currentIndexChanged.connect(self._on_project_filter_changed)
        self._plan_filter_combo.currentIndexChanged.connect(self._on_plan_filter_changed)

        filter_label = QLabel("项目筛选:", self)
        filter_label.setProperty("class", "filter-label")
        plan_label = QLabel("计划:", self)
        plan_label.setProperty("class", "filter-label")

        # 快捷 Spotlight 按钮
        from PySide6.QtWidgets import QPushButton
        cmd_btn = QPushButton("🔍 命令 (Ctrl+K)", self)
        cmd_btn.setProperty("class", "btn-secondary")
        cmd_btn.setToolTip("快捷搜功能、指引、项目或 Issue (Ctrl+K)")
        cmd_btn.clicked.connect(self._open_command_palette)

        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(8, 0, 4, 0)
        filter_bar.setSpacing(6)
        filter_bar.addWidget(cmd_btn)
        filter_bar.addWidget(filter_label)
        filter_bar.addWidget(self._project_filter_combo)
        filter_bar.addWidget(plan_label)
        filter_bar.addWidget(self._plan_filter_combo)



        widget = QWidget(self)
        widget.setLayout(filter_bar)
        widget.setProperty("class", "filter-bar")
        parent.setCornerWidget(widget, Qt.Corner.TopRightCorner)

        # 绑定 Ctrl+K 与 ? 快捷键
        from PySide6.QtGui import QKeySequence, QShortcut
        self._shortcut_cmd_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self._shortcut_cmd_k.activated.connect(self._open_command_palette)
        self._shortcut_help = QShortcut(QKeySequence("?"), self)
        self._shortcut_help.activated.connect(self._open_keyboard_shortcuts)

    def _open_view_theme_settings(self) -> None:
        """打开视图偏好与主题融合设置中心。"""
        from src.views.widgets.view_theme_settings_dialog import ViewThemeSettingsDialog
        dlg = ViewThemeSettingsDialog(self)
        dlg.show_centered()

    def _open_report_bundle(self) -> None:

        """打开测试全景简报打包导出中心。"""
        from src.views.widgets.report_bundle_dialog import ReportBundleDialog

        def _get_plan_id() -> int | None:
            if hasattr(self, "test_plan_view"):
                return self.test_plan_view.get_selected_plan_id()
            return None

        def _get_project_id() -> int | None:
            combo = getattr(self, "_project_filter_combo", None)
            if combo is not None:
                return combo.currentData()
            return None

        dlg = ReportBundleDialog(
            self,
            controller=self._ctrl,
            get_plan_id=_get_plan_id,
            get_project_id=_get_project_id,
        )
        dlg.show_centered()

    def _open_keyboard_shortcuts(self) -> None:
        """打开键盘快捷键地图弹窗。"""
        from src.views.widgets.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
        dlg = KeyboardShortcutsDialog(self)
        dlg.show_centered()


    def _open_command_palette(self) -> None:

        """打开 Spotlight 命令面板。"""
        from src.views.widgets.command_palette_dialog import CommandPaletteDialog
        dlg = CommandPaletteDialog(self, self._ctrl)
        dlg.action_triggered.connect(self._on_command_palette_action)
        dlg.show_centered()

    def _on_command_palette_action(self, result: tuple) -> None:
        """命令面板触发动作执行。"""
        if not result or not isinstance(result, tuple):
            return
        kind, value = result[0], result[1]
        if kind == "tab":
            if isinstance(value, int) and 0 <= value < self._tab_widget.count():
                self._tab_widget.setCurrentIndex(value)
        elif kind == "action":
            if value == "8d_report":
                self._on_8d_report()
            elif value == "backup":
                self._on_backup_db()
            elif value == "theme":
                self._on_toggle_dark_theme(True)
        elif kind == "project":
            idx = self._project_filter_combo.findData(value)
            if idx >= 0:
                self._project_filter_combo.setCurrentIndex(idx)
            self._tab_widget.setCurrentIndex(1)
        elif kind == "sample":
            self._tab_widget.setCurrentIndex(2)

    def _check_todo_reminders(self) -> None:
        """[已废弃] 旧 30s 提醒回调 — 审计 #8 后统一走 _check_due_reminders。保留空壳防外部引用。"""
        return

    def _setup_menubar(self) -> None:
        """创建菜单栏。"""
        menubar = self.menuBar()

        # 操作菜单
        op_menu = menubar.addMenu("操作(&O)")

        act_refresh = QAction("刷新(&R) ⏱", self)
        act_refresh.setIcon(RI_REFRESH.icon())
        act_refresh.setShortcut("F5")
        act_refresh.setToolTip("刷新所有数据 (F5)")
        act_refresh.triggered.connect(self._refresh_all)
        op_menu.addAction(act_refresh)

        act_health = QAction("数据体检(&H)…", self)
        act_health.setToolTip("扫描附件完整性、孤儿文件与断链引用")
        act_health.triggered.connect(self._on_data_health_check)
        op_menu.addAction(act_health)

        act_backup = QAction("数据管理(&B)…", self)
        act_backup.setIcon(RI_BACKUP.icon())
        act_backup.setToolTip("数据库备份与恢复")
        act_backup.triggered.connect(self._backup_handlers._on_data_manage)
        op_menu.addAction(act_backup)

        # 导出子菜单 — 归拢所有导出入口，避免平铺混乱
        export_menu = op_menu.addMenu("导出(&E)")
        export_menu.setIcon(RI_EXPORT.icon())

        act_export = QAction("通用导出(&E)…", self)
        act_export.setIcon(RI_EXPORT.icon())
        act_export.setShortcut("Ctrl+E")
        act_export.setToolTip("导出任务/Issue/样品/综合报告 (Ctrl+E)")
        act_export.triggered.connect(self._export_handlers._on_export)
        export_menu.addAction(act_export)

        act_report_bundle = QAction("📊 导出全景总结简报(&B)…", self)
        act_report_bundle.setToolTip("一键打包导出多维测试总结简报与 8D 报告")
        act_report_bundle.triggered.connect(self._open_report_bundle)
        export_menu.addAction(act_report_bundle)

        op_menu.addSeparator()

        act_backup = QAction("数据管理(&B)…", self)
        act_backup.setIcon(RI_BACKUP.icon())
        act_backup.setToolTip("数据库备份与恢复")
        act_backup.triggered.connect(self._backup_handlers._on_data_manage)
        op_menu.addAction(act_backup)

        act_health = QAction("数据体检(&H)…", self)
        act_health.setToolTip("扫描附件完整性、孤儿文件与断链引用")
        act_health.triggered.connect(self._on_data_health_check)
        op_menu.addAction(act_health)

        # 视图菜单 — 唯一精简入口
        view_menu = menubar.addMenu("视图(&V)")

        act_view_theme_settings = QAction("⚙️ 视图偏好与主题设置(&S)…", self)
        act_view_theme_settings.setShortcut("Ctrl+Shift+T")
        act_view_theme_settings.setToolTip("实时切换主题风格、强调色与表格列偏好 (Ctrl+Shift+T)")
        act_view_theme_settings.triggered.connect(self._open_view_theme_settings)
        view_menu.addAction(act_view_theme_settings)

        # 订阅主题变化
        theme_host.theme_changed.connect(self._on_theme_changed)



        # 全局项目/计划筛选 — 菜单栏右侧（直接插入 QMenuBar 的布局，避免 setCornerWidget Windows 兼容问题）
        self._create_filter_bar_content(menubar)

        # 筛选栏创建后才触发完整刷新（否则 combo 尚未创建，填充不了项目列表）
        self._refresh_all()

    def _on_data_health_check(self) -> None:
        """操作菜单 → 数据体检：后台扫描 + 结果对话框。"""
        from src.views.dialogs.data_health_dialog import DataHealthDialog

        dlg = DataHealthDialog(self._ctrl, self)
        dlg.exec()

    def _on_toggle_dark_theme(self, checked: bool) -> None:
        """菜单 Toggle 回调 — 切换主题并持久化。"""
        from PySide6.QtWidgets import QApplication
        name = "dark" if checked else "light"
        set_theme(name)
        apply_palette()
        QApplication.instance().setStyleSheet(get_stylesheet())
        self._refresh_remaining_inline_styles()
        QSettings().setValue("ReliaTrack/theme", name)

    def _on_theme_changed(self, name: str) -> None:
        """外部主题切换回调。"""
        if hasattr(self, "_act_dark_theme"):
            self._act_dark_theme.blockSignals(True)
            self._act_dark_theme.setChecked(name == "dark")
            self._act_dark_theme.blockSignals(False)
        self._refresh_remaining_inline_styles()
        # setForeground 写死 QColor 的表格不随 QSS 刷新 — 全量刷新让所有视图重绘
        # (覆盖设备/项目/任务表/Issue/结果矩阵/知识库/样品tab等全部常驻表格)
        self._schedule_refresh("all")


    def _refresh_remaining_inline_styles(self) -> None:
        """主题切换后刷新仍有动态内联样式的控件。

        大部分控件已迁移到 QSS 类选择器（全局 QSS 自动刷新），
        以下情况仍需手动：
        - dashboard stat card 数值颜色（DASH_NEUTRAL = theme 变量）
        - result_matrix 模式按钮（运行时 checked/unchecked 动态切换）
        - 已打开 dialog 中的 _ResultRow/_btn_pass_all（已有 refresh_theme）
        """
        # 1. 长驻视图的剩余 refresh_theme
        for view in (self._dashboard, self._bug_tracker_view, self._todo_view):
            if hasattr(view, "refresh_theme"):
                view.refresh_theme()

        # result_matrix 是 test_plan_view 的子 widget
        matrix = getattr(self._test_plan_view, "_result_matrix", None)
        if matrix and hasattr(matrix, "refresh_theme"):
            matrix.refresh_theme()

        # 2. 已打开的弹窗 — 调用 refresh_theme（若有）
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        for win in app.topLevelWidgets():
            if hasattr(win, "refresh_theme"):
                win.refresh_theme()

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
            self._bug_tracker_view._act_new_issue.trigger()
        elif idx == 5:
            self._todo_handlers._on_todo_add()
        elif idx == 6:
            # 设备管理外层 Tab 内含 设备/技术员 两个子 Tab
            if self._equip_tech_tabs.currentIndex() == 1:
                self._technician_handlers._on_technician_add()
            else:
                self._equipment_handlers._on_equipment_add()
        elif idx == 7:
            self._knowledge_handlers._on_knowledge_add()

    def _on_shortcut_delete(self) -> None:
        """Delete: 删除当前 Tab 的选中项。"""
        idx = self._tab_widget.currentIndex()
        if idx == 1:
            self._project_handlers._on_project_delete()
        elif idx == 3:
            self._plan_handlers._on_task_delete_menu()
        elif idx == 4:
            pass  # Issue 管理通过内部看板/列表操作删除
        elif idx == 5:
            self._todo_handlers._on_todo_delete()
        elif idx == 6:
            if self._equip_tech_tabs.currentIndex() == 1:
                self._technician_handlers._on_technician_delete()
            else:
                self._equipment_handlers._on_equipment_delete()
        elif idx == 7:
            self._knowledge_handlers._on_knowledge_delete()

    def _on_shortcut_edit(self) -> None:
        """F2: 编辑当前 Tab 的选中项。"""
        idx = self._tab_widget.currentIndex()
        if idx == 1:
            self._project_handlers._on_project_edit()
        elif idx == 3:
            self._plan_handlers._on_task_edit_menu()
        elif idx == 5:
            self._todo_handlers._on_todo_edit()
        elif idx == 6:
            if self._equip_tech_tabs.currentIndex() == 1:
                self._technician_handlers._on_technician_edit()
            else:
                self._equipment_handlers._on_equipment_edit()
        elif idx == 7:
            self._knowledge_handlers._on_knowledge_edit()

    def _on_shortcut_find(self) -> None:
        """Ctrl+F: 聚焦当前 Tab 的搜索框。"""
        search_map = {
            1: lambda: self._project_view.search_input,
            2: lambda: self._sample_view.pool_tab.search_input,
            3: lambda: self._test_plan_view._search_edit,
            4: lambda: self._bug_tracker_view.list_view._search_input if self._bug_tracker_view.list_view else None,
            5: lambda: self._todo_view._search_edit,
            6: lambda: self._equipment_view._search_edit,
            7: lambda: self._knowledge_view._search_edit,
        }
        idx = self._tab_widget.currentIndex()
        if idx == 6 and self._equip_tech_tabs.currentIndex() == 1:
            # 技术员子 Tab：聚焦技术员搜索框
            getter = lambda: self._technician_view._search_edit  # noqa: E731
        else:
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
        if not self._project_filter_combo:
            return None
        try:
            return self._project_filter_combo.currentData()
        except RuntimeError:
            return None

    def get_plan_filter_id(self) -> int | None:
        """获取当前计划筛选 combo 的 currentData（None = 全部计划）。"""
        if not self._plan_filter_combo:
            return None
        try:
            if not self._plan_filter_combo.isEnabled():
                return None
            return self._plan_filter_combo.currentData()
        except RuntimeError:
            return None

    def refresh_project_filter(self, projects: list, current_id: int | None = None) -> None:
        """刷新项目筛选 combo 选项（不触发信号）。
        """
        combo = self._project_filter_combo
        if not combo:
            return
        try:
            combo.blockSignals(True)
            _current = current_id if current_id is not None else combo.currentData()
            combo.clear()
            combo.addItem("全部项目", None)
            for p in projects:
                combo.addItem(p.name, p.id)
            for i in range(combo.count()):
                if combo.itemData(i) == _current:
                    combo.setCurrentIndex(i)
                    break
            combo.blockSignals(False)
        except RuntimeError:
            pass

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
        """更新撤销/重做状态 — 状态栏显示可撤销/重做操作描述。"""
        parts = []
        if can_undo and undo_desc:
            parts.append(f"撤销: {undo_desc}")
        if can_redo and redo_desc:
            parts.append(f"重做: {redo_desc}")
        if parts:
            self.statusBar().showMessage(" | ".join(parts), 5000)

    # ── 公共属性（Handler 通过 .ctrl 访问，替代直接操作 _ctrl） ──────

    @property
    def ctrl(self) -> AppController:
        """获取应用控制器。"""
        return self._ctrl

    @property
    def test_plan_view(self) -> TestPlanView:
        return self._test_plan_view

    @property
    def bug_tracker_view(self):
        """Bug Tracker 视图（合并了 Issue 追踪功能）。"""
        return self._bug_tracker_view

    @property
    def issue_view(self):
        """兼容别名 — 返回 bug_tracker_view（Issue 追踪已合并）。"""
        return self._bug_tracker_view

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
    def todo_view(self) -> TodoView:
        return self._todo_view

    @property
    def dashboard(self) -> DashboardView:
        return self._dashboard

    @property
    def db_path(self) -> str:
        """获取当前数据库路径。"""
        return getattr(self._ctrl, '_db_path', '')

    @property
    def project_filter_combo(self) -> QComboBox:
        return self._project_filter_combo

    def _on_project_filter_changed(self, index: int) -> None:
        """项目筛选变化时：更新计划 combo + 刷新所有视图。"""
        # 更新计划 combo
        self.refresh_plan_combo()
        self._refresh_all()

    def _on_plan_filter_changed(self, index: int) -> None:
        """计划筛选变化时刷新仪表盘，并同步测试计划视图的本地 combo。"""
        if not self._plan_filter_combo:
            return
        try:
            plan_id = self._plan_filter_combo.currentData()
        except RuntimeError:
            return
        if hasattr(self, '_test_plan_view') and self._test_plan_view:
            self._test_plan_view.select_plan_by_id(plan_id)
        self._refresh_all()


    def refresh_plan_combo(self) -> None:
        """根据当前选中的项目更新计划筛选 combo（保留之前选中项）。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        try:
            project_id = self._project_filter_combo.currentData()
        except RuntimeError:
            return

        try:
            # 记住当前选中
            _current_plan_id = self._plan_filter_combo.currentData()

            self._plan_filter_combo.blockSignals(True)
            self._plan_filter_combo.clear()
            self._plan_filter_combo.addItem("全部计划", None)

            if project_id is None:
                self._plan_filter_combo.setEnabled(False)
            else:
                show_archived = getattr(self.test_plan_view, 'show_archived', False)
                if show_archived:
                    plans = ctrl.test_plan_service.get_archived_plans_by_project(project_id)
                else:
                    plans = ctrl.test_plan_service.get_active_plans_by_project(project_id)
                for p in plans:
                    self._plan_filter_combo.addItem(p.name, p.id)
                self._plan_filter_combo.setEnabled(True)

                for i in range(self._plan_filter_combo.count()):
                    if self._plan_filter_combo.itemData(i) == _current_plan_id:
                        self._plan_filter_combo.setCurrentIndex(i)
                        break
            self._plan_filter_combo.blockSignals(False)
        except RuntimeError:
            pass

    def _entity_types_for_command(self, cmd: object) -> set[str]:
        """根据 undo/redo 命令推断需要刷新的实体类型。

        undo/redo 后必须按命令实际影响的实体刷新视图，否则
        撤销设备/知识/技术员/待办删除后对应视图停留在旧状态。
        """
        from src.services.undo_manager import (
            BatchEditSamplesCommand,
            BatchScheduleCommand,
            MacroCommand,
            SoftDeleteCommand,
            TransitionIssueStatusCommand,
            UpdateFieldCommand,
        )
        if cmd is None:
            return {"issue"}
        # MacroCommand: 合并所有子命令的实体类型
        if isinstance(cmd, MacroCommand):
            entities: set[str] = set()
            for sub in getattr(cmd, "_commands", []) or []:
                entities |= self._entity_types_for_command(sub)
            return entities or {"all"}
        # 明确类型的命令 → 固定实体
        if isinstance(cmd, BatchEditSamplesCommand):
            return {"sample"}
        if isinstance(cmd, (BatchScheduleCommand, UpdateFieldCommand)):
            # UpdateFieldCommand 子类: MoveTask/UpdateProgress/UpdateTaskStatus → task
            return {"task"}
        if isinstance(cmd, (SoftDeleteCommand, TransitionIssueStatusCommand)):
            return {"issue"}
        # 通用: 从 repo._table 推断
        repo = getattr(cmd, "_repo", None)
        table = getattr(repo, "_table", "")
        table_to_entity = {
            "issues": "issue",
            "test_tasks": "task",
            "test_plans": "plan",
            "samples": "sample",
            "equipment": "equipment",
            "technicians": "technician",
            "knowledge_entries": "knowledge",
            "todos": "todo",
        }
        entity = table_to_entity.get(table)
        if entity:
            return {entity}
        entity_name = getattr(cmd, "_entity_name", "")
        name_to_entity = {
            "设备": "equipment", "技术员": "technician", "知识": "knowledge",
            "知识库": "knowledge", "待办": "todo", "任务": "task",
            "样品": "sample", "项目": "project", "Issue": "issue",
        }
        mapped = name_to_entity.get(entity_name)
        if mapped:
            return {mapped}
        return {"all"}

    def _on_undo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        cmd = um.peek_undo()
        desc = um.undo()
        if desc:
            self.statusBar().showMessage(f"已撤销: {desc}", 3000)
            for entity in self._entity_types_for_command(cmd):
                self._ctrl.notify_data_changed(entity)
            self._replay_sync_after_undo_redo(cmd)
            self._flash_undo_affected_row(cmd)

    def _on_redo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        cmd = um.peek_redo()
        desc = um.redo()
        if desc:
            self.statusBar().showMessage(f"已重做: {desc}", 3000)
            for entity in self._entity_types_for_command(cmd):
                self._ctrl.notify_data_changed(entity)
            self._replay_sync_after_undo_redo(cmd)
            self._flash_undo_affected_row(cmd)

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

    def _flash_undo_affected_row(self, cmd: object) -> None:
        """撤销/重做后尝试从命令提取 entity_id，闪烁对应表格行。"""
        from src.services.undo_manager import (
            UpdateFieldCommand, DeleteEntityCommand,
            MoveTaskCommand, UpdateProgressCommand, UpdateTaskStatusCommand,
        )
        # 提取 task_id
        task_id: int | None = None
        if isinstance(cmd, (UpdateFieldCommand, MoveTaskCommand,
                           UpdateProgressCommand, UpdateTaskStatusCommand)):
            task_id = cmd._entity_id
        elif isinstance(cmd, DeleteEntityCommand):
            task_id = cmd._saved_data.get("id")
        if task_id is not None:
            table = self._test_plan_view.task_table
            if hasattr(table, "flash_row"):
                # 延迟一下让刷新完成，再闪烁
                from PySide6.QtCore import QTimer
                QTimer.singleShot(300, lambda tid=task_id: table.flash_row(tid))

    def toast(self, message: str, level: str = "success") -> None:
        """显示 Toast 提示（使用 ToastNotificationStack 浮动叠放）。"""
        if not hasattr(self, '_toast_stack'):
            from src.views.widgets.toast_stack import ToastNotificationStack
            self._toast_stack = ToastNotificationStack(self)
        self._toast_stack.show_toast(message, level)

    def _start_reminder_check(self) -> None:
        """待办提醒检查 — 启动 1.5s 后首次检查 + 每 60s 轮询。"""
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(60_000)
        self._reminder_timer.timeout.connect(self._check_due_reminders)
        self._reminder_timer.start()
        QTimer.singleShot(1500, self._check_due_reminders)

    def _check_due_reminders(self) -> None:
        """检查到期待办并 toast 提醒（一次性标记 reminded 防重复）。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.todo_service:
            return
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            due = ctrl.todo_service.list_due_reminders(now)
        except Exception:
            return
        for todo in due:
            if todo.id is None:
                continue
            try:
                ctrl.todo_service.mark_reminded(todo.id)
            except Exception:
                continue
            title = todo.title or "(无标题)"
            self.toast(f"待办提醒：{title}", "warning")
            # statusBar 持久提示（toast 瞬时，防错过）
            self.statusBar().showMessage(f"待办提醒：{title}", 10_000)

    def _check_calibration_reminders(self) -> None:
        """检查 30 天内到期/已过期的设备校准并提示（同一天只提醒一次）。"""
        from PySide6.QtCore import QSettings
        ctrl = self._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        try:
            expiring = ctrl.equipment_service.get_expiring_calibrations(30)
        except Exception:
            return
        if not expiring:
            return
        # 一天只提醒一次（QSettings 记录上次提醒日期）
        from datetime import datetime
        settings = QSettings()
        today = datetime.now().strftime("%Y-%m-%d")
        if settings.value("ReliaTrack/last_cal_remind_date") == today:
            return
        settings.setValue("ReliaTrack/last_cal_remind_date", today)
        overdue = [e for e, d in expiring if d < 0]
        due_soon = [e for e, d in expiring if d >= 0]
        parts = []
        if overdue:
            parts.append(f"{len(overdue)} 台已过期")
        if due_soon:
            parts.append(f"{len(due_soon)} 台 30 天内到期")
        if not parts:
            return
        names = "、".join(e.name for e, _d in expiring[:3])
        more = f" 等 {len(expiring)} 台" if len(expiring) > 3 else ""
        self.toast(f"校准提醒：{names}{more}（{ '，'.join(parts) }）", "warning")
        self.statusBar().showMessage(f"校准提醒：{len(expiring)} 台设备校准到期/即将到期，请前往设备管理处理。", 15_000)


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
        self._save_window_geometry()
        event.accept()

    # ── 窗口几何记忆 ──────────────────────────────────────────

    _GEOMETRY_KEY = "ReliaTrack/window_geometry"
    _STATE_KEY = "ReliaTrack/window_state"

    def _restore_window_geometry(self) -> None:
        """从 QSettings 恢复上次窗口大小/位置；无记录时用默认尺寸。"""
        settings = QSettings()
        geo = settings.value(self._GEOMETRY_KEY)
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1100, 700)
        state = settings.value(self._STATE_KEY)
        if state:
            self.restoreState(state)

    def _save_window_geometry(self) -> None:
        """保存窗口几何到 QSettings（关闭时调用）。"""
        settings = QSettings()
        settings.setValue(self._GEOMETRY_KEY, self.saveGeometry())
        settings.setValue(self._STATE_KEY, self.saveState())

    # ── UX 增强：平滑滚动 + 动效 ──

    def _install_ux_enhancements(self) -> None:
        """全局安装平滑滚动和动效。"""
        # 查找所有 QScrollArea 安装平滑滚动
        for sa in self.findChildren(QScrollArea):
            SmoothScroll(sa)

        # 所有按钮安装 TranslateYAnimation（press 沉降动画）
        for btn in self.findChildren(QPushButton):
            TranslateYAnimation(btn, offset=1.5)
        for btn in self.findChildren(QToolButton):
            TranslateYAnimation(btn, offset=1.5)


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
    # 使用 Fusion 作为 base style — 跨平台一致，完全遵循 QPalette，
    # 避免 Windows 暗色系统主题通过 QWindowsVistaStyle 注入暗色 palette
    from PySide6.QtWidgets import QStyleFactory
    _base_style = QStyleFactory.create("Fusion")
    from src.styles.proxy_style import CheckboxProxyStyle
    app.setStyle(CheckboxProxyStyle(_base_style))

    apply_palette()
    app.setStyleSheet(get_stylesheet())

    # 恢复主题偏好与强调色配置（QSettings，controller 初始化前即可用）
    _settings = QSettings()
    _saved_accent = _settings.value("ReliaTrack/accent_color", None)
    if _saved_accent and isinstance(_saved_accent, str):
        from src.styles.theme import apply_accent_color
        apply_accent_color(_saved_accent)

    _saved_theme = _settings.value("ReliaTrack/theme", "light")
    if _saved_theme in ("light", "dark"):
        set_theme(_saved_theme)

    apply_palette()
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
        # 抢锁失败说明另一实例正持有锁——绝不能 unlock/unlink，
        # 否则会拆掉对方的互斥保护，制造双实例窗口（2026-08-21 审计 #1）
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
    try:
        controller.initialize()
    except DbCorruptError as exc:
        # 启动自检失败 → 引导从备份恢复；恢复成功则重试初始化
        from src.views.dialogs.db_corrupt_dialog import DbCorruptDialog

        while True:
            dlg = DbCorruptDialog(exc, _db_path)
            if dlg.exec() and dlg.restored:
                controller = AppController(_db_path)
                try:
                    controller.initialize()
                    break  # 恢复后初始化成功
                except DbCorruptError as exc2:
                    exc = exc2  # 恢复的库仍有问题，继续让用户选下一个备份
                    continue
            else:
                logging.getLogger("reliatrack").error("用户放弃恢复，程序退出")
                return 1

    # 启动主窗口
    window = MainWindow(controller)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
