"""ReliaTrack — 可靠性测试全生命周期管理系统。

主入口：创建 QApplication，初始化 AppController，显示主窗口。
"""

from __future__ import annotations

import sys
import os
from collections import Counter

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
)
from PySide6.QtGui import QAction, QKeySequence

from src.styles.theme import get_stylesheet, TEXT, SURFACE0, SURFACE1, MANTLE
from src.controllers import AppController
from src.views.dashboard_view import DashboardView
from src.views.sample_view import SampleView
from src.views.test_plan_view import TestPlanView
from src.views.issue_view import IssueView
from src.views.equipment_view import EquipmentView
from src.views.dialogs.sample_checkin_dialog import SampleCheckInDialog
from src.views.dialogs.sample_checkout_dialog import SampleCheckoutDialog
from src.views.dialogs.batch_import_dialog import BatchImportDialog
from src.views.dialogs.task_dialog import TaskEditDialog
from src.views.dialogs.plan_edit_dialog import PlanEditDialog
from src.views.dialogs.export_dialog import ExportDialog
from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog
from src.views.dialogs.project_edit_dialog import ProjectEditDialog
from src.views.dialogs.sample_edit_dialog import SampleEditDialog
# attachment management
from src.views.dialogs.attachment_dialog import AttachmentDialog
from src.views.project_view import ProjectView
# knowledge management
from src.views.knowledge_view import KnowledgeView
from src.views.dialogs.knowledge_edit_dialog import KnowledgeEditDialog


