"""测试项目分类管理对话框"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QSpinBox, QHeaderView,
    QColorDialog, QFrame, QAbstractItemView, QMessageBox, QWidget,
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor

from src.db.database import Database
from src.styles.colors import (
    BASE_QSS, BLUE, SUCCESS, DANGER, SUBTEXT1,
)


# ── 分类管理专用样式（在 BASE_QSS 基础上追加） ────────────────────────
SECTION_QSS = BASE_QSS + f"""
QTableWidget {{
    font-size: 13px;
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QTableWidget::item:selected {{
    background-color: {{"#45475a"}};
}}
QHeaderView::section {{
    font-weight: bold;
    font-size: 13px;
    padding: 6px 8px;
}}
QPushButton {{
    font-size: 13px;
}}
QLineEdit, QSpinBox {{
    font-size: 13px;
}}
QLabel {{
    font-size: 13px;
}}
QLabel#formLabel {{
    color: {SUBTEXT1};
    font-weight: bold;
}}
QMessageBox {{
    background-color: {{"#1e1e2e"}};
}}
QMessageBox QLabel {{
    font-size: 13px;
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}
QPushButton#btnAdd {{
    background-color: #1e6640;
    color: {SUCCESS};
    border-color: #2d9f5f;
}}
QPushButton#btnAdd:hover {{
    background-color: #2d9f5f;
}}
QPushButton#btnEdit {{
    background-color: #1e4f7a;
    color: {BLUE};
    border-color: #3574b8;
    padding: 3px 10px;
    font-size: 12px;
}}
QPushButton#btnEdit:hover {{
    background-color: #3574b8;
}}
QPushButton#btnDelete {{
    background-color: #6e2535;
    color: {DANGER};
    border-color: #a6374d;
    padding: 3px 10px;
    font-size: 12px;
}}
QPushButton#btnDelete:hover {{
    background-color: #a6374d;
}}
"""


class SectionEditorDialog(QDialog):
    """添加 / 编辑分类的内联对话框"""

    def __init__(self, parent=None, *, section=None, db=None):
        super().__init__(parent)
        self.db = db  # Database for uniqueness check
        self.section = section  # None = 添加模式, dict = 编辑模式
        self.selected_color = QColor(section["color"]) if section else QColor(BLUE)
        self.setWindowTitle("编辑分类" if section else "添加分类")
        self.setMinimumWidth(380)
        self.setStyleSheet(SECTION_QSS)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── key ──
        layout.addWidget(QLabel("分类标识 (key)", objectName="formLabel"))
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("英文标识，如 thermal")
        if self.section:
            self.key_edit.setText(self.section["key"])
        layout.addWidget(self.key_edit)

        self._key_hint = QLabel("")
        self._key_hint.setStyleSheet("color: #f38ba8; font-size: 11px;")
        layout.addWidget(self._key_hint)

        # debounce 计时器：key 唯一性实时验证
        self._key_validate_timer = QTimer(self)
        self._key_validate_timer.setSingleShot(True)
        self._key_validate_timer.setInterval(300)
        self._key_validate_timer.timeout.connect(self._check_key_uniqueness)
        self.key_edit.textChanged.connect(self._schedule_key_check)

        # ── label ──
        layout.addWidget(QLabel("显示名称 (label)", objectName="formLabel"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("中文名，如 热学测试")
        if self.section:
            self.label_edit.setText(self.section["label"])
        layout.addWidget(self.label_edit)

        # ── color ──
        layout.addWidget(QLabel("颜色", objectName="formLabel"))
        color_row = QHBoxLayout()
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self._update_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_btn)
        self.color_label = QLabel(self.selected_color.name())
        self.color_label.setStyleSheet("color: #6c7086; font-family: monospace;")
        color_row.addWidget(self.color_label)
        color_row.addStretch()
        layout.addLayout(color_row)

        # ── sort_order ──
        layout.addWidget(QLabel("排序", objectName="formLabel"))
        self.sort_spin = QSpinBox()
        self.sort_spin.setRange(0, 9999)
        if self.section:
            self.sort_spin.setValue(self.section["sort_order"])
        layout.addWidget(self.sort_spin)

        # ── buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet(
            ok_btn.styleSheet() + "background-color:#1e6640; color:#a6e3a1; border-color:#2d9f5f;"
        )
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    # ── helpers ────────────────────────────────────────────────────────

    def _schedule_key_check(self, text: str):
        """textChanged → 启动 300ms debounce 计时器"""
        self._key_validate_timer.start()

    def _check_key_uniqueness(self):
        """查询数据库检查 key 是否已存在（编辑模式排除自身）"""
        key = self.key_edit.text().strip()
        if not key:
            self._key_hint.setText("")
            self.key_edit.setStyleSheet("")
            return
        section_id = self.section["id"] if self.section else None
        existing = self.db.conn.execute(
            "SELECT id FROM sections WHERE key = ?", (key,)
        ).fetchone()
        if existing and existing[0] != section_id:
            self._key_hint.setText("⚠ 此分类标识已存在")
            self.key_edit.setStyleSheet("border: 1px solid #f38ba8;")
        else:
            self._key_hint.setText("")
            self.key_edit.setStyleSheet("")

    def _update_color_btn(self):
        self.color_btn.setStyleSheet(
            f"background-color: {self.selected_color.name()}; "
            f"border: 2px solid #45475a; border-radius: 4px;"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(self.selected_color, self, "选择颜色")
        if color.isValid():
            self.selected_color = color
            self._update_color_btn()
            self.color_label.setText(color.name())

    def _on_accept(self):
        key = self.key_edit.text().strip()
        label = self.label_edit.text().strip()
        if not key or not label:
            return
        # Check key uniqueness
        section_id = self.section["id"] if self.section else None
        existing = self.db.conn.execute("SELECT id FROM sections WHERE key = ?", (key,)).fetchone()
        if existing and existing[0] != section_id:
            QMessageBox.warning(self, "错误", f"分类标识 \"{key}\" 已存在，请使用唯一标识")
            return
        self.accept()

    def get_data(self):
        return {
            "key": self.key_edit.text().strip(),
            "label": self.label_edit.text().strip(),
            "color": self.selected_color.name(),
            "sort_order": self.sort_spin.value(),
        }


class SectionManagerDialog(QDialog):
    """测试项目分类管理对话框"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("🏷️ 测试项目分类管理")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setStyleSheet(SECTION_QSS)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── table ──
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["颜色", "分类标识 (key)", "显示名称 (label)", "排序", "任务数", "操作"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 50)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 60)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 60)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 140)

        self.table.setColumnHidden(0, False)
        layout.addWidget(self.table)

        # ── bottom bar ──
        bottom = QHBoxLayout()
        bottom.addStretch()
        add_btn = QPushButton("＋ 添加分类")
        add_btn.setObjectName("btnAdd")
        add_btn.clicked.connect(self._on_add)
        bottom.addWidget(add_btn)
        layout.addLayout(bottom)

    # ── data ───────────────────────────────────────────────────────────

    def refresh(self):
        """从数据库重新加载分类列表"""
        sections = self.db.get_all_sections()
        self.table.setRowCount(len(sections))

        for row, sec in enumerate(sections):
            # 颜色预览
            color_frame = QFrame()
            color_frame.setStyleSheet(
                f"background-color: {sec['color']}; "
                f"border: 2px solid #45475a; border-radius: 4px;"
            )
            color_frame.setFixedSize(28, 20)
            self.table.setCellWidget(row, 0, color_frame)

            # key
            self.table.setItem(row, 1, QTableWidgetItem(sec["key"]))

            # label
            self.table.setItem(row, 2, QTableWidgetItem(sec["label"]))

            # sort_order
            sort_item = QTableWidgetItem(str(sec["sort_order"]))
            sort_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, sort_item)

            # 任务数
            count = self.db.section_task_count(sec["key"])
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, count_item)

            # 操作按钮
            btn_container = QHBoxLayout()
            btn_container.setContentsMargins(4, 2, 4, 2)
            btn_container.setSpacing(6)

            edit_btn = QPushButton("编辑")
            edit_btn.setObjectName("btnEdit")
            edit_btn.clicked.connect(lambda checked, s=sec: self._on_edit(s))
            btn_container.addWidget(edit_btn)

            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("btnDelete")
            delete_btn.clicked.connect(lambda checked, s=sec: self._on_delete(s))
            btn_container.addWidget(delete_btn)

            cell_widget = QWidget()
            cell_widget.setLayout(btn_container)
            self.table.setCellWidget(row, 5, cell_widget)

    # ── actions ────────────────────────────────────────────────────────

    def _on_add(self):
        dlg = SectionEditorDialog(self, db=self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.db.insert_section(
                data["key"], data["label"], data["color"], data["sort_order"]
            )
            self.refresh()

    def _on_edit(self, section: dict):
        dlg = SectionEditorDialog(self, section=section, db=self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.db.update_section(
                section["id"], data["key"], data["label"], data["color"], data["sort_order"]
            )
            self.refresh()

    def _on_delete(self, section: dict):
        count = self.db.section_task_count(section["key"])
        msg = f"确定要删除分类「{section['label']}」吗？"
        if count > 0:
            msg += (
                f"\n\n该分类下有 {count} 个任务，是否确认删除？"
                f"\n（任务不会被删除，但分类标识将变为空值）"
            )

        from PySide6.QtWidgets import QMessageBox

        ret = QMessageBox.warning(
            self,
            "确认删除",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.db.delete_section(section["id"])
            self.refresh()
