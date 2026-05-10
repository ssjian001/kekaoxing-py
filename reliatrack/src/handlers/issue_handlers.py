"""Issue tracking handlers — attachments, CRUD callbacks, FA records, 8D export."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from src.services.undo_manager import DeleteEntityCommand
from src.views.dialogs.attachment_dialog import AttachmentDialog

if TYPE_CHECKING:
    from main import MainWindow

logger = logging.getLogger(__name__)


class IssueHandlers:
    """Handles issue/FA operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win
        self._current_fa_records: list = []
        self._current_capa_records: list = []

    def connect_signals(self) -> None:
        win = self._win
        v = win._issue_view
        v.issue_saved.connect(self._handle_issue_saved)
        v.issue_deleted.connect(self._handle_issue_deleted)
        v.issue_selected.connect(self._handle_issue_selected)
        v.fa_record_added.connect(self._handle_fa_record_added)
        v.fa_record_edited.connect(self._handle_edit_fa)
        v.fa_record_deleted.connect(self._handle_delete_fa)
        v.capa_record_added.connect(self._handle_capa_record_added)
        v.capa_record_edited.connect(self._handle_edit_capa)
        v.capa_record_deleted.connect(self._handle_delete_capa)
        v.export_8d_requested.connect(self._handle_export_8d)
        v.btn_attachments.clicked.connect(self._on_issue_attachments)

    def _on_issue_attachments(self) -> None:
        """打开 Issue 附件管理弹窗。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = self._win._issue_view.get_selected_issue_id()
        if issue_id is None:
            self._win.toast("请先选中一个 Issue", "info")
            return
        dlg = AttachmentDialog(
            issue_id=issue_id,
            issue_service=ctrl.issue_service,
            parent=self._win,
        )
        dlg.exec()
        dlg.deleteLater()

    def _handle_issue_saved(self, data: dict) -> None:
        """Issue 新建/编辑后回调。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            if "id" in data:
                # 记录关闭前的状态，用于判断是否刚关闭
                old_issue = ctrl.issue_service.get(data["id"])
                old_status = old_issue.status if old_issue else None

                kwargs = {k: v for k, v in data.items() if k != "id"}
                ctrl.issue_service.update(data["id"], **kwargs)
                self._win.toast(f"Issue #{data['id']} 已更新", "success")

                # 状态变更为 closed 时做 FRACAS 完整性检查
                new_status = data.get("status")
                if new_status == "closed" and old_status != "closed":
                    issue_id = data["id"]
                    fa_records = ctrl.issue_service.get_fa_records(issue_id)
                    capa_records = ctrl.issue_service.get_capa_records(issue_id)
                    warnings: list[str] = []
                    if not fa_records:
                        warnings.append("• 无 FA 分析记录（建议至少记录根因分析步骤）")
                    if not capa_records:
                        warnings.append("• 无 CAPA 纠正预防措施（建议至少记录一项纠正措施）")
                    elif not any(c.status == "verified" for c in capa_records):
                        warnings.append("• 无已验证的 CAPA（建议至少一项 CAPA 标记为\"已验证\"）")
                    if warnings:
                        reply = QMessageBox.warning(
                            self._win, "FRACAS 完整性检查",
                            "Issue 关闭前检查发现以下不完整项：\n\n"
                            + "\n".join(warnings)
                            + "\n\n仍要关闭吗？（不完整的 Issue 可能不满足审核要求）",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        )
                        if reply != QMessageBox.StandardButton.Yes:
                            self._win._ctrl.notify_data_changed("issue")
                            return
                    self._prompt_archive_to_knowledge(old_issue or data)
            else:
                ctrl.issue_service.create(**data)
                self._win.toast("Issue 已创建", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            QMessageBox.critical(self._win, "保存失败", f"Issue 保存失败: {e}")

    def _prompt_archive_to_knowledge(self, issue_or_data) -> None:
        """Issue 关闭后提示归档到知识库。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.knowledge_service:
            return

        # 从 Issue 对象或 dict 中提取字段
        if isinstance(issue_or_data, dict):
            title = issue_or_data.get("title", "")
            failure_mode = issue_or_data.get("failure_mode", "")
            root_cause = issue_or_data.get("root_cause", "")
            resolution = issue_or_data.get("resolution", "")
            description = issue_or_data.get("description", "")
        else:
            title = getattr(issue_or_data, "title", "")
            failure_mode = getattr(issue_or_data, "failure_mode", "")
            root_cause = getattr(issue_or_data, "root_cause", "")
            resolution = getattr(issue_or_data, "resolution", "")
            description = getattr(issue_or_data, "description", "")

        reply = QMessageBox.question(
            self._win,
            "归档到知识库",
            f"Issue \"{title}\" 已关闭。\n是否将失效分析经验归档到知识库？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                entry_data = {
                    "category": "其他",
                    "failure_mode": failure_mode,
                    "cause_analysis": root_cause,
                    "improvement": resolution,
                    "keywords": failure_mode,
                    "summary": f"{title}: {description[:100]}",
                    "root_cause": root_cause,
                    "resolution": resolution,
                }
                ctrl.knowledge_service.create(**entry_data)
                self._win.toast("已归档到知识库", "success")
                self._win._ctrl.notify_data_changed("knowledge")
            except Exception as e:
                QMessageBox.warning(self._win, "归档失败", f"知识库归档失败: {e}")

    def _handle_issue_deleted(self, issue_id: int) -> None:
        """Issue 删除后回调（软删除，可撤销）。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            cmd = ctrl.issue_service.create_delete_command(issue_id)
            ctrl.undo_manager.execute(cmd)
            self._win.toast(f"Issue #{issue_id} 已删除（可撤销）", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            QMessageBox.critical(self._win, "删除失败", f"Issue 删除失败: {e}")

    def _handle_issue_selected(self, issue_id: int | None) -> None:
        """Issue 选中时加载 FA 和 CAPA 记录。"""
        if issue_id is None:
            self._current_fa_records = []
            self._current_capa_records = []
            self._win._issue_view.refresh_fa([])
            self._win._issue_view.refresh_capa([])
            return
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
        self._win._issue_view.refresh_fa(self._current_fa_records)
        # CAPA 记录
        self._current_capa_records = ctrl.issue_service.get_capa_records(issue_id)
        self._win._issue_view.refresh_capa(self._current_capa_records)

    def _handle_fa_record_added(self, data: dict) -> None:
        """FA 记录添加后回调。自动联动更新 Issue。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = data.get("issue_id")
        if issue_id is None:
            return
        fa_data = {k: v for k, v in data.items() if k != "issue_id"}
        try:
            ctrl.issue_service.add_fa_record(issue_id, **fa_data)
            # 刷新 FA 面板
            self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
            self._win._issue_view.refresh_fa(self._current_fa_records)
            # ── 联动: FA → Issue ──
            self._sync_issue_from_fa(issue_id)
            self._win.toast(f"FA 步骤已添加", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            QMessageBox.critical(self._win, "保存失败", f"FA 记录添加失败: {e}")

    def _handle_edit_fa(self, data: dict) -> None:
        """FA 记录编辑后回调。自动联动更新 Issue。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        fa_id = data.get("id")
        if fa_id is None:
            return
        try:
            update_data = {k: v for k, v in data.items() if k not in ("id", "issue_id")}
            ctrl.issue_service.update_fa_record(fa_id, **update_data)
            # 刷新 FA 面板
            issue_id = self._win._issue_view.get_selected_issue_id()
            if issue_id is not None:
                self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
                self._win._issue_view.refresh_fa(self._current_fa_records)
                self._sync_issue_from_fa(issue_id)
            self._win.toast(f"FA #{fa_id} 已更新", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            logger.exception("FA update failed for fa_id=%s", fa_id)
            QMessageBox.critical(self._win, "保存失败", f"FA 记录更新失败: {e}")

    def _handle_delete_fa(self, fa_id: int) -> None:
        """FA 记录删除后回调。自动联动更新 Issue。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            cmd = ctrl.issue_service.create_fa_delete_command(fa_id)
            ctrl.undo_manager.execute(cmd)
            # 刷新 FA 面板
            issue_id = self._win._issue_view.get_selected_issue_id()
            if issue_id is not None:
                self._current_fa_records = ctrl.issue_service.get_fa_records(issue_id)
                self._win._issue_view.refresh_fa(self._current_fa_records)
                self._sync_issue_from_fa(issue_id)
            self._win.toast(f"FA #{fa_id} 已删除", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            logger.exception("FA delete failed for fa_id=%s", fa_id)
            QMessageBox.critical(self._win, "删除失败", f"FA 记录删除失败: {e}")

    def _handle_capa_record_added(self, data: dict) -> None:
        """CAPA 记录添加后回调。自动联动更新 Issue。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        issue_id = data.get("issue_id")
        if issue_id is None:
            return
        try:
            record_data = {k: v for k, v in data.items() if k != "issue_id"}
            ctrl.issue_service.add_capa_record(issue_id, **record_data)
            # 刷新 CAPA 面板
            self._current_capa_records = ctrl.issue_service.get_capa_records(issue_id)
            self._win._issue_view.refresh_capa(self._current_capa_records)
            # ── 联动: CAPA → Issue ──
            self._sync_issue_from_capa(issue_id)
            self._win.toast("CAPA 措施已添加", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            QMessageBox.critical(self._win, "保存失败", f"CAPA 记录添加失败: {e}")

    def _handle_edit_capa(self, data: dict) -> None:
        """CAPA 记录编辑后回调。自动联动更新 Issue。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        capa_id = data.get("id")
        if capa_id is None:
            return
        try:
            update_data = {k: v for k, v in data.items() if k != "id"}
            ctrl.issue_service.update_capa_record(capa_id, **update_data)
            # 刷新 CAPA 面板：从当前选中 Issue 重新加载
            issue_id = self._win._issue_view.get_selected_issue_id()
            if issue_id is not None:
                self._current_capa_records = ctrl.issue_service.get_capa_records(issue_id)
                self._win._issue_view.refresh_capa(self._current_capa_records)
                # ── 联动: CAPA → Issue ──
                self._sync_issue_from_capa(issue_id)
            self._win.toast(f"CAPA #{capa_id} 已更新", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            logger.exception("CAPA update failed for capa_id=%s", capa_id)
            QMessageBox.critical(self._win, "保存失败", f"CAPA 记录更新失败: {e}")

    def _handle_delete_capa(self, capa_id: int) -> None:
        """CAPA 记录删除后回调。自动联动更新 Issue。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            cmd = ctrl.issue_service.create_capa_delete_command(capa_id)
            ctrl.undo_manager.execute(cmd)
            # 刷新 CAPA 面板
            issue_id = self._win._issue_view.get_selected_issue_id()
            if issue_id is not None:
                self._current_capa_records = ctrl.issue_service.get_capa_records(issue_id)
                self._win._issue_view.refresh_capa(self._current_capa_records)
                # ── 联动: CAPA → Issue ──
                self._sync_issue_from_capa(issue_id)
            self._win.toast(f"CAPA #{capa_id} 已删除", "success")
            self._win._ctrl.notify_data_changed("issue")
        except Exception as e:
            logger.exception("CAPA delete failed for capa_id=%s", capa_id)
            QMessageBox.critical(self._win, "删除失败", f"CAPA 记录删除失败: {e}")

    def _handle_export_8d(self, issue_id: int) -> None:
        """导出 8D 报告（PDF / Word 格式选择）。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service or not ctrl.export_service:
            return
        try:
            issue = ctrl.issue_service.get(issue_id)
            if issue is None:
                QMessageBox.warning(self._win, "导出失败", f"Issue #{issue_id} 不存在。")
                return

            # 格式选择
            fmt = QMessageBox.question(
                self._win, "导出格式",
                "选择导出格式：\n\n"
                "「是」= PDF\n「否」= Word (.docx)\n「取消」= 放弃",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if fmt == QMessageBox.StandardButton.Cancel:
                return

            fa_records = ctrl.issue_service.get_fa_records(issue_id)
            capa_records = ctrl.issue_service.get_capa_records(issue_id)

            # 查关联任务和样品信息
            _task = None
            _sample_sn = ""
            _tech_name = ""
            if issue.task_id:
                _task = ctrl.test_plan_service.get_task(issue.task_id)
            if issue.sample_id:
                s = ctrl.sample_service.get(issue.sample_id)
                if s:
                    _sample_sn = s.sn or ""
            if issue.assignee_id and ctrl.technicians:
                for t in ctrl.technicians.list_all():
                    if t.id == issue.assignee_id:
                        _tech_name = t.name
                        break

            if fmt == QMessageBox.StandardButton.Yes:
                filepath = ctrl.export_service.export_8d_pdf(
                    issue, fa_records, capa_records,
                    technician_name=_tech_name, task=_task, sample_sn=_sample_sn,
                )
            else:
                filepath = ctrl.export_service.export_8d_docx(
                    issue, fa_records, capa_records,
                    technician_name=_tech_name, task=_task, sample_sn=_sample_sn,
                )
            self._win.toast(f"8D 报告已导出: {os.path.basename(filepath)}", "success")
        except Exception as e:
            logger.exception("8D report export failed for issue_id=%s", issue_id)
            QMessageBox.critical(self._win, "导出失败", f"8D 报告导出失败: {e}")

    # ══════════════════════════════════════════════════════════════
    #  Issue ↔ FA/CAPA 联动
    # ══════════════════════════════════════════════════════════════

    def _sync_issue_from_fa(self, issue_id: int) -> None:
        """FA 记录变更后自动回写 Issue。

        规则:
        1. 有 FA 记录 → 状态改为 'analyzing'（如果当前是 'open'）
        2. FA 中 confirmed=1 的 possible_cause → 回写 Issue.root_cause
        """
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            issue = ctrl.issue_service.get(issue_id)
            if not issue:
                return

            fa_records = ctrl.issue_service.get_fa_records(issue_id)
            updates: dict = {}

            # 状态联动: open → analyzing
            if issue.status == "open" and fa_records:
                updates["status"] = "analyzing"

            # 根因联动: 确认的原因（confirmed=1）汇总
            confirmed_causes = [
                rec.possible_cause for rec in fa_records
                if rec.confirmed == 1 and rec.possible_cause
            ]
            if confirmed_causes:
                root_cause = "; ".join(confirmed_causes)
                if root_cause != issue.root_cause:
                    updates["root_cause"] = root_cause

            if updates:
                ctrl.issue_service.update(issue_id, **updates)
        except Exception:
            logger.exception("FA→Issue sync failed for issue_id=%s", issue_id)

    def _sync_issue_from_capa(self, issue_id: int) -> None:
        """CAPA 记录变更后自动回写 Issue。

        规则:
        1. 所有 CAPA action 汇总 → 回写 Issue.resolution
        2. 所有 CAPA 都 completed/verified → 状态改为 'verified'
        """
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.issue_service:
            return
        try:
            issue = ctrl.issue_service.get(issue_id)
            if not issue:
                return

            capa_records = ctrl.issue_service.get_capa_records(issue_id)
            updates: dict = {}

            # 解决方案联动: 汇总所有 CAPA action
            actions = [rec.action for rec in capa_records if rec.action]
            if actions:
                resolution = "; ".join(actions)
                if resolution != issue.resolution:
                    updates["resolution"] = resolution
            elif not capa_records and issue.resolution:
                # 所有 CAPA 被删空，清空 resolution
                updates["resolution"] = ""
            elif capa_records and not actions and issue.resolution:
                # CAPA 存在但 action 全为空，清空旧 resolution
                updates["resolution"] = ""

            # 状态联动: 全部完成/验证 → verified（仅当状态为 analyzing 时）
            if capa_records and issue.status == "analyzing":
                all_done = all(
                    rec.status in ("completed", "verified")
                    for rec in capa_records
                )
                if all_done:
                    updates["status"] = "verified"

            if updates:
                ctrl.issue_service.update(issue_id, **updates)
        except Exception:
            logger.exception("CAPA→Issue sync failed for issue_id=%s", issue_id)
