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
    QLabel,
    QStatusBar,
    QToolBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from src.styles.theme import get_stylesheet
from src.controllers import AppController
from src.views.dashboard_view import DashboardView
from src.views.sample_view import SampleView
from src.views.test_plan_view import TestPlanView
from src.views.issue_view import IssueView
from src.views.dialogs.sample_checkin_dialog import SampleCheckInDialog
from src.views.dialogs.sample_checkout_dialog import SampleCheckoutDialog
from src.views.dialogs.issue_dialog import IssueEditDialog
from src.views.dialogs.fa_record_dialog import FARecordDialog
from src.views.dialogs.task_dialog import TaskEditDialog
from src.views.dialogs.export_dialog import ExportDialog


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
        self._issue_view._on_issue_saved = self._handle_issue_saved
        self._issue_view._on_issue_deleted = self._handle_issue_deleted
        self._issue_view._on_issue_selected = self._handle_issue_selected
        self._issue_view._on_fa_record_added = self._handle_fa_record_added
        self._issue_view._current_fa_records = lambda: self._current_fa_records

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
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background-color: transparent;
                color: #a6adc8;
                padding: 10px 24px;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
            }
        """)

        # Tab 0: 仪表盘
        self._dashboard = DashboardView()
        self._tab_widget.addTab(self._dashboard, "📊 仪表盘")

        # Tab 1: 样品管理
        self._sample_view = SampleView()
        self._tab_widget.addTab(self._sample_view, "📦 样品管理")

        # 样品出入库按钮
        self._sample_view.pool_tab.btn_add.clicked.connect(self._on_sample_checkin)
        self._sample_view.pool_tab.btn_out.clicked.connect(self._on_sample_checkout)

        # Tab 2: 测试计划
        self._test_plan_view = TestPlanView()
        self._tab_widget.addTab(self._test_plan_view, "📋 测试计划")
        self._test_plan_view.btn_schedule.clicked.connect(self._on_auto_schedule)
        self._test_plan_view._plan_combo.currentIndexChanged.connect(
            self._on_plan_changed
        )

        # 测试任务增删改
        self._test_plan_view.setup_task_callbacks(
            on_add=self._on_task_add,
            on_edit=self._on_task_edit,
            on_delete=self._on_task_delete,
        )

        # Tab 3: Issue 追踪
        self._issue_view = IssueView()
        self._tab_widget.addTab(self._issue_view, "🐛 Issue 追踪")

        # Issue 追踪 — FA 记录缓存
        self._current_fa_records: list = []

        layout.addWidget(self._tab_widget)
        self.setCentralWidget(central)

    def _setup_toolbar(self) -> None:
        """创建工具栏。"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #181825;
                border-bottom: 1px solid #313244;
                spacing: 8px;
                padding: 4px 8px;
            }
        """)
        self.addToolBar(toolbar)

        # 撤销 / 重做
        self._act_undo = QAction("↩ 撤销", self)
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self._on_undo)
        toolbar.addAction(self._act_undo)

        self._act_redo = QAction("↪ 重做", self)
        self._act_redo.setEnabled(False)
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
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #11111b;
                color: #a6adc8;
                font-size: 12px;
            }
        """)
        status_bar.showMessage("ReliaTrack v2.0.0 — 就绪")

    # ── 数据刷新 ──

    def _refresh_all(self) -> None:
        """刷新所有视图数据。"""
        ctrl = self._ctrl
        if ctrl is None:
            return

        # Dashboard KPI
        if ctrl.test_tasks and ctrl.issues and ctrl.equipment:
            all_tasks = ctrl.test_tasks.list_all()
            total = len(all_tasks)
            completed = sum(1 for t in all_tasks if t.status == "completed")
            in_progress = sum(1 for t in all_tasks if t.status == "in_progress")
            pending = sum(1 for t in all_tasks if t.status == "pending")
            issues = len(ctrl.issues.list_all())
            equipment = len(ctrl.equipment.list_all())
            self._dashboard.refresh(
                task_total=total, task_completed=completed,
                task_in_progress=in_progress, task_pending=pending,
                issue_count=issues, equipment_count=equipment,
            )

        # 样品管理
        if ctrl.sample_service:
            all_samples = ctrl.sample_service.list_all()
            self._sample_view.refresh_ledger(all_samples)
            in_stock = ctrl.sample_service.get_by_status("in_stock")
            self._sample_view.refresh_pool(in_stock)

        # 测试计划
        if ctrl.test_plan_service and ctrl.test_tasks:
            all_plans = ctrl.test_plan_service.list_all_plans()
            self._test_plan_view.set_plans(
                [p.name for p in all_plans],
                [p.id for p in all_plans],
            )
            if all_plans:
                tasks = ctrl.test_plan_service.get_tasks(all_plans[0].id)
                max_day = max((t.start_day + t.duration for t in tasks), default=30)
                self._test_plan_view.refresh(tasks, max_day)

        # Issue 追踪
        if ctrl.issue_service:
            all_issues = ctrl.issue_service.list_all()
            self._issue_view.refresh(all_issues)

        # 更新撤销/重做按钮状态
        if ctrl.undo_manager:
            self._act_undo.setEnabled(ctrl.undo_manager.can_undo())
            self._act_redo.setEnabled(ctrl.undo_manager.can_redo())
            if ctrl.undo_manager.undo_description():
                self._act_undo.setText(f"↩ {ctrl.undo_manager.undo_description()}")
            if ctrl.undo_manager.redo_description():
                self._act_redo.setText(f"↪ {ctrl.undo_manager.redo_description()}")

    # ── 槽函数 ──

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

    def _on_plan_changed(self, index: int) -> None:
        """切换测试计划时刷新任务列表。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.test_plan_service:
            return
        all_plans = ctrl.test_plan_service.list_all_plans()
        if 0 <= index < len(all_plans):
            plan = all_plans[index]
            tasks = ctrl.test_plan_service.get_tasks(plan.id)
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
            technician_list=ctrl.technicians.list_all() if ctrl.technicians else [],
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
            technician_list=ctrl.technicians.list_all() if ctrl.technicians else [],
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

    def _on_sample_checkin(self) -> None:
        """样品入库。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        dlg = SampleCheckInDialog(
            parent=self,
            sn_exists_cb=lambda sn: ctrl.sample_service.get_by_sn(sn) is not None,
        )
        if dlg.exec():
            data = dlg.get_data()
            ctrl.sample_service.create(
                sn=data["sn"],
                batch_no=data.get("batch_no") or None,
                spec=data.get("spec") or None,
                project_id=data.get("project_id") or None,
                location=data.get("location") or None,
                notes=data.get("notes") or None,
                status="in_stock",
            )
            self.statusBar().showMessage(f"✅ 样品 {data['sn']} 入库成功", 5000)
            self._ctrl.notify_data_changed()

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
        dlg = SampleCheckoutDialog(sample=sample, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            ctrl.sample_service.add_transaction(
                sample_id=sample.id,
                txn_type="check_out",
                purpose=data.get("purpose"),
                related_task_id=data.get("related_task_id"),
                expected_return=data.get("expected_return"),
                operator=data.get("operator"),
                notes=data.get("notes"),
            )
            ctrl.sample_service.update_status(sample.id, "checked_out")
            self.statusBar().showMessage(f"✅ 样品 {sample.sn} 出库成功", 5000)
            self._ctrl.notify_data_changed()

    # ── Issue / FA 回调 ──

    def _handle_issue_saved(self, data: dict) -> None:
        """Issue 新建/编辑后回调。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        if "id" in data:
            kwargs = {k: v for k, v in data.items() if k != "id"}
            ctrl.issue_service.update(data["id"], **kwargs)
            self.statusBar().showMessage(f"✅ Issue #{data['id']} 已更新", 5000)
        else:
            ctrl.issue_service.create(**data)
            self.statusBar().showMessage("✅ Issue 已创建", 5000)
        self._ctrl.notify_data_changed()

    def _handle_issue_deleted(self, issue_id: int) -> None:
        """Issue 删除后回调。"""
        ctrl = self._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        ctrl.issue_service.delete(issue_id)
        self.statusBar().showMessage(f"✅ Issue #{issue_id} 已删除", 5000)
        self._ctrl.notify_data_changed()

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
        ctrl.issue_service.add_fa_record(issue_id, **data)
        # 刷新 FA 面板
        self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
        self._issue_view.refresh_fa(self._current_fa_records)
        self.statusBar().showMessage("✅ FA 步骤已添加", 5000)

    def _on_export(self) -> None:
        """导出数据。"""
        ctrl = self._ctrl
        if not ctrl:
            return
        dlg = ExportDialog(parent=self)
        if not dlg.exec():
            return
        data = dlg.get_data()
        content = data["content"]
        fmt = data["format"]

        # 综合报告强制 PDF
        if "综合" in content:
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
                else:
                    path = svc.export_report_pdf(plan, tasks, ctrl.issue_service.list_all(), ctrl.sample_service.list_all())
                self.statusBar().showMessage(f"✅ 已导出: {path}", 10000)

            elif "Issue" in content:
                issues = ctrl.issue_service.list_all()
                if not issues:
                    self.statusBar().showMessage("⚠️ 没有 Issue 数据", 5000)
                    return
                path = svc.export_issues_excel(issues)
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
