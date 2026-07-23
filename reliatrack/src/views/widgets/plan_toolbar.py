"""测试计划工具栏组件 — 计划管理/任务管理/操作分组。

提取自 test_plan_view.py row1，封装为独立 CommandBar 组件。
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from src.styles.icon import set_icon, RI_CHECK, RI_MORE
from src.views.widgets.command_bar import CommandBar


class PlanToolbar(QWidget):
    """测试计划顶栏：计划管理/任务管理/操作分组按钮 + 菜单。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cmd_bar = self._build()

    def command_bar(self) -> CommandBar:
        return self._cmd_bar

    def _build(self) -> CommandBar:
        cmd_bar = CommandBar()
        cmd_bar.setButtonTight(True)

        # ── 分组 1: 计划管理 ──
        self._plan_menu = QMenu(self)
        self._act_add_plan = self._plan_menu.addAction("新建计划")
        self._act_edit_plan = self._plan_menu.addAction("编辑计划")
        self._plan_menu.addSeparator()
        self._act_unarchive_plan = self._plan_menu.addAction("取消归档")
        self._act_unarchive_plan.setVisible(False)
        self._act_archive_plan = self._plan_menu.addAction("归档")
        self._plan_menu.addSeparator()
        self._act_toggle_archived = self._plan_menu.addAction("查看归档")
        self._act_toggle_archived.setCheckable(True)

        self._btn_plan_manage = QToolButton(self)
        self._btn_plan_manage.setText("计划管理")
        self._btn_plan_manage.setMenu(self._plan_menu)
        self._btn_plan_manage.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_plan_manage.setProperty("class", "action")
        self._btn_plan_manage.setFixedHeight(26)
        self._btn_plan_manage.setToolTip("计划管理：新建、编辑、归档、查看归档")
        cmd_bar.addWidget(self._btn_plan_manage)

        cmd_bar.addSeparator()

        # ── 分组 2: 任务管理 ──
        self._task_menu = QMenu(self)
        self._act_add_task = self._task_menu.addAction("添加任务")
        self._act_edit_task = self._task_menu.addAction("编辑任务")
        self._act_delete_task = self._task_menu.addAction("删除任务")
        self._task_menu.addSeparator()
        self._act_import_tasks = self._task_menu.addAction("导入任务")
        self._act_import_from_plan = self._task_menu.addAction("从计划导入")

        self._btn_task_manage = QToolButton(self)
        self._btn_task_manage.setText("任务管理")
        self._btn_task_manage.setMenu(self._task_menu)
        self._btn_task_manage.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_task_manage.setProperty("class", "action")
        self._btn_task_manage.setFixedHeight(26)
        self._btn_task_manage.setToolTip("任务管理：增删改、导入")
        cmd_bar.addWidget(self._btn_task_manage)

        cmd_bar.addSeparator()

        # ── 分组 3: 操作 ──
        self._btn_record_result = QPushButton("录入结果")
        self._btn_record_result.setProperty("class", "primary")
        self._btn_record_result.setFixedHeight(26)
        self._btn_record_result.setToolTip("录入测试结果")
        set_icon(self._btn_record_result, RI_CHECK)
        cmd_bar.addWidget(self._btn_record_result)

        # 更多操作下拉
        self._more_menu = QMenu(self)
        self._act_schedule = self._more_menu.addAction("自动排程")
        self._act_quick_add = self._more_menu.addAction("快速加任务")
        self._more_menu.addSeparator()
        self._act_summary_report = self._more_menu.addAction("总结报告")
        self._btn_more = QToolButton(self)
        self._btn_more.setText("更多")
        self._btn_more.setMenu(self._more_menu)
        self._btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_more.setProperty("class", "action")
        self._btn_more.setFixedHeight(26)
        self._btn_more.setToolTip("自动排程、快速加任务、总结报告等")
        set_icon(self._btn_more, RI_MORE)
        cmd_bar.addWidget(self._btn_more)

        return cmd_bar
