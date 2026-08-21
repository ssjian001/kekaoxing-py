"""2026-08-21 审计修复回归测试。

覆盖 6 项修复:
- #1 单实例锁: 失败分支不再 unlock/unlink（静态断言）
- #2 入库原子化: create_with_ledger 单事务，台账失败整体回滚
- #3 矩阵编辑: save_result 即 upsert（handler 不再 delete+save）
- #4 result_matrix: 双击从内部缓存取真值（实测值模式不再误写 pass）
- #5 就地编辑: 原值不在选项列表时占位项守卫，被动关闭不提交
- S1 compress_schedule: 找不到槽位时任务放回时间线
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import apsw
import pytest

from PySide6.QtWidgets import QApplication

from src.db.schema import init_schema


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db_conn(tmp_path):
    conn = apsw.Connection(str(tmp_path / "audit_fix.db"))
    init_schema(conn)
    yield conn
    conn.close()


# ── #1 单实例锁 ──────────────────────────────────────────────

class TestSingleInstanceLock:
    def test_lock_failure_branch_does_not_unlock_or_unlink(self):
        """抢锁失败分支不得调用 unlock/unlink（否则拆掉对方互斥保护）。"""
        import re
        src = open(os.path.join(os.path.dirname(__file__), "..", "main.py")).read()
        m = re.search(r"if not _lock\.tryLock\(100\):.*?return 1", src, re.S)
        assert m, "找不到单实例锁失败分支"
        # 只看实际代码行，注释里允许出现 unlock/unlink 字样
        code_lines = [
            ln for ln in m.group(0).splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        block = "\n".join(code_lines)
        assert "_lock.unlock()" not in block, "失败分支仍在 unlock 对方持有的锁"
        assert ".unlink(" not in block, "失败分支仍在删除对方的锁文件"


# ── #2 入库原子化 ────────────────────────────────────────────

class TestCreateWithLedger:
    def _make_service(self, db_conn):
        from src.db.repositories.sample_repo import SampleRepository
        from src.services.sample_service import SampleService
        repo = SampleRepository(db_conn)
        return SampleService(repo)

    def test_create_with_ledger_success(self, qapp, db_conn):
        svc = self._make_service(db_conn)
        sid = svc.create_with_ledger(
            sn="AUDIT-001", status="in_stock",
        )
        txns = [t for t in svc.list_transactions(filter_sn="AUDIT-001")]
        assert len(txns) == 1
        assert txns[0]["type"] == "check_in"

    def test_ledger_failure_rolls_back_sample(self, qapp, db_conn):
        """台账写入失败 → 样品也必须不存在（整体回滚）。"""
        svc = self._make_service(db_conn)
        original = svc._repo.add_transaction

        def boom(*a, **kw):
            raise RuntimeError("simulated ledger failure")

        svc._repo.add_transaction = boom  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            svc.create_with_ledger(sn="AUDIT-002", status="in_stock")
        svc._repo.add_transaction = original  # type: ignore[method-assign]
        assert svc.get_by_sn("AUDIT-002") is None, "样品未被回滚——入库仍非原子"

    def test_handler_uses_create_with_ledger(self):
        """handler 必须走 create_with_ledger，且不再有越层 _repo.transaction。"""
        src = open(
            os.path.join(
                os.path.dirname(__file__), "..", "src/handlers/sample_handlers.py"
            )
        ).read()
        assert "create_with_ledger" in src
        assert "_repo.transaction" not in src.split("def _on_sample_checkout")[0].split("def _on_sample_checkin")[-1]


# ── #3 矩阵编辑 upsert ───────────────────────────────────────

class TestMatrixUpsert:
    def test_handler_no_delete_before_save(self):
        src = open(
            os.path.join(
                os.path.dirname(__file__), "..", "src/handlers/plan_handlers.py"
            )
        ).read()
        fn = src.split("def _on_matrix_result_edit")[1].split("def ")[0]
        assert "delete_result" not in fn, "矩阵编辑仍在 delete+save（非原子）"

    def test_save_result_is_upsert(self, qapp, db_conn):
        """同 (task_id, sample_id) 二次保存应更新而非新增行。"""
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.db.repositories.test_result_repo import TestResultRepository
        from src.models.test_plan import TestPlan, TestTask

        plan_repo = TestPlanRepository(db_conn)
        task_repo = TestTaskRepository(db_conn)
        result_repo = TestResultRepository(db_conn)

        from src.db.repositories.project_repo import ProjectRepository
        project_id = ProjectRepository(db_conn).insert(name="P-audit-proj")
        pid = plan_repo.insert(name="P-audit", project_id=project_id)
        tid = task_repo.insert(plan_id=pid, name="T-audit")

        rid1 = result_repo.upsert(task_id=tid, sample_id=None, result="pass")
        rid2 = result_repo.upsert(task_id=tid, sample_id=None, result="fail")
        assert rid1 == rid2, "upsert 应更新同一行"
        rows = result_repo.get_by_task(tid)
        assert len(rows) == 1
        assert rows[0].result == "fail"


# ── #4 result_matrix 双击真值 ────────────────────────────────

class TestMatrixDoubleClickTruth:
    def _build_matrix(self, qapp):
        from src.views.widgets.result_matrix import _ResultMatrixWidget
        return _ResultMatrixWidget()

    def _feed_data(self, matrix, fail_measured=""):
        """构造 1 任务 × 1 样品，结果为 fail。"""
        from src.models.test_plan import TestTask

        class _R:
            id = 900
            task_id = 1
            sample_id = 100
            result = "fail"
            measured_value = fail_measured
            test_date = "2026-08-21"

        task = TestTask(id=1, name="T")
        matrix.refresh([task], [_R()], {100: "SN-100"})

    def test_lookup_cache_populated(self, qapp):
        matrix = self._build_matrix(qapp)
        self._feed_data(matrix)
        assert matrix._result_lookup.get((1, 100)) == "fail"

    def test_double_click_in_measured_mode_cycles_from_fail(self, qapp):
        """实测值模式下双击 fail 单元格 → conditional（而非 pass）。"""
        matrix = self._build_matrix(qapp)
        self._feed_data(matrix, fail_measured="0.83")
        # 切实测值模式（走真实 _on_mode_changed 路径）
        matrix._on_mode_changed(matrix._MODE_MEASURED)
        received: list[tuple] = []
        matrix._on_result_changed = lambda t, s, r: received.append((t, s, r))
        # 找到 fail 单元格并双击
        table = matrix._table
        target = None
        for row in range(table.rowCount()):
            for col in range(1, table.columnCount() - 1):
                item = table.item(row, col)
                if item and item.data(Qt_UserRole()) is not None:
                    target = (row, col)
        assert target, "找不到可编辑单元格"
        table.cellDoubleClicked.emit(*target)
        assert received, "双击未触发回调"
        assert received[0][2] == "conditional", (
            f"实测值模式双击 fail 得到 {received[0][2]}，应为 conditional"
        )


def Qt_UserRole():
    from PySide6.QtCore import Qt
    return Qt.ItemDataRole.UserRole


# ── #5 就地编辑占位项守卫 ─────────────────────────────────────

class TestInlineEditorGuard:
    def _make_table(self, qapp):
        from src.views.widgets.task_table import _TaskTable
        t = _TaskTable()
        return t

    def _seed_row(self, table, task):
        """set_tasks 建立行映射（get_task_at_row 需要 item(0,0) 存在）。"""
        table.set_tasks([task])

    def test_empty_category_gets_placeholder_item(self, qapp):
        """空 category（默认值）→ combo 含「（当前）」占位项且选中它。"""
        from src.models.test_plan import TestTask
        table = self._make_table(qapp)
        task = TestTask(id=7, name="T", category="")
        self._seed_row(table, task)
        table._edit_inline_category(0, task)
        combo = table.cellWidget(0, 2)
        assert combo is not None
        assert "（当前）" in combo.currentText(), "空 category 未被占位项保护"

    def test_legacy_status_gets_placeholder(self, qapp):
        """历史状态 "done" 不在枚举 → 占位项保护，不落 pending。"""
        from src.models.test_plan import TestTask
        table = self._make_table(qapp)
        task = TestTask(id=8, name="T", status="done")
        self._seed_row(table, task)
        table._edit_inline_status(0, task)
        combo = table.cellWidget(0, 8)
        assert combo is not None
        assert "done（当前）" in combo.currentText()

    def test_deleted_technician_gets_placeholder(self, qapp):
        """technician_id 指向已删除技术员 → 占位项保持原指派。"""
        from src.models.test_plan import TestTask
        table = self._make_table(qapp)
        table._technician_list = []  # 技术员已全部删除
        task = TestTask(id=9, name="T", technician_id=42)
        self._seed_row(table, task)
        table._edit_inline_technician(0, task)
        combo = table.cellWidget(0, 9)
        assert combo is not None
        assert "已删除" in combo.currentText()
        assert combo.currentData() == 42

    def test_out_of_range_priority_gets_placeholder(self, qapp):
        """越界 priority（∉1..5，模拟绕过模型校验的脏数据）→ 占位项保持原值。"""
        from src.models.test_plan import TestTask
        table = self._make_table(qapp)
        task = TestTask(id=11, name="T")
        task.priority = 9  # 直接改属性绕过 __post_init__ 校验，模拟历史脏数据
        self._seed_row(table, task)
        table._edit_inline_priority(0, task)
        combo = table.cellWidget(0, 7)
        assert combo is not None
        assert "9（当前）" in combo.currentText()

    def test_valid_category_no_placeholder(self, qapp):
        """合法 category 不应出现占位项（回归保护）。"""
        from src.models.test_plan import TestTask
        table = self._make_table(qapp)
        task = TestTask(id=10, name="T", category="环境试验")
        self._seed_row(table, task)
        table._edit_inline_category(0, task)
        combo = table.cellWidget(0, 2)
        assert combo is not None
        assert "（当前）" not in combo.currentText()
        assert combo.currentText() == "环境试验"


# ── #6 设备校准日期「未校准」开关 ─────────────────────────────

class TestNeverCalibratedSwitch:
    def _make_dialog(self, qapp, equipment=None):
        from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog
        return EquipmentEditDialog(equipment=equipment)

    def test_new_equipment_defaults_to_never_calibrated(self, qapp):
        """新建设备默认勾选未校准 → get_data 返回空校准数据（不伪造今天）。"""
        dlg = self._make_dialog(qapp)
        assert dlg._never_calibrated_chk.isChecked()
        data = dlg.get_data()
        assert data["calibration_date"] == ""
        assert data["next_calibration_date"] == ""

    def test_unchecked_keeps_date_semantics(self, qapp):
        """取消勾选后日期字段启用，get_data 走原逻辑。"""
        dlg = self._make_dialog(qapp)
        dlg._never_calibrated_chk.setChecked(False)
        assert dlg._calibration_edit.isEnabled()
        data = dlg.get_data()
        assert data["calibration_date"] != ""  # QDateEdit 默认今天，显式选择保留

    def test_edit_with_cal_date_starts_unchecked(self, qapp):
        """编辑已有校准日期的设备 → 默认不勾选，数据预填。"""
        from src.models.common import Equipment
        eq = Equipment(
            id=1, name="温度箱", model="TH-001", type="温度箱",
            calibration_date="2026-01-15",
            next_calibration_date="2027-01-15",
            calibration_interval_months=12,
        )
        dlg = self._make_dialog(qapp, eq)
        assert not dlg._never_calibrated_chk.isChecked()
        data = dlg.get_data()
        assert data["calibration_date"] == "2026-01-15"

    def test_toggle_disables_inputs(self, qapp):
        """勾选切换联动禁用/启用输入控件。"""
        dlg = self._make_dialog(qapp)
        dlg._never_calibrated_chk.setChecked(False)
        assert dlg._calibration_edit.isEnabled()
        assert dlg._interval_spin.isEnabled()
        dlg._never_calibrated_chk.setChecked(True)
        assert not dlg._calibration_edit.isEnabled()
        assert not dlg._interval_spin.isEnabled()


# ── #7 项目级联删除解关联跨项目引用 ───────────────────────────

class TestProjectDeleteDetachesCrossRefs:
    def _setup(self, db_conn):
        from src.db.repositories.project_repo import ProjectRepository
        from src.db.repositories.sample_repo import SampleRepository
        from src.db.repositories.issue_repo import IssueRepository
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.db.repositories.test_task_repo import TestTaskRepository
        from src.services.project_service import ProjectService

        project_repo = ProjectRepository(db_conn)
        sample_repo = SampleRepository(db_conn)
        issue_repo = IssueRepository(db_conn)
        svc = ProjectService(
            project_repo,
            plan_repo=TestPlanRepository(db_conn),
            task_repo=TestTaskRepository(db_conn),
            sample_repo=sample_repo,
            issue_repo=issue_repo,
        )
        return svc, project_repo, sample_repo, issue_repo

    def test_soft_deleted_cross_project_issue_survives(self, qapp, db_conn):
        """外项目软删 Issue 引用本项目样品 → 删项目后 Issue 本体存活、引用置空。"""
        from src.models.issue import Issue
        from src.models.sample import Sample

        svc, project_repo, sample_repo, issue_repo = self._setup(db_conn)
        pid_a = project_repo.insert(name="项目A")
        pid_b = project_repo.insert(name="项目B")
        sid = sample_repo.insert(sn="X-REF-001", project_id=pid_a, status="in_stock")

        # 项目B 的 Issue 引用项目A 的样品，然后软删
        iid = issue_repo.insert(
            title="跨项目引用", project_id=pid_b, sample_id=sid, severity="major",
        )
        issue_repo.soft_delete(iid)

        # 删除项目A
        svc.delete(pid_a)

        # 软删 Issue 必须存活且引用被置空
        survivor = issue_repo.get_by_id(iid)
        assert survivor is not None, "外项目软删 Issue 被 CASCADE 物理清除——软删保护仍被绕过"
        assert survivor.sample_id is None, "引用未被解关联"
        assert survivor.is_deleted == 1

    def test_active_cross_project_issue_survives(self, qapp, db_conn):
        """外项目活跃 Issue 引用本项目任务 → 删项目后存活。"""
        from src.models.issue import Issue

        svc, project_repo, sample_repo, issue_repo = self._setup(db_conn)
        pid_a = project_repo.insert(name="项目A")
        pid_b = project_repo.insert(name="项目B")
        from src.db.repositories.test_plan_repo import TestPlanRepository
        from src.db.repositories.test_task_repo import TestTaskRepository
        plan_id = TestPlanRepository(db_conn).insert(name="PA计划", project_id=pid_a)
        task_id = TestTaskRepository(db_conn).insert(plan_id=plan_id, name="T1")

        iid = issue_repo.insert(
            title="跨项目任务引用", project_id=pid_b, task_id=task_id, severity="major",
        )

        svc.delete(pid_a)

        survivor = issue_repo.get_by_id(iid)
        assert survivor is not None, "外项目活跃 Issue 被物理清除"
        assert survivor.task_id is None

    def test_same_project_issue_still_deleted(self, qapp, db_conn):
        """本项目自己的 Issue 照常级联删除（解关联不影响正常路径）。"""
        from src.models.issue import Issue

        svc, project_repo, sample_repo, issue_repo = self._setup(db_conn)
        pid_a = project_repo.insert(name="项目A")
        sid = sample_repo.insert(sn="OWN-001", project_id=pid_a, status="in_stock")
        iid = issue_repo.insert(
            title="本项目Issue", project_id=pid_a, sample_id=sid, severity="major",
        )

        svc.delete(pid_a)
        assert issue_repo.get_by_id(iid) is None, "本项目 Issue 应随项目删除"


# ── S1 compress 放回时间线 ────────────────────────────────────

class TestCompressRestoresOnFailure:
    def test_no_slot_task_stays_in_timeline(self):
        """find_earliest_slot 返回 None 时任务资源占用必须保留在时间线。"""
        from src.services.scheduler import (
            ScheduleConfig, build_dependency_map, compress_schedule,
            place_task,
        )
        from src.models.test_plan import TestTask

        config = ScheduleConfig(start_date="2026-08-21", skip_weekends=False)

        blocker = TestTask(id=1, name="blocker", duration=400, priority=1)
        mover = TestTask(id=2, name="mover", duration=1, priority=2)
        blocker.start_day = 0
        mover.start_day = 0

        timeline: dict[int, dict[int, int]] = {}
        place_task(blocker, 0, timeline, config)
        # 记录 blocker 的占用指纹
        before = {d: dict(u) for d, u in timeline.items()}
        assert sum(u.get(-1, 0) for u in timeline.values()) >= 1

        dep_map = build_dependency_map([blocker, mover])
        # mover 从 day 0 起找槽位；max_scan 默认 365，blocker 占满 400 天
        # → mover 找不到合法槽位 → 必须放回原位（时间线计数不变）
        compress_schedule(
            [mover], timeline, config, dep_map,
            locked_ids=set(), all_tasks=[blocker, mover],
        )
        after = {d: dict(u) for d, u in timeline.items()}
        # blocker 的占用不能因 compress 流程丢失
        for day, usage in before.items():
            for eq, cnt in usage.items():
                assert after.get(day, {}).get(eq, 0) >= cnt, (
                    f"day {day} eq {eq} 占用丢失: {before} -> {after}"
                )
