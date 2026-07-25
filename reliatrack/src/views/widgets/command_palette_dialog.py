"""全局 Ctrl+K 命令面板 — Spotlight 样式毛玻璃快捷搜索与指令触发器。"""
from __future__ import annotations

from typing import Callable, Any
from PySide6.QtCore import Qt, Signal, QEvent, QRectF
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QWidget,
    QFrame,
    QGraphicsDropShadowEffect,
    QSizePolicy,
)

import src.styles.theme as _theme
from src.styles.constants import (
    FONT_FAMILY,
    DASH_PRIMARY,
    DASH_SUCCESS,
    DASH_WARNING,
    DASH_DANGER,
    add_shadow,
)


class CommandItem:
    """命令面板条目数据封装。"""

    def __init__(
        self,
        category: str,
        title: str,
        subtitle: str = "",
        badge: str = "",
        action: Callable[[], Any] | None = None,
        data: Any = None,
    ):
        self.category = category
        self.title = title
        self.subtitle = subtitle
        self.badge = badge
        self.action = action
        self.data = data


class _CommandItemWidget(QFrame):
    """自定义条目渲染控件。"""

    def __init__(self, item: CommandItem, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("command-palette-item")
        self.setProperty("class", "card-bg")
        self.setFixedHeight(44)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        # 类别 Icon / Badge
        self._badge_label = QLabel(item.badge or item.category[:2])
        self._badge_label.setStyleSheet(
            f"background: transparent; color: {DASH_PRIMARY}; "
            f"border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;"
        )
        lay.addWidget(self._badge_label)


        # 标题与副标题
        vbox = QVBoxLayout()
        vbox.setSpacing(0)
        self._title_lbl = QLabel(item.title)
        self._title_lbl.setStyleSheet(f"color: {_theme.TEXT}; font-size: 13px; font-weight: 500;")
        vbox.addWidget(self._title_lbl)

        if item.subtitle:
            self._sub_lbl = QLabel(item.subtitle)
            self._sub_lbl.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
            vbox.addWidget(self._sub_lbl)
        lay.addLayout(vbox, 1)

        # 快捷提示
        self._cat_lbl = QLabel(item.category)
        self._cat_lbl.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
        lay.addWidget(self._cat_lbl)


class CommandPaletteDialog(QDialog):
    """Spotlight 风格居中 Command Palette 弹窗。"""

    action_triggered = Signal(object)  # (CommandItem)

    def __init__(self, parent: QWidget | None = None, controller: Any = None):
        super().__init__(parent)
        self._ctrl = controller
        self._items: list[CommandItem] = []
        self._filtered_items: list[CommandItem] = []
        self._setup_ui()
        self._build_default_items()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(620, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # 毛玻璃容器卡片
        self._container = QFrame()
        self._container.setObjectName("command-palette-container")
        self._container.setStyleSheet(
            f"QFrame#command-palette-container {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 12px;"
            f"}}"
        )
        add_shadow(self._container)

        clay = QVBoxLayout(self._container)
        clay.setContentsMargins(12, 12, 12, 12)
        clay.setSpacing(10)

        # 搜索输入框
        search_box = QHBoxLayout()
        search_box.setSpacing(8)

        self._search_icon = QLabel("🔍")
        self._search_icon.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        search_box.addWidget(self._search_icon)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索功能、指令、项目、样品或 Issue (Ctrl+K)...")
        self._search_input.setStyleSheet(
            f"QLineEdit {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  color: {_theme.TEXT};"
            f"  font-size: 15px;"
            f"  font-weight: 500;"
            f"}}"
        )
        self._search_input.textChanged.connect(self._on_search_text_changed)
        search_box.addWidget(self._search_input, 1)

        esc_hint = QLabel("ESC 关闭")
        esc_hint.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px; background: {_theme.SURFACE0}; padding: 2px 6px; border-radius: 4px;")
        search_box.addWidget(esc_hint)

        clay.addLayout(search_box)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {_theme.SURFACE0}; max-height: 1px; border: none;")
        clay.addWidget(line)

        # 结果列表
        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(
            f"QListWidget {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  border-radius: 6px;"
            f"  padding: 2px;"
            f"  margin-bottom: 2px;"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {_theme.SURFACE0};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background: {_theme.SURFACE0};"
            f"}}"
        )
        self._list_widget.itemActivated.connect(self._on_item_activated)
        self._list_widget.itemClicked.connect(self._on_item_activated)
        clay.addWidget(self._list_widget, 1)

        # 底部帮助栏
        hint_bar = QHBoxLayout()
        hint_bar.setSpacing(12)
        h1 = QLabel("↑↓ 导航")
        h2 = QLabel("↵ 执行 / 跳转")
        for h in (h1, h2):
            h.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
            hint_bar.addWidget(h)
        hint_bar.addStretch()
        clay.addLayout(hint_bar)

        root.addWidget(self._container)

    def _build_default_items(self) -> None:
        """构建内置系统快捷操作。"""
        self._items = [
            CommandItem("快捷指令", "新建测试计划", "进入测试计划模块创建新计划", "⚡", action=lambda: ("tab", 3)),
            CommandItem("快捷指令", "新建 8D 质量分析报告", "预览与导出可视化 8D 报告", "📄", action=lambda: ("action", "8d_report")),
            CommandItem("快捷指令", "新建 Issue 缺陷单", "登记新的可靠性故障与隐患", "🐞", action=lambda: ("tab", 4)),
            CommandItem("快捷指令", "数据库安全备份与恢复", "立即执行 WAL checkpoint 与数据库打包", "💾", action=lambda: ("action", "backup")),
            CommandItem("快捷指令", "切换深色 / 浅色主题", "切换系统全局视觉配色主题", "🌓", action=lambda: ("action", "theme")),
            CommandItem("页面跳转", "跳转到 仪表盘 (Dashboard)", "查看总体健康度与质量概览", "📊", action=lambda: ("tab", 0)),
            CommandItem("页面跳转", "跳转到 项目管理 (Projects)", "查看与编辑可靠性项目列表", "📁", action=lambda: ("tab", 1)),
            CommandItem("页面跳转", "跳转到 样品台账 (Samples)", "查询样品 S/N、批次与流转状态", "📦", action=lambda: ("tab", 2)),
            CommandItem("页面跳转", "跳转到 测试计划与甘特图 (Test Plans)", "查看测试任务排程、关键路径与冲突", "🗓️", action=lambda: ("tab", 3)),
            CommandItem("页面跳转", "跳转到 Issue 与 Bug Tracker", "追踪缺陷闭环、CAPA 与超期预警", "🐛", action=lambda: ("tab", 4)),
            CommandItem("页面跳转", "跳转到 试验设备管理 (Equipment)", "管理试验箱、温湿度箱及状态", "🔬", action=lambda: ("tab", 5)),
            CommandItem("页面跳转", "跳转到 技术员与实验室 (Technicians)", "管理测试人员与排班角色", "👨‍🔬", action=lambda: ("tab", 6)),
            CommandItem("页面跳转", "跳转到 知识库与规范 (Knowledge)", "检索试验标准与故障模式库", "📚", action=lambda: ("tab", 7)),
            CommandItem("页面跳转", "跳转到 个人待办清单 (Todos)", "查看与处理个人任务安排", "✅", action=lambda: ("tab", 8)),
        ]

        # 动态从 Controller 填充项目与样品
        if self._ctrl:
            try:
                if self._ctrl.project_service:
                    for p in self._ctrl.project_service.list_all():
                        self._items.append(
                            CommandItem("项目", f"项目: {p.name}", f"客户: {p.customer or '未指定'} | 产品: {p.product or ''}", "📁", action=lambda pid=p.id: ("project", pid))
                        )
                if self._ctrl.sample_service:
                    for s in self._ctrl.sample_service.list_all()[:20]:  # 限制 20 项
                        self._items.append(
                            CommandItem("样品", f"样品 S/N: {s.sn}", f"型号: {s.model or ''} | 状态: {s.status}", "📦", action=lambda sn=s.sn: ("sample", sn))
                        )
                if self._ctrl.issue_service:
                    for iss in self._ctrl.issue_service.list_all()[:20]:
                        self._items.append(
                            CommandItem("Issue", f"Issue #{iss.id}: {iss.title}", f"严重度: {iss.severity} | 状态: {iss.status}", "⚠️", action=lambda iid=iss.id: ("issue", iid))
                        )
            except Exception:
                pass

        self._render_items(self._items)

    def _render_items(self, items: list[CommandItem]) -> None:
        self._list_widget.clear()
        self._filtered_items = items
        for item in items:
            lwi = QListWidgetItem(self._list_widget)
            lwi.setSizeHint(_CommandItemWidget(item).sizeHint())
            w = _CommandItemWidget(item)
            self._list_widget.addItem(lwi)
            self._list_widget.setItemWidget(lwi, w)

        if items:
            self._list_widget.setCurrentRow(0)

    def _on_search_text_changed(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self._render_items(self._items)
            return

        matched = [
            it for it in self._items
            if query in it.title.lower() or query in it.subtitle.lower() or query in it.category.lower()
        ]
        self._render_items(matched)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        elif event.key() == Qt.Key.Key_Down:
            curr = self._list_widget.currentRow()
            if curr < self._list_widget.count() - 1:
                self._list_widget.setCurrentRow(curr + 1)
            return
        elif event.key() == Qt.Key.Key_Up:
            curr = self._list_widget.currentRow()
            if curr > 0:
                self._list_widget.setCurrentRow(curr - 1)
            return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            curr = self._list_widget.currentRow()
            if 0 <= curr < len(self._filtered_items):
                self._execute_item(self._filtered_items[curr])
            return
        super().keyPressEvent(event)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        row = self._list_widget.row(item)
        if 0 <= row < len(self._filtered_items):
            self._execute_item(self._filtered_items[row])

    def _execute_item(self, item: CommandItem) -> None:
        self.accept()
        if item.action:
            result = item.action()
            self.action_triggered.emit(result)

    def show_centered(self) -> None:
        """在主窗口中央平滑浮动显示。"""
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self._search_input.clear()
        self._search_input.setFocus()
        self.exec()
