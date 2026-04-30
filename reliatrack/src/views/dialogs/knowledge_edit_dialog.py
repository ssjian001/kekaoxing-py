"""知识库编辑弹窗 — 新建 / 编辑 KnowledgeEntry。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
)

from src.models.knowledge import KnowledgeEntry
from src.views.dialogs.base_dialog import _BaseDialog


class KnowledgeEditDialog(_BaseDialog):
    """知识库新建 / 编辑弹窗。

    Parameters
    ----------
    entry:
        若为 None 则为新建模式，否则为编辑模式并预填数据。
    """

    _CATEGORIES = [
        "元器件", "结构", "软件", "工艺", "材料", "环境", "其他",
    ]

    def __init__(
        self,
        entry: KnowledgeEntry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        is_edit = entry is not None
        super().__init__(
            "✏️ 编辑知识条目" if is_edit else "➕ 新增知识条目",
            parent,
            width=520,
        )
        self._entry = entry

        # ── 基本信息 ──
        self._category_combo = self._add_combo_field(
            "类别",
            items=self._CATEGORIES,
            default=entry.category if entry else self._CATEGORIES[0],
            editable=True,
            placeholder="选择或输入类别",
        )
        self._failure_mode_edit = self._add_text_field(
            "失效模式 *",
            default=entry.failure_mode if entry else "",
            placeholder="必填，如：焊点开裂、电容短路…",
        )
        self._reference_edit = self._add_text_field(
            "参考标准",
            default=entry.reference_standard if entry else "",
            placeholder="如：IPC-A-610, JEDEC…",
        )

        self._add_separator()

        # ── 分析 ──
        self._cause_area = self._add_text_area(
            "原因分析",
            default=entry.cause_analysis if entry else "",
        )
        self._improvement_area = self._add_text_area(
            "改进措施",
            default=entry.improvement if entry else "",
        )

        self._add_separator()

        # ── 关键词 & 深度分析 ──
        self._keywords_edit = self._add_text_field(
            "关键词",
            default=entry.keywords if entry else "",
            placeholder="逗号分隔，如：焊接, 热应力, PCB",
        )
        self._summary_area = self._add_text_area(
            "摘要",
            default=entry.summary if entry else "",
        )
        self._root_cause_area = self._add_text_area(
            "根因",
            default=entry.root_cause if entry else "",
        )
        self._resolution_area = self._add_text_area(
            "解决方案",
            default=entry.resolution if entry else "",
        )

    # ── 公开 API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """返回表单数据字典。"""
        return {
            "category": self._category_combo.currentText().strip(),
            "failure_mode": self._failure_mode_edit.text().strip(),
            "cause_analysis": self._cause_area.toPlainText().strip(),
            "improvement": self._improvement_area.toPlainText().strip(),
            "reference_standard": self._reference_edit.text().strip(),
            "keywords": self._keywords_edit.text().strip(),
            "summary": self._summary_area.toPlainText().strip(),
            "root_cause": self._root_cause_area.toPlainText().strip(),
            "resolution": self._resolution_area.toPlainText().strip(),
        }

    # ── 校验 ───────────────────────────────────────────────────

    def accept(self) -> None:
        """覆盖 accept 以校验必填字段。"""
        data = self.get_data()
        if not data["failure_mode"]:
            QMessageBox.warning(self, "校验失败", "失效模式为必填项，请输入。")
            self._failure_mode_edit.setFocus()
            return

        super().accept()
