"""表格多选与底部平滑批量操作浮动工具条 (Batch Action Floating Bar)。"""
from __future__ import annotations

from typing import Callable, Any
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QRect, QPoint
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMenu,
    QWidget,
    QGraphicsDropShadowEffect,
)

import src.styles.theme as _theme
from src.styles.constants import add_shadow, DASH_PRIMARY, DASH_SUCCESS, DASH_WARNING, DASH_DANGER


class BatchActionBar(QFrame):
    """底部平滑浮动批量操作工具条。"""

    status_selected = Signal(str)      # 选中的目标状态 ("completed", "in_progress", etc.)
    tech_selected = Signal(int)        # 选中的目标技术员 ID
    export_clicked = Signal()          # 批量导出请求
    clear_clicked = Signal()           # 取消多选请求

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._selected_count = 0
        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        self.setObjectName("batch-action-bar")
        self.setFixedHeight(50)
        self.setStyleSheet(
            f"QFrame#batch-action-bar {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 25px;"
            f"}}"
        )
        add_shadow(self)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 6, 18, 6)
        lay.setSpacing(12)

        # 选中计数 badge
        self._count_label = QLabel("已选中 0 项")
        self._count_label.setStyleSheet(
            f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;"
        )
        lay.addWidget(self._count_label)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet(f"background: {_theme.SURFACE1}; max-width: 1px;")
        lay.addWidget(line)

        # 批量变更状态按钮
        self._btn_status = QPushButton("🏷️ 批量变更状态 ▾", self)
        self._btn_status.setStyleSheet(
            f"QPushButton {{ background: {_theme.SURFACE0}; color: {_theme.TEXT}; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {_theme.SURFACE1}; }}"
        )
        self._status_menu = QMenu(self)
        self._btn_status.setMenu(self._status_menu)
        lay.addWidget(self._btn_status)

        # 批量指派技术员按钮
        self._btn_tech = QPushButton("👨‍🔬 批量指派技术员 ▾", self)
        self._btn_tech.setStyleSheet(
            f"QPushButton {{ background: {_theme.SURFACE0}; color: {_theme.TEXT}; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {_theme.SURFACE1}; }}"
        )
        self._tech_menu = QMenu(self)
        self._btn_tech.setMenu(self._tech_menu)
        lay.addWidget(self._btn_tech)

        # 批量导出按钮
        btn_export = QPushButton("📥 批量导出", self)
        btn_export.setStyleSheet(
            f"QPushButton {{ background: {_theme.SURFACE0}; color: {_theme.TEXT}; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {_theme.SURFACE1}; }}"
        )
        btn_export.clicked.connect(self.export_clicked.emit)
        lay.addWidget(btn_export)

        # 清除/取消多选按钮
        btn_clear = QPushButton("✖ 取消选择", self)
        btn_clear.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_theme.SUBTEXT0}; border-radius: 6px; padding: 4px 8px; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {_theme.DANGER}; }}"
        )
        btn_clear.clicked.connect(self.clear_clicked.emit)
        lay.addWidget(btn_clear)

    def set_status_options(self, options: list[tuple[str, str]]) -> None:
        """设置可用的批量变更状态菜单。

        Args:
            options: [(display_label, status_code), ...]
        """
        self._status_menu.clear()
        for label, code in options:
            act = self._status_menu.addAction(label)
            act.triggered.connect(lambda _, c=code: self.status_selected.emit(c))

    def set_technician_options(self, technicians: list[tuple[str, int]]) -> None:
        """设置可用的批量指派技术员菜单。

        Args:
            technicians: [(tech_name, tech_id), ...]
        """
        self._tech_menu.clear()
        for name, tid in technicians:
            act = self._tech_menu.addAction(name)
            act.triggered.connect(lambda _, t=tid: self.tech_selected.emit(t))

    def update_selection_count(self, count: int) -> None:
        """更新选中行数并自动平滑控制工具条浮现与隐藏。"""
        self._selected_count = count
        self._count_label.setText(f"已选中 {count} 项")

        if count > 0 and self.isHidden():
            self.show()
            self._animate_slide(show=True)
        elif count == 0 and not self.isHidden():
            self._animate_slide(show=False)

    def _animate_slide(self, show: bool) -> None:
        """底部平滑滑动浮沉动效。"""
        if not self.parent():
            return
        pw, ph = self.parent().width(), self.parent().height()
        w, h = 560, self.height()
        target_x = (pw - w) // 2

        start_y = ph if show else ph - h - 20
        end_y = ph - h - 20 if show else ph

        self.setGeometry(target_x, start_y, w, h)
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(180)
        anim.setStartValue(QRect(target_x, start_y, w, h))
        anim.setEndValue(QRect(target_x, end_y, w, h))
        if not show:
            anim.finished.connect(self.hide)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def update_position() -> None:
        """跟随父窗口 resize 重新居中定位。"""
        if self.parent() and not self.isHidden():
            pw, ph = self.parent().width(), self.parent().height()
            w, h = 560, self.height()
            self.move((pw - w) // 2, ph - h - 20)
