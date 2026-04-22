"""任务模板库对话框 — 预置可靠性测试常用模板 + 用户自定义模板，一键添加任务到项目。"""

from __future__ import annotations

import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QScrollArea, QWidget, QGridLayout, QPushButton, QLabel,
    QInputDialog, QMessageBox, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

from src.models import Section, Task


# ── 预置模板数据 ────────────────────────────────────────────────────────────

BUILTIN_TEMPLATES = [
    {
        "category": "环境测试",
        "icon": "🌡️",
        "templates": [
            {"name_cn": "高低温循环试验", "name_en": "High-Low Temperature Cycle", "section": "env", "duration": 7, "sample_qty": 3, "priority": 3, "notes": "温度范围 -40°C~85°C，循环100次"},
            {"name_cn": "恒温恒湿试验", "name_en": "Temperature & Humidity", "section": "env", "duration": 5, "sample_qty": 3, "priority": 3, "notes": "温度 85°C，湿度 85% RH"},
            {"name_cn": "冷热冲击试验", "name_en": "Thermal Shock", "section": "env", "duration": 3, "sample_qty": 3, "priority": 4, "notes": "-40°C ↔ 125°C，转换时间≤15s"},
            {"name_cn": "盐雾试验", "name_en": "Salt Spray", "section": "env", "duration": 14, "sample_qty": 3, "priority": 3, "notes": "连续盐雾 5% NaCl"},
            {"name_cn": "紫外老化试验", "name_en": "UV Aging", "section": "env", "duration": 10, "sample_qty": 2, "priority": 2, "notes": "UVA-340，辐照度 0.89 W/m²"},
            {"name_cn": "IP防护等级测试", "name_en": "IP Protection Test", "section": "env", "duration": 3, "sample_qty": 5, "priority": 3, "notes": "按 IP67 标准测试"},
        ],
    },
    {
        "category": "机械测试",
        "icon": "⚙️",
        "templates": [
            {"name_cn": "振动试验", "name_en": "Vibration Test", "section": "mech", "duration": 5, "sample_qty": 3, "priority": 3, "notes": "随机振动 10-500Hz"},
            {"name_cn": "跌落试验", "name_en": "Drop Test", "section": "mech", "duration": 2, "sample_qty": 5, "priority": 3, "notes": "1m 高度，6面3棱1角"},
            {"name_cn": "冲击试验", "name_en": "Impact Test", "section": "mech", "duration": 2, "sample_qty": 3, "priority": 3, "notes": "半正弦波，30g/11ms"},
            {"name_cn": "按键寿命测试", "name_en": "Button Life Test", "section": "mech", "duration": 10, "sample_qty": 3, "priority": 2, "notes": "≥50万次"},
            {"name_cn": "插拔寿命测试", "name_en": "Connector Durability", "section": "mech", "duration": 7, "sample_qty": 5, "priority": 2, "notes": "USB/Type-C ≥10000次"},
            {"name_cn": "扭曲试验", "name_en": "Twist Test", "section": "mech", "duration": 3, "sample_qty": 3, "priority": 2, "notes": "±15° 扭曲角度"},
        ],
    },
    {
        "category": "表面/材料测试",
        "icon": "🎨",
        "templates": [
            {"name_cn": "色牢度测试", "name_en": "Color Fastness", "section": "surf", "duration": 3, "sample_qty": 3, "priority": 2, "notes": "摩擦/光照/水洗"},
            {"name_cn": "耐磨测试", "name_en": "Abrasion Test", "section": "surf", "duration": 5, "sample_qty": 3, "priority": 2, "notes": "Taber 磨耗机，CS-10 轮"},
            {"name_cn": "百格测试", "name_en": "Cross-cut Adhesion", "section": "surf", "duration": 2, "sample_qty": 3, "priority": 3, "notes": "100 格刀，3M 胶带"},
            {"name_cn": "耐化学测试", "name_en": "Chemical Resistance", "section": "surf", "duration": 3, "sample_qty": 3, "priority": 2, "notes": "酒精/汗液/化妆品擦拭"},
            {"name_cn": "光泽度测试", "name_en": "Gloss Test", "section": "surf", "duration": 1, "sample_qty": 3, "priority": 2, "notes": "60° 光泽仪"},
        ],
    },
    {
        "category": "包装测试",
        "icon": "📦",
        "templates": [
            {"name_cn": "包装跌落试验", "name_en": "Package Drop Test", "section": "pack", "duration": 2, "sample_qty": 3, "priority": 3, "notes": "ISTA 1A 标准"},
            {"name_cn": "振动模拟试验", "name_en": "Vibration Simulation", "section": "pack", "duration": 3, "sample_qty": 2, "priority": 3, "notes": "随机振动模拟运输"},
            {"name_cn": "压力测试", "name_en": "Compression Test", "section": "pack", "duration": 2, "sample_qty": 3, "priority": 2, "notes": "堆码压力测试"},
        ],
    },
]


# ── 深色主题常量 ────────────────────────────────────────────────────────────

DARK_BG       = "#11111b"
CARD_BG       = "#181825"
TEXT_PRIMARY  = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
BORDER_COLOR  = "#313244"
PRIMARY_COLOR = "#89b4fa"
ADDED_BG      = "#1e1e2e"
ADDED_TEXT    = "#585b70"


# ── 对话框 ──────────────────────────────────────────────────────────────────

class TemplateLibraryDialog(QDialog):
    """任务模板库对话框：左侧分类导航 + 右侧模板卡片网格。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.added_count: int = 0
        # 已添加模板的标识集合: (category, name_cn)
        self._added_keys: set[tuple[str, str]] = set()
        # 所有分类（内置 + 自定义），每个元素结构同 BUILTIN_TEMPLATES 中的 dict
        self._categories: list[dict] = []

        self._load_custom_templates()
        self._categories = list(BUILTIN_TEMPLATES) + self._custom_categories

        self.setWindowTitle("📚 任务模板库")
        self.setMinimumSize(820, 580)
        self.resize(860, 620)
        self._setup_ui()
        self._apply_stylesheet()
        self._populate_categories()
        # 默认选中第一个分类
        if self._category_list.count() > 0:
            self._category_list.setCurrentRow(0)

    # ── 自定义模板读写 ─────────────────────────────

    def _get_custom_categories(self) -> list[dict]:
        """从数据库读取自定义模板分类列表。"""
        raw = self.db.get_setting("custom_templates", "")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _save_custom_templates(self):
        """将自定义模板分类列表写回数据库。"""
        self.db.set_setting("custom_templates", json.dumps(self._custom_categories, ensure_ascii=False))

    def _load_custom_templates(self):
        """加载自定义模板（内部方法，初始化时调用）。"""
        self._custom_categories = self._get_custom_categories_from_db()

    def _get_custom_categories_from_db(self) -> list[dict]:
        raw = self.db.get_setting("custom_templates", "")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    # ── UI 构建 ───────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(48)
        title_bar.setStyleSheet(f"background:{CARD_BG}; border-bottom:1px solid {BORDER_COLOR};")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        title_label = QLabel("📚 任务模板库")
        title_label.setStyleSheet(f"font-size:16px; font-weight:bold; color:{TEXT_PRIMARY};")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 摘要信息
        self._summary_label = QLabel("已添加 0 个模板")
        self._summary_label.setStyleSheet(f"font-size:12px; color:{TEXT_SECONDARY};")
        title_layout.addWidget(self._summary_label)
        outer.addWidget(title_bar)

        # 内容区域
        content = QHBoxLayout()
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(12)

        # ── 左侧分类列表 ──
        left_panel = QVBoxLayout()
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(8)

        self._category_list = QListWidget()
        self._category_list.setFixedWidth(200)
        self._category_list.setIconSize(QSize(24, 24))
        self._category_list.currentRowChanged.connect(self._on_category_changed)
        left_panel.addWidget(self._category_list)

        # 添加分类按钮
        self._btn_add_category = QPushButton("＋ 新建分类")
        self._btn_add_category.setFixedHeight(36)
        self._btn_add_category.setObjectName("secondaryBtn")
        self._btn_add_category.clicked.connect(self._on_add_category)
        left_panel.addWidget(self._btn_add_category)

        content.addLayout(left_panel)

        # ── 右侧模板区域 ──
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(8)

        # 滚动区域
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(10)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._scroll.setWidget(self._cards_container)
        right_panel.addWidget(self._scroll)

        # 底部全部添加按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_add_all = QPushButton("📥 全部添加")
        self._btn_add_all.setFixedHeight(36)
        self._btn_add_all.setMinimumWidth(120)
        self._btn_add_all.setObjectName("primaryBtn")
        self._btn_add_all.clicked.connect(self._on_add_all)
        btn_row.addWidget(self._btn_add_all)
        right_panel.addLayout(btn_row)

        content.addLayout(right_panel, 1)
        outer.addLayout(content, 1)

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {DARK_BG};
            }}
            QListWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 6px;
                color: {TEXT_PRIMARY};
                font-size: 13px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 8px;
                border-radius: 6px;
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background: {PRIMARY_COLOR}22;
                color: {PRIMARY_COLOR};
            }}
            QListWidget::item:hover {{
                background: {BORDER_COLOR}88;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {CARD_BG};
                width: 8px;
                border-radius: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_COLOR};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QPushButton {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 14px;
                background: {CARD_BG};
                color: {TEXT_PRIMARY};
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {PRIMARY_COLOR};
                background: {PRIMARY_COLOR}22;
            }}
            QPushButton#primaryBtn {{
                background: {PRIMARY_COLOR};
                color: {DARK_BG};
                font-weight: bold;
                border: none;
                padding: 8px 20px;
            }}
            QPushButton#primaryBtn:hover {{
                background: {PRIMARY_COLOR}cc;
            }}
            QPushButton#secondaryBtn {{
                background: transparent;
                border: 1px dashed {TEXT_SECONDARY};
                color: {TEXT_SECONDARY};
            }}
            QPushButton#secondaryBtn:hover {{
                border-color: {PRIMARY_COLOR};
                color: {PRIMARY_COLOR};
            }}
            QPushButton#addedBtn {{
                background: {ADDED_BG};
                color: {ADDED_TEXT};
                border: 1px solid {BORDER_COLOR};
            }}
            QPushButton#addedBtn:hover {{
                background: {ADDED_BG};
                border-color: {BORDER_COLOR};
            }}
            QPushButton#cardAddBtn {{
                background: {PRIMARY_COLOR}22;
                color: {PRIMARY_COLOR};
                border: 1px solid {PRIMARY_COLOR}44;
                font-size: 12px;
                padding: 4px 10px;
                border-radius: 4px;
            }}
            QPushButton#cardAddBtn:hover {{
                background: {PRIMARY_COLOR}44;
            }}
            QPushButton#cardAddBtn:disabled {{
                background: {ADDED_BG};
                color: {ADDED_TEXT};
                border: 1px solid {BORDER_COLOR};
            }}
        """)

    # ── 分类列表 ───────────────────────────────────

    def _populate_categories(self):
        """填充左侧分类列表。"""
        self._category_list.clear()
        for cat in self._categories:
            count = len(cat["templates"])
            text = f'{cat["icon"]}  {cat["category"]}  ({count})'
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, cat["category"])
            self._category_list.addItem(item)

    def _on_category_changed(self, row: int):
        """切换分类时刷新右侧卡片。"""
        if row < 0 or row >= len(self._categories):
            return
        cat = self._categories[row]
        self._show_template_cards(cat["category"], cat["templates"])

    # ── 模板卡片 ───────────────────────────────────

    def _clear_cards(self):
        """清除所有卡片 widget。"""
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _show_template_cards(self, category: str, templates: list[dict]):
        """在右侧网格中展示模板卡片。"""
        self._clear_cards()

        col = 0
        row = 0
        for tpl in templates:
            card = self._create_card(category, tpl)
            self._cards_layout.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        # 设置列拉伸
        for c in range(2):
            self._cards_layout.setColumnStretch(c, 1)

    def _create_card(self, category: str, tpl: dict) -> QFrame:
        """创建单个模板卡片。"""
        card = QFrame()
        card.setFixedHeight(150)
        card.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 10px;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        # 中文名（粗体）+ 英文名（小字）
        name_label = QLabel(tpl["name_cn"])
        name_label.setStyleSheet(f"font-size:14px; font-weight:bold; color:{TEXT_PRIMARY};")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        en_label = QLabel(tpl.get("name_en", ""))
        en_label.setStyleSheet(f"font-size:11px; color:{TEXT_SECONDARY};")
        en_label.setWordWrap(True)
        layout.addWidget(en_label)

        # 信息行
        duration = tpl.get("duration", 1)
        sample_qty = tpl.get("sample_qty", 3)
        priority = tpl.get("priority", 3)
        notes = tpl.get("notes", "")
        if len(notes) > 20:
            notes = notes[:20] + "…"
        info_text = f"⏱ {duration}天  ·  📦 {sample_qty}件  ·  🔴 P{priority}"
        if notes:
            info_text += f"  ·  💬 {notes}"
        info_label = QLabel(info_text)
        info_label.setStyleSheet(f"font-size:11px; color:{TEXT_SECONDARY};")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        # 添加按钮
        key = (category, tpl["name_cn"])
        if key in self._added_keys:
            btn = QPushButton("✅ 已添加")
            btn.setObjectName("addedBtn")
            btn.setEnabled(False)
        else:
            btn = QPushButton("➕ 添加")
            btn.setObjectName("cardAddBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=category, t=tpl: self._on_add_one(c, t))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        return card

    # ── 添加任务逻辑 ───────────────────────────────

    def _on_add_one(self, category: str, tpl: dict):
        """添加单个模板到项目。"""
        key = (category, tpl["name_cn"])
        if key in self._added_keys:
            return
        try:
            self._insert_template_task(tpl)
            self._added_keys.add(key)
            self.added_count += 1
            self._update_summary()
            # 刷新当前分类的卡片以更新按钮状态
            row = self._category_list.currentRow()
            if 0 <= row < len(self._categories):
                cat = self._categories[row]
                if cat["category"] == category:
                    self._show_template_cards(cat["category"], cat["templates"])
        except Exception as e:
            QMessageBox.warning(self, "添加失败", f"添加任务失败：{e}")

    def _on_add_all(self):
        """添加当前分类下所有未添加的模板。"""
        row = self._category_list.currentRow()
        if row < 0 or row >= len(self._categories):
            return
        cat = self._categories[row]
        added_in_batch = 0
        for tpl in cat["templates"]:
            key = (cat["category"], tpl["name_cn"])
            if key in self._added_keys:
                continue
            try:
                self._insert_template_task(tpl)
                self._added_keys.add(key)
                self.added_count += 1
                added_in_batch += 1
            except Exception:
                pass
        if added_in_batch > 0:
            self._update_summary()
            self._show_template_cards(cat["category"], cat["templates"])

    def _insert_template_task(self, tpl: dict):
        """将模板数据转为 Task 并插入数据库。"""
        # 自动生成编号
        num = self._generate_task_num(tpl.get("section", "env"))
        section_val = tpl.get("section", "env")
        try:
            section = Section(section_val)
        except ValueError:
            section = section_val  # type: ignore[assignment]

        task = Task(
            id=0,
            num=num,
            name_en=tpl.get("name_en", ""),
            name_cn=tpl.get("name_cn", ""),
            section=section,
            duration=tpl.get("duration", 1),
            start_day=0,
            progress=0.0,
            priority=tpl.get("priority", 3),
            done=False,
            is_serial=False,
            serial_group="",
            sample_pool="product",
            sample_qty=tpl.get("sample_qty", 3),
            setup_time=0,
            teardown_time=0,
            dependencies=[],
            requirements=[],
            notes=tpl.get("notes", ""),
            created_at="",
            updated_at="",
        )
        self.db.insert_task(task)

    def _generate_task_num(self, section_key: str) -> str:
        """根据 section 和现有任务自动生成下一个编号。"""
        tasks = self.db.get_all_tasks()
        # 筛选同 section 的任务
        same_section_nums: list[tuple[int, int]] = []
        for t in tasks:
            s = t.section.value if isinstance(t.section, Section) else t.section
            if s == section_key:
                parts = t.num.split(".")
                try:
                    major = int(parts[0])
                    minor = int(parts[1]) if len(parts) > 1 else 0
                    same_section_nums.append((major, minor))
                except (ValueError, IndexError):
                    continue

        if not same_section_nums:
            # 此分类尚无任务，根据 section_key 分配主编号
            section_order = {"env": 1, "mech": 2, "surf": 3, "pack": 4}
            major = section_order.get(section_key, 5)
            return f"{major}.1"

        # 找到最大主编号
        max_major = max(m for m, _ in same_section_nums)
        # 找该主编号下的最大次编号
        max_minor = max(minor for m, minor in same_section_nums if m == max_major)
        return f"{max_major}.{max_minor + 1}"

    def _update_summary(self):
        """更新标题栏的已添加计数。"""
        self._summary_label.setText(f"已添加 {self.added_count} 个模板")

    # ── 自定义分类 ─────────────────────────────────

    def _on_add_category(self):
        """弹出对话框，让用户输入自定义分类名称。"""
        name, ok = QInputDialog.getText(
            self, "新建自定义分类", "请输入分类名称：",
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        # 检查重名
        for cat in self._categories:
            if cat["category"] == name:
                QMessageBox.warning(self, "提示", f"分类「{name}」已存在。")
                return

        new_cat = {
            "category": name,
            "icon": "📁",
            "templates": [],
            "_custom": True,
        }
        self._custom_categories.append(new_cat)
        self._save_custom_templates()
        self._categories = list(BUILTIN_TEMPLATES) + self._custom_categories
        self._populate_categories()
        # 选中新创建的分类
        self._category_list.setCurrentRow(self._category_list.count() - 1)

    # ── 关闭行为 ───────────────────────────────────

    def closeEvent(self, event):
        """关闭时，如果有模板被添加则返回 Accepted。"""
        if self.added_count > 0:
            self.setResult(QDialog.DialogCode.Accepted)
        else:
            self.setResult(QDialog.DialogCode.Rejected)
        super().closeEvent(event)
