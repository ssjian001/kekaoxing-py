"""样品批量导入对话框 — 从 Excel 文件导入样品数据。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox,
    QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from src.views.dialogs.base_dialog import _BaseDialog
from src.styles.theme import (
    CRUST, MANTLE, BASE, SURFACE0, SURFACE1, SURFACE2,
    TEXT, SUBTEXT0, SUBTEXT1, GREEN, YELLOW, RED, BLUE, PEACH, LAVENDER,
)
from src.styles.constants import TABLE_QSS


class BatchImportDialog(_BaseDialog):
    """样品批量导入 Excel 对话框。

    流程：
    1. 选择 Excel 文件
    2. 预览前 20 行数据
    3. 配置列映射（Excel 列 → Sample 字段）
    4. 确认导入
    5. 显示导入结果统计
    """

    # Sample 可映射字段：显示名 → 字段名
    _FIELD_MAP = [
        ("SN（必填）", "sn"),
        ("批次号", "batch_no"),
        ("规格", "spec"),
        ("存放位置", "location"),
        ("备注", "notes"),
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        on_import: Callable[[list[dict]], tuple[int, int]] | None = None,
    ) -> None:
        super().__init__("📥 批量导入样品", parent=parent, width=800)
        self._on_import = on_import
        self._wb_path: Path | None = None
        self._headers: list[str] = []
        self._rows: list[list[str]] = []
        self._imported = False

        # 隐藏默认 OK/Cancel 按钮栏
        self._btn_box.setVisible(False)

        self._build_ui()

    # ── UI 构建 ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 1. 文件选择区
        file_bar = QHBoxLayout()
        self._lbl_file = QLabel("未选择文件")
        self._lbl_file.setStyleSheet(f"color: {SUBTEXT0}; font-size: 13px;")
        file_bar.addWidget(self._lbl_file, 1)

        self._btn_browse = QPushButton("📂 选择 Excel 文件")
        self._btn_browse.setStyleSheet(
            f"QPushButton {{ background-color: {BLUE}; color: {CRUST}; "
            f"border: none; border-radius: 6px; padding: 8px 16px; "
            f"font-weight: bold; font-size: 13px; }}"
        )
        self._btn_browse.clicked.connect(self._on_browse)
        file_bar.addWidget(self._btn_browse)
        self._root.addLayout(file_bar)

        # 2. 列映射区（初始隐藏）
        self._mapping_widget = QWidget()
        mapping_layout = QVBoxLayout(self._mapping_widget)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        mapping_layout.setSpacing(8)

        lbl_map = QLabel("📌 列映射 — 请为每个字段选择对应的 Excel 列")
        lbl_map.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: bold;")
        mapping_layout.addWidget(lbl_map)

        self._combos: dict[str, QComboBox] = {}
        for display_name, field_name in self._FIELD_MAP:
            row = QHBoxLayout()
            required = " *" if field_name == "sn" else ""
            lbl = QLabel(f"{display_name}{required}:")
            lbl.setFixedWidth(140)
            lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
            if required:
                lbl.setStyleSheet(f"color: {PEACH}; font-size: 13px;")
            row.addWidget(lbl)

            combo = QComboBox()
            combo.setMinimumWidth(200)
            combo.addItem("— 不导入 —", None)
            combo.setStyleSheet(
                f"QComboBox {{ background-color: {SURFACE0}; color: {TEXT}; "
                f"border: 1px solid {SURFACE1}; border-radius: 6px; "
                f"padding: 6px 10px; font-size: 13px; min-height: 28px; }}"
            )
            row.addWidget(combo, 1)
            self._combos[field_name] = combo
            mapping_layout.addLayout(row)

        self._mapping_widget.setVisible(False)
        self._root.addWidget(self._mapping_widget)

        # 3. 预览表格
        lbl_preview = QLabel("📊 数据预览（前 20 行）")
        lbl_preview.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: bold;")
        self._root.addWidget(lbl_preview)

        self._preview_table = QTableWidget()
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._preview_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview_table.verticalHeader().setVisible(False)
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._preview_table.setStyleSheet(TABLE_QSS.format(
            bg=BASE, text=TEXT, gridline=SURFACE1,
            alt_row=MANTLE, header_bg=SURFACE0, header_text=TEXT,
            font_size=12,
        ))
        self._root.addWidget(self._preview_table, 1)

        # 4. 结果统计（初始隐藏）
        self._lbl_result = QLabel("")
        self._lbl_result.setWordWrap(True)
        self._lbl_result.setVisible(False)
        self._root.addWidget(self._lbl_result)

        # 5. 底部按钮栏
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self._btn_import = QPushButton("📥 开始导入")
        self._btn_import.setStyleSheet(
            f"QPushButton {{ background-color: {GREEN}; color: {CRUST}; "
            f"border: none; border-radius: 6px; padding: 8px 24px; "
            f"font-weight: bold; font-size: 14px; }}"
            f"QPushButton:disabled {{ background-color: {SURFACE0}; color: {SUBTEXT0}; }}"
        )
        self._btn_import.setEnabled(False)
        self._btn_import.clicked.connect(self._on_import_clicked)
        btn_bar.addWidget(self._btn_import)

        self._btn_close = QPushButton("关闭")
        self._btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {SURFACE1}; color: {TEXT}; "
            f"border: none; border-radius: 6px; padding: 8px 24px; "
            f"font-weight: bold; font-size: 14px; }}"
        )
        self._btn_close.clicked.connect(self._on_close)
        btn_bar.addWidget(self._btn_close)

        self._root.addLayout(btn_bar)

    # ── 事件处理 ─────────────────────────────────────────────────

    def _on_browse(self) -> None:
        """打开文件选择器。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Excel 文件",
            "",
            "Excel 文件 (*.xlsx *.xls);;所有文件 (*)",
        )
        if not path:
            return
        self._wb_path = Path(path)
        self._lbl_file.setText(f"📄 {self._wb_path.name}")
        self._lbl_file.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        self._load_preview()

    def _load_preview(self) -> None:
        """读取 Excel 文件并显示预览。"""
        if not self._wb_path:
            return

        try:
            import openpyxl

            wb = openpyxl.load_workbook(self._wb_path, read_only=True, data_only=True)
            ws = wb.active
            if ws is None:
                QMessageBox.warning(self, "错误", "无法读取工作表")
                return

            rows_iter = ws.iter_rows(values_only=True)
            # 读取表头
            first_row = next(rows_iter, None)
            if first_row is None:
                QMessageBox.warning(self, "错误", "Excel 文件为空")
                wb.close()
                return

            self._headers = [str(c or "") if c is not None else "" for c in first_row]
            self._rows = []
            for row in rows_iter:
                self._rows.append([str(c) if c is not None else "" for c in row])

            wb.close()
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"无法读取 Excel 文件：\n{e}")
            return

        # 填充列映射下拉框
        col_options = ["— 不导入 —"] + self._headers
        for field_name, combo in self._combos.items():
            combo.clear()
            for opt in col_options:
                combo.addItem(opt, None if opt == "— 不导入 —" else opt)

        # 自动匹配：根据表头文字猜测
        for field_name, combo in self._combos.items():
            guessed_idx = self._guess_column(field_name)
            if guessed_idx >= 0:
                combo.setCurrentIndex(guessed_idx + 1)  # +1 因为第一个是 "不导入"

        self._mapping_widget.setVisible(True)

        # 填充预览表格
        preview_rows = self._rows[:20]
        self._preview_table.setColumnCount(len(self._headers))
        self._preview_table.setRowCount(len(preview_rows))
        self._preview_table.setHorizontalHeaderLabels(self._headers)
        for r, row_data in enumerate(preview_rows):
            for c, val in enumerate(row_data):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._preview_table.setItem(r, c, item)

        self._btn_import.setEnabled(True)

    def _guess_column(self, field_name: str) -> int:
        """根据字段名猜测对应的 Excel 列索引，返回 -1 表示未找到。"""
        keywords = {
            "sn": ["sn", "序列号", "序列", "serial", "serial number", "编号"],
            "batch_no": ["batch", "批次", "批次号", "batch_no", "batch no"],
            "spec": ["spec", "规格", "规格型号", "型号", "model"],
            "location": ["location", "位置", "存放", "存放位置", "库位"],
            "notes": ["notes", "备注", "说明", "描述", "remark"],
        }
        guesses = keywords.get(field_name, [])
        for idx, header in enumerate(self._headers):
            h_lower = header.strip().lower()
            for kw in guesses:
                if kw in h_lower:
                    return idx
        return -1

    def _on_import_clicked(self) -> None:
        """执行批量导入。"""
        if self._imported:
            return

        # 获取映射
        mapping: dict[str, str] = {}
        for field_name, combo in self._combos.items():
            col_header = combo.currentData()
            if col_header is not None:
                mapping[field_name] = col_header

        # SN 必须映射
        if "sn" not in mapping:
            QMessageBox.warning(self, "缺少映射", "请为「SN（必填）」选择对应的 Excel 列")
            return

        # 构建 header → index 映射
        header_to_idx: dict[str, int] = {}
        for idx, h in enumerate(self._headers):
            header_to_idx[h.strip()] = idx

        # 构建 field → col_idx
        field_to_col: dict[str, int] = {}
        for field_name, col_header in mapping.items():
            col_idx: int | None = header_to_idx.get(col_header.strip())
            if col_idx is None:
                QMessageBox.warning(
                    self, "映射错误",
                    f"列「{col_header}」在 Excel 中未找到",
                )
                return
            field_to_col[field_name] = col_idx

        # 解析数据
        sample_list: list[dict] = []
        for row in self._rows:
            data: dict = {}
            # SN 为空则跳过
            sn_idx = field_to_col["sn"]
            sn_val = (row[sn_idx] or "").strip()
            if not sn_val:
                continue

            data["sn"] = sn_val
            for fname in ("batch_no", "spec", "location", "notes"):
                if fname in field_to_col:
                    col_idx = field_to_col[fname]
                    data[fname] = (row[col_idx] or "").strip() if col_idx < len(row) else ""

            sample_list.append(data)

        if not sample_list:
            QMessageBox.information(self, "无数据", "没有可导入的样品数据（SN 为空）")
            return

        # 禁用按钮，显示进度
        self._btn_import.setEnabled(False)
        self._btn_import.setText("⏳ 导入中…")

        # 调用导入回调
        if self._on_import:
            try:
                success_count, skip_count = self._on_import(sample_list)
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入过程中出错：\n{e}")
                self._btn_import.setEnabled(True)
                self._btn_import.setText("📥 开始导入")
                return
        else:
            # 没有回调，仅显示解析结果
            success_count = len(sample_list)
            skip_count = 0

        self._imported = True
        self._btn_import.setText("✅ 导入完成")
        self._btn_close.setText("关闭")

        # 显示结果统计
        self._lbl_result.setVisible(True)
        self._lbl_result.setText(
            f"📊 导入完成！\n"
            f"  ✅ 成功导入：{success_count} 条\n"
            f"  ⏭️ 跳过（重复 SN）：{skip_count} 条\n"
            f"  📋 总计解析：{len(sample_list)} 条"
        )
        if skip_count > 0:
            self._lbl_result.setStyleSheet(
                f"color: {YELLOW}; font-size: 14px; padding: 8px; "
                f"background-color: {SURFACE0}; border-radius: 6px;"
            )
        else:
            self._lbl_result.setStyleSheet(
                f"color: {GREEN}; font-size: 14px; padding: 8px; "
                f"background-color: {SURFACE0}; border-radius: 6px;"
            )

    def _on_close(self) -> None:
        """关闭对话框。"""
        self.done(1 if self._imported else 0)

    # ── 公开方法 ─────────────────────────────────────────────────

    def was_imported(self) -> bool:
        """返回是否有数据被成功导入。"""
        return self._imported

    def get_result(self) -> tuple[int, int]:
        """返回 (成功数, 跳过数)。"""
        return (0, 0)
