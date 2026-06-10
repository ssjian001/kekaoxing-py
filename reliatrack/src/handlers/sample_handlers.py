"""Sample management handlers — check-in / checkout / batch import / edit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMessageBox

from src.handlers.crud_helpers import exec_crud

logger = logging.getLogger(__name__)

from src.views.dialogs.sample_checkin_dialog import SampleCheckInDialog
from src.views.dialogs.sample_checkout_dialog import SampleCheckoutDialog
from src.views.dialogs.sample_return_dialog import SampleReturnDialog
from src.views.dialogs.batch_import_dialog import BatchImportDialog
from src.views.dialogs.sample_edit_dialog import SampleEditDialog
from src.views.dialogs.batch_edit_sample_dialog import BatchEditSampleDialog
from src.services.undo_manager import BatchEditSamplesCommand

if TYPE_CHECKING:
    from main import MainWindow


class SampleHandlers:
    """Handles sample CRUD and transaction operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win.sample_view
        v.pool_tab.btn_add.clicked.connect(self._on_sample_checkin)
        v.pool_tab.btn_out.clicked.connect(self._on_sample_checkout)
        v.pool_tab.btn_batch_import.clicked.connect(self._on_sample_batch_import)
        v.pool_tab.btn_edit.clicked.connect(self._on_sample_edit)
        v.pool_tab.btn_batch_edit.clicked.connect(self._on_pool_batch_edit)
        v.pool_tab.btn_delete.clicked.connect(self._on_sample_delete)
        v.ledger_tab.btn_edit.clicked.connect(self._on_ledger_edit)
        v.ledger_tab.btn_return.clicked.connect(self._on_sample_return)
        v.ledger_tab.btn_batch_edit.clicked.connect(self._on_ledger_batch_edit)
        v.usage_tab.set_refresh_callback(self._refresh_sample_usage)

    def _refresh_sample_usage(self) -> None:
        """刷新出入库记录 Tab。

        始终从 DB 拉全量记录，前端过滤由 _apply_filter 独立完成。
        避免双重过滤（DB 层过滤 + 前端过滤）导致数据源被污染。
        """
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return
        data = ctrl.sample_service.list_transactions("", "")
        self._win.sample_view.refresh_usage(data)

    def _on_sample_checkin(self) -> None:
        """样品入库。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return


        sample_svc = ctrl.sample_service
        project_list = ctrl.project_service.list_all() if ctrl.project_service else []
        default_project_id = self._win.get_project_filter_id()
        dlg = SampleCheckInDialog(
            parent=self._win,
            sn_exists_cb=lambda sn: sample_svc.get_by_sn(sn) is not None,
            project_list=project_list,
            default_project_id=default_project_id,
        )
        if dlg.exec():
            data = dlg.get_data()
            sample_project_id = data.get("project_id") or None
            ok = exec_crud(
                win=self._win,
                action=ctrl.sample_service.create,
                action_kwargs=dict(
                    sn=data["sn"],
                    batch_no=data.get("batch_no") or "",
                    spec=data.get("spec") or "",
                    project_id=sample_project_id,
                    location=data.get("location") or "",
                    test_hours=data.get("test_hours") or 0.0,
                    supplier=data.get("supplier") or "",
                    notes=data.get("notes") or "",
                    status="in_stock",
                ),
                toast_msg=f"样品 {data['sn']} 入库成功",
                entity="sample",
                error_title="入库失败",
            )
            # 入库成功后，确保用户能看到新样品：
            # 如果样品所属项目与当前筛选不同，切换到"全部项目"
            if ok:
                current_filter = self._win.get_project_filter_id()
                if current_filter is not None and sample_project_id != current_filter:
                    self._win.project_filter_combo.setCurrentIndex(0)
                # 同步创建入库记录
                created = ctrl.sample_service.get_by_sn(data["sn"])
                if created is not None and created.id is not None:
                    ctrl.sample_service.add_transaction(
                        sample_id=created.id,
                        txn_type="check_in",
                    )
        dlg.deleteLater()

    def _on_sample_checkout(self) -> None:
        """样品出库。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._win.sample_view.pool_tab.table.get_selected_sample_id()
        if sample_id is None:
            self._win.toast("请先选中一个样品", "info")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        # 获取当前项目下的测试任务列表，供出库时关联
        task_list: list = []
        filter_pid = self._win.get_project_filter_id()
        if filter_pid and ctrl.test_plan_service:
            plans = ctrl.test_plan_service.get_active_plans_by_project(filter_pid)
            for p in plans:
                if p.id is not None:
                    task_list.extend(ctrl.test_plan_service.get_tasks(p.id))
        dlg = SampleCheckoutDialog(
            sample=sample,
            technicians=ctrl.technician_service.list_all() if ctrl.technician_service else [],
            task_list=task_list,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                if sample.id is None:
                    raise ValueError("Sample id is None")
                # 出库操作包裹在事务中，保证原子性
                with ctrl.sample_service.transaction():
                    ctrl.sample_service.add_transaction(
                        sample_id=sample.id,
                        txn_type="check_out",
                        purpose=data.get("purpose"),
                        related_task_id=data.get("related_task_id"),
                        expected_return=data.get("expected_return"),
                        operator_id=data.get("operator_id"),
                        notes=data.get("notes"),
                    )
                    ctrl.sample_service.update_status(sample.id, "checked_out")
                self._win.toast(f"样品 {sample.sn} 出库成功", "success")
                self._win.ctrl.notify_data_changed("sample")
            except Exception as e:
                logger.exception("出库失败")
                QMessageBox.critical(self._win, "出库失败", f"保存失败: {e}")
        dlg.deleteLater()

    def _on_sample_batch_import(self) -> None:
        """样品批量导入。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return

        def _do_import(sample_list: list[dict]) -> tuple[int, int]:
            """执行批量导入，返回 (成功数, 跳过数)。"""
            assert ctrl is not None and ctrl.sample_service is not None
            success = 0
            skip = 0
            for data in sample_list:
                sn = data.get("sn", "").strip()
                if not sn:
                    continue
                # 检查 SN 是否已存在
                if ctrl.sample_service.get_by_sn(sn) is not None:
                    skip += 1
                    continue
                try:
                    ctrl.sample_service.create(
                        sn=sn,
                        batch_no=data.get("batch_no") or "",
                        spec=data.get("spec") or "",
                        location=data.get("location") or "",
                        supplier=data.get("supplier") or "",
                        notes=data.get("notes") or "",
                        status="in_stock",
                    )
                    success += 1
                except Exception:
                    logger.exception("Failed to import sample SN=%s: data=%s", sn, data)
                    skip += 1
            return success, skip

        dlg = BatchImportDialog(
            parent=self._win,
            on_import=_do_import,
            required_fields=["sn"],
        )
        dlg.exec()
        dlg.deleteLater()
        if dlg.was_imported():
            self._win.ctrl.notify_data_changed("sample")
            success, skip = dlg.get_result()
            msg = f"样品批量导入完成: {success} 条成功"
            if skip:
                msg += f"，{skip} 条跳过（详见日志）"
            self._win.toast(msg, "success" if not skip else "warning")

    def _on_sample_edit(self) -> None:
        """编辑选中样品（样品池 Tab）。"""
        self._edit_sample_from_table(self._win.sample_view.pool_tab.table)

    def _on_sample_delete(self) -> None:
        """彻底删除选中样品（样品池 Tab）。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._win.sample_view.pool_tab.table.get_selected_sample_id()
        if sample_id is None:
            self._win.toast("请先选中一个样品", "info")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return

        # 先检查引用（在确认对话框之前，避免用户确认后被告知无法删除）
        try:
            ctrl.sample_service._check_references(sample_id)
        except ValueError as e:
            QMessageBox.warning(self._win, "无法删除", str(e))
            return

        # 无引用，二次确认
        reply = QMessageBox.question(
            self._win,
            "确认删除",
            f"确定要彻底删除样品「{sample.sn}」吗？\n"
            f"该操作将同时删除出入库记录，且不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            ctrl.sample_service.delete(sample_id)
            self._win.toast(f"样品「{sample.sn}」已删除", "success")
            ctrl.notify_data_changed("sample")
        except Exception as e:
            logger.exception("删除样品失败")
            QMessageBox.critical(self._win, "删除失败", f"删除失败: {e}")

    def _on_ledger_edit(self) -> None:
        """编辑选中样品（样品台账 Tab）。"""
        self._edit_sample_from_table(self._win.sample_view.ledger_tab.table)

    def _on_pool_batch_edit(self) -> None:
        """批量编辑选中样品（样品池 Tab）。"""
        self._batch_edit_from_table(self._win.sample_view.pool_tab.table)

    def _on_ledger_batch_edit(self) -> None:
        """批量编辑选中样品（样品台账 Tab）。"""
        self._batch_edit_from_table(self._win.sample_view.ledger_tab.table)

    def _edit_sample_from_table(self, table: Any) -> None:
        """从指定表格获取选中样品并编辑。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = table.get_selected_sample_id()
        if sample_id is None:
            QMessageBox.warning(self._win, "提示", "请先选中一个样品。")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        dlg = SampleEditDialog(
            sample=sample,
            project_list=ctrl.project_service.list_all() if ctrl.project_service else [],
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            if sample.id is None:
                QMessageBox.warning(self._win, "更新失败", "Sample id is None")
                return
            exec_crud(
                win=self._win,
                action=ctrl.sample_service.update,
                action_args=(sample.id,),
                action_kwargs=data,
                toast_msg=f"样品「{data['sn']}」已更新",
                entity="sample",
                error_title="更新失败",
            )
        dlg.deleteLater()

    def _batch_edit_from_table(self, table: Any) -> None:
        """批量编辑选中样品。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return

        # 获取选中行的 sample IDs
        sample_ids = table.get_selected_sample_ids()
        if len(sample_ids) < 2:
            self._win.toast("请选中 2 个以上的样品进行批量编辑", "info")
            return

        # 加载选中样品的完整数据
        samples: list = []
        for sid in sample_ids:
            s = ctrl.sample_service.get(sid)
            if s is not None:
                samples.append(s)

        if not samples:
            return

        # 弹出批量编辑对话框
        project_list = ctrl.project_service.list_all() if ctrl.project_service else []
        dlg = BatchEditSampleDialog(
            samples=samples,
            project_list=project_list,
            parent=self._win,
        )
        if dlg.exec():
            changes = dlg.get_changes()
            if not changes:
                dlg.deleteLater()
                return

            # 构建 Command 的 changes 列表：[(sample_id, {field: old}, {field: new})]
            command_changes: list[tuple[int, dict, dict]] = []
            for sample in samples:
                if sample.id is None:
                    continue
                old_vals: dict = {}
                new_vals: dict = {}
                for field, new_value in changes.items():
                    old_value = getattr(sample, field, None)
                    old_vals[field] = old_value
                    new_vals[field] = new_value
                if old_vals and new_vals:
                    command_changes.append((sample.id, old_vals, new_vals))

            if not command_changes:
                dlg.deleteLater()
                return

            try:
                # 事务中执行批量更新
                sample_repo = ctrl.sample_service._repo
                cmd = BatchEditSamplesCommand(sample_repo, command_changes)
                with ctrl.sample_service.transaction():
                    ctrl.undo_manager.execute(cmd)
                self._win.toast(
                    f"已批量修改 {len(command_changes)} 个样品", "success"
                )
                ctrl.notify_data_changed("sample")
            except Exception as e:
                logger.exception("批量编辑失败")
                QMessageBox.critical(self._win, "批量编辑失败", f"保存失败: {e}")

        dlg.deleteLater()

    def _on_sample_return(self) -> None:
        """样品归还。"""
        ctrl = self._win.ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._win.sample_view.ledger_tab.table.get_selected_sample_id()
        if sample_id is None:
            self._win.toast("请先选中一个样品", "info")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        if sample.status != "checked_out":
            self._win.toast("只能归还已出库样品", "warning")
            return
        dlg = SampleReturnDialog(
            sample=sample,
            technicians=ctrl.technician_service.list_all() if ctrl.technician_service else [],
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                if sample.id is None:
                    raise ValueError("Sample id is None")
                # 归还操作包裹在事务中，保证原子性
                with ctrl.sample_service.transaction():
                    ctrl.sample_service.add_transaction(
                        sample_id=sample.id,
                        txn_type="return",
                        actual_return=data.get("actual_return"),
                        operator_id=data.get("operator_id"),
                        notes=data.get("notes"),
                    )
                    ctrl.sample_service.update_status(sample.id, "in_stock")
                self._win.toast(f"样品 {sample.sn} 归还成功", "success")
                self._win.ctrl.notify_data_changed("sample")
            except Exception as e:
                logger.exception("归还失败")
                QMessageBox.critical(self._win, "归还失败", f"保存失败: {e}")
        dlg.deleteLater()