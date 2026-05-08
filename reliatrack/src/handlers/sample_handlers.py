"""Sample management handlers — check-in / checkout / batch import / edit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)

from src.views.dialogs.sample_checkin_dialog import SampleCheckInDialog
from src.views.dialogs.sample_checkout_dialog import SampleCheckoutDialog
from src.views.dialogs.batch_import_dialog import BatchImportDialog
from src.views.dialogs.sample_edit_dialog import SampleEditDialog

if TYPE_CHECKING:
    from main import MainWindow


class SampleHandlers:
    """Handles sample CRUD and transaction operations triggered from the UI."""

    def __init__(self, win: MainWindow) -> None:
        self._win = win

    def connect_signals(self) -> None:
        win = self._win
        v = win._sample_view
        v.pool_tab.btn_add.clicked.connect(self._on_sample_checkin)
        v.pool_tab.btn_out.clicked.connect(self._on_sample_checkout)
        v.pool_tab.btn_batch_import.clicked.connect(self._on_sample_batch_import)
        v.pool_tab.btn_edit.clicked.connect(self._on_sample_edit)
        v.ledger_tab.btn_edit.clicked.connect(self._on_ledger_edit)
        v.usage_tab.set_refresh_callback(self._refresh_sample_usage)

    def _refresh_sample_usage(self) -> None:
        """刷新出入库记录 Tab。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        usage_tab = self._win._sample_view.usage_tab
        sn_filter = usage_tab._search_input.text()
        type_filter = usage_tab._type_combo.currentData() or ""
        data = ctrl.sample_service.list_transactions(sn_filter, type_filter)
        self._win._sample_view.refresh_usage(data)

    def _on_sample_checkin(self) -> None:
        """样品入库。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.sample_service:
            return


        sample_svc = ctrl.sample_service
        project_list = ctrl.project_service.list_all() if ctrl.project_service else []
        default_project_id = self._win._project_filter_combo.currentData()
        dlg = SampleCheckInDialog(
            parent=self._win,
            sn_exists_cb=lambda sn: sample_svc.get_by_sn(sn) is not None,
            project_list=project_list,
            default_project_id=default_project_id,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                ctrl.sample_service.create(
                    sn=data["sn"],
                    batch_no=data.get("batch_no") or "",
                    spec=data.get("spec") or "",
                    project_id=data.get("project_id") or None,
                    location=data.get("location") or "",
                    test_hours=data.get("test_hours") or 0.0,
                    supplier=data.get("supplier") or "",
                    notes=data.get("notes") or "",
                    status="in_stock",
                )
                self._win.toast(f"样品 {data['sn']} 入库成功", "success")
                self._win._ctrl.notify_data_changed("sample")
            except Exception as e:
                logger.exception("入库失败")
                QMessageBox.critical(self._win, "入库失败", f"保存失败: {e}")

    def _on_sample_checkout(self) -> None:
        """样品出库。"""
        ctrl = self._win._ctrl
        if not ctrl or not ctrl.sample_service:
            return
        sample_id = self._win._sample_view.pool_tab.table.get_selected_sample_id()
        if sample_id is None:
            self._win.toast("请先选中一个样品", "info")
            return
        sample = ctrl.sample_service.get(sample_id)
        if sample is None:
            return
        # 获取当前项目下的测试任务列表，供出库时关联
        task_list: list = []
        filter_pid = self._win._refresh_handlers._get_filter_project_id()
        if filter_pid and ctrl.test_plan_service:
            plans = ctrl.test_plan_service.get_plans_by_project(filter_pid)
            for p in plans:
                if p.id is not None:
                    task_list.extend(ctrl.test_plan_service.get_tasks(p.id))
        dlg = SampleCheckoutDialog(
            sample=sample,
            technicians=[],
            task_list=task_list,
            parent=self._win,
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                if sample.id is None:
                    raise ValueError("Sample id is None")
                # 出库操作包裹在事务中，保证原子性
                with ctrl.sample_service._repo.transaction():
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
                self._win._ctrl.notify_data_changed("sample")
            except Exception as e:
                logger.exception("出库失败")
                QMessageBox.critical(self._win, "出库失败", f"保存失败: {e}")

    def _on_sample_batch_import(self) -> None:
        """样品批量导入。"""
        ctrl = self._win._ctrl
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
        if dlg.was_imported():
            self._win._ctrl.notify_data_changed("sample")
            success, skip = dlg.import_result()
            msg = f"样品批量导入完成: {success} 条成功"
            if skip:
                msg += f"，{skip} 条跳过（详见日志）"
            self._win.toast(msg, "success" if not skip else "warning")

    def _on_sample_edit(self) -> None:
        """编辑选中样品（样品池 Tab）。"""
        self._edit_sample_from_table(self._win._sample_view.pool_tab.table)

    def _on_ledger_edit(self) -> None:
        """编辑选中样品（样品台账 Tab）。"""
        self._edit_sample_from_table(self._win._sample_view.ledger_tab.table)

    def _edit_sample_from_table(self, table: Any) -> None:
        """从指定表格获取选中样品并编辑。"""
        ctrl = self._win._ctrl
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
            try:
                data = dlg.get_data()
                if sample.id is None:
                    raise ValueError("Sample id is None")
                ctrl.sample_service.update(sample.id, **data)
                self._win.toast(f"样品「{data['sn']}」已更新", "success")
                self._win._ctrl.notify_data_changed("sample")
            except Exception as e:
                logger.exception("更新失败")
                QMessageBox.critical(self._win, "更新失败", f"保存失败: {e}")