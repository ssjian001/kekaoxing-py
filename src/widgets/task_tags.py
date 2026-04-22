"""任务标签/颜色自定义标记系统"""

from __future__ import annotations

import json
import uuid

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QColorDialog,
    QMenu, QWidget, QFrame, QAbstractItemView,
    QGridLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPainter, QFontMetrics

from src.models import PRESET_COLORS
from src.styles.colors import (
    BASE_QSS,
    RED, YELLOW, BLUE, PEACH, GREEN, PINK, TEAL, MAUVE,
    SUBTEXT1, BORDER, SUCCESS, DANGER,
)


# ── 预置标签 ──────────────────────────────────────────────────────────
DEFAULT_TAGS = [
    {"id": "urgent", "label": "紧急", "color": RED},
    {"id": "review", "label": "待审核", "color": YELLOW},
    {"id": "customer", "label": "客户需求", "color": BLUE},
    {"id": "blocker", "label": "阻塞", "color": PEACH},
]

# 标签颜色小圆点的显示色板
TAG_DOT_COLORS = [
    RED, YELLOW, BLUE, PEACH,
    GREEN, PINK, TEAL, MAUVE,
]

# ── 任务标签专用样式（在 BASE_QSS 基础上追加） ────────────────────────
TAG_QSS = BASE_QSS + f"""
QListWidget {{
    font-size: 13px;
    outline: none;
}}
QListWidget::item {{
    border-bottom: 1px solid {BORDER};
}}
QPushButton {{
    font-size: 13px;
}}
QLineEdit {{
    font-size: 13px;
}}
QLabel {{
    font-size: 13px;
}}
QLabel#formLabel {{
    color: {SUBTEXT1};
    font-weight: bold;
}}
QPushButton#btnAdd {{
    background-color: #1e6640;
    color: {SUCCESS};
    border-color: #2d9f5f;
}}
QPushButton#btnAdd:hover {{
    background-color: #2d9f5f;
}}
QPushButton#btnDelete {{
    background-color: #6e2535;
    color: {DANGER};
    border-color: #a6374d;
}}
QPushButton#btnDelete:hover {{
    background-color: #a6374d;
}}
QPushButton#btnPrimary {{
    background-color: #1e6640;
    color: {SUCCESS};
    border-color: #2d9f5f;
}}
QPushButton#btnPrimary:hover {{
    background-color: #2d9f5f;
}}
"""


# ── 标签色点小部件 ──────────────────────────────────────────────────────

class _TagDot(QWidget):
    """一个小的颜色圆点，用于列表项中显示标签颜色。"""

    def __init__(self, color: str, size: int = 14, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self.width(), self.height())
        p.end()


# ── 标签 Chip ──────────────────────────────────────────────────────────

class _TagChip(QWidget):
    """单个标签 chip: 圆角背景 + 文字 + × 关闭按钮。"""

    remove_clicked = Signal(str)  # 发出 tag_id

    def __init__(self, tag_id: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self.tag_id = tag_id
        self._color = QColor(color)
        self._label = label
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)

        lbl = QLabel(self._label)
        lbl.setStyleSheet("color: #1e1e2e; font-size: 12px; font-weight: bold; border: none;")
        layout.addWidget(lbl)

        close = QPushButton("×")
        close.setFixedSize(18, 18)
        close.setStyleSheet(
            "QPushButton {"
            "  color: #1e1e2e; border: none; background: transparent;"
            "  font-size: 14px; font-weight: bold; padding: 0;"
            "}"
            "QPushButton:hover { background: rgba(0,0,0,40); border-radius: 9px; }"
        )
        close.clicked.connect(lambda: self.remove_clicked.emit(self.tag_id))
        layout.addWidget(close)

        # 圆角背景色
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b});"
            f"border-radius: 13px;"
        )

    def textWidth(self):
        """估算标签文本宽度（用于外部计算是否需要折叠）。"""
        fm = QFontMetrics(self.font())
        return fm.horizontalAdvance(self._label) + 32  # padding + close btn


# ── TaskTagManager ─────────────────────────────────────────────────────

