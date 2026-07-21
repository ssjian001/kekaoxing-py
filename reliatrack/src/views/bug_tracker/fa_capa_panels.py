"""FA/CAPA 面板 — 從 issue_view.py 提取，供 BugListView 嵌入使用。

包含:
- FAPanel: FA 失效分析記錄面板（卡片式展示 + 編輯/刪除信號）
- CAPAPanel: CAPA 糾正預防措施面板（卡片式展示 + 編輯/刪除信號）
- CAPADialog: 新建/編輯 CAPA 彈窗（PDCA 擴展欄位）
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.models.issue import Issue, FARecord, CAPARecord
from src.views.dialogs.base_dialog import _BaseDialog


# ═══════════════════════════════════════════════════════════════
#  FAPanel — FA 失效分析記錄面板
# ═══════════════════════════════════════════════════════════════

class FAPanel(QScrollArea):
    """FA 分析記錄面板。"""

    fa_edit_requested = Signal(int)     # fa_record.id
    fa_delete_requested = Signal(int)   # fa_record.id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._records: list[FARecord] = []
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)
        self.setProperty("class", "issue-scroll")

    def refresh_theme(self) -> None:
        """主題切換回調 — 用當前數據重建卡片以刷新內聯顏色。"""
        self.set_fa_records(self._records)

    def set_fa_records(self, records: list[FARecord]) -> None:
        self._records = records
        # 清空
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        if not records:
            label = QLabel("選擇一個 Issue 查看 FA 分析記錄")
            label.setProperty("class", "subtext")
            self._layout.addWidget(label)
            return

        for i, rec in enumerate(records):
            card = QFrame()
            card.setProperty("class", "issue-card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # 標題行
            header = QHBoxLayout()
            step_label = QLabel(f"Step {rec.step_no}")
            step_label.setProperty("class", "step-label")
            header.addWidget(step_label)

            method_label = QLabel(rec.method or "")
            method_label.setProperty("class", "subtext")
            header.addWidget(method_label)
            header.addStretch()

            # 編輯/刪除按鈕
            btn_edit = QPushButton("編輯")
            btn_edit.setFixedHeight(26)
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            rec_id = rec.id
            btn_edit.clicked.connect(lambda checked, rid=rec_id: self.fa_edit_requested.emit(rid))
            header.addWidget(btn_edit)

            btn_del = QPushButton("刪除")
            btn_del.setFixedHeight(26)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, rid=rec_id: self.fa_delete_requested.emit(rid))
            header.addWidget(btn_del)

            card_layout.addLayout(header)

            # 步驟標題
            title = QLabel(rec.step_title or "")
            title.setProperty("class", "text-bold")
            card_layout.addWidget(title)

            # 描述
            desc = QLabel(rec.description or "")
            desc.setWordWrap(True)
            desc.setProperty("class", "body-text")
            card_layout.addWidget(desc)

            # 發現
            if rec.findings:
                findings = QLabel(f"發現: {rec.findings}")
                findings.setWordWrap(True)
                findings.setProperty("class", "warning-text")
                card_layout.addWidget(findings)

            # 可能原因（魚骨圖分類）
            if rec.possible_cause:
                cause = QLabel(f"可能原因: {rec.possible_cause}")
                cause.setWordWrap(True)
                cause.setProperty("class", "cause-text")
                card_layout.addWidget(cause)

            # 原因分類 + 確認狀態
            meta_parts = []
            if rec.cause_category:
                meta_parts.append(f"分類: {rec.cause_category}")
            confirmed_labels = {0: "待定", 1: "確認", 2: "排除"}
            confirmed_colors = {0: _t.SUBTEXT0, 1: _t.GREEN, 2: _t.RED}
            confirmed_label = confirmed_labels.get(rec.confirmed, "待定")
            confirmed_color = confirmed_colors.get(rec.confirmed, _t.SUBTEXT0)
            meta_parts.append(f"狀態: {confirmed_label}")
            meta_text = "  |  ".join(meta_parts)
            meta = QLabel(meta_text)
            # 動態顏色（confirmed_color 取決於運行時狀態），保留內聯
            meta.setStyleSheet(f"color: {confirmed_color};")
            card_layout.addWidget(meta)

            self._layout.addWidget(card)


# ═══════════════════════════════════════════════════════════════
#  CAPAPanel — CAPA 糾正預防措施面板
# ═══════════════════════════════════════════════════════════════

class CAPAPanel(QScrollArea):
    """CAPA 糾正預防措施面板。

    與舊版差異：不再透過 parent_issue_view() 向上查找，
    改為發射信號 capa_edit_requested / capa_delete_requested。
    """

    capa_edit_requested = Signal(object)   # CAPARecord
    capa_delete_requested = Signal(object) # CAPARecord

    @classmethod
    def _status_labels(cls) -> dict[str, tuple[str, str]]:
        """動態讀取主題色，主題切換後自動生效。"""
        return {
            "pending": ("待執行", _t.SUBTEXT0),
            "in_progress": ("進行中", _t.YELLOW),
            "completed": ("已完成", _t.GREEN),
            "verified": ("已驗證", _t.BLUE),
        }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)
        self.setProperty("class", "issue-scroll")
        self._records: list = []
        # 初始佔位
        label = QLabel("選擇一個 Issue 查看 CAPA 記錄")
        label.setProperty("class", "subtext")
        self._layout.addWidget(label)

    def refresh_theme(self) -> None:
        """主題切換回調 — 用當前數據重建卡片以刷新內聯顏色。"""
        self.set_capa_records(self._records)

    def set_capa_records(self, records: list) -> None:
        """刷新 CAPA 記錄卡片。"""
        self._records = records
        # 清空
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        if not records:
            label = QLabel("暫無 CAPA 記錄")
            label.setProperty("class", "subtext")
            self._layout.addWidget(label)
            return

        for rec in records:
            card = QFrame()
            card.setProperty("class", "issue-card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # 狀態行
            status_label_text, status_color = self._status_labels().get(
                rec.status, ("未知", _t.SUBTEXT0)
            )
            header = QHBoxLayout()
            status_lbl = QLabel(status_label_text)
            # 動態顏色（status_color 取決於運行時狀態），保留內聯
            status_lbl.setStyleSheet(f"color: {status_color}; font-weight: bold;")
            header.addWidget(status_lbl)
            if rec.due_date:
                due_lbl = QLabel(f"截止: {rec.due_date}")
                due_lbl.setProperty("class", "hint-label")
                header.addWidget(due_lbl)
            header.addStretch()

            # 編輯/刪除按鈕
            btn_edit = QPushButton("編輯")
            btn_edit.setFixedHeight(26)
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.clicked.connect(lambda checked, r=rec: self.capa_edit_requested.emit(r))
            header.addWidget(btn_edit)

            btn_del = QPushButton("刪除")
            btn_del.setFixedHeight(26)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, r=rec: self.capa_delete_requested.emit(r))
            header.addWidget(btn_del)

            card_layout.addLayout(header)

            # 措施內容
            action_lbl = QLabel(rec.action or "")
            action_lbl.setWordWrap(True)
            action_lbl.setProperty("class", "body-text")
            card_layout.addWidget(action_lbl)

            # 負責人
            assignee_name = getattr(rec, 'assignee_name', '') or ''
            if assignee_name:
                assignee_lbl = QLabel(f"負責人: {assignee_name}")
                assignee_lbl.setProperty("class", "hint-label")
                card_layout.addWidget(assignee_lbl)

            # PDCA 欄位：根因分析
            root_cause = getattr(rec, 'root_cause', '') or ''
            if root_cause:
                rc_lbl = QLabel(f"根因分析: {root_cause}")
                rc_lbl.setWordWrap(True)
                rc_lbl.setProperty("class", "cause-text-sm")
            else:
                rc_lbl = QLabel("根因分析: 待填寫")
                rc_lbl.setProperty("class", "hint-italic")
            card_layout.addWidget(rc_lbl)

            # PDCA 欄位：效果驗證
            effectiveness = getattr(rec, 'effectiveness', '') or ''
            if effectiveness:
                eff_lbl = QLabel(f"效果驗證: {effectiveness}")
                eff_lbl.setWordWrap(True)
                eff_lbl.setProperty("class", "success-text")
            else:
                eff_lbl = QLabel("效果驗證: 待填寫")
                eff_lbl.setProperty("class", "hint-italic")
            card_layout.addWidget(eff_lbl)

            # PDCA 欄位：改善追蹤
            follow_up = getattr(rec, 'follow_up', '') or ''
            if follow_up:
                fu_lbl = QLabel(f"改善追蹤: {follow_up}")
                fu_lbl.setWordWrap(True)
                fu_lbl.setProperty("class", "track-text")
            else:
                fu_lbl = QLabel("改善追蹤: 待填寫")
                fu_lbl.setProperty("class", "hint-italic")
            card_layout.addWidget(fu_lbl)

            # 驗證結果
            if rec.verification_result:
                v_lbl = QLabel(f"驗證: {rec.verification_result}")
                v_lbl.setWordWrap(True)
                v_lbl.setProperty("class", "success-text")
                card_layout.addWidget(v_lbl)

            self._layout.addWidget(card)


# ═══════════════════════════════════════════════════════════════
#  CAPADialog — 新建/編輯 CAPA 彈窗
# ═══════════════════════════════════════════════════════════════

class CAPADialog(_BaseDialog):
    """新建/編輯 CAPA 記錄彈窗。"""

    _STATUS_OPTIONS = [
        ("待執行", "pending"),
        ("進行中", "in_progress"),
        ("已完成", "completed"),
        ("已驗證", "verified"),
    ]

    def __init__(self, technician_list: list | None = None,
                 capa_record: CAPARecord | None = None,
                 issue: Issue | None = None,
                 parent: QWidget | None = None):
        is_edit = capa_record is not None
        title = "編輯 CAPA 措施" if is_edit else "新建 CAPA 措施"
        super().__init__(title, parent, width=520)

        self._capa_record = capa_record
        self._technician_list = technician_list or []

        # 新建模式：顯示關聯 Issue 參考資訊
        if not is_edit and issue:
            parts = [issue.title]
            if getattr(issue, "failure_mode", ""):
                parts.append(f"失效模式: {issue.failure_mode}")
            desc = getattr(issue, "description", "")
            if desc:
                parts.append(desc[:120])
            ref_text = "\n".join(parts)
            ref_label = QLabel(ref_text)
            ref_label.setWordWrap(True)
            ref_label.setProperty("class", "ref-info")
            self._form.addRow("關聯 Issue", ref_label)

        self._action_edit = self._add_text_area(
            "措施描述",
            default=(capa_record.action or "") if is_edit else "",
            placeholder="描述糾正或預防措施",
        )
        self._due_date_edit = self._add_date_field("截止日期")
        # 編輯模式：恢復已保存的截止日期
        if is_edit and capa_record.due_date:
            d = QDate.fromString(capa_record.due_date, "yyyy-MM-dd")
            if d.isValid():
                self._due_date_edit.setDate(d)

        # 負責人（自由輸入）
        self._assignee_edit = self._add_text_field(
            "負責人",
            default=(capa_record.assignee_name or "") if is_edit else (
                getattr(issue, "dri_name", "") or "" if issue else ""
            ),
            placeholder="輸入負責人姓名",
        )

        # 驗證人（自由輸入，一直顯示）
        self._verifier_edit = self._add_text_field(
            "驗證人",
            default=(capa_record.verifier_name or "") if is_edit and hasattr(capa_record, "verifier_name") else "",
            placeholder="輸入驗證人姓名",
        )

        status_labels = [label for label, _ in self._STATUS_OPTIONS]
        default_status = ""
        if is_edit:
            status_val = capa_record.status or ""
            for lbl, val in self._STATUS_OPTIONS:
                if val == status_val:
                    default_status = lbl
                    break
        self._status_combo = self._add_combo_field(
            "狀態",
            items=status_labels,
            default=default_status,
        )

        self._add_separator()

        # PDCA 擴展欄位
        self._root_cause_edit = self._add_text_area(
            "根因分析",
            default=(capa_record.root_cause or "") if is_edit else (
                getattr(issue, "root_cause", "") or "" if issue else ""
            ),
            placeholder="Plan: 分析問題根因",
        )
        self._effectiveness_edit = self._add_text_area(
            "效果驗證",
            default=(capa_record.effectiveness or "") if is_edit else "",
            placeholder="Check: 措施效果如何",
        )
        self._follow_up_edit = self._add_text_area(
            "改善追蹤",
            default=(capa_record.follow_up or "") if is_edit else "",
            placeholder="Act: 後續改善計劃",
        )

    def get_data(self) -> dict:
        status_map = {label: val for label, val in self._STATUS_OPTIONS}
        assignee_name = self._assignee_edit.text().strip()
        verifier_name = self._verifier_edit.text().strip()
        data = {
            "action": self._action_edit.toPlainText().strip(),
            "due_date": self._due_date_edit.date().toString("yyyy-MM-dd")
                if self._due_date_edit.date().isValid()
                else "",
            "assignee_id": None,
            "assignee_name": assignee_name,
            "verifier_name": verifier_name,
            "status": status_map.get(self._status_combo.currentText(), "pending"),
            "root_cause": self._root_cause_edit.toPlainText().strip(),
            "effectiveness": self._effectiveness_edit.toPlainText().strip(),
            "follow_up": self._follow_up_edit.toPlainText().strip(),
        }
        # 編輯模式時附帶 id
        if self._capa_record is not None:
            data["id"] = self._capa_record.id
        return data

    def accept(self) -> None:
        if not self._action_edit.toPlainText().strip():
            QMessageBox.warning(self, "校驗失敗", "措施描述為必填項。")
            self._action_edit.setFocus()
            return
        # 職責分離檢查：驗證人不能是負責人
        status_map = {label: val for label, val in self._STATUS_OPTIONS}
        status = status_map.get(self._status_combo.currentText(), "pending")
        if status == "verified":
            assignee_name = self._assignee_edit.text().strip()
            verifier_name = self._verifier_edit.text().strip()
            if verifier_name and assignee_name and verifier_name == assignee_name:
                QMessageBox.warning(
                    self, "職責分離衝突",
                    f"按品質管理要求，驗證人不應與負責人為同一人。\n\n"
                    f"當前負責人：{assignee_name}\n"
                    f"當前驗證人：{verifier_name}\n\n"
                    f"請修改後再保存。",
                )
                return
            if not verifier_name:
                reply = QMessageBox.question(
                    self, "驗證人未指定",
                    "狀態為「已驗證」但未指定驗證人。\n\n"
                    "建議填寫驗證人以確保職責分離。仍要繼續嗎？",
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
        super().accept()
