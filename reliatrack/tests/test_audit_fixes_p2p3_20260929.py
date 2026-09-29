"""审计修复回归测试 — P2-10 / P2-14 / P3-2 / P3-5 / P3-6（2026-09-29）。

每个用例都对应一个「修复前必失败」的行为，断言不放宽：

- P2-10: 批量导入样品走 create_with_ledger 写"入库"台账（与单个入库口径一致），
         且整批一个事务；单条失败只回滚该条。
- P2-14: sample/equipment 编辑弹窗不再把枚举外/legacy 状态洗成默认标签
         （"已归还"→在库 / 'in_use'→正常）再回写枚举值。
- P3-2 : add_transaction 的"台账行 + 状态联动"两步写包在原子单元里，
         状态更新失败不留脏流水。
- P3-5 : 批量撤销/重做对已删实体报失败（UndoConflictError），不再静默 no-op。
- P3-6 : holidays 存量非法日期行不再静默漏假：读取跳过 + 告警日志 + 只读报告。
"""

from __future__ import annotations

import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest
import apsw

from PySide6.QtWidgets import QApplication, QDialog

from src.constants import (
    EQUIPMENT_STATUS_LABELS,
    SAMPLE_STATUS_LABELS,
    SAMPLE_STATUS_MAP,
    SAMPLE_STATUS_OPTIONS,
)
from src.db.repositories.sample_repo import SampleRepository
from src.models.common import Equipment
from src.services.holiday_service import HolidayService
from src.services.sample_service import SampleService
from src.services.undo_manager import (
    BatchEditSamplesCommand,
    UndoConflictError,
    UndoManager,
)


# ═══════════════════════════════════════════════════════════════════
#  共享 fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture()
def svc(db_conn: apsw.Connection) -> SampleService:
    """内存库上的样品 service（每个用例独立 DB）。"""
    return SampleService(SampleRepository(db_conn))


# ═══════════════════════════════════════════════════════════════════
#  P2-10 — 批量导入写入库台账
# ═══════════════════════════════════════════════════════════════════


class _FakeCtrl:
    """只实现 _on_sample_batch_import 用到的 ctrl 接口。"""

    def __init__(self, sample_service: SampleService) -> None:
        self.sample_service = sample_service
        self.notified: list[str] = []

    def notify_data_changed(self, kind: str) -> None:
        self.notified.append(kind)


class _FakeWin:
    """只实现 _on_sample_batch_import 用到的窗口接口。"""

    def __init__(self, ctrl: _FakeCtrl, project_id: int | None = None) -> None:
        self.ctrl = ctrl
        self._project_id = project_id
        self.toasts: list[tuple[str, str]] = []

    def get_project_filter_id(self) -> int | None:
        return self._project_id

    def toast(self, msg: str, level: str = "success") -> None:
        self.toasts.append((msg, level))


def _install_fake_batch_import(monkeypatch, box: dict) -> None:
    """把 sample_handlers 模块里的 BatchImportDialog 换成直接回调的假实现。"""
    import src.handlers.sample_handlers as sh

    class _FakeBatchImport:
        def __init__(self, *args, **kwargs) -> None:
            self._on_import = kwargs["on_import"]

        def exec(self) -> int:
            box["result"] = self._on_import(box["records"])
            return QDialog.DialogCode.Accepted

        def deleteLater(self) -> None:
            pass

        def was_imported(self) -> bool:
            return True

        def get_result(self) -> tuple[int, int]:
            return box["result"]

    monkeypatch.setattr(sh, "BatchImportDialog", _FakeBatchImport)