class TaskTagManager(QWidget):
    """嵌入到 TaskEditor 中的小组件，用于管理单个任务的标签。

    水平排列标签 chip + 添加按钮。点击 "+" 弹出已有标签列表，
    可选择或管理标签定义。
    """

    tags_changed = Signal(list)  # 发出标签 ID 列表

    SETTING_KEY = "task_tags"

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._current_tags: list[str] = []  # 当前任务的标签 ID
        self._tag_definitions: list[dict] = DEFAULT_TAGS[:]
        self._build_ui()
        self.load_definitions()

    def set_db(self, db):
        """延迟设置数据库引用（TaskEditor 构造时可能尚未初始化 db）。"""
        self._db = db

    # ── UI 构建 ──────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 标签容器
        self._chip_container = QWidget()
        self._chip_layout = QHBoxLayout(self._chip_container)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(4)
        layout.addWidget(self._chip_container, stretch=1)

        # "+" 添加按钮
        self._add_btn = QPushButton("＋ 标签")
        self._add_btn.setFixedHeight(28)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #313244; color: #89b4fa; border: 1px dashed #585b70;"
            "  border-radius: 14px; padding: 2px 12px; font-size: 12px;"
            "}"
            "QPushButton:hover { background-color: #45475a; border-color: #89b4fa; }"
        )
        self._add_btn.clicked.connect(self._show_tag_menu)
        layout.addWidget(self._add_btn)

        # 占位提示
        self._hint_label = QLabel("点击添加标签...")
        self._hint_label.setStyleSheet("color: #6c7086; font-size: 12px; border: none;")
        self._hint_label.setVisible(True)
        layout.addWidget(self._hint_label)

    # ── 公开 API ─────────────────────────────────────────────────────

    def set_tags(self, tag_ids: list[str]):
        """设置当前任务的标签。"""
        self._current_tags = list(tag_ids)
        self._refresh_chips()

    def get_tags(self) -> list[str]:
        """获取当前标签 ID 列表。"""
        return list(self._current_tags)

    def load_definitions(self):
        """从数据库加载标签定义。"""
        if self._db is None:
            return
        raw = self._db.get_setting(self.SETTING_KEY, "")
        if raw:
            try:
                data = json.loads(raw)
                defs = data.get("tag_definitions", [])
                if defs:
                    self._tag_definitions = defs
            except (json.JSONDecodeError, TypeError):
                pass

    def save_definitions(self):
        """保存标签定义到数据库。"""
        if self._db is None:
            return
        data = {
            "tag_definitions": self._tag_definitions,
        }
        self._db.set_setting(self.SETTING_KEY, json.dumps(data, ensure_ascii=False))

    def load_task_tags(self, task_tags_data: dict):
        """从外部加载任务-标签映射，由 TaskEditor 调用。"""
        # task_tags_data 格式: {"3": ["urgent"], "7": ["urgent", "review"]}
        # 本组件只负责当前任务的标签，此方法为兼容保留
        pass

    def get_tag_definitions(self) -> list[dict]:
        """返回当前标签定义列表。"""
        return list(self._tag_definitions)

    def get_tag_def(self, tag_id: str) -> dict | None:
        """根据 ID 获取标签定义。"""
        for t in self._tag_definitions:
            if t.get("id") == tag_id:
                return t
        return None

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _refresh_chips(self):
        """刷新标签 chip 显示。"""
        # 清空
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        has_tags = bool(self._current_tags)
        self._hint_label.setVisible(not has_tags)
        self._chip_container.setVisible(has_tags)

        for tid in self._current_tags:
            tag_def = self.get_tag_def(tid)
            if not tag_def:
                continue
            chip = _TagChip(tid, tag_def["label"], tag_def["color"])
            chip.remove_clicked.connect(self._remove_tag)
            self._chip_layout.addWidget(chip)

    def _remove_tag(self, tag_id: str):
        """移除一个标签。"""
        if tag_id in self._current_tags:
            self._current_tags.remove(tag_id)
            self._refresh_chips()
            self.tags_changed.emit(self._current_tags)

    def _show_tag_menu(self):
        """弹出标签选择菜单。"""
        menu = QMenu(self)
        menu.setStyleSheet(TAG_QSS)

        # 列出已有标签定义（带勾选状态）
        for tag_def in self._tag_definitions:
            tid = tag_def["id"]
            checked = tid in self._current_tags
            prefix = "✓ " if checked else "   "
            color = tag_def["color"]

            action = menu.addAction(f"{prefix}  {tag_def['label']}")
            # 用 tooltip 存储颜色，用于样式
            r, g, b = QColor(color).red(), QColor(color).green(), QColor(color).blue()
            action.setToolTip(color)
            action.setData(tid)

        if self._tag_definitions:
            menu.addSeparator()

        # 管理标签定义
        manage_action = menu.addAction("⚙️ 管理标签定义...")
        manage_action.setData("__manage__")

        # 全部清除
        if self._current_tags:
            clear_action = menu.addAction("🗑️ 清除所有标签")
            clear_action.setData("__clear__")

        # 执行
        chosen = menu.exec(self._add_btn.mapToGlobal(self._add_btn.rect().bottomLeft()))
        if chosen is None:
            return

        data = chosen.data()
        if data == "__manage__":
            self._open_definition_dialog()
        elif data == "__clear__":
            self._current_tags.clear()
            self._refresh_chips()
            self.tags_changed.emit(self._current_tags)
        else:
            # 切换标签
            if data in self._current_tags:
                self._current_tags.remove(data)
            else:
                self._current_tags.append(data)
            self._refresh_chips()
            self.tags_changed.emit(self._current_tags)

    def _open_definition_dialog(self):
        """打开标签定义管理对话框。"""
        dlg = TagDefinitionDialog(self._tag_definitions, parent=self)
        dlg.setStyleSheet(TAG_QSS)
        if dlg.exec():
            self._tag_definitions = dlg.get_definitions()
            self.save_definitions()
            # 刷新 chip 显示（标签定义可能被删除或改名）
            self._current_tags = [
                tid for tid in self._current_tags
                if self.get_tag_def(tid) is not None
            ]
            self._refresh_chips()


