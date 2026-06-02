"""样品批量编辑弹窗 — 同时修改多个样品的选定字段。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from src.models.sample import Sample
from src.views.dialogs.base_dialog import _BaseDialog
from src.constants import (
    SAMPLE_STATUS_OPTIONS,
    SAMPLE_STATUS_MAP,
    SAMPLE_STATUS_REVERSE,
)


class BatchEditSampleDialog(_BaseDialog):
    """样品批量编辑弹窗。

    每个可编辑字段前有 QCheckBox，勾选 = "要修改这个字段"。
    未勾选的字段灰化(disabled)，get_changes() 只返回勾选项。

    Parameters
    ----------
    samples : list[Sample]
        要批量编辑的样品列表（至少 1 个）。
    project_list : list
        项目列表（用于关联项目下拉框）。
    """

    _STATUS_OPTIONS = SAMPLE_STATUS_OPTIONS
    _STATUS_MAP = SAMPLE_STATUS_MAP
    _STATUS_REVERSE = SAMPLE_STATUS_REVERSE

    def __init__(
        self,
        samples: list[Sample],
        project_list: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            f"批量编辑（已选 {len(samples)} 个样品）",
            parent,
            width=480,
        )
        self._samples = samples
        self._project_list = project_list or []
        self._field_widgets: dict[str, tuple[QCheckBox, QWidget]] = {}

        # ── 提示 ──
        hint = QLabel("勾选要修改的字段，未勾选的字段保持原值不变。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 4px;")
        self._form.addRow(hint)

        # ── 可批量编辑的字段 ──

        self._add_check_field(
            "batch_no", "批次号",
            self._add_text_field("批次号", placeholder="留空 = 清空"),
        )

        self._add_check_field(
            "spec", "规格",
            self._add_text_field("规格", placeholder="如：DIP-14"),
        )

        self._add_check_field(
            "supplier", "供应商",
            self._add_text_field("供应商", placeholder="如：村田/TDK"),
        )

        # 关联项目
        project_names = ["（无）"]
        project_names += [f"{p.name}" for p in self._project_list]
        project_combo = self._add_combo_field("关联项目", items=project_names)
        self._add_check_field("project_id", "关联项目", project_combo)

        self._add_separator()

        # 状态
        status_combo = self._add_combo_field(
            "状态", items=self._STATUS_OPTIONS,
        )
        self._add_check_field("status", "状态", status_combo)

        # 报废原因（条件显示）
        scrapped_edit = self._add_text_field(
            "报废原因", placeholder="状态选「已报废」时必填",
        )
        self._add_check_field("scrapped_reason", "报废原因", scrapped_edit)

        self._add_separator()

        self._add_check_field(
            "location", "位置",
            self._add_text_field("位置", placeholder="如：A区-01柜"),
        )

        # 备注
        notes_edit = self._add_text_area("备注", placeholder="留空 = 清空")
        self._add_check_field("notes", "备注", notes_edit)

        # 状态→报废原因联动
        status_combo.currentTextChanged.connect(
            lambda text: self._on_status_changed(text, scrapped_edit)
        )

    # ── 内部辅助 ──────────────────────────────────────────────

    def _add_check_field(
        self, field_name: str, label_text: str, widget: QWidget,
    ) -> None:
        """将 (field_name, (checkbox, widget)) 注册到 _field_widgets。

        把 checkbox 和 widget 放在同一个 row 中：
        checkbox 替换 label 位置，widget 保持 field 位置。
        """
        cb = QCheckBox()
        cb.setToolTip(f"勾选以修改「{label_text}」")

        # 禁用 widget 直到 checkbox 被勾选
        widget.setEnabled(False)
        cb.toggled.connect(widget.setEnabled)

        # 用自定义 row 替代标准 addRow(label, widget)
        # 取消 base_dialog 中已添加的 row，改为带 checkbox 的版本
        # 由于 _add_text_field 等已经 addRow 了，我们需要改布局策略
        # 替代方案：在 field widget 前插入 checkbox
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(cb)
        row_layout.addWidget(widget, stretch=1)

        # 替换最后一行
        # 找到 form 中最后一行的 field item，将其替换
        last_row = self._form.rowCount() - 1
        # 移除原有 field widget（不让 Qt 删除）
        old_item = self._form.itemAt(last_row, self._form.ItemRole.FieldRole)
        if old_item and old_item.widget():
            self._form.removeWidget(old_item.widget())
            old_item.widget().setParent(row_widget)  # reparent
        # 设置新的 field
        self._form.setWidget(last_row, self._form.ItemRole.FieldRole, row_widget)

        self._field_widgets[field_name] = (cb, widget)

    def _on_status_changed(self, status_text: str, scrapped_edit: QWidget) -> None:
        """状态选"已报废"时自动勾选并启用报废原因。"""
        if status_text == "已报废":
            cb, _ = self._field_widgets.get("scrapped_reason", (None, None))
            if cb:
                cb.setChecked(True)
            scrapped_edit.setEnabled(True)
            scrapped_edit.setFocus()

    # ── 公开 API ──────────────────────────────────────────────

    def get_changes(self) -> dict:
        """返回勾选字段的变更字典。

        Returns
        -------
        dict
            只包含被勾选的字段及其新值。例如：
            {"batch_no": "B2026-001", "status": "in_stock"}
        """
        result: dict = {}

        # 文本字段
        for fname in ("batch_no", "spec", "supplier", "location", "scrapped_reason"):
            cb, widget = self._field_widgets.get(fname, (None, None))
            if cb and cb.isChecked() and isinstance(widget, QWidget):
                # 找到 widget 内部的 QLineEdit
                line_edit = self._find_line_edit(widget)
                if line_edit:
                    result[fname] = line_edit.text().strip()

        # 备注字段 (QTextEdit)
        cb, widget = self._field_widgets.get("notes", (None, None))
        if cb and cb.isChecked():
            text_edit = self._find_text_edit(widget)
            if text_edit:
                result["notes"] = text_edit.toPlainText().strip()

        # 状态字段 (QComboBox)
        cb, widget = self._field_widgets.get("status", (None, None))
        if cb and cb.isChecked():
            combo = self._find_combo(widget)
            if combo:
                result["status"] = self._STATUS_MAP.get(
                    combo.currentText(), "in_stock"
                )

        # 关联项目 (QComboBox)
        cb, widget = self._field_widgets.get("project_id", (None, None))
        if cb and cb.isChecked():
            combo = self._find_combo(widget)
            if combo:
                proj_text = combo.currentText()
                project_id = None
                if proj_text != "（无）":
                    for p in self._project_list:
                        if p.name == proj_text:
                            project_id = p.id
                            break
                result["project_id"] = project_id

        return result

    def get_preview_text(self) -> str:
        """生成预览摘要文本。"""
        changes = self.get_changes()
        if not changes:
            return "未勾选任何字段。"

        _LABELS = {
            "batch_no": "批次号",
            "spec": "规格",
            "supplier": "供应商",
            "project_id": "关联项目",
            "status": "状态",
            "scrapped_reason": "报废原因",
            "location": "位置",
            "notes": "备注",
        }
        lines = []
        for field, value in changes.items():
            label = _LABELS.get(field, field)
            if value is None:
                display = "（无）"
            elif isinstance(value, str) and len(value) > 30:
                display = value[:30] + "…"
            else:
                display = str(value)
            lines.append(f"  • {label} → {display}")
        return "\n".join(lines)

    def _find_line_edit(self, widget: QWidget):
        """从容器中找到 QLineEdit。"""
        from PySide6.QtWidgets import QLineEdit
        if isinstance(widget, QLineEdit):
            return widget
        for child in widget.findChildren(QLineEdit):
            return child
        return None

    def _find_text_edit(self, widget: QWidget):
        """从容器中找到 QTextEdit。"""
        if isinstance(widget, QTextEdit):
            return widget
        for child in widget.findChildren(QTextEdit):
            return child
        return None

    def _find_combo(self, widget: QWidget):
        """从容器中找到 QComboBox。"""
        from PySide6.QtWidgets import QComboBox
        if isinstance(widget, QComboBox):
            return widget
        for child in widget.findChildren(QComboBox):
            return child
        return None

    # ── 校验 ──────────────────────────────────────────────────

    def accept(self) -> None:
        """校验：至少勾选一个字段，报废状态需填写原因。"""
        changes = self.get_changes()
        if not changes:
            QMessageBox.warning(self, "提示", "请至少勾选一个要修改的字段。")
            return

        # 报废状态校验
        if changes.get("status") == "scrapped":
            reason = changes.get("scrapped_reason", "").strip()
            if not reason:
                QMessageBox.warning(
                    self, "校验失败", "状态为「已报废」时，报废原因不能为空。",
                )
                return

        # 预览确认
        preview = self.get_preview_text()
        confirm = QMessageBox.question(
            self,
            "确认批量修改",
            f"即将修改 {len(self._samples)} 个样品的以下字段：\n\n"
            f"{preview}\n\n"
            f"确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        super().accept()
