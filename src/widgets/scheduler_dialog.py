"""自动排程对话框"""

from __future__ import annotations
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QDateEdit,
    QGroupBox, QTextEdit, QMessageBox, QScrollArea, QWidget,
    QProgressDialog,
)
from PySide6.QtCore import Qt, QDate

from src.db.database import Database
from src.models import Task, ScheduleConfig, ScheduleMode
from src.core.scheduler import run_auto_schedule


class SchedulerDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("⚡ 一键自动排程")
        self.setMinimumSize(600, 500)
        self.scheduled_tasks: list[Task] = []
        self.report: dict = {}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── 配置区 ──
        config_group = QGroupBox("排程配置")
        config_layout = QFormLayout()

        self.mode_combo = QComboBox()
        modes = [
            ("均衡模式（推荐）", ScheduleMode.BALANCED),
            ("最快完成", ScheduleMode.FASTEST),
            ("最少样品", ScheduleMode.MINIMAL),
        ]
        for label, mode in modes:
            self.mode_combo.addItem(label, mode.value)
        config_layout.addRow("排程模式:", self.mode_combo)

        self.skip_weekends_cb = QCheckBox("跳过周末")
        # 从数据库恢复上次设置
        if self.db.get_setting("skip_weekends") == "true":
            self.skip_weekends_cb.setChecked(True)
        config_layout.addRow(self.skip_weekends_cb)

        self.lock_existing_cb = QCheckBox("锁定已有排程")
        self.lock_existing_cb.setChecked(True)
        config_layout.addRow(self.lock_existing_cb)

        # 从数据库恢复上次起始日期
        saved_date = self.db.get_setting("start_date")
        if saved_date:
            try:
                start_qdate = QDate.fromString(saved_date, "yyyy-MM-dd")
            except Exception:
                start_qdate = QDate.currentDate()
        else:
            start_qdate = QDate.currentDate()
        self.start_date_edit = QDateEdit(start_qdate if start_qdate.isValid() else QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        config_layout.addRow("起始日期:", self.start_date_edit)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # ── 按钮 ──
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("⚡ 开始排程")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.clicked.connect(self._run_schedule)
        btn_layout.addWidget(self.btn_run)

        self.btn_apply = QPushButton("✅ 应用结果")
        self.btn_apply.clicked.connect(self._apply_results)
        self.btn_apply.setEnabled(False)
        btn_layout.addWidget(self.btn_apply)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        # ── 报告区 ──
        report_group = QGroupBox("排程报告")
        report_layout = QVBoxLayout()
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        report_layout.addWidget(self.report_text)
        report_group.setLayout(report_layout)
        layout.addWidget(report_group)

    def _run_schedule(self):
        """执行自动排程"""
        tasks = self.db.get_all_tasks()
        if not tasks:
            QMessageBox.warning(self, "提示", "没有可排程的任务")
            return

        resources = self.db.get_all_resources()

        config = ScheduleConfig(
            mode=ScheduleMode(self.mode_combo.currentData()),
            skip_weekends=self.skip_weekends_cb.isChecked(),
            start_date=self.start_date_edit.date().toString("yyyy-MM-dd"),
            lock_existing=self.lock_existing_cb.isChecked(),
        )

        # 持久化排程设置到数据库
        self.db.set_setting("skip_weekends", "true" if config.skip_weekends else "false")
        self.db.set_setting("start_date", config.start_date)

        # 显示进度对话框（indeterminate mode）
        progress = QProgressDialog("正在排程...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

            result = run_auto_schedule(tasks, resources, config)

            self.scheduled_tasks = result["scheduled_tasks"]
            self.report = result.get("report", {})

            # 显示报告
            report_lines = []
            r = self.report
            report_lines.append(f"📅 总工期: {r.get('total_days', 0)} 天")
            if r.get("original_days"):
                improvement = r.get("improvement", 0)
                arrow = "⬇️" if improvement > 0 else "➡️"
                report_lines.append(f"📊 原工期: {r['original_days']} 天  {arrow} 优化 {improvement}%")

            # 设备利用率
            bottleneck_names = {b["name"] for b in r.get("bottlenecks", [])}
            for util in r.get("device_utilization", []):
                pct = util["utilization"]
                bar_len = min(int(pct / 5), 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                bottleneck = " ⚠️ 瓶颈" if util["name"] in bottleneck_names else ""
                report_lines.append(
                    f"\n🔧 {util['name']}  [{bar}] {pct}%{bottleneck}"
                )
                # 利用率等级提示
                if pct <= 50:
                    status = "🟢 正常"
                elif pct <= 80:
                    status = "🟡 较忙"
                elif pct <= 100:
                    status = "🟠 繁忙"
                else:
                    status = "🔴 超载"
                report_lines.append(f"   {status}")

            # 警告和建议
            if r.get("bottlenecks"):
                report_lines.append("\n⚠️ 瓶颈设备:")
                for b in r["bottlenecks"]:
                    report_lines.append(f"  • {b['name']} — 利用率 {b['utilization']}%，建议增加设备")

            if r.get("suggestions"):
                report_lines.append("\n💡 建议:")
                for s in r["suggestions"]:
                    report_lines.append(f"  • {s}")

            self.report_text.setPlainText("\n".join(report_lines))
            self.btn_apply.setEnabled(True)
        finally:
            progress.close()

    def _apply_results(self):
        """将排程结果写入数据库"""
        updates = [
            {"id": t.id, "start_day": t.start_day, "duration": t.duration}
            for t in self.scheduled_tasks
        ]
        self.db.batch_update_schedule(updates)
        QMessageBox.information(self, "成功", f"已更新 {len(updates)} 个任务的排程")
        self.btn_apply.setEnabled(False)

        # 通知主窗口刷新
        parent = self.parent()
        while parent:
            if hasattr(parent, 'gantt_view'):
                parent.gantt_view.refresh()
                break
            parent = parent.parent()