@pytest.fixture()
def batch_import(db_conn: apsw.Connection, monkeypatch):
    """驱动 SampleHandlers._on_sample_batch_import 的真实代码路径。

    用假窗口/假 Ctrl（仅提供 handler 实际使用的接口）+ 假 BatchImportDialog
    （exec 时直接回调 on_import），不依赖 MainWindow，每个用例一个内存库。
    """
    from src.handlers.sample_handlers import SampleHandlers

    sample_svc = SampleService(SampleRepository(db_conn))
    ctrl = _FakeCtrl(sample_svc)
    win = _FakeWin(ctrl)
    handlers = SampleHandlers(win)  # type: ignore[arg-type]

    box: dict = {}
    call_log: list[bool] = []
    _install_fake_batch_import(monkeypatch, box)

    # 记录调用台账写入时是否处于显式事务中（批量导入"整批一个事务"）
    original_add_transaction = sample_svc.repo().add_transaction

    def _recording_add_transaction(*args, **kwargs):
        call_log.append(sample_svc.repo().conn.in_transaction)
        return original_add_transaction(*args, **kwargs)

    monkeypatch.setattr(
        sample_svc.repo(), "add_transaction", _recording_add_transaction
    )

    def _run(records: list[dict]) -> tuple[int, int]:
        box["records"] = records
        handlers._on_sample_batch_import()
        return box["result"]

    return SimpleNamespace(
        run=_run, svc=sample_svc, ctrl=ctrl, win=win,
        call_log=call_log, repo=sample_svc.repo(),
    )


def _txn_types(svc: SampleService, sn: str) -> list[str]:
    return [t["type"] for t in svc.list_transactions(filter_sn=sn)]


