"""主窗口 - 包含工具栏、甘特图和资源配置视图"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QToolBar,
    QToolButton, QFileDialog, QMessageBox, QWidget, QVBoxLayout,
    QLabel, QInputDialog,
)
from PySide6.QtGui import QAction, QIcon, QPen, QShortcut, QKeySequence, QPageLayout
from PySide6.QtCore import Qt, QPointF, QRectF, QMarginsF

from src.db.database import Database
from src.views.gantt_view import GanttView
from src.views.resource_view import ResourceView
from src.core.default_data import DEFAULT_TASKS, DEFAULT_RESOURCES
from src.models import Task, Resource, Section, ResourceType, ScheduleConfig, ScheduleMode
from src.core.undo_manager import UndoManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("可靠性测试甘特图 v1.0")
        self.resize(1400, 900)

        # 数据库
        self.db = Database()

        # 撤销/重做管理器
        self.undo_manager = UndoManager()

        # 首次运行初始化默认数据
        if self.db.task_count() == 0:
            self._init_default_data()

        # 项目文件路径
        self._current_project_path = ""

        # 数据看板脏标记（避免切换 tab 时重复查询 DB）
        self._dashboard_dirty = True

        # UI
        self._setup_toolbar()
        self._setup_tabs()
        self._setup_statusbar()
        self._setup_shortcuts()

    def _init_default_data(self):
        """首次运行时加载默认任务和资源"""
        for t_dict in DEFAULT_TASKS:
            task = Task(
                id=0, num=t_dict["num"], name_en=t_dict["name_en"],
                name_cn=t_dict["name_cn"], section=Section(t_dict["section"]),
                duration=t_dict["duration"], priority=t_dict["priority"],
                is_serial=t_dict.get("is_serial", False),
                serial_group=t_dict.get("serial_group") or "",
                sample_pool=t_dict.get("sample_pool", "product"),
                sample_qty=t_dict.get("sample_qty", 3),
                setup_time=t_dict.get("setup_time", 0),
                teardown_time=t_dict.get("teardown_time", 0),
                dependencies=t_dict.get("dependencies", []),
            )
            self.db.insert_task(task)

        for r_dict in DEFAULT_RESOURCES:
            res = Resource(
                id=0, name=r_dict["name"], type=ResourceType(r_dict["type"]),
                category=r_dict.get("category", ""),
                unit=r_dict.get("unit", "台"),
                available_qty=r_dict.get("available_qty", 1),
                icon=r_dict.get("icon", "📦"),
                description=r_dict.get("description", ""),
            )
            self.db.insert_resource(res)

    def _setup_toolbar(self):
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # ── 启动时恢复主题 ──
        theme = self.db.get_setting("theme", "dark")
        if theme == "light":
            from src.styles.theme import apply_theme
            from PySide6.QtWidgets import QApplication
            apply_theme(QApplication.instance(), dark=False)

        # ── 文件操作组 ──
        self.act_new = QAction("📁 新建项目", self)
        self.act_new.setToolTip("新建项目 (Ctrl+N)")
        self.act_new.setShortcut(QKeySequence("Ctrl+N"))
        self.act_new.triggered.connect(self._on_new_project)
        toolbar.addAction(self.act_new)

        self.act_open = QAction("📂 打开项目", self)
        self.act_open.setToolTip("打开项目 (Ctrl+O)")
        self.act_open.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open.triggered.connect(self._on_open_project)
        toolbar.addAction(self.act_open)

        self.act_save = QAction("💾 保存项目", self)
        self.act_save.setToolTip("保存项目 (Ctrl+S)")
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.triggered.connect(self._on_save_project)
        toolbar.addAction(self.act_save)

        toolbar.addSeparator()
        # ── 撤销/重做组 ──
        self.act_undo = QAction("↩️ 撤销", self)
        self.act_undo.triggered.connect(self._on_undo)
        self.act_undo.setEnabled(False)
        self.act_undo.setToolTip("撤销 (Ctrl+Z)")
        toolbar.addAction(self.act_undo)

        self.act_redo = QAction("↪️ 重做", self)
        self.act_redo.triggered.connect(self._on_redo)
        self.act_redo.setEnabled(False)
        self.act_redo.setToolTip("重做 (Ctrl+Y)")
        toolbar.addAction(self.act_redo)

        toolbar.addSeparator()

        # ── 任务操作组 ──
        self.act_add_task = QAction("➕ 添加任务", self)
        self.act_add_task.setToolTip("添加任务 (Ctrl+T)")
        self.act_add_task.setShortcut(QKeySequence("Ctrl+T"))
        self.act_add_task.triggered.connect(self._on_add_task)
        toolbar.addAction(self.act_add_task)

        self.act_template = QAction("📋 任务模板", self)
        self.act_template.setToolTip("任务模板 (Ctrl+Shift+T)")
        self.act_template.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.act_template.triggered.connect(self._on_template_library)
        toolbar.addAction(self.act_template)

        toolbar.addSeparator()

        # ── 排程组 ──
        self.act_schedule = QAction("⚡ 一键排程", self)
        self.act_schedule.setToolTip("一键排程 (F5)")
        self.act_schedule.setShortcut(QKeySequence("F5"))
        self.act_schedule.triggered.connect(self._on_auto_schedule)
        toolbar.addAction(self.act_schedule)

        toolbar.addSeparator()

        # ── 设置组 ──
        self.act_manage_sections = QAction("🏷️ 分类管理", self)
        self.act_manage_sections.setToolTip("分类管理")
        self.act_manage_sections.triggered.connect(self._on_manage_sections)
        toolbar.addAction(self.act_manage_sections)

        self.act_toggle_theme = QAction("🌗 切换主题", self)
        self.act_toggle_theme.setToolTip("切换亮/暗主题")
        self.act_toggle_theme.triggered.connect(self._on_toggle_theme)
        toolbar.addAction(self.act_toggle_theme)

        self.act_manage_tags = QAction("🫧 标签管理", self)
        self.act_manage_tags.setToolTip("标签定义管理")
        self.act_manage_tags.triggered.connect(self._on_manage_tags)
        toolbar.addAction(self.act_manage_tags)

        self.act_validate = QAction("✅ 数据校验", self)
        self.act_validate.setToolTip("数据校验 — 检测依赖冲突/资源超载/工时异常")
        self.act_validate.triggered.connect(self._on_validate_data)
        toolbar.addAction(self.act_validate)

        toolbar.addSeparator()

        # ── 导出组 ──
        self.act_import_excel = QAction("📥 导入 Excel", self)
        self.act_import_excel.setToolTip("导入 Excel (Ctrl+I)")
        self.act_import_excel.setShortcut(QKeySequence("Ctrl+I"))
        self.act_import_excel.triggered.connect(self._on_import_excel)
        toolbar.addAction(self.act_import_excel)

        self.act_export_excel = QAction("📊 导出 Excel", self)
        self.act_export_excel.setToolTip("导出 Excel (Ctrl+E)")
        self.act_export_excel.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export_excel.triggered.connect(self._on_export_excel)
        toolbar.addAction(self.act_export_excel)

        self.act_export_pdf = QAction("📄 导出 PDF", self)
        self.act_export_pdf.setToolTip("导出 PDF (Ctrl+P)")
        self.act_export_pdf.setShortcut(QKeySequence("Ctrl+P"))
        self.act_export_pdf.triggered.connect(self._on_export_pdf)
        toolbar.addAction(self.act_export_pdf)

        self.act_print = QAction("🖨️ 打印预览", self)
        self.act_print.setToolTip("打印预览 (Ctrl+Shift+P)")
        self.act_print.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_print.triggered.connect(self._on_print_preview)
        toolbar.addAction(self.act_print)

        # 测试记录相关
        self.act_test_result = QAction("📝 测试记录", self)
        self.act_test_result.setToolTip("打开测试记录对话框")
        self.act_test_result.triggered.connect(self._on_test_result)
        toolbar.addAction(self.act_test_result)

        toolbar.addSeparator()

        # ── 数据管理 ──
        self.act_reset = QAction("🔄 重置数据", self)
        self.act_reset.setToolTip("重置所有数据到默认状态")
        self.act_reset.triggered.connect(self._on_reset)
        toolbar.addAction(self.act_reset)

        self.act_snapshots = QAction("💾 快照恢复", self)
        self.act_snapshots.setToolTip("查看并恢复历史快照")
        self.act_snapshots.triggered.connect(self._on_snapshot_restore)
        toolbar.addAction(self.act_snapshots)

    def _setup_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.gantt_view = GanttView(self.db, undo_manager=self.undo_manager)
        self.resource_view = ResourceView(self.db)

        # 连接甘特图选中信号到状态栏
        self.gantt_view.task_selected.connect(self._on_gantt_task_selected)

        self.tabs.addTab(self.gantt_view, "📊 甘特图")
        self.tabs.addTab(self.resource_view, "🔧 资源配置")

        # 拖拽分配资源 Tab
        from src.widgets.resource_drag_view import ResourceDragView
        self.resource_drag = ResourceDragView(self.db)
        self.tabs.addTab(self.resource_drag, "🎯 拖拽分配")

        # 数据看板 Tab
        from src.widgets.dashboard import DashboardWidget
        self.dashboard = DashboardWidget()
        self.tabs.addTab(self.dashboard, "📈 数据看板")

        # Issue 追踪 Tab
        from src.widgets.issue_tracker import IssueTrackerWidget
        self.issue_tracker = IssueTrackerWidget(self.db)
        self.tabs.addTab(self.issue_tracker, "🐛 Issue 追踪")

        # 数据联动：双击跳转甘特图任务
        self.issue_tracker.jump_to_task.connect(self._on_jump_to_task)
        self.dashboard.jump_to_task.connect(self._on_jump_to_task)

        # 切换到甘特图 tab 时刷新
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _setup_shortcuts(self):
        """绑定全局快捷键：Ctrl+Z 撤销，Ctrl+Y 重做。"""
        self._shortcut_undo = QShortcut(
            QKeySequence.StandardKey.Undo, self,
            self._on_undo,
        )
        self._shortcut_redo = QShortcut(
            QKeySequence.StandardKey.Redo, self,
            self._on_redo,
        )

        # Alt+1~5 快速切换 Tab
        for i in range(min(5, self.tabs.count())):
            QShortcut(
                QKeySequence(f"Alt+{i+1}"),
                self,
                lambda idx=i: self.tabs.setCurrentIndex(idx),
            )

    def _on_undo(self):
        desc = self.undo_manager.undo()
        if desc:
            self.statusbar.showMessage(f"撤销: {desc}", 3000)
            self.gantt_view.refresh()
        else:
            self.statusbar.showMessage("没有可撤销的操作", 2000)
        self.act_undo.setEnabled(self.undo_manager.can_undo())
        self.act_redo.setEnabled(self.undo_manager.can_redo())

    def _on_redo(self):
        desc = self.undo_manager.redo()
        if desc:
            self.statusbar.showMessage(f"重做: {desc}", 3000)
            self.gantt_view.refresh()
        else:
            self.statusbar.showMessage("没有可重做的操作", 2000)
        self.act_undo.setEnabled(self.undo_manager.can_undo())
        self.act_redo.setEnabled(self.undo_manager.can_redo())

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        # 左侧永久标签：项目路径
        self._project_path_label = QLabel("📂 未保存")
        self._project_path_label.setStyleSheet("color: #a6adc8; padding: 0 8px;")
        self.statusbar.addPermanentWidget(self._project_path_label)
        # 选中信息标签
        self._selection_label = QLabel("")
        self._selection_label.setStyleSheet("color: #89b4fa; padding: 0 8px;")
        self.statusbar.addWidget(self._selection_label)
        self._update_status()

    def _update_status(self):
        total = self.db.task_count()
        done = self.db.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE done = 1"
        ).fetchone()[0]
        self.statusbar.showMessage(
            f"共 {total} | 完成 {done} | 未完成 {total - done}"
        )

    def _show_selection_info(self, text: str, timeout: int = 0):
        """在状态栏显示当前选中信息"""
        self._selection_label.setText(text)
        if timeout > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(timeout, lambda: self._selection_label.setText(""))

    def _on_gantt_task_selected(self, task_id: int):
        """甘特图选中任务时更新状态栏"""
        task = self.db.get_task(task_id)
        if task:
            self._show_selection_info(f"当前选中: {task.num} {task.name_cn}")
        else:
            self._selection_label.setText("")

    def _on_tab_changed(self, index: int):
        """切换 tab 时刷新对应视图"""
        if index == 0:
            self.gantt_view.refresh()
            self._dashboard_dirty = True
        elif index == 1:
            self.resource_view.refresh()
            self._dashboard_dirty = True
        elif index == 2:
            self.resource_drag.refresh()
            self._dashboard_dirty = True
        elif index == 3:
            if self._dashboard_dirty:
                # 数据看板
                from datetime import date
                tasks = self.db.get_all_tasks()
                sections = self.db.get_all_sections()
                sd_str = self.db.get_setting("start_date", date.today().isoformat())
                start_date = date.fromisoformat(sd_str)
                schedule_result = None
                if hasattr(self.gantt_view, '_last_schedule_result') and self.gantt_view._last_schedule_result:
                    schedule_result = self.gantt_view._last_schedule_result
                self.dashboard.update_data(tasks, sections, schedule_result, start_date)
                self._dashboard_dirty = False
        elif index == 4:
            self.issue_tracker.refresh()
        self._update_status()

    # ── 文件操作 ───────────────────────────────────

    def _on_new_project(self):
        reply = QMessageBox.question(
            self, "新建项目",
            "确定要新建项目吗？当前数据将被清空。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.conn.execute("DELETE FROM tasks")
            self.db.conn.execute("DELETE FROM resources")
            self._current_project_path = ""
            self._init_default_data()
            self.gantt_view.refresh()
            self.resource_view.refresh()
            self._update_status()
            self.statusbar.showMessage("已新建项目（默认数据）", 3000)
            self._dashboard_dirty = True

    def _on_open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "",
            "可测排程项目 (*.kekaoxing *.json);;所有文件 (*)",
        )
        if path:
            try:
                from src.core.project_io import import_project
                reply = QMessageBox.question(
                    self, "导入方式",
                    "是否合并到当前项目？\n\n"
                    "「是」= 保留现有数据并添加\n"
                    "「否」= 清空当前数据后导入",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.No,
                )
                if reply == QMessageBox.Cancel:
                    return
                merge = (reply == QMessageBox.Yes)
                result = import_project(self.db, path, merge=merge)
                self._current_project_path = path
                self._project_path_label.setText(f"📂 {path}")
                self.gantt_view.refresh()
                self.resource_view.refresh()
                self._update_status()
                msg = f"已导入 {result['task_count']} 个任务, {result['resource_count']} 个资源"
                if result["warnings"]:
                    msg += f"\n⚠️ {len(result['warnings'])} 个警告"
                self.statusbar.showMessage(msg, 5000)
                self._dashboard_dirty = True
                if result["warnings"]:
                    QMessageBox.warning(
                        self, "导入警告",
                        "\n".join(result["warnings"][:5])
                    )
            except Exception as e:
                err_msg = _friendly_error_msg(e, "导入项目")
                QMessageBox.critical(self, "导入失败", err_msg)

    def _on_save_project(self):
        if self._current_project_path:
            path = self._current_project_path
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存项目", "可靠性测试排程.kekaoxing",
                "可测排程项目 (*.kekaoxing);;JSON 文件 (*.json)",
            )
        if path:
            if not path.endswith((".kekaoxing", ".json")):
                path += ".kekaoxing"
            try:
                from src.core.project_io import export_project
                export_project(self.db, path)
                self._current_project_path = path
                self._project_path_label.setText(f"📂 {path}")
                self.statusbar.showMessage(f"已保存到 {path}", 5000)
            except Exception as e:
                err_msg = _friendly_error_msg(e, "保存项目")
                QMessageBox.critical(self, "保存失败", err_msg)

    # ── 任务操作 ───────────────────────────────────

    def _on_add_task(self):
        from src.widgets.task_editor import TaskEditor
        result = TaskEditor.add_new(self.db, self)
        if result:
            self.gantt_view.refresh()
            self._update_status()
            self._dashboard_dirty = True

    def _on_template_library(self):
        from src.widgets.template_library import TemplateLibraryDialog
        dlg = TemplateLibraryDialog(self.db, self)
        if dlg.exec() == 1 and dlg.added_count > 0:
            self.gantt_view.refresh()
            self.resource_view.refresh()
            self._update_status()
            self.statusbar.showMessage(f"已从模板库添加 {dlg.added_count} 个任务", 5000)

    # ── 排程 ───────────────────────────────────────

    def _on_auto_schedule(self):
        self.gantt_view.show_scheduler_dialog()
        self._update_status()
        self._dashboard_dirty = True

    # ── 分类管理 ───────────────────────────────────

    def _on_manage_sections(self):
        from src.widgets.section_manager import SectionManagerDialog
        dlg = SectionManagerDialog(self.db, self)
        dlg.exec()
        # 分类修改后刷新甘特图
        self.gantt_view.refresh()

    def _on_toggle_theme(self):
        from src.styles.theme import apply_theme
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        current = app.styleSheet()
        is_dark = "#11111b" in current
        apply_theme(app, dark=not is_dark)
        self.db.set_setting("theme", "dark" if not is_dark else "light")

    def _on_manage_tags(self):
        from src.widgets.task_tags import TagDefinitionDialog
        dlg = TagDefinitionDialog(self.db, self)
        dlg.exec()
        self.gantt_view.refresh()

    def _on_validate_data(self):
        from src.core.data_validator import DataValidator
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLabel
        from PySide6.QtCore import Qt

        tasks = self.db.get_all_tasks()
        resources = self.db.get_all_resources()

        validator = DataValidator(tasks, resources)
        issues = validator.validate_all()

        dlg = QDialog(self)
        dlg.setWindowTitle("数据校验结果")
        dlg.resize(700, 500)
        layout = QVBoxLayout(dlg)

        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        infos = [i for i in issues if i.severity == "info"]

        header = QLabel(
            f"校验完成：{len(errors)} 个错误，{len(warnings)} 个警告，{len(infos)} 条提示"
        )
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(header)

        text = QTextEdit()
        text.setReadOnly(True)
        parts = []
        if errors:
            parts.append("━━ ❌ 错误 ━━")
            for i in errors:
                parts.append(f"  [{i.category}] {i.message}")
        if warnings:
            parts.append("\n━━ ⚠️ 警告 ━━")
            for i in warnings:
                parts.append(f"  [{i.category}] {i.message}")
        if infos:
            parts.append("\n━━ ℹ️ 提示 ━━")
            for i in infos:
                parts.append(f"  [{i.category}] {i.message}")
        if not issues:
            parts.append("✅ 未发现数据问题，一切正常！")
        text.setText("\n".join(parts))
        layout.addWidget(text)
        dlg.exec()

    # ── 导入/导出 ─────────────────────────────────────

    def _on_import_excel(self):
        from src.widgets.excel_import_dialog import ExcelImportDialog
        dlg = ExcelImportDialog(self.db, self)
        if dlg.exec() == 1:
            self.gantt_view.refresh()
            self.resource_view.refresh()
            self._update_status()
            self.statusbar.showMessage(f"成功导入 {dlg.imported_count} 条任务", 5000)
            self._dashboard_dirty = True

    def _on_export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel", "可靠性测试排程.xlsx",
            "Excel Files (*.xlsx)",
        )
        if path:
            try:
                self.gantt_view.export_to_excel(path)
                self.statusbar.showMessage(f"已导出到 {path}", 5000)
            except Exception as e:
                err_msg = _friendly_error_msg(e, "导出 Excel")
                QMessageBox.critical(self, "导出失败", err_msg)

    def _on_export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PDF", "可靠性测试排程.pdf",
            "PDF 文件 (*.pdf)",
        )
        if path:
            try:
                self.statusbar.showMessage("正在生成 PDF...")
                self.statusbar.repaint()
                try:
                    self._export_pdf(path)
                finally:
                    self.statusbar.showMessage("导出完成", 2000)
                self.statusbar.showMessage(f"已导出到 {path}", 5000)
            except Exception as e:
                self.statusbar.clearMessage()
                err_msg = _friendly_error_msg(e, "导出 PDF")
                QMessageBox.critical(self, "导出失败", err_msg)

    def _export_pdf(self, path: str):
        """导出甘特图为 PDF（含标题、任务表、甘特图、资源时间线）"""
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtGui import QPainter

        printer = QPrinter(QPrinter.PrinterResolution.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPrinter.PageSize.A4)
        printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)

        painter = QPainter(printer)
        if not painter.isActive():
            raise RuntimeError("无法初始化打印机")
        self._paint_print_content(painter, printer)
        painter.end()

    def _on_test_result(self):
        """打开测试结果记录对话框（含任务选择器）"""
        tasks = self.db.get_all_tasks()
        if not tasks:
            QMessageBox.information(self, "提示", "暂无测试任务，请先添加任务")
            return
        from src.widgets.test_result_dialog import TestResultDialog
        # 弹出任务选择对话框
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
        sel_dlg = QDialog(self)
        sel_dlg.setWindowTitle("选择测试任务")
        sel_dlg.setMinimumSize(400, 500)
        sel_layout = QVBoxLayout(sel_dlg)
        sel_layout.addWidget(QLabel("请选择要记录测试结果的任务："))
        task_list = QListWidget()
        task_list.setAlternatingRowColors(True)
        for t in tasks:
            status = "✅" if t.done else "⏳"
            task_list.addItem(f"{status} #{t.num} {t.name_cn or t.name_en}")
        sel_layout.addWidget(task_list)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(sel_dlg.accept)
        btn_box.rejected.connect(sel_dlg.reject)
        sel_layout.addWidget(btn_box)
        if sel_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        row = task_list.currentRow()
        if row < 0 or row >= len(tasks):
            return
        selected = tasks[row]
        dlg = TestResultDialog(self.db, selected.id, selected.num, selected.name_cn, self)
        dlg.exec()

    def _on_print_preview(self):
        """打开打印预览对话框"""
        from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter

        self.statusbar.showMessage("正在准备打印预览...")
        self.statusbar.repaint()
        try:
            printer = QPrinter(QPrinter.PrinterResolution.HighResolution)
            printer.setPageSize(QPrinter.PageSize.A4)
            printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)

            dialog = QPrintPreviewDialog(printer, self)
            dialog.setWindowTitle("打印预览 - 可靠性测试排程")

            def paint_preview(printer):
                from PySide6.QtGui import QPainter
                painter = QPainter(printer)
                self._paint_print_content(painter, printer)
                painter.end()

            dialog.paintRequested.connect(paint_preview)
            dialog.exec()
        finally:
            self.statusbar.showMessage("打印预览已关闭", 2000)

    def _paint_print_content(self, painter, printer):
        """绘制打印内容（打印预览和 PDF 导出共用），支持多页"""
        from PySide6.QtGui import QPainter, QFont, QColor, QPixmap
        from PySide6.QtCore import QSize, Qt
        from datetime import date

        if not painter.isActive():
            raise RuntimeError("无法初始化打印机")

        page_rect = printer.pageRect(QPrinter.Unit.Point)
        page_w = page_rect.width()
        page_h = page_rect.height()
        dpi_scale = printer.resolution() / 96.0

        # ── 准备甘特图 pixmap ──
        canvas = self.gantt_view.gantt_canvas
        day_w = canvas.day_width
        total_w_px = max(canvas.width(), LEFT_MARGIN + canvas.total_days * day_w + 50)
        total_h_px = canvas.height()

        gantt_pixmap = QPixmap(QSize(int(total_w_px), int(total_h_px)))
        gantt_pixmap.fill(QColor("#ffffff"))
        old_size = canvas.size()
        canvas.resize(int(total_w_px), int(total_h_px))
        canvas.render(gantt_pixmap)
        canvas.resize(old_size)

        # ── 准备资源时间线 pixmap ──
        timeline = self.gantt_view.timeline_widget
        tl_pixmap = None
        tl_w_px = 0
        tl_h_px = 0
        if timeline and timeline.isVisible():
            tl_w_px = max(timeline.width(), timeline.minimumWidth())
            tl_h_px = timeline.height()
            tl_pixmap = QPixmap(QSize(tl_w_px, tl_h_px))
            tl_pixmap.fill(QColor("#ffffff"))
            old_tl_size = timeline.size()
            timeline.resize(tl_w_px, tl_h_px)
            timeline.render(tl_pixmap)
            timeline.resize(old_tl_size)

        # ── 统计信息 ──
        tasks = self.db.get_all_tasks()
        total = len(tasks)
        done = sum(1 for t in tasks if getattr(t, "progress", 0) >= 100)
        info_text = f"导出日期: {date.today().strftime('%Y-%m-%d')}  |  总任务: {total}  |  已完成: {done}"
        if tasks:
            max_end = max((t.start_day + t.duration for t in tasks), default=0)
            info_text += f"  |  预计总工期: {max_end} 天"

        # ── 计算需要的页面空间，决定单页/多页 ──
        # 头部区域高度: 标题25 + 副标题20 + 分隔线10 = 55pt
        header_height = 55

        # 甘特图占用的可用高度 = 页面高度 - 头部 - 底部留白
        gantt_avail_h = page_h - header_height - 30
        scale_x = page_w / total_w_px
        scale_y = gantt_avail_h / total_h_px
        gantt_scale = min(scale_x, scale_y, 1.0)

        gantt_draw_h = total_h_px * gantt_scale

        # 计算资源时间线需要的空间（如果有的话）
        tl_draw_h = 0
        tl_total_needed = 0
        if tl_pixmap:
            tl_label_h = 15  # "设备占用时间线" 标签高度
            tl_scale = min(page_w / tl_w_px, 1.0)
            tl_draw_h = tl_h_px * tl_scale
            tl_total_needed = tl_label_h + tl_draw_h

        # 如果甘特图+时间线的缩放比例 < 0.4，则分页
        use_multipage = (gantt_scale < 0.4) or (gantt_draw_h + tl_total_needed > gantt_avail_h and gantt_scale < 0.4)

        if use_multipage:
            # ── 多页模式 ──
            # 第一页：标题 + 统计信息
            self._draw_header(painter, page_w, 0, info_text)

            # 统计摘要
            painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#1e1e2e"))
            painter.drawText(QRectF(0, 80, page_w, 25), Qt.AlignmentFlag.AlignLeft, "测试项目概览")
            y = 115

            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.setPen(QColor("#313244"))
            for task in tasks:
                task_status = "✅" if getattr(task, "progress", 0) >= 100 else "⏳"
                line = f"{task_status} #{task.num} {task.name_cn or task.name_en}  工期:{task.duration}天  开始:第{task.start_day}天"
                if task.duration > 0:
                    line += f"  结束:第{task.start_day + task.duration}天"
                painter.drawText(QRectF(0, y, page_w, 18), Qt.AlignmentFlag.AlignLeft, line)
                y += 18
                if y > page_h - 30:
                    break

            # 第二页：甘特图
            printer.newPage()
            painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#1e1e2e"))
            painter.drawText(QRectF(0, 0, page_w, 20), Qt.AlignmentFlag.AlignLeft, "甘特图")
            content_y = 25

            # 甘特图单独占一页，尽量利用全页
            gantt_page_h = page_h - content_y - 20
            g_scale_x = page_w / total_w_px
            g_scale_y = gantt_page_h / total_h_px
            g_scale = min(g_scale_x, g_scale_y, 1.0)
            g_draw_w = total_w_px * g_scale
            g_draw_h = total_h_px * g_scale
            g_offset_x = (page_w - g_draw_w) / 2
            painter.drawPixmap(QRectF(g_offset_x, content_y, g_draw_w, g_draw_h),
                             gantt_pixmap, QRectF(0, 0, total_w_px, total_h_px))

            # 第三页：资源时间线
            if tl_pixmap:
                printer.newPage()
                painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
                painter.setPen(QColor("#1e1e2e"))
                painter.drawText(QRectF(0, 0, page_w, 20), Qt.AlignmentFlag.AlignLeft, "设备占用时间线")
                content_y = 25

                tl_page_h = page_h - content_y - 20
                tl_scale2 = min(page_w / tl_w_px, tl_page_h / tl_h_px, 1.0)
                tl_dw = tl_w_px * tl_scale2
                tl_dh = tl_h_px * tl_scale2
                tl_ox = (page_w - tl_dw) / 2
                painter.drawPixmap(QRectF(tl_ox, content_y, tl_dw, tl_dh),
                                 tl_pixmap, QRectF(0, 0, tl_w_px, tl_h_px))
        else:
            # ── 单页模式 ──
            content_y = self._draw_header(painter, page_w, 0, info_text)

            # 绘制甘特图
            gantt_draw_w = total_w_px * gantt_scale
            gantt_draw_h = total_h_px * gantt_scale
            gantt_offset_x = (page_w - gantt_draw_w) / 2
            painter.drawPixmap(QRectF(gantt_offset_x, content_y, gantt_draw_w, gantt_draw_h),
                             gantt_pixmap, QRectF(0, 0, total_w_px, total_h_px))
            content_y += gantt_draw_h + 15

            # 绘制资源时间线
            if tl_pixmap:
                painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#1e1e2e"))
                painter.drawText(QRectF(0, content_y, page_w, 15), Qt.AlignmentFlag.AlignLeft, "设备占用时间线")
                content_y += 15

                tl_scale = min(page_w / tl_w_px, (page_h - content_y - 10) / tl_h_px, 1.0)
                tl_draw_w = tl_w_px * tl_scale
                tl_draw_h = tl_h_px * tl_scale
                tl_offset_x = (page_w - tl_draw_w) / 2
                painter.drawPixmap(QRectF(tl_offset_x, content_y, tl_draw_w, tl_draw_h),
                                 tl_pixmap, QRectF(0, 0, tl_w_px, tl_h_px))

    def _draw_header(self, painter, page_w, y_start, info_text):
        """绘制打印页头部（标题 + 副标题 + 分隔线），返回 y 终点"""
        from PySide6.QtGui import QFont, QColor, QPen
        from PySide6.QtCore import Qt, QPointF, QRectF

        # 标题
        title_font = QFont("Microsoft YaHei", 14, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#1e1e2e"))
        painter.drawText(QRectF(0, y_start, page_w, 30), Qt.AlignmentFlag.AlignLeft, "可靠性测试排程甘特图")
        content_y = y_start + 25

        # 副标题
        info_font = QFont("Microsoft YaHei", 9)
        painter.setFont(info_font)
        painter.setPen(QColor("#6c7086"))
        painter.drawText(QRectF(0, content_y, page_w, 20), Qt.AlignmentFlag.AlignLeft, info_text)
        content_y += 20

        # 分隔线
        painter.setPen(QPen(QColor("#cdd6f4"), 0.5))
        painter.drawLine(QPointF(0, content_y), QPointF(page_w, content_y))
        content_y += 10

        return content_y

    # ── 数据管理 ───────────────────────────────────

    def _on_reset(self):
        reply = QMessageBox.question(
            self, "重置数据",
            "确定要重置所有数据吗？这将删除所有任务和资源配置，恢复为默认数据。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.db.conn.execute("DELETE FROM issue_history")
                self.db.conn.execute("DELETE FROM test_issues")
                self.db.conn.execute("DELETE FROM test_results")
                self.db.conn.execute("DELETE FROM tasks")
                self.db.conn.execute("DELETE FROM resources")
                self.db.conn.execute("DELETE FROM sections")
                self._current_project_path = ""
                self._init_default_data()
                self.gantt_view.refresh()
                self.resource_view.refresh()
                self._update_status()
                self.statusbar.showMessage("数据已重置", 3000)
                self._dashboard_dirty = True
            except Exception as e:
                err_msg = _friendly_error_msg(e, "重置数据")
                QMessageBox.critical(self, "重置失败", err_msg)

    def _on_snapshot_restore(self):
        """快照恢复：列出可用快照，选择后恢复"""
        from src.core.auto_save import AutoSaveManager
        auto_save = AutoSaveManager(self.db.db_path)
        snapshots = auto_save.list_snapshots()
        if not snapshots:
            QMessageBox.information(self, "快照恢复", "没有可用的快照")
            return

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("💾 快照恢复")
        dlg.setMinimumSize(500, 400)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("选择要恢复的快照（最近修改的在上）："))

        snap_list = QListWidget()
        snap_list.setAlternatingRowColors(True)
        for s in snapshots:
            label = s.get("label", "")
            size_kb = s.get("size_mb", 0) * 1024
            snap_list.addItem(f"{label}  ({size_kb:.0f}KB)")
        layout.addWidget(snap_list)

        warn = QLabel("⚠️ 恢复快照将覆盖当前数据库，此操作不可撤销！")
        warn.setStyleSheet("color: #f38ba8; font-weight: bold;")
        layout.addWidget(warn)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            row = snap_list.currentRow()
            if row < 0:
                return
            reply = QMessageBox.warning(
                self, "确认恢复",
                "确定要从选中的快照恢复吗？当前所有数据将被覆盖！\n\n此操作不可撤销！",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                try:
                    auto_save.restore_snapshot(snapshots[row]["path"])
                    QMessageBox.information(self, "恢复成功", "快照已恢复，请关闭并重新打开应用")
                except Exception as e:
                    err_msg = _friendly_error_msg(e, "恢复快照")
                    QMessageBox.critical(self, "恢复失败", err_msg)

    def _on_jump_to_task(self, task_id: int):
        """从 Issue/看板双击跳转到甘特图对应任务"""
        self.tabs.setCurrentIndex(0)
        self.gantt_view.select_task_by_id(task_id)

    def closeEvent(self, event):
        """关闭窗口时提示保存"""
        reply = QMessageBox.question(
            self, "退出确认",
            "确定要退出吗？未保存的数据将会丢失。\n\n"
            "（自动保存已在后台运行，通常不会丢失数据）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def _friendly_error_msg(exc: Exception, context: str) -> str:
    """将 Python 异常转为用户友好的中文提示。"""
    import errno
    if isinstance(exc, FileNotFoundError):
        return f"文件不存在: {getattr(exc, 'filename', str(exc))}"
    if isinstance(exc, PermissionError):
        return "权限不足，无法访问文件或目录"
    if isinstance(exc, KeyError):
        return f"数据中缺少必需字段: {exc}"
    if isinstance(exc, ValueError):
        msg = str(exc).strip()
        return msg if msg else "数据格式不正确"
    if isinstance(exc, RuntimeError):
        return str(exc)
    msg = str(exc).strip()
    return msg if msg else f"{context}时发生未知错误"