# ── TagDefinitionDialog ────────────────────────────────────────────────

class TagDefinitionDialog(QDialog):
    """管理所有标签定义的对话框。

    布局: 标签列表 + 添加/编辑/删除按钮。
    编辑时: 标签名输入 + 颜色选择（预设色板 + 自定义颜色）。
    """

    def __init__(self, definitions: list[dict], parent=None):
        super().__init__(parent)
        self._definitions = [dict(d) for d in definitions]  # 深拷贝
        self._selected_color = PRESET_COLORS[0]
        self.setWindowTitle("🏷️ 标签定义管理")
        self.setMinimumWidth(480)
        self.setMinimumHeight(420)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 标签列表 ──
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list)

        # ── 编辑区域 ──
        edit_group = QFrame()
        edit_group.setStyleSheet(
            "QFrame { background-color: #181825; border-radius: 6px; padding: 8px; }"
        )
        edit_layout = QVBoxLayout(edit_group)
        edit_layout.setSpacing(8)

        # 标签名
        edit_layout.addWidget(QLabel("标签名称", objectName="formLabel"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例: 紧急、待审核、客户需求")
        self._name_edit.textChanged.connect(self._on_name_changed)
        edit_layout.addWidget(self._name_edit)

        # 标签 ID
        edit_layout.addWidget(QLabel("标签 ID", objectName="formLabel"))
        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("英文标识，如 urgent")
        self._id_edit.setEnabled(False)  # 创建后不可改
        edit_layout.addWidget(self._id_edit)

        # 颜色选择
        edit_layout.addWidget(QLabel("颜色", objectName="formLabel"))
        color_row = QHBoxLayout()
        color_row.setSpacing(6)

        # 预设色板
        self._color_btns: list[QPushButton] = []
        for c in PRESET_COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            r, g, b = QColor(c).red(), QColor(c).green(), QColor(c).blue()
            btn.setStyleSheet(
                f"QPushButton {{ background-color: rgb({r},{g},{b}); "
                f"border: 2px solid transparent; border-radius: 14px; }}"
                f"QPushButton:hover {{ border-color: #cdd6f4; }}"
            )
            btn.clicked.connect(lambda checked, cc=c: self._select_color(cc))
            color_row.addWidget(btn)
            self._color_btns.append(btn)

        # 自定义颜色按钮
        color_row.addWidget(QLabel("  "))
        self._custom_color_btn = QPushButton("🎨 自定义")
        self._custom_color_btn.setFixedHeight(28)
        self._custom_color_btn.clicked.connect(self._pick_custom_color)
        color_row.addWidget(self._custom_color_btn)

        color_row.addStretch()
        edit_layout.addLayout(color_row)

        layout.addWidget(edit_group)

        # ── 按钮栏 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        # 删除
        self._del_btn = QPushButton("🗑️ 删除")
        self._del_btn.setObjectName("btnDelete")
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._del_btn)

        # 添加
        self._add_btn = QPushButton("＋ 添加标签")
        self._add_btn.setObjectName("btnAdd")
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)

        # 保存
        self._save_btn = QPushButton("保存")
        self._save_btn.setObjectName("btnPrimary")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        layout.addLayout(btn_row)

    # ── 列表刷新 ─────────────────────────────────────────────────────

    def _refresh_list(self):
        self._list.clear()
        for tag in self._definitions:
            item = QListWidgetItem()
            # 自定义 widget 以显示颜色圆点 + 标签名
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 0, 4, 0)
            row_layout.setSpacing(8)

            dot = _TagDot(tag["color"], size=16)
            row_layout.addWidget(dot)

            label = QLabel(f"{tag['label']}  ({tag['id']})")
            label.setStyleSheet("border: none;")
            row_layout.addWidget(label)
            row_layout.addStretch()

            item.setSizeHint(QSize(0, 32))
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

        # 绑定选中事件
        self._list.currentRowChanged.connect(self._on_row_changed)

    # ── 事件处理 ─────────────────────────────────────────────────────

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self._definitions):
            tag = self._definitions[row]
            self._name_edit.setText(tag["label"])
            self._id_edit.setText(tag["id"])
            self._select_color(tag["color"])
            self._del_btn.setEnabled(True)
        else:
            self._del_btn.setEnabled(False)

    def _on_name_changed(self, text: str):
        """实时更新选中标签的名称（列表同步刷新）。"""
        row = self._list.currentRow()
        if 0 <= row < len(self._definitions):
            self._definitions[row]["label"] = text.strip()
            # 刷新列表项显示
            item_widget = self._list.itemWidget(self._list.item(row))
            if item_widget:
                lbl = item_widget.findChild(QLabel)
                if lbl:
                    lbl.setText(f"{text.strip()}  ({self._definitions[row]['id']})")

    def _select_color(self, color: str):
        self._selected_color = color
        # 更新色板按钮边框
        for btn, c in zip(self._color_btns, PRESET_COLORS):
            r, g, b = QColor(c).red(), QColor(c).green(), QColor(c).blue()
            border_color = "#cdd6f4" if c.lower() == color.lower() else "transparent"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: rgb({r},{g},{b}); "
                f"border: 2px solid {border_color}; border-radius: 14px; }}"
                f"QPushButton:hover {{ border-color: #cdd6f4; }}"
            )

    def _pick_custom_color(self):
        color = QColorDialog.getColor(
            QColor(self._selected_color), self, "选择自定义颜色"
        )
        if color.isValid():
            self._select_color(color.name())

    def _on_add(self):
        """添加新标签。"""
        label = self._name_edit.text().strip()
        if not label:
            return
        # 生成 ID
        base_id = label.lower().replace(" ", "_").replace("/", "_")
        # 确保 ID 唯一
        existing_ids = {t["id"] for t in self._definitions}
        tag_id = base_id
        counter = 1
        while tag_id in existing_ids:
            tag_id = f"{base_id}_{counter}"
            counter += 1

        new_tag = {
            "id": tag_id,
            "label": label,
            "color": self._selected_color,
        }
        self._definitions.append(new_tag)
        self._refresh_list()

        # 选中新添加的项
        self._list.setCurrentRow(len(self._definitions) - 1)

    def _on_delete(self):
        """删除选中标签。"""
        row = self._list.currentRow()
        if 0 <= row < len(self._definitions):
            self._definitions.pop(row)
            self._refresh_list()

    def _on_save(self):
        """应用当前编辑区域的值到选中标签，然后关闭。"""
        # 先确保当前编辑内容已同步
        row = self._list.currentRow()
        if 0 <= row < len(self._definitions):
            self._definitions[row]["label"] = self._name_edit.text().strip()
            self._definitions[row]["color"] = self._selected_color
        self.accept()

    def get_definitions(self) -> list[dict]:
        """返回编辑后的标签定义列表。"""
        return list(self._definitions)