class MainWindow(QMainWindow):
    """ReliaTrack 主窗口。"""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._ctrl = controller
        self.setWindowTitle("ReliaTrack — 可靠性测试管理")
        self.setMinimumSize(1024, 768)
        self.resize(1280, 800)

        self._setup_central_widget()
        self._setup_toolbar()
        self._setup_status_bar()

        # Issue 追踪钩子
        self._issue_view._on_issue_saved = self._handle_issue_saved  # type: ignore[method-assign]
        self._issue_view._on_issue_deleted = self._handle_issue_deleted  # type: ignore[method-assign]
        self._issue_view._on_issue_selected = self._handle_issue_selected  # type: ignore[method-assign]
        self._issue_view._on_fa_record_added = self._handle_fa_record_added  # type: ignore[method-assign]
        self._issue_view._current_fa_records = lambda: self._current_fa_records  # type: ignore[method-assign]

        # 初始数据加载
        self._refresh_all()

        # 监听数据变更
        controller.register_on_data_changed(self._refresh_all)

    def _setup_central_widget(self) -> None:
        """创建中央 Tab Widget。"""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()

        # Tab 0: 项目管理
        self._project_view = ProjectView()
        self._tab_widget.addTab(self._project_view, "📁 项目管理")
        self._project_view.btn_add.clicked.connect(self._on_project_add)
        self._project_view.btn_edit.clicked.connect(self._on_project_edit)
        self._project_view.btn_delete.clicked.connect(self._on_project_delete)

        # Tab 1: 仪表盘
        self._dashboard = DashboardView()
        self._tab_widget.addTab(self._dashboard, "📊 仪表盘")

        # Tab 2: 样品管理
        self._sample_view = SampleView()
        self._tab_widget.addTab(self._sample_view, "📦 样品管理")

        # 样品出入库按钮
        self._sample_view.pool_tab.btn_add.clicked.connect(self._on_sample_checkin)
        self._sample_view.pool_tab.btn_out.clicked.connect(self._on_sample_checkout)
        self._sample_view.pool_tab.btn_batch_import.clicked.connect(self._on_sample_batch_import)
        self._sample_view.pool_tab.btn_generate_qr.clicked.connect(self._on_sample_generate_qr)
        self._sample_view.pool_tab.btn_edit.clicked.connect(self._on_sample_edit)

        # 台账 Tab 按钮
        self._sample_view.ledger_tab.btn_generate_qr.clicked.connect(self._on_ledger_generate_qr)
        self._sample_view.ledger_tab.btn_edit.clicked.connect(self._on_ledger_edit)

        # 出入库记录 Tab 搜索回调
        self._sample_view.usage_tab.set_refresh_callback(self._refresh_sample_usage)

        # Tab 3: 测试计划
        self._test_plan_view = TestPlanView()
        self._tab_widget.addTab(self._test_plan_view, "📋 测试计划")
        self._test_plan_view.btn_schedule.clicked.connect(self._on_auto_schedule)
        self._test_plan_view.btn_add_plan.clicked.connect(self._on_plan_add)
        self._test_plan_view.btn_edit_plan.clicked.connect(self._on_plan_edit)
        self._test_plan_view._plan_combo.currentIndexChanged.connect(
            self._on_plan_changed
        )

        # 测试任务增删改
        self._test_plan_view.setup_task_callbacks(
            on_add=self._on_task_add,
            on_edit=self._on_task_edit,
            on_delete=self._on_task_delete,
        )

        # Tab 4: Issue 追踪
        self._issue_view = IssueView()
        self._tab_widget.addTab(self._issue_view, "🐛 Issue 追踪")

        # attachment management: 连接附件按钮
        self._issue_view.btn_attachments.clicked.connect(self._on_issue_attachments)

        # Issue 追踪 — FA 记录缓存
        self._current_fa_records: list = []

        # Tab 5: 设备管理
        self._equipment_view = EquipmentView()
        self._tab_widget.addTab(self._equipment_view, "🔧 设备管理")
        self._equipment_view.btn_add.clicked.connect(self._on_equipment_add)
        self._equipment_view.btn_edit.clicked.connect(self._on_equipment_edit)
        self._equipment_view.btn_delete.clicked.connect(self._on_equipment_delete)

        # knowledge management: Tab 6: 知识库
        self._knowledge_view = KnowledgeView()
        self._tab_widget.addTab(self._knowledge_view, "📚 知识库")
        self._knowledge_view.btn_add.clicked.connect(self._on_knowledge_add)
        self._knowledge_view.btn_edit.clicked.connect(self._on_knowledge_edit)
        self._knowledge_view.btn_delete.clicked.connect(self._on_knowledge_delete)

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
        act_export.triggered.connect(self._on_export)
        toolbar.addAction(act_export)

    def _setup_status_bar(self) -> None:
        """创建状态栏。"""
        status_bar: QStatusBar = self.statusBar()
        status_bar.showMessage("ReliaTrack v2.0.0 — 就绪")

    # ── 数据刷新 ──

    def _refresh_all(self) -> None:
        """刷新所有视图数据。"""
        ctrl = self._ctrl
        if ctrl is None:
            return

        # 获取当前筛选的项目 ID（None = 全部）
        filter_project_id = self._project_filter_combo.currentData()

        # 项目管理 — 始终显示全部项目 + 更新筛选器下拉列表
        if ctrl.project_service:
            all_projects = ctrl.project_service.list_all()
            self._project_view.refresh(all_projects)
            # 更新筛选 combo 选项（不触发信号）
            self._project_filter_combo.blockSignals(True)
            current_filter = self._project_filter_combo.currentData()
            self._project_filter_combo.clear()
            self._project_filter_combo.addItem("📋 全部项目", None)
            for p in all_projects:
                self._project_filter_combo.addItem(f"📁 {p.name}", p.id)
            # 恢复之前选中的筛选项
            for i in range(self._project_filter_combo.count()):
                if self._project_filter_combo.itemData(i) == current_filter:
                    self._project_filter_combo.setCurrentIndex(i)
                    break
            self._project_filter_combo.blockSignals(False)
            # 重新读取筛选值（可能在 blockSignals 期间被恢复）
            filter_project_id = self._project_filter_combo.currentData()

        # 注入项目列表和默认项目到 IssueView（供弹窗使用）
        self._issue_view._project_list = all_projects if ctrl.project_service else []
        self._issue_view._default_project_id = filter_project_id

        # 当前筛选项目名称
        current_project_name: str | None = None
        if filter_project_id and ctrl.project_service:
            for p in all_projects:
                if p.id == filter_project_id:
                    current_project_name = p.name
                    break

        # Dashboard KPI + 图表
        task_status_data: dict[str, int] = {}
        sample_status_data: dict[str, int] = {}
        issue_severity_data: dict[str, int] = {}
        sample_count = 0

        # 样品（提前加载以供 Dashboard 使用）
        if ctrl.sample_service:
            if filter_project_id:
                all_samples = ctrl.sample_service.get_by_project(filter_project_id)
            else:
                all_samples = ctrl.sample_service.list_all()
            sample_count = len(all_samples)
            sample_counter = Counter(s.status for s in all_samples)
            sample_status_data = dict(sample_counter)

        if ctrl.test_tasks and ctrl.issues and ctrl.equipment:
            all_tasks = ctrl.test_tasks.list_all()

            # 按项目筛选任务：通过关联的计划筛选
            if filter_project_id:
                assert ctrl.test_plan_service is not None
                filtered_plans = ctrl.test_plan_service.get_plans_by_project(
                    filter_project_id
                )
                plan_ids = {p.id for p in filtered_plans}
                all_tasks = [t for t in all_tasks if t.plan_id in plan_ids]

            total = len(all_tasks)
            completed = sum(1 for t in all_tasks if t.status == "completed")
            in_progress = sum(1 for t in all_tasks if t.status == "in_progress")
            pending = sum(1 for t in all_tasks if t.status == "pending")

            # 任务状态分布
            task_counter = Counter(t.status for t in all_tasks)
            task_status_data = dict(task_counter)

            # 按项目筛选 issues
            if filter_project_id:
                issues_list = ctrl.issues.get_by_project(filter_project_id)
            else:
                issues_list = ctrl.issues.list_all()
            issues = len(issues_list)
            equipment = len(ctrl.equipment.list_all())

            # Issue 严重度分布
            severity_counter = Counter(i.severity for i in issues_list)
            issue_severity_data = dict(severity_counter)

            self._dashboard.refresh(
                task_total=total, task_completed=completed,
                task_in_progress=in_progress, task_pending=pending,
                issue_count=issues, equipment_count=equipment,
                sample_count=sample_count,
                project_name=current_project_name,
                task_status_data=task_status_data,
                sample_status_data=sample_status_data,
                issue_severity_data=issue_severity_data,
            )

        # 样品视图
        if ctrl.sample_service:
            # 更新样品状态图表
            self._dashboard._chart_sample_status.set_data(
                {({"in_stock": "在库", "checked_out": "已借出", "in_test": "测试中",
                   "suspended": "暂停", "scrapped": "已报废", "returned": "已归还"}).get(k, k): v
                 for k, v in sample_status_data.items() if v > 0}
            )

            self._sample_view.refresh_ledger(all_samples)
            # 样品池只显示在库样品（也按项目筛选）
            in_stock = [s for s in all_samples if s.status == "in_stock"]
            self._sample_view.refresh_pool(in_stock)
            # 出入库记录
            self._refresh_sample_usage()

        # 测试计划
        if ctrl.test_plan_service and ctrl.test_tasks:
            # 按项目筛选计划
            if filter_project_id:
                all_plans = ctrl.test_plan_service.get_plans_by_project(
                    filter_project_id
                )
            else:
                all_plans = ctrl.test_plan_service.list_all_plans()
            # 保存当前选中索引
            current_plan_id = self._test_plan_view.get_selected_plan_id()
            self._test_plan_view._plan_combo.blockSignals(True)
            self._test_plan_view.set_plans(
                [p.name for p in all_plans],
                [p.id for p in all_plans],  # type: ignore[misc]
            )
            restore_idx = 0
            if all_plans:
                # 尝试恢复之前选中的计划
                target_id = current_plan_id if current_plan_id else all_plans[0].id
                # 在新 plan_ids 中找到对应索引
                new_ids = [p.id for p in all_plans]
                restore_idx = new_ids.index(target_id) if target_id in new_ids else 0
                self._test_plan_view._plan_combo.setCurrentIndex(restore_idx)
            self._test_plan_view._plan_combo.blockSignals(False)
            # 手动加载选中计划的任务
            if all_plans:
                plan_id = all_plans[restore_idx].id
                assert plan_id is not None
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                max_day = max((t.start_day + t.duration for t in tasks), default=30)
                self._test_plan_view.refresh(tasks, max_day)

        # Issue 追踪
        if ctrl.issue_service:
            # 按项目筛选 issues
            if filter_project_id:
                all_issues = ctrl.issue_service.get_by_project(filter_project_id)
            else:
                all_issues = ctrl.issue_service.list_all()
            self._issue_view.refresh(all_issues)

        # 设备管理 — 无 project_id，不筛选
        if ctrl.equipment_service:
            all_equipment = ctrl.equipment_service.list_all()
            self._equipment_view.refresh(all_equipment)

        # knowledge management: 知识库 — 无 project_id，不筛选
        if ctrl.knowledge_service:
            all_knowledge = ctrl.knowledge_service.list_all()
            self._knowledge_view.refresh(all_knowledge)

        # 更新撤销/重做按钮状态
        if ctrl.undo_manager:
            self._act_undo.setEnabled(ctrl.undo_manager.can_undo())
            self._act_redo.setEnabled(ctrl.undo_manager.can_redo())
            if ctrl.undo_manager.undo_description():
                self._act_undo.setText(f"↩ {ctrl.undo_manager.undo_description()}")
            if ctrl.undo_manager.redo_description():
                self._act_redo.setText(f"↪ {ctrl.undo_manager.redo_description()}")

    # ── 槽函数 ──

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
            self._ctrl.notify_data_changed()

    def _on_redo(self) -> None:
        um = self._ctrl.undo_manager
        if not um:
            return
        desc = um.redo()
        if desc:
            self.statusBar().showMessage(f"已重做: {desc}", 3000)
            self._ctrl.notify_data_changed()

    def _on_auto_schedule(self) -> None:
        """执行自动排程。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.scheduler_service:
            return

        plan_id = self._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self.statusBar().showMessage("⚠️ 没有测试计划，请先创建计划", 5000)
            return

        self.statusBar().showMessage("⏳ 正在排程…", 0)

        try:
            report = ctrl.scheduler_service.auto_schedule(
                plan_id, skip_weekends=True,
            )
            msg = (
                f"✅ 排程完成：{report['task_count']} 个任务，"
                f"总工期 {report['total_days']} 天，"
                f"更新 {report['updated_count']} 个任务"
            )
            self.statusBar().showMessage(msg, 10000)
            if report.get("suggestions"):
                for s in report["suggestions"][:2]:
                    print(f"[Schedule] {s}")
        except Exception as e:
            self.statusBar().showMessage(f"❌ 排程失败: {e}", 10000)

        # 刷新视图
        self._refresh_all()

    def _on_plan_add(self) -> None:
        """新建测试计划。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service or not ctrl.project_service:
            return
        project_list = ctrl.project_service.list_all()
        default_project_id = self._project_filter_combo.currentData()
        dlg = PlanEditDialog(
            plan=None,
            project_list=project_list,
            default_project_id=default_project_id,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                # 从 data 中提取用于 create_plan 的参数
                kwargs = {k: v for k, v in data.items() if k != "id"}
                # project_id 为 0 表示未选择项目，弹出提示
                if kwargs.get("project_id") == 0:
                    QMessageBox.warning(self, "校验失败", "请选择关联项目后再创建计划。")
                    return
                ctrl.test_plan_service.create_plan(**kwargs)
                self.statusBar().showMessage(f"✅ 计划「{data['name']}」已创建", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "创建失败", f"保存失败: {e}")

    def _on_plan_edit(self) -> None:
        """编辑当前选中的测试计划。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self.statusBar().showMessage("⚠️ 请先选中一个测试计划", 5000)
            return
        plan = ctrl.test_plan_service.get_plan(plan_id)
        if plan is None:
            return
        project_list = ctrl.project_service.list_all() if ctrl.project_service else []
        dlg = PlanEditDialog(
            plan=plan,
            project_list=project_list,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            plan_id_from_data = data.pop("id", None)
            if plan_id_from_data is None:
                return
            try:
                ctrl.test_plan_service.update_plan(plan_id_from_data, **data)
                self.statusBar().showMessage(f"✅ 计划「{data['name']}」已更新", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "更新失败", f"保存失败: {e}")

    def _on_plan_changed(self, index: int) -> None:
        """切换测试计划时刷新任务列表。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            return
        tasks = ctrl.test_plan_service.get_tasks(plan_id)
        max_day = max((t.start_day + t.duration for t in tasks), default=30)
        self._test_plan_view.refresh(tasks, max_day)

    def _on_task_add(self) -> None:
        """新建测试任务。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            self.statusBar().showMessage("⚠️ 没有测试计划，请先创建计划", 5000)
            return
        current_tasks = ctrl.test_plan_service.get_tasks(plan_id)
        dlg = TaskEditDialog(
            task=None,
            equipment_list=ctrl.equipment.list_all() if ctrl.equipment else [],
            technician_list=[],
            all_tasks=current_tasks,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            ctrl.test_plan_service.create_task(plan_id, **data)
            self.statusBar().showMessage(f"✅ 任务「{data['name']}」已创建", 5000)
            self._ctrl.notify_data_changed()

    def _on_task_edit(self, task) -> None:
        """编辑测试任务。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        plan_id = self._test_plan_view.get_selected_plan_id()
        if plan_id is None:
            return
        current_tasks = ctrl.test_plan_service.get_tasks(plan_id)
        dlg = TaskEditDialog(
            task=task,
            equipment_list=ctrl.equipment.list_all() if ctrl.equipment else [],
            technician_list=[],
            all_tasks=current_tasks,
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            ctrl.test_plan_service.update_task(task.id, **data)
            self.statusBar().showMessage(f"✅ 任务「{data['name']}」已更新", 5000)
            self._ctrl.notify_data_changed()

    def _on_task_delete(self, task) -> None:
        """删除测试任务。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        name = task.name
        ctrl.test_plan_service.delete_task(task.id)
        self.statusBar().showMessage(f"✅ 任务「{name}」已删除", 5000)
        self._ctrl.notify_data_changed()

    def _refresh_sample_usage(self) -> None:
        """刷新出入库记录 Tab。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        usage_tab = self._sample_view.usage_tab
        sn_filter = usage_tab._search_input.text()
        type_filter = usage_tab._type_combo.currentData() or ""
        data = ctrl.sample_service.list_transactions(sn_filter, type_filter)
        self._sample_view.refresh_usage(data)

    def _on_sample_checkin(self) -> None:
        """样品入库。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        assert ctrl is not None
        assert ctrl.sample_service is not None
        sample_svc = ctrl.sample_service
        project_list = ctrl.project_service.list_all() if ctrl.project_service else []
        default_project_id = self._project_filter_combo.currentData()
        dlg = SampleCheckInDialog(
            parent=self,
            sn_exists_cb=lambda sn: sample_svc.get_by_sn(sn) is not None,
            project_list=project_list,
            default_project_id=default_project_id,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.sample_service.create(
                    sn=data["sn"],
                    batch_no=data.get("batch_no") or "",
                    spec=data.get("spec") or "",
                    project_id=data.get("project_id") or None,
                    location=data.get("location") or "",
                    notes=data.get("notes") or "",
                    status="in_stock",
                )
                self.statusBar().showMessage(f"✅ 样品 {data['sn']} 入库成功", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "入库失败", f"保存失败: {e}")

    def _on_sample_checkout(self) -> None:
        """样品出库。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._sample_view.pool_tab.table.get_selected_sample_id()
        if sample_id is None:
            self.statusBar().showMessage("⚠️ 请先选中一个样品", 5000)
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        dlg = SampleCheckoutDialog(
            sample=sample,
            technicians=[],
            parent=self,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                assert sample.id is not None
                ctrl.sample_service.add_transaction(
                    sample_id=sample.id,
                    txn_type="check_out",
                    purpose=data.get("purpose"),
                    related_task_id=data.get("related_task_id"),
                    expected_return=data.get("expected_return"),
                    operator_id=data.get("operator_id"),
                    notes=data.get("notes"),
                )
                ctrl.sample_service.update_status(sample.id, "checked_out")
                self.statusBar().showMessage(f"✅ 样品 {sample.sn} 出库成功", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "出库失败", f"保存失败: {e}")

    def _on_sample_batch_import(self) -> None:
        """样品批量导入。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return

        def _do_import(sample_list: list[dict]) -> tuple[int, int]:
            """执行批量导入，返回 (成功数, 跳过数)。"""
            success = 0
            skip = 0
            assert ctrl is not None
            assert ctrl.sample_service is not None
            for data in sample_list:
                sn = data.get("sn", "").strip()
                if not sn:
                    continue
                # 检查 SN 是否已存在
                if ctrl.sample_service.get_by_sn(sn) is not None:
                    skip += 1
                    continue
                try:
                    ctrl.sample_service.create(
                        sn=sn,
                        batch_no=data.get("batch_no") or "",
                        spec=data.get("spec") or "",
                        location=data.get("location") or "",
                        notes=data.get("notes") or "",
                        status="in_stock",
                    )
                    success += 1
                except Exception:
                    skip += 1
            return success, skip

        dlg = BatchImportDialog(
            parent=self,
            on_import=_do_import,
        )
        dlg.exec()
        if dlg.was_imported():
            self._ctrl.notify_data_changed()
            self.statusBar().showMessage("✅ 样品批量导入完成", 5000)

    def _on_sample_generate_qr(self) -> None:
        """为选中样品生成二维码（样品池 Tab）。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._sample_view.pool_tab.table.get_selected_sample_id()
        if sample_id is None:
            QMessageBox.warning(self, "提示", "请先选中一个样品。")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        if not sample.sn:
            QMessageBox.warning(self, "提示", "样品 SN 为空，无法生成二维码。")
            return

        def _save_qr_to_db(sn: str, png_bytes: bytes) -> None:
            """将 base64 编码的 QR 码保存到样品的 qr_code 字段。"""
            import base64
            b64 = base64.b64encode(png_bytes).decode("ascii")
            try:
                ctrl.sample_service.update(sample.id, qr_code=b64)  # type: ignore[union-attr, arg-type]
                self.statusBar().showMessage(
                    f"✅ 样品 {sn} 的二维码已保存到数据库", 5000
                )
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存到数据库失败: {e}")

        self._sample_view.pool_tab.show_qr_dialog(
            sample.sn, parent=self, on_save_to_db=_save_qr_to_db,
        )

    def _on_ledger_generate_qr(self) -> None:
        """为选中样品生成二维码（样品台账 Tab）。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._sample_view.ledger_tab.table.get_selected_sample_id()
        if sample_id is None:
            QMessageBox.warning(self, "提示", "请先选中一个样品。")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        if not sample.sn:
            QMessageBox.warning(self, "提示", "样品 SN 为空，无法生成二维码。")
            return

        def _save_qr_to_db(sn: str, png_bytes: bytes) -> None:
            """将 base64 编码的 QR 码保存到样品的 qr_code 字段。"""
            import base64
            b64 = base64.b64encode(png_bytes).decode("ascii")
            try:
                ctrl.sample_service.update(sample.id, qr_code=b64)  # type: ignore[union-attr, arg-type]
                self.statusBar().showMessage(
                    f"✅ 样品 {sn} 的二维码已保存到数据库", 5000
                )
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存到数据库失败: {e}")

        self._sample_view.pool_tab.show_qr_dialog(
            sample.sn, parent=self, on_save_to_db=_save_qr_to_db,
        )

    def _on_sample_edit(self) -> None:
        """编辑选中样品（样品池 Tab）。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._sample_view.pool_tab.table.get_selected_sample_id()
        if sample_id is None:
            QMessageBox.warning(self, "提示", "请先选中一个样品。")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        dlg = SampleEditDialog(
            sample=sample,
            project_list=ctrl.project_service.list_all() if ctrl.project_service else [],
            parent=self,
        )
        if dlg.exec():
            try:
                data = dlg.get_data()
                assert sample.id is not None
                ctrl.sample_service.update(sample.id, **data)
                self.statusBar().showMessage(f"✅ 样品「{data['sn']}」已更新", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "更新失败", f"保存失败: {e}")

    def _on_ledger_edit(self) -> None:
        """编辑选中样品（样品台账 Tab）。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._sample_view.ledger_tab.table.get_selected_sample_id()
        if sample_id is None:
            QMessageBox.warning(self, "提示", "请先选中一个样品。")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        dlg = SampleEditDialog(
            sample=sample,
            project_list=ctrl.project_service.list_all() if ctrl.project_service else [],
            parent=self,
        )
        if dlg.exec():
            try:
                data = dlg.get_data()
                assert sample.id is not None
                ctrl.sample_service.update(sample.id, **data)
                self.statusBar().showMessage(f"✅ 样品「{data['sn']}」已更新", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "更新失败", f"保存失败: {e}")

    # ── 项目管理回调 ──

    def _on_project_add(self) -> None:
        """新建项目。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.project_service:
            return
        dlg = ProjectEditDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.project_service.create(**data)
                self.statusBar().showMessage(f"✅ 项目「{data['name']}」已创建", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "创建失败", f"保存失败: {e}")

    def _on_project_edit(self) -> None:
        """编辑选中的项目。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.project_service:
            return
        proj = self._project_view.get_selected_project()
        if proj is None:
            self.statusBar().showMessage("⚠️ 请先选中一个项目", 5000)
            return
        dlg = ProjectEditDialog(project=proj, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            proj_id = data.pop("id", None)
            if proj_id is None:
                return
            try:
                ctrl.project_service.update(proj_id, **data)
                self.statusBar().showMessage(f"✅ 项目「{data['name']}」已更新", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "更新失败", f"保存失败: {e}")

    def _on_project_delete(self) -> None:
        """删除选中的项目。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.project_service:
            return
        proj = self._project_view.get_selected_project()
        if proj is None:
            self.statusBar().showMessage("⚠️ 请先选中一个项目", 5000)
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除项目「{proj.name}」吗？\n关联的测试计划、任务、样品、Issue 等数据将一并删除。\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            assert proj.id is not None
            ctrl.project_service.delete(proj.id)
            self.statusBar().showMessage(f"✅ 项目「{proj.name}」已删除", 5000)
            self._ctrl.notify_data_changed()
        except ValueError as e:
            QMessageBox.warning(self, "删除失败", str(e))
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除失败: {e}")

    # ── 设备管理回调 ──

    def _on_equipment_add(self) -> None:
        """新建设备。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        dlg = EquipmentEditDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.equipment_service.create(**data)
                self.statusBar().showMessage(f"✅ 设备「{data['name']}」已创建", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "创建失败", f"保存失败: {e}")

    def _on_equipment_edit(self) -> None:
        """编辑选中的设备。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        eq = self._equipment_view.get_selected_equipment()
        if eq is None:
            self.statusBar().showMessage("⚠️ 请先选中一个设备", 5000)
            return
        dlg = EquipmentEditDialog(equipment=eq, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                assert eq.id is not None
                ctrl.equipment_service.update(eq.id, **data)
                self.statusBar().showMessage(f"✅ 设备「{data['name']}」已更新", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "更新失败", f"保存失败: {e}")

    def _on_equipment_delete(self) -> None:
        """删除选中的设备。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.equipment_service:
            return
        eq = self._equipment_view.get_selected_equipment()
        if eq is None:
            self.statusBar().showMessage("⚠️ 请先选中一个设备", 5000)
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除设备「{eq.name}」({eq.model}) 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            assert eq.id is not None
            ctrl.equipment_service.delete(eq.id)
            self.statusBar().showMessage(f"✅ 设备「{eq.name}」已删除", 5000)
            self._ctrl.notify_data_changed()
        except ValueError as e:
            QMessageBox.warning(self, "删除失败", str(e))
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除失败: {e}")

    # ── 知识库管理回调 (knowledge management) ──

    def _on_knowledge_add(self) -> None:
        """新建知识条目。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        dlg = KnowledgeEditDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.knowledge_service.create(**data)
                self.statusBar().showMessage(f"✅ 知识条目「{data['failure_mode']}」已创建", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "创建失败", f"保存失败: {e}")

    def _on_knowledge_edit(self) -> None:
        """编辑选中的知识条目。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        entry = self._knowledge_view.get_selected_entry()
        if entry is None:
            self.statusBar().showMessage("⚠️ 请先选中一个知识条目", 5000)
            return
        dlg = KnowledgeEditDialog(entry=entry, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                assert entry.id is not None
                ctrl.knowledge_service.update(entry.id, **data)
                self.statusBar().showMessage(f"✅ 知识条目「{data['failure_mode']}」已更新", 5000)
                self._ctrl.notify_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "更新失败", f"保存失败: {e}")

    def _on_knowledge_delete(self) -> None:
        """删除选中的知识条目。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return
        entry = self._knowledge_view.get_selected_entry()
        if entry is None:
            self.statusBar().showMessage("⚠️ 请先选中一个知识条目", 5000)
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除知识条目「{entry.failure_mode}」({entry.category}) 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            assert entry.id is not None
            ctrl.knowledge_service.delete(entry.id)
            self.statusBar().showMessage(f"✅ 知识条目「{entry.failure_mode}」已删除", 5000)
            self._ctrl.notify_data_changed()
        except ValueError as e:
            QMessageBox.warning(self, "删除失败", str(e))
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除失败: {e}")

    # ── Issue / FA 回调 ──

    # attachment management: 附件管理槽
    def _on_issue_attachments(self) -> None:
        """打开 Issue 附件管理弹窗。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = self._issue_view.get_selected_issue_id()
        if issue_id is None:
            self.statusBar().showMessage("⚠️ 请先选中一个 Issue", 5000)
            return
        dlg = AttachmentDialog(
            issue_id=issue_id,
            issue_service=ctrl.issue_service,
            parent=self,
        )
        dlg.exec()

    def _handle_issue_saved(self, data: dict) -> None:
        """Issue 新建/编辑后回调。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            if "id" in data:
                kwargs = {k: v for k, v in data.items() if k != "id"}
                ctrl.issue_service.update(data["id"], **kwargs)
                self.statusBar().showMessage(f"✅ Issue #{data['id']} 已更新", 5000)
            else:
                ctrl.issue_service.create(**data)
                self.statusBar().showMessage("✅ Issue 已创建", 5000)
            self._ctrl.notify_data_changed()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"Issue 保存失败: {e}")

    def _handle_issue_deleted(self, issue_id: int) -> None:
        """Issue 删除后回调。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            ctrl.issue_service.delete(issue_id)
            self.statusBar().showMessage(f"✅ Issue #{issue_id} 已删除", 5000)
            self._ctrl.notify_data_changed()
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"Issue 删除失败: {e}")

    def _handle_issue_selected(self, issue_id: int) -> None:
        """Issue 选中时加载 FA 记录。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
        self._issue_view.refresh_fa(self._current_fa_records)

    def _handle_fa_record_added(self, data: dict) -> None:
        """FA 记录添加后回调。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = data.pop("issue_id", None)
        if issue_id is None:
            return
        try:
            ctrl.issue_service.add_fa_record(issue_id, **data)
            # 刷新 FA 面板
            self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
            self._issue_view.refresh_fa(self._current_fa_records)
            self.statusBar().showMessage("✅ FA 步骤已添加", 5000)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"FA 记录添加失败: {e}")

    def _on_export(self) -> None:
        """导出数据。"""
        ctrl = self._ctrl
        if not ctrl:
            return
        assert ctrl is not None
        assert ctrl.test_plan_service is not None
        assert ctrl.issue_service is not None
        assert ctrl.sample_service is not None
        dlg = ExportDialog(parent=self)
        if not dlg.exec():
            return
        data = dlg.get_data()
        content = data["content"]
        fmt = data["format"]

        # 综合报告默认 PDF，但用户可选 Word
        # word export: 综合报告不再强制 PDF
        if "综合" in content and "Excel" in fmt:
            fmt = "PDF (.pdf)"

        # 确保导出目录
        export_dir = os.path.join(_PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)

        try:
            from src.services.export_service import ExportService
            svc = ExportService(output_dir=export_dir)

            if "测试任务" in content:
                plan_id = self._test_plan_view.get_selected_plan_id()
                if plan_id is None:
                    self.statusBar().showMessage("⚠️ 没有选中测试计划", 5000)
                    return
                plan = ctrl.test_plan_service.get_plan(plan_id)
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                if not plan or not tasks:
                    self.statusBar().showMessage("⚠️ 当前计划没有任务", 5000)
                    return
                if "Excel" in fmt:
                    path = svc.export_tasks_excel(plan, tasks)
                # word export: 测试任务也支持 Word 格式（综合报告）
                elif "Word" in fmt:
                    path = svc.export_to_word(
                        plan, tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                else:
                    path = svc.export_report_pdf(plan, tasks, ctrl.issue_service.list_all(), ctrl.sample_service.list_all())
                self.statusBar().showMessage(f"✅ 已导出: {path}", 10000)

            elif "Issue" in content:
                issues = ctrl.issue_service.list_all()
                if not issues:
                    self.statusBar().showMessage("⚠️ 没有 Issue 数据", 5000)
                    return
                # Build fa_map
                fa_map = {}
                for issue in issues:
                    if issue.id is not None:
                        fa_map[issue.id] = ctrl.issue_service.get_fa_records(issue.id)
                path = svc.export_issues_excel(issues, fa_map=fa_map)
                self.statusBar().showMessage(f"✅ 已导出: {path}", 10000)

            elif "样品" in content:
                samples = ctrl.sample_service.list_all()
                if not samples:
                    self.statusBar().showMessage("⚠️ 没有样品数据", 5000)
                    return
                path = svc.export_samples_excel(samples)
                self.statusBar().showMessage(f"✅ 已导出: {path}", 10000)

            elif "综合" in content:
                plan_id = self._test_plan_view.get_selected_plan_id()
                if plan_id is None:
                    self.statusBar().showMessage("⚠️ 没有选中测试计划", 5000)
                    return
                plan = ctrl.test_plan_service.get_plan(plan_id)
                tasks = ctrl.test_plan_service.get_tasks(plan_id)
                if not plan:
                    return
                # word export: 综合报告支持 Word 格式
                if "Word" in fmt:
                    path = svc.export_to_word(
                        plan, tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                else:
                    path = svc.export_report_pdf(
                        plan, tasks,
                        ctrl.issue_service.list_all(),
                        ctrl.sample_service.list_all(),
                    )
                self.statusBar().showMessage(f"✅ 已导出: {path}", 10000)

        except Exception as e:
            self.statusBar().showMessage(f"❌ 导出失败: {e}", 10000)

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
