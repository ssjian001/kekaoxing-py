"""任务编辑对话框 - 新增/编辑任务"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QLineEdit, QGroupBox, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QWidget, QScrollArea,
    QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from src.db.database import Database
from src.models import (
    Task, Section, ResourceType, EquipmentRequirement,
    DEFAULT_SECTION_LABELS,
)
from src.widgets.task_tags import TaskTagManager, load_task_tags_from_db, save_task_tags_to_db, DEFAULT_TAGS


def _save_tags_for_task(db: Database, task_id: int, tag_ids: list[str]):
    """保存单个任务的标签到 DB"""
    try:
        _, task_tags = load_task_tags_from_db(db)
        if tag_ids:
            task_tags[str(task_id)] = tag_ids
        else:
            task_tags.pop(str(task_id), None)
        raw = db.get_setting("task_tags", "")
        tag_defs = DEFAULT_TAGS[:]
        if raw:
            try:
                import json as _json
                data = _json.loads(raw)
                td = data.get("tag_definitions", [])
                if td:
                    tag_defs = td
            except Exception:
                pass
        save_task_tags_to_db(db, tag_defs, task_tags)
    except Exception:
        pass


class TaskEditor(QDialog):
    """任务编辑对话框"""

    def __init__(
        self,
        db: Database,
        task: Task | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self._existing_task = task
        self._is_new = task is None
        self._all_tasks = db.get_all_tasks()
        self._equipment_resources = [
            r for r in db.get_all_resources()
            if r.type == ResourceType.EQUIPMENT
        ]

        self.setWindowTitle("📋 新增任务" if self._is_new else f"📋 编辑任务 {task.num}")
        self.setMinimumSize(580, 780)

        self._setup_ui()
        self._load_data(task)

        # 连接实时验证信号（在加载数据之后，避免触发无效状态）
        self.num_edit.textChanged.connect(self._validate_num)
        self.name_cn_edit.textChanged.connect(self._validate_name_cn)

    # ── UI 构建 ──────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)

        # 使用滚动区域包裹，防止内容过多时窗口溢出
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(12)

        # ── 基本信息 ──
        basic_group = QGroupBox("基本信息")
        basic_form = QFormLayout()
        basic_form.setLabelAlignment(Qt.AlignRight)

        self.num_edit = QLineEdit()
        self.num_edit.setPlaceholderText("例: 1.1")
        basic_form.addRow("编号:", self.num_edit)

        self._num_hint = QLabel("")
        self._num_hint.setStyleSheet("color: #f38ba8; font-size: 11px;")
        basic_form.addRow("", self._num_hint)

        self.name_cn_edit = QLineEdit()
        self.name_cn_edit.setPlaceholderText("例: 高温高湿测试")
        basic_form.addRow("中文名称:", self.name_cn_edit)

        self._name_cn_hint = QLabel("")
        self._name_cn_hint.setStyleSheet("color: #f38ba8; font-size: 11px;")
        basic_form.addRow("", self._name_cn_hint)

        self.name_en_edit = QLineEdit()
        self.name_en_edit.setPlaceholderText("例: High Temperature / Humidity Test")
        basic_form.addRow("英文名称:", self.name_en_edit)

        self.section_combo = QComboBox()
        # 从数据库读取自定义分类
        for s in self.db.get_all_sections():
            self.section_combo.addItem(s["label"], s["key"])
        # 如果数据库为空，回退到内置默认
        if self.section_combo.count() == 0:
            for key, label in DEFAULT_SECTION_LABELS.items():
                self.section_combo.addItem(label, key)
        basic_form.addRow("分类:", self.section_combo)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 365)
        self.duration_spin.setValue(1)
        basic_form.addRow("持续天数:", self.duration_spin)

        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 9)
        self.priority_spin.setValue(3)
        basic_form.addRow("优先级:", self.priority_spin)

        self.progress_spin = QSpinBox()
        self.progress_spin.setRange(0, 100)
        self.progress_spin.setSuffix(" %")
        self.progress_spin.setValue(0)
        basic_form.addRow("进度:", self.progress_spin)

        self.done_cb = QCheckBox("已完成")
        basic_form.addRow(self.done_cb)

        basic_group.setLayout(basic_form)
        main_layout.addWidget(basic_group)

        # ── 排程参数 ──
        schedule_group = QGroupBox("排程参数")
        schedule_form = QFormLayout()
        schedule_form.setLabelAlignment(Qt.AlignRight)

        self.sample_pool_combo = QComboBox()
        self.sample_pool_combo.addItem("无", "")
        for r in self.db.get_all_resources():
            if r.type == ResourceType.SAMPLE_POOL:
                self.sample_pool_combo.addItem(f"{r.icon} {r.name}", r.name)
        schedule_form.addRow("样品池:", self.sample_pool_combo)

        self.sample_qty_spin = QSpinBox()
        self.sample_qty_spin.setRange(1, 100)
        self.sample_qty_spin.setValue(3)
        schedule_form.addRow("样品数量:", self.sample_qty_spin)

        self.setup_time_spin = QDoubleSpinBox()
        self.setup_time_spin.setRange(0, 10)
        self.setup_time_spin.setSingleStep(0.5)
        self.setup_time_spin.setValue(0)
        self.setup_time_spin.setSuffix(" 天")
        schedule_form.addRow("准备时间:", self.setup_time_spin)

        self.teardown_time_spin = QDoubleSpinBox()
        self.teardown_time_spin.setRange(0, 10)
        self.teardown_time_spin.setSingleStep(0.5)
        self.teardown_time_spin.setValue(0)
        self.teardown_time_spin.setSuffix(" 天")
        schedule_form.addRow("收尾时间:", self.teardown_time_spin)

        self.start_day_spin = QSpinBox()
        self.start_day_spin.setRange(0, 999)
        self.start_day_spin.setValue(0)
        self.start_day_label = QLabel("D0")
        self.start_day_spin.valueChanged.connect(
            lambda v: self.start_day_label.setText(f"D{v}")
        )
        start_row = QHBoxLayout()
        start_row.addWidget(self.start_day_spin)
        start_row.addWidget(self.start_day_label)
        schedule_form.addRow("开始日:", start_row)

        schedule_group.setLayout(schedule_form)
        main_layout.addWidget(schedule_group)

        # ── 依赖关系 ──
        deps_group = QGroupBox("依赖关系")
        deps_layout = QVBoxLayout()

        self.deps_list = QListWidget()
        self.deps_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.deps_list.setMaximumHeight(160)
        deps_layout.addWidget(self.deps_list)

        hint_label = QLabel("选择前置任务（不同分类 或 同分类非串行任务）")
        hint_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        deps_layout.addWidget(hint_label)

        deps_group.setLayout(deps_layout)
        main_layout.addWidget(deps_group)

        # ── 串行链 ──
        serial_group = QGroupBox("串行链")
        serial_form = QFormLayout()
        serial_form.setLabelAlignment(Qt.AlignRight)

        self.is_serial_cb = QCheckBox("标记为串行任务")
        self.is_serial_cb.toggled.connect(self._on_serial_toggled)
        serial_form.addRow(self.is_serial_cb)

        self.serial_group_combo = QComboBox()
        serial_form.addRow("串行组:", self.serial_group_combo)

        serial_group.setLayout(serial_form)
        main_layout.addWidget(serial_group)

        # ── 设备需求 ──
        equip_group = QGroupBox("设备需求")
        equip_layout = QVBoxLayout()

        self.equip_table = QTableWidget()
        self.equip_table.setColumnCount(3)
        self.equip_table.setHorizontalHeaderLabels(["设备", "数量", ""])
        self.equip_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.equip_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.equip_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Fixed
        )
        self.equip_table.setColumnWidth(2, 40)
        self.equip_table.verticalHeader().setVisible(False)
        self.equip_table.setMaximumHeight(160)
        equip_layout.addWidget(self.equip_table)

        equip_btn_layout = QHBoxLayout()
        btn_add_equip = QPushButton("➕ 添加设备")
        btn_add_equip.clicked.connect(self._add_equip_row)
        equip_btn_layout.addWidget(btn_add_equip)

        btn_remove_equip = QPushButton("➖ 移除选中")
        btn_remove_equip.clicked.connect(self._remove_equip_row)
        equip_btn_layout.addWidget(btn_remove_equip)

        equip_btn_layout.addStretch()
        equip_group.setLayout(equip_layout)
        main_layout.addWidget(equip_group)
        equip_layout.addLayout(equip_btn_layout)

        # ── 标签 ──
        tags_group = QGroupBox("🏷️ 标签")
        tags_layout = QVBoxLayout()
        self._tag_manager = TaskTagManager(self.db)
        tags_layout.addWidget(self._tag_manager)
        tags_group.setLayout(tags_layout)
        main_layout.addWidget(tags_group)

        main_layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("确认")
        self.btn_ok.setObjectName("primaryBtn")
        self.btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.btn_ok)

        outer.addLayout(btn_layout)

    # ── 数据加载 ──────────────────────────────────

    def _load_data(self, task: Task | None):
        """加载任务数据到 UI"""
        # 基本信息
        if task:
            self.num_edit.setText(task.num)
            self.num_edit.setReadOnly(True)
            self.name_cn_edit.setText(task.name_cn)
            self.name_en_edit.setText(task.name_en)

            # section
            section_key = task.section.value if isinstance(task.section, Section) else task.section
            idx = self.section_combo.findData(section_key)
            if idx >= 0:
                self.section_combo.setCurrentIndex(idx)

            self.duration_spin.setValue(task.duration)
            self.priority_spin.setValue(task.priority)
            self.progress_spin.setValue(int(task.progress))
            self.done_cb.setChecked(task.done)

            # 排程
            pool_idx = self.sample_pool_combo.findData(task.sample_pool)
            if pool_idx >= 0:
                self.sample_pool_combo.setCurrentIndex(pool_idx)
            self.sample_qty_spin.setValue(task.sample_qty)
            self.setup_time_spin.setValue(task.setup_time)
            self.teardown_time_spin.setValue(task.teardown_time)
            self.start_day_spin.setValue(task.start_day)

            # 串行
            self.is_serial_cb.setChecked(task.is_serial)
            self._populate_serial_groups(task.section, task.serial_group)

            # 依赖
            self._populate_dependencies(task)

            # 设备需求
            for req in task.requirements:
                self._add_equip_row(req.resource_id, req.quantity)

            # 标签
            try:
                _, task_tags = load_task_tags_from_db(self.db)
                self._tag_manager.set_tags(task_tags.get(str(task.id), []))
            except Exception:
                pass

        else:
            # 新建任务默认
            self._populate_serial_groups(None, "")
            self._populate_dependencies(None)

    def _populate_serial_groups(
        self,
        current_section: Section | None,
        current_group: str,
    ):
        """填充串行组下拉框"""
        self.serial_group_combo.clear()

        # 收集已有的串行组
        existing_groups: set[str] = set()
        for t in self._all_tasks:
            if t.serial_group:
                existing_groups.add(t.serial_group)

        for g in sorted(existing_groups):
            self.serial_group_combo.addItem(g)

        self.serial_group_combo.addItem("新建")

        # 选中当前值
        if current_group:
            idx = self.serial_group_combo.findText(current_group)
            if idx >= 0:
                self.serial_group_combo.setCurrentIndex(idx)
            else:
                self.serial_group_combo.setCurrentText(current_group)
                # 如果不在列表中，插入
                self.serial_group_combo.insertItem(
                    self.serial_group_combo.count() - 1, current_group
                )
                self.serial_group_combo.setCurrentText(current_group)

        self.serial_group_combo.setEnabled(self.is_serial_cb.isChecked())

    def _populate_dependencies(self, task: Task | None):
        """填充可选依赖任务列表"""
        self.deps_list.clear()
        task_section = task.section if task else None
        task_id = task.id if task else None

        current_deps = set(task.dependencies) if task else set()

        for t in self._all_tasks:
            if t.id == task_id:
                continue
            # 只能选择：其他分类的任务 + 同分类中非串行任务
            if t.section == task_section and t.is_serial:
                continue

            item = QListWidgetItem(f"{t.num}  {t.name_cn}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if t.num in current_deps else Qt.Unchecked
            )
            # 存储任务 num 作为 data
            item.setData(Qt.ItemDataRole.UserRole, t.num)
            self.deps_list.addItem(item)

    def _on_serial_toggled(self, checked: bool):
        """串行复选框切换"""
        self.serial_group_combo.setEnabled(checked)
        if checked:
            # 自动设置为 section_serial
            section_val = self.section_combo.currentData()
            default_group = f"{section_val}_serial"
            # 如果当前为空或"新建"，设为默认值
            current = self.serial_group_combo.currentText()
            if not current or current == "新建":
                idx = self.serial_group_combo.findText(default_group)
                if idx >= 0:
                    self.serial_group_combo.setCurrentIndex(idx)
                else:
                    # 插入默认组名
                    self.serial_group_combo.insertItem(
                        self.serial_group_combo.count() - 1, default_group
                    )
                    self.serial_group_combo.setCurrentText(default_group)

    # ── 设备需求表格 ──────────────────────────────

    def _add_equip_row(
        self,
        resource_id: int | None = None,
        quantity: int = 1,
    ):
        """添加一行设备需求"""
        row = self.equip_table.rowCount()
        self.equip_table.insertRow(row)

        # 设备选择 ComboBox
        equip_combo = QComboBox()
        for r in self._equipment_resources:
            equip_combo.addItem(f"{r.icon} {r.name}", r.id)
        if resource_id is not None:
            idx = equip_combo.findData(resource_id)
            if idx >= 0:
                equip_combo.setCurrentIndex(idx)
        self.equip_table.setCellWidget(row, 0, equip_combo)

        # 数量 SpinBox
        qty_spin = QSpinBox()
        qty_spin.setRange(1, 10)
        qty_spin.setValue(quantity)
        self.equip_table.setCellWidget(row, 1, qty_spin)

        # 移除按钮
        btn_remove = QPushButton("✕")
        btn_remove.setFixedWidth(36)
        btn_remove.clicked.connect(lambda: self.equip_table.removeRow(row))
        self.equip_table.setCellWidget(row, 2, btn_remove)

    def _remove_equip_row(self):
        """移除当前选中行"""
        row = self.equip_table.currentRow()
        if row >= 0:
            self.equip_table.removeRow(row)

    # ── 数据收集 ──────────────────────────────────

    def get_task(self) -> Task:
        """从 UI 收集数据并返回 Task dataclass"""
        section_key = self.section_combo.currentData()
        try:
            section = Section(section_key)
        except ValueError:
            section = section_key  # type: ignore[assignment]
        serial_group_text = self.serial_group_combo.currentText()
        if serial_group_text == "新建":
            serial_group_text = ""

        # 依赖
        deps: list[str] = []
        for i in range(self.deps_list.count()):
            item = self.deps_list.item(i)
            if item.checkState() == Qt.Checked:
                deps.append(item.data(Qt.ItemDataRole.UserRole))

        # 设备需求
        requirements: list[EquipmentRequirement] = []
        for row in range(self.equip_table.rowCount()):
            combo = self.equip_table.cellWidget(row, 0)
            spin = self.equip_table.cellWidget(row, 1)
            if combo and spin:
                resource_id = combo.currentData()
                qty = spin.value()
                requirements.append(
                    EquipmentRequirement(resource_id=resource_id, quantity=qty)
                )

        task_id = self._existing_task.id if self._existing_task else 0

        return Task(
            id=task_id,
            num=self.num_edit.text().strip(),
            name_cn=self.name_cn_edit.text().strip(),
            name_en=self.name_en_edit.text().strip(),
            section=section,
            duration=self.duration_spin.value(),
            priority=self.priority_spin.value(),
            progress=float(self.progress_spin.value()),
            done=self.done_cb.isChecked(),
            start_day=self.start_day_spin.value(),
            sample_pool=self.sample_pool_combo.currentData(),
            sample_qty=self.sample_qty_spin.value(),
            setup_time=self.setup_time_spin.value(),
            teardown_time=self.teardown_time_spin.value(),
            is_serial=self.is_serial_cb.isChecked(),
            serial_group=serial_group_text,
            dependencies=deps,
            requirements=requirements,
            created_at=self._existing_task.created_at if self._existing_task else "",
            updated_at=self._existing_task.updated_at if self._existing_task else "",
        )

    # ── 实时验证 ──────────────────────────────────

    def _validate_num(self, text: str):
        """实时验证任务编号"""
        if not text.strip():
            self._num_hint.setText("⚠ 任务编号不能为空")
            self.num_edit.setStyleSheet("border: 1px solid #f38ba8;")
        else:
            self._num_hint.setText("")
            self.num_edit.setStyleSheet("")

    def _validate_name_cn(self, text: str):
        """实时验证中文名称"""
        if not text.strip():
            self._name_cn_hint.setText("⚠ 中文名称不能为空")
            self.name_cn_edit.setStyleSheet("border: 1px solid #f38ba8;")
        else:
            self._name_cn_hint.setText("")
            self.name_cn_edit.setStyleSheet("")

    # ── 验证 & 接受 ──────────────────────────────

    def _on_accept(self):
        """验证输入后接受对话框"""
        # 编号
        num = self.num_edit.text().strip()
        if not num:
            QMessageBox.warning(self, "验证失败", "请输入任务编号")
            self.num_edit.setFocus()
            return

        # 检查编号唯一性
        for t in self._all_tasks:
            if t.num == num and (
                self._is_new or t.id != self._existing_task.id
            ):
                QMessageBox.warning(
                    self, "验证失败",
                    f"任务编号 \"{num}\" 已存在，请使用唯一编号"
                )
                self.num_edit.setFocus()
                return

        # 中文名
        name_cn = self.name_cn_edit.text().strip()
        if not name_cn:
            QMessageBox.warning(self, "验证失败", "请输入中文名称")
            self.name_cn_edit.setFocus()
            return

        # 英文名
        name_en = self.name_en_edit.text().strip()
        if not name_en:
            QMessageBox.warning(self, "验证失败", "请输入英文名称")
            self.name_en_edit.setFocus()
            return

        self.accept()

    # ── 静态方法 ──────────────────────────────────

    @staticmethod
    def add_new(db: Database, parent=None) -> Task | None:
        """打开新增任务对话框，返回 Task（已写入DB）或 None"""
        dlg = TaskEditor(db, task=None, parent=parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            task = dlg.get_task()
            task_id = db.insert_task(task)
            task.id = task_id
            # 保存标签
            _save_tags_for_task(db, task_id, dlg._tag_manager.get_tags())
            return task
        return None

    @staticmethod
    def edit(db: Database, task_id: int, parent=None) -> Task | None:
        """打开编辑任务对话框，返回更新后的 Task 或 None"""
        task = db.get_task(task_id)
        if task is None:
            QMessageBox.critical(
                parent, "错误", f"找不到任务 (id={task_id})"
            )
            return None

        dlg = TaskEditor(db, task=task, parent=parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_task()
            db.update_task(updated)
            # 保存标签
            _save_tags_for_task(db, task_id, dlg._tag_manager.get_tags())
            return updated
        return None