# ── 辅助函数（供 gantt_view 等外部模块使用）───────────────────────────

def load_task_tags_from_db(db) -> tuple[list[dict], dict]:
    """从数据库加载标签定义和任务-标签映射。

    Returns:
        (tag_definitions, task_tags)  — tag_definitions 为列表，
        task_tags 为 {task_id_str: [tag_id, ...]} 字典。
    """
    raw = db.get_setting("task_tags", "")
    if not raw:
        return DEFAULT_TAGS[:], {}

    try:
        data = json.loads(raw)
        tag_defs = data.get("tag_definitions", [])
        if not tag_defs:
            tag_defs = DEFAULT_TAGS[:]
        task_tags = data.get("task_tags", {})
        return tag_defs, task_tags
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_TAGS[:], {}


def save_task_tags_to_db(db, tag_definitions: list[dict], task_tags: dict):
    """保存标签定义和任务-标签映射到数据库。"""
    data = {
        "tag_definitions": tag_definitions,
        "task_tags": task_tags,
    }
    db.set_setting("task_tags", json.dumps(data, ensure_ascii=False))


def get_tag_defs_dict(tag_definitions: list[dict]) -> dict:
    """将标签定义列表转为 {id: def} 字典，方便快速查找。"""
    return {t["id"]: t for t in tag_definitions}