class TestP210BatchImportLedger:

    def test_batch_import_writes_check_in_ledger(self, batch_import):
        """批量导入的每个样品都要有 check_in 台账行（修复前为 0 行）。"""
        result = batch_import.run([
            {"sn": "AUDIT-BI-01"},
            {"sn": "AUDIT-BI-02", "batch_no": "BATCH-BI", "location": "A区-01"},
        ])

        assert result == (2, 0)
        for sn in ("AUDIT-BI-01", "AUDIT-BI-02"):
            assert batch_import.svc.get_by_sn(sn) is not None
            assert _txn_types(batch_import.svc, sn) == ["check_in"]
        sample2 = batch_import.svc.get_by_sn("AUDIT-BI-02")
        assert sample2 is not None
        assert sample2.batch_no == "BATCH-BI"
        assert sample2.location == "A区-01"
        assert batch_import.ctrl.notified == ["sample"]

    def test_batch_import_runs_inside_one_transaction(self, batch_import):
        """整批一个事务：每条写入都发生在显式事务内。"""
        result = batch_import.run([{"sn": "AUDIT-BI-T1"}, {"sn": "AUDIT-BI-T2"}])

        assert result == (2, 0)
        assert batch_import.call_log, "台账写入未被触发"
        assert all(batch_import.call_log), "批量导入未包在显式事务中"
        assert batch_import.repo.conn.in_transaction is False  # 批次结束后已提交

    def test_batch_import_duplicates_still_skipped(self, batch_import):
        """重复 SN 仍按 skip 计数，且不给老样品补写重复台账。"""
        batch_import.svc.create_with_ledger(sn="AUDIT-BI-DUP")
        before = _txn_types(batch_import.svc, "AUDIT-BI-DUP")

        result = batch_import.run([
            {"sn": "AUDIT-BI-DUP"},
            {"sn": "AUDIT-BI-NEW"},
            {"sn": "   "},
        ])

        assert result == (1, 1)
        assert _txn_types(batch_import.svc, "AUDIT-BI-DUP") == before
        assert _txn_types(batch_import.svc, "AUDIT-BI-NEW") == ["check_in"]

    def test_batch_import_single_failure_rolls_back_only_that_row(
        self, db_conn, monkeypatch
    ):
        """单条台账写入失败：只回滚该条（样品不留孤儿行），批次继续。"""
        from src.handlers.sample_handlers import SampleHandlers

        sample_svc = SampleService(SampleRepository(db_conn))
        ctrl = _FakeCtrl(sample_svc)
        handlers = SampleHandlers(_FakeWin(ctrl))  # type: ignore[arg-type]

        repo = sample_svc.repo()
        original = repo.add_transaction
        state = {"calls": 0}

        def _flaky_add_transaction(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("simulated ledger failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(repo, "add_transaction", _flaky_add_transaction)

        box: dict = {"records": [
            {"sn": "AUDIT-BI-FAIL"},
            {"sn": "AUDIT-BI-OK"},
        ]}
        _install_fake_batch_import(monkeypatch, box)
        handlers._on_sample_batch_import()

        assert box["result"] == (1, 1)
        # 失败条整体回滚：样品本身也不能落库（savepoint 只回滚该条）
        assert sample_svc.get_by_sn("AUDIT-BI-FAIL") is None
        assert _txn_types(sample_svc, "AUDIT-BI-FAIL") == []
        # 成功条不受影响
        assert sample_svc.get_by_sn("AUDIT-BI-OK") is not None
        assert _txn_types(sample_svc, "AUDIT-BI-OK") == ["check_in"]

    def test_batch_import_keeps_continuing_after_failure(self, batch_import,
                                                         monkeypatch):
        """失败条后面的记录仍会被导入（批次不因单条失败整体放弃）。"""
        repo = batch_import.repo
        original = repo.add_transaction
        state = {"calls": 0}

        def _fail_first_call(sample_id, txn_type, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("simulated ledger failure")
            return original(sample_id, txn_type, **kwargs)

        monkeypatch.setattr(repo, "add_transaction", _fail_first_call)

        result = batch_import.run([
            {"sn": "AUDIT-BI-X1"},
            {"sn": "AUDIT-BI-X2"},
            {"sn": "AUDIT-BI-X3"},
        ])

        assert result == (2, 1)
        assert batch_import.svc.get_by_sn("AUDIT-BI-X1") is None
        for sn in ("AUDIT-BI-X2", "AUDIT-BI-X3"):
            assert _txn_types(batch_import.svc, sn) == ["check_in"]


# ═══════════════════════════════════════════════════════════════════
#  P2-14 — 编辑弹窗不得把枚举外状态洗成默认值
# ═══════════════════════════════════════════════════════════════════

_LEGACY_SUFFIX = "（原状态，不可改）"


def _insert_sample(db_conn, sn: str, status: str) -> int:
    db_conn.execute(
        "INSERT INTO samples (sn, batch_no, spec, status) VALUES (?, '', '', ?)",
        (sn, status),
    )
    row = db_conn.execute("SELECT id FROM samples WHERE sn = ?", (sn,)).fetchone()
    return row[0]


def _combo_items(dialog) -> list[str]:
    combo = dialog._status_combo
    return [combo.itemText(i) for i in range(combo.count())]


def _select_status(dialog, text: str) -> None:
    combo = dialog._status_combo
    index = combo.findText(text)
    assert index >= 0, f"下拉框中没有 {text!r}（候选：{_combo_items(dialog)}）"
    combo.setCurrentIndex(index)


class TestP214SampleEditStatus:

    @pytest.fixture()
    def make_dialog(self, qapp, db_conn):
        from src.db.repositories.sample_repo import SampleRepository as _Repo
        from src.views.dialogs.sample_edit_dialog import SampleEditDialog

        def _make(status: str):
            repo = _Repo(db_conn)
            sample_id = _insert_sample(db_conn, f"SN-P214-{status}", status)
            sample = repo.get_by_id(sample_id)
            assert sample is not None
            return SampleEditDialog(sample=sample)

        return _make

    def test_legacy_chinese_status_not_rewritten(self, make_dialog):
        """legacy 中文状态（'已归还' 存在 status 列）不得洗成 '在库'/in_stock。"""
        dlg = make_dialog("已归还")

        assert dlg.get_data()["status"] == "已归还"
        assert "已归还（原状态，不可改）" in _combo_items(dlg)
        dlg.deleteLater()

    def test_unknown_enum_value_not_rewritten(self, make_dialog):
        """枚举外的英文状态（'in_use'）原值透传。"""
        dlg = make_dialog("in_use")

        assert dlg.get_data()["status"] == "in_use"
        assert "in_use（原状态，不可改）" in _combo_items(dlg)
        dlg.deleteLater()

    def test_known_status_round_trips(self, make_dialog):
        """枚举内状态正常往返（占位逻辑不干扰正常编辑）。"""
        for value in SAMPLE_STATUS_MAP.values():
            dlg = make_dialog(value)
            assert dlg._status_combo.currentText() == SAMPLE_STATUS_LABELS[value]
            assert dlg.get_data()["status"] == value
            assert len(_combo_items(dlg)) == len(SAMPLE_STATUS_OPTIONS)
            dlg.deleteLater()

    def test_user_can_replace_legacy_status(self, make_dialog):
        """用户主动选择合法状态时按枚举值写入（占位项不阻断正常修改）。"""
        dlg = make_dialog("已归还")
        _select_status(dlg, "已报废")

        assert dlg.get_data()["status"] == "scrapped"
        dlg.deleteLater()

    def test_empty_status_defaults_to_first_option(self, make_dialog):
        """空状态回落第一个选项（in_stock），且不产生占位项。"""
        dlg = make_dialog("")

        assert dlg.get_data()["status"] == "in_stock"
        assert _combo_items(dlg) == list(SAMPLE_STATUS_OPTIONS)
        dlg.deleteLater()


class TestP214EquipmentEditStatus:

    def test_unknown_status_not_rewritten(self, qapp):
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        dlg = EquipmentEditDialog(Equipment(id=1, name="温度箱", status="in_use"))

        assert dlg.get_data()["status"] == "in_use"
        assert "in_use（原状态，不可改）" in _combo_items(dlg)
        dlg.deleteLater()

    def test_legacy_chinese_status_not_rewritten(self, qapp):
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        dlg = EquipmentEditDialog(Equipment(id=2, name="振动台", status="已维修"))

        assert dlg.get_data()["status"] == "已维修"
        dlg.deleteLater()

    def test_legacy_status_survives_never_calibrated_branch(self, qapp):
        """「未校准」分支同样按原状态透传（审计点名的第二条回写路径）。"""
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        dlg = EquipmentEditDialog(Equipment(id=3, name="湿热箱", status="in_use"))
        dlg._never_calibrated_chk.setChecked(True)

        data = dlg.get_data()
        assert data["status"] == "in_use"
        assert data["calibration_date"] == ""
        dlg.deleteLater()

    def test_known_status_round_trips(self, qapp):
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        for value, label in EQUIPMENT_STATUS_LABELS.items():
            dlg = EquipmentEditDialog(Equipment(id=4, name="设备X", status=value))
            assert dlg._status_combo.currentText() == label
            assert dlg.get_data()["status"] == value
            assert len(_combo_items(dlg)) == len(EQUIPMENT_STATUS_LABELS)
            dlg.deleteLater()

    def test_user_can_replace_legacy_status(self, qapp):
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        dlg = EquipmentEditDialog(Equipment(id=5, name="盐雾箱", status="in_use"))
        _select_status(dlg, "停用")

        assert dlg.get_data()["status"] == "offline"
        dlg.deleteLater()

    def test_new_equipment_has_no_placeholder(self, qapp):
        """新建（equipment=None）不产生占位项，默认'正常'。"""
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        dlg = EquipmentEditDialog(None)

        assert dlg._status_combo.currentText() == "正常"
        assert _combo_items(dlg) == list(EQUIPMENT_STATUS_LABELS.values())
        assert dlg.get_data()["status"] == "available"
        dlg.deleteLater()

    def test_status_options_single_source(self, qapp):
        """状态候选/映射以 constants.EQUIPMENT_STATUS_LABELS 为唯一真源。"""
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

        assert EquipmentEditDialog._STATUS_OPTIONS == list(EQUIPMENT_STATUS_LABELS.values())
        assert EquipmentEditDialog._STATUS_MAP == {
            label: value for value, label in EQUIPMENT_STATUS_LABELS.items()
        }
        assert EquipmentEditDialog._STATUS_REVERSE == dict(EQUIPMENT_STATUS_LABELS)


# ═══════════════════════════════════════════════════════════════════
#  P3-2 — add_transaction 两步写的原子性
# ═══════════════════════════════════════════════════════════════════


class TestP32AddTransactionAtomic:

    def test_status_failure_rolls_back_ledger_row(self, svc, monkeypatch):
        """状态更新失败 → 台账行不能留下（修复前会留下脏流水）。"""
        sample_id = svc.create(sn="AUDIT-TXN-01", status="in_stock")
        repo = svc.repo()

        def _boom(_id: int, _status: str) -> None:
            raise RuntimeError("simulated update_status failure")

        monkeypatch.setattr(repo, "update_status", _boom)

        with pytest.raises(RuntimeError, match="simulated update_status failure"):
            svc.add_transaction(sample_id, "check_out")

        assert svc.list_transactions(filter_sn="AUDIT-TXN-01") == []
        assert svc.get(sample_id).status == "in_stock"

    def test_ledger_failure_rolls_back_status(self, svc, monkeypatch):
        """台账写入失败 → 状态联动也不能生效。"""
        sample_id = svc.create(sn="AUDIT-TXN-02", status="in_stock")
        repo = svc.repo()

        def _boom(*_a, **_kw):
            raise RuntimeError("simulated ledger failure")

        monkeypatch.setattr(repo, "add_transaction", _boom)

        with pytest.raises(RuntimeError, match="simulated ledger failure"):
            svc.add_transaction(sample_id, "check_out")

        assert svc.get(sample_id).status == "in_stock"

    def test_success_path_still_writes_ledger_and_status(self, svc):
        """正常路径：台账行 + 状态联动都生效（防过度收紧）。"""
        sample_id = svc.create(sn="AUDIT-TXN-03", status="in_stock")

        svc.add_transaction(sample_id, "check_out")
        assert _txn_types(svc, "AUDIT-TXN-03") == ["check_out"]
        assert svc.get(sample_id).status == "checked_out"

        svc.add_transaction(sample_id, "return")
        assert _txn_types(svc, "AUDIT-TXN-03") == ["return", "check_out"]
        assert svc.get(sample_id).status == "in_stock"

    def test_create_with_ledger_rolls_back_sample_on_ledger_failure(
        self, svc, monkeypatch
    ):
        """台账失败时新建样品整体回滚（原有保证不回退）。"""
        repo = svc.repo()

        def _boom(*_a, **_kw):
            raise RuntimeError("simulated ledger failure")

        monkeypatch.setattr(repo, "add_transaction", _boom)

        with pytest.raises(RuntimeError, match="simulated ledger failure"):
            svc.create_with_ledger(sn="AUDIT-TXN-04")

        assert svc.get_by_sn("AUDIT-TXN-04") is None

    def test_nested_atomic_does_not_swallow_outer_writes(self, svc, monkeypatch):
        """调用方事务内的失败只回滚本次写入，外层已写数据仍提交。"""
        repo = svc.repo()
        original = repo.add_transaction

        def _boom(*_a, **_kw):
            raise RuntimeError("simulated ledger failure")

        with svc.transaction():
            svc.create(sn="AUDIT-TXN-OUTER")
            monkeypatch.setattr(repo, "add_transaction", _boom)
            with pytest.raises(RuntimeError, match="simulated ledger failure"):
                svc.create_with_ledger(sn="AUDIT-TXN-INNER")
            monkeypatch.setattr(repo, "add_transaction", original)

        assert svc.get_by_sn("AUDIT-TXN-OUTER") is not None
        assert svc.get_by_sn("AUDIT-TXN-INNER") is None

    def test_outer_transaction_rollback_still_wins(self, svc):
        """调用方的整体回滚仍然生效（嵌套 savepoint 不破坏外层原子性）。"""
        sample_id = svc.create(sn="AUDIT-TXN-05", status="in_stock")

        with pytest.raises(RuntimeError, match="boom"):
            with svc.transaction():
                svc.add_transaction(sample_id, "check_out")
                raise RuntimeError("boom")

        assert svc.list_transactions(filter_sn="AUDIT-TXN-05") == []
        assert svc.get(sample_id).status == "in_stock"


# ═══════════════════════════════════════════════════════════════════
#  P3-5 — 批量撤销对已删实体必须报失败
# ═══════════════════════════════════════════════════════════════════


class TestP35BatchUndoConflict:

    @pytest.fixture()
    def undo_case(self, svc):
        repo = svc.repo()
        s1 = repo.insert(sn="AUDIT-UNDO-01", status="in_stock", location="旧A")
        s2 = repo.insert(sn="AUDIT-UNDO-02", status="in_stock", location="旧B")
        cmd = BatchEditSamplesCommand(repo, [
            (s1, {"location": "旧A"}, {"location": "新A"}),
            (s2, {"location": "旧B"}, {"location": "新B"}),
        ])
        mgr = UndoManager()
        mgr.execute(cmd)
        assert repo.get_by_id(s1).location == "新A"
        assert repo.get_by_id(s2).location == "新B"
        return SimpleNamespace(repo=repo, mgr=mgr, cmd=cmd, s1=s1, s2=s2)

    def test_undo_raises_when_target_deleted(self, undo_case):
        """已删实体的撤销必须抛错，而不是返回描述假装成功。"""
        undo_case.repo.delete(undo_case.s2)

        with pytest.raises(UndoConflictError, match="已被删除"):
            undo_case.mgr.undo()

    def test_failed_undo_applies_nothing(self, undo_case):
        """失败时不留半成品：还存在的那个样品保持撤销前状态。"""
        undo_case.repo.delete(undo_case.s2)

        with pytest.raises(UndoConflictError):
            undo_case.mgr.undo()

        assert undo_case.repo.get_by_id(undo_case.s1).location == "新A"

    def test_failed_undo_keeps_command_on_stack(self, undo_case):
        """命令保留在栈上可重试，用户不会静默丢掉撤销能力。"""
        undo_case.repo.delete(undo_case.s2)

        with pytest.raises(UndoConflictError):
            undo_case.mgr.undo()

        assert undo_case.mgr.peek_undo() is undo_case.cmd
        assert undo_case.mgr.can_undo() is True
        assert undo_case.mgr.can_redo() is False

    def test_undo_restores_all_when_targets_exist(self, undo_case):
        """目标都在时批量撤销照常工作。"""
        description = undo_case.mgr.undo()

        assert description == undo_case.cmd.description
        assert undo_case.repo.get_by_id(undo_case.s1).location == "旧A"
        assert undo_case.repo.get_by_id(undo_case.s2).location == "旧B"

    def test_redo_raises_when_target_deleted(self, undo_case):
        """重做路径同样不能静默 no-op。"""
        undo_case.mgr.undo()
        undo_case.repo.delete(undo_case.s2)

        with pytest.raises(UndoConflictError, match="重做"):
            undo_case.mgr.redo()

    def test_apply_raises_when_update_affects_zero_rows(self, undo_case,
                                                        monkeypatch):
        """竞态路径：存在性预检通过但 update 影响 0 行 → 按失败处理。"""
        repo = undo_case.repo
        real_get_by_id = repo.get_by_id
        seen = {"count": 0}

        def _race_get_by_id(sample_id: int):
            if sample_id == undo_case.s2:
                seen["count"] += 1
                if seen["count"] == 1:
                    # 预检时假装还在（模拟预检与写入之间被并发删除）
                    return real_get_by_id(undo_case.s1)
            return real_get_by_id(sample_id)

        repo.delete(undo_case.s2)
        monkeypatch.setattr(repo, "get_by_id", _race_get_by_id)

        with pytest.raises(UndoConflictError, match="影响 0 行"):
            undo_case.mgr.undo()

    def test_undo_succeeds_after_conflict_resolved(self, undo_case, db_conn):
        """冲突解除（实体重新存在）后同一命令仍可撤销 —— 命令未被破坏。"""
        undo_case.repo.delete(undo_case.s2)
        with pytest.raises(UndoConflictError):
            undo_case.mgr.undo()

        # 用原 id 恢复该样品（模拟数据被找回）
        db_conn.execute(
            "INSERT INTO samples (id, sn, status, location) VALUES (?, ?, 'in_stock', '新B')",
            (undo_case.s2, "AUDIT-UNDO-02"),
        )

        assert undo_case.mgr.undo() == undo_case.cmd.description
        assert undo_case.repo.get_by_id(undo_case.s1).location == "旧A"
        assert undo_case.repo.get_by_id(undo_case.s2).location == "旧B"


# ═══════════════════════════════════════════════════════════════════
#  P3-6 — holidays 存量非法日期行不再静默漏假
# ═══════════════════════════════════════════════════════════════════


_INVALID_HOLIDAY_ROWS = [
    ("2026/05/01", "斜杠格式", "legacy"),
    ("2026-13-99", "非法月份日", "legacy"),
    ("20260501", "紧凑格式", "legacy"),
    ("01/01/2026", "倒序格式", "legacy"),
]


class TestP36HolidayInvalidRows:

    @pytest.fixture()
    def holiday_svc(self, db_conn):
        return HolidayService(db_conn)

    @pytest.fixture()
    def with_bad_rows(self, db_conn, holiday_svc):
        for date_str, name, source in _INVALID_HOLIDAY_ROWS:
            db_conn.execute(
                "INSERT INTO holidays (date, name, source) VALUES (?, ?, ?)",
                (date_str, name, source),
            )
        # schema 种子数据里已有 '2026-05-02' 等合法日期，OR IGNORE 保证幂等
        db_conn.execute(
            "INSERT OR IGNORE INTO holidays (date, name, source) "
            "VALUES ('2026-05-02','合法','custom')"
        )
        return holiday_svc

    def test_get_holidays_set_skips_invalid_rows(self, with_bad_rows):
        """非法日期行不进集合（修复前 '2026/05/01' 会被原样返回）。"""
        holidays = with_bad_rows.get_holidays_set()

        for date_str, _name, _source in _INVALID_HOLIDAY_ROWS:
            assert date_str not in holidays, f"{date_str} 是非法行，不该进集合"
        assert "2026-05-02" in holidays

    def test_get_holidays_set_filters_by_year_without_invalid(self, with_bad_rows):
        """按年查询同样不含非法行（修复前 '01/01/2026' 被静默吞掉）。"""
        holidays = with_bad_rows.get_holidays_set(year=2026)

        assert "2026-05-02" in holidays
        assert all(h[:4] == "2026" and h[4] == "-" for h in holidays)
        for date_str, _name, _source in _INVALID_HOLIDAY_ROWS:
            assert date_str not in holidays

    def test_get_holidays_set_logs_warning(self, with_bad_rows, caplog):
        """跳过非法行必须留日志，不静默。"""
        with caplog.at_level(logging.WARNING, logger="src.services.holiday_service"):
            with_bad_rows.get_holidays_set()

        messages = [r.getMessage() for r in caplog.records]
        assert any("非法日期行" in m for m in messages), messages
        assert any(str(len(_INVALID_HOLIDAY_ROWS)) in m for m in messages), messages

    def test_valid_only_data_logs_nothing(self, holiday_svc, caplog):
        """没有非法行时不产生噪声日志（区分度对照）。"""
        with caplog.at_level(logging.WARNING, logger="src.services.holiday_service"):
            holiday_svc.get_holidays_set()

        assert not [r for r in caplog.records if "非法日期行" in r.getMessage()]

    def test_list_invalid_holidays_reports_without_mutation(self, db_conn,
                                                            with_bad_rows):
        """提供只读报告，且绝不静默修改/删除用户数据。"""
        before = db_conn.execute("SELECT COUNT(*) FROM holidays").fetchone()[0]

        invalid = with_bad_rows.list_invalid_holidays()

        assert {row["date"] for row in invalid} == {
            d for d, _n, _s in _INVALID_HOLIDAY_ROWS
        }
        assert all("id" in row and "name" in row for row in invalid)
        after = db_conn.execute("SELECT COUNT(*) FROM holidays").fetchone()[0]
        assert after == before
        raw = {
            r[0] for r in db_conn.execute("SELECT date FROM holidays").fetchall()
        }
        assert {d for d, _n, _s in _INVALID_HOLIDAY_ROWS} <= raw
        # get_holidays（列表接口）仍如实呈现脏数据，交由用户决定是否清洗
        listed = {h["date"] for h in with_bad_rows.get_holidays()}
        assert {d for d, _n, _s in _INVALID_HOLIDAY_ROWS} <= listed

    def test_write_path_rejects_non_iso_formats(self, holiday_svc):
        """写入侧与读取侧同口径：非严格 YYYY-MM-DD 一律拒绝。"""
        for bad in ("2026/05/01", "20260501", "2026-13-99", "01/01/2026", ""):
            with pytest.raises(ValueError, match="格式非法"):
                holiday_svc.add_holiday(bad, "非法", "custom")

    def test_write_path_still_accepts_valid_dates(self, holiday_svc):
        """正常写入不受影响（防过度收紧）。"""
        assert holiday_svc.add_holiday("2031-05-01", "劳动节", "custom") > 0
        assert "2031-05-01" in holiday_svc.get_holidays_set(year=2031)
