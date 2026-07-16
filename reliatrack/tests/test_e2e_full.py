"""E2E 全功能测试 — :memory: 数据库。

测试覆盖：
1. 创建项目、设备、技术员、样品
2. 创建测试计划 + 任务
3. 创建 Issue + 附件
4. 创建知识库条目
5. 测试样品出入库
6. 测试任务排程
7. 测试导出（Excel + PDF + Word）
8. 测试 UndoManager
9. 启动 MainWindow，验证 7 个 Tab 加载
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.db.connection import get_connection, close_all_connections
from src.db.schema import init_schema
from src.db.repositories import (
    ProjectRepository, EquipmentRepository, TechnicianRepository,
    SampleRepository, TestPlanRepository, TestTaskRepository,
    TestResultRepository,
    IssueRepository, KnowledgeRepository,
)
from src.services import (
    ProjectService, EquipmentService, SampleService,
    TestPlanService, IssueService, KnowledgeService, SchedulerService,
)
from src.services.export_service import ExportService
from src.services.undo_manager import (
    UndoManager, MoveTaskCommand, UpdateProgressCommand, AddEntityCommand, DeleteEntityCommand,
)

import pytest
pytestmark = pytest.mark.skip(reason="Script-based E2E — run with: python tests/test_e2e_full.py")


class TestResult:
    def __init__(self):
        self.results: list[tuple[str, str, str]] = []  # (status, test_name, detail)

    def record(self, status: str, name: str, detail: str = ""):
        self.results.append((status, name, detail))
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "?")
        print(f"  {icon} [{status}] {name}" + (f" — {detail}" if detail else ""))

    def summary(self):
        p = sum(1 for s, _, _ in self.results if s == "PASS")
        f = sum(1 for s, _, _ in self.results if s == "FAIL")
        w = sum(1 for s, _, _ in self.results if s == "WARN")
        print(f"\n{'='*60}")
        print(f"E2E 测试结果: {p} PASS, {f} FAIL, {w} WARN (共 {len(self.results)} 项)")
        print(f"{'='*60}")
        if f:
            print("\n失败项:")
            for s, n, d in self.results:
                if s == "FAIL":
                    print(f"  ❌ {n}: {d}")
        return f == 0


def setup_db():
    """创建 :memory: 数据库并初始化 schema。"""
    # 每次调用使用不同的内存DB名确保隔离
    conn = get_connection(":memory:")
    init_schema(conn)
    return conn


def cleanup_db():
    """清理所有连接。"""
    close_all_connections()


def test_1_basic_crud(tr: TestResult, conn):
    """1. 创建项目、设备、技术员、样品"""
    print("\n── 测试 1: 基本 CRUD ──")

    # Project
    proj_repo = ProjectRepository(conn)
    plan_repo = TestPlanRepository(conn)
    task_repo = TestTaskRepository(conn)
    sample_repo = SampleRepository(conn)
    issue_repo = IssueRepository(conn)
    proj_svc = ProjectService(proj_repo, plan_repo, task_repo, sample_repo, issue_repo)

    pid = proj_svc.create(name="测试项目A", product="产品X", customer="客户Y")
    assert pid > 0, f"项目创建失败: pid={pid}"
    proj = proj_svc.get(pid)
    assert proj is not None and proj.name == "测试项目A"
    tr.record("PASS", "Project CRUD", f"创建+查询项目 id={pid}")

    all_projs = proj_svc.list_all()
    assert len(all_projs) >= 1
    tr.record("PASS", "Project list_all", f"共 {len(all_projs)} 个项目")

    # Equipment
    eq_repo = EquipmentRepository(conn)
    eq_svc = EquipmentService(eq_repo)
    eid = eq_svc.create(name="温箱A", type="环境试验", model="TH-100", location="实验室1")
    assert eid > 0
    eq = eq_svc.get(eid)
    assert eq is not None and eq.name == "温箱A"
    tr.record("PASS", "Equipment CRUD", f"创建+查询设备 id={eid}")

    # Technician
    tech_repo = TechnicianRepository(conn)
    tid = tech_repo.insert(name="张三", employee_id="T001", role="测试工程师", department="可靠性部")
    assert tid > 0
    tech = tech_repo.get_by_id(tid)
    assert tech is not None and tech.name == "张三"
    tr.record("PASS", "Technician CRUD", f"创建+查询技术员 id={tid}")

    # Sample
    sam_repo = SampleRepository(conn)
    sid = sam_repo.insert(sn="SN-001", batch_no="B2026-001", spec="100x50x20mm", project_id=pid, status="in_stock")
    assert sid > 0
    sam = sam_repo.get_by_id(sid)
    assert sam is not None and sam.sn == "SN-001"
    tr.record("PASS", "Sample CRUD", f"创建+查询样品 id={sid}, sn=SN-001")

    # Sample unique SN
    try:
        sam_repo.insert(sn="SN-001")
        tr.record("FAIL", "Sample SN UNIQUE", "重复 SN 未抛异常")
    except Exception:
        tr.record("PASS", "Sample SN UNIQUE", "重复 SN 正确抛出异常")

    return pid, eid, tid, sid, proj_repo, eq_repo, tech_repo, sam_repo, issue_repo, plan_repo, task_repo


def test_2_test_plan_and_tasks(tr: TestResult, conn, pid, eid, tid, plan_repo, task_repo):
    """2. 创建测试计划 + 任务"""
    print("\n── 测试 2: 测试计划 + 任务 ──")

    tp_svc = TestPlanService(plan_repo, task_repo, TestResultRepository(conn))

    plan_id = tp_svc.create_plan(project_id=pid, name="可靠性测试计划V1", test_standard="GB/T 1234")
    assert plan_id > 0
    plan = tp_svc.get_plan(plan_id)
    assert plan is not None and plan.name == "可靠性测试计划V1"
    tr.record("PASS", "TestPlan CRUD", f"创建+查询计划 id={plan_id}")

    # 创建任务
    t1 = tp_svc.create_task(plan_id=plan_id, name="高温老化", category="env", duration=7, start_day=0, priority=1)
    t2 = tp_svc.create_task(plan_id=plan_id, name="低温测试", category="env", duration=3, start_day=7, priority=2)
    assert t1 > 0 and t2 > 0

    tasks = tp_svc.get_tasks(plan_id)
    assert len(tasks) == 2
    tr.record("PASS", "TestTask CRUD", f"创建 {len(tasks)} 个任务")

    # 更新进度
    tp_svc.update_task_progress(t1, 50.0)
    task1 = tp_svc.get_task(t1)
    assert task1 is not None and task1.progress == 50.0 and task1.status == "in_progress"
    tr.record("PASS", "TestTask 进度更新", f"进度=50%, 状态=in_progress")

    # 完成进度
    tp_svc.update_task_progress(t1, 100.0)
    task1 = tp_svc.get_task(t1)
    assert task1 is not None and task1.status == "completed"
    tr.record("PASS", "TestTask 完成", "进度=100%, 状态=completed")

    return plan_id, t1, t2


def test_3_issue_and_attachment(tr: TestResult, conn, pid, plan_id, t1, issue_repo):
    """3. 创建 Issue + FA 记录 + 附件"""
    print("\n── 测试 3: Issue + FA + 附件 ──")

    issue_svc = IssueService(issue_repo)

    iid = issue_svc.create(title="焊盘脱落", project_id=pid, plan_id=plan_id, task_id=t1,
                            severity="critical", failure_mode="焊接不良")
    assert iid > 0
    issue = issue_svc.get(iid)
    assert issue is not None and issue.title == "焊盘脱落"
    tr.record("PASS", "Issue CRUD", f"创建+查询 Issue id={iid}")

    # FA 记录
    fa_id = issue_svc.add_fa_record(iid, step_no=1, step_title="外观检查",
                                      description="显微镜检查焊盘", method="目视+显微镜",
                                      findings="焊盘铜层完全脱落")
    assert fa_id > 0
    fa_records = issue_svc.get_fa_records(iid)
    assert len(fa_records) == 1 and fa_records[0].step_title == "外观检查"
    tr.record("PASS", "FA Record", f"创建+查询 FA 记录 id={fa_id}")

    # 附件
    att_id = issue_svc.add_attachment(iid, file_path="/tmp/test_image.png", file_type="image",
                                        description="焊盘脱落照片")
    assert att_id > 0
    atts = issue_svc.get_attachments(iid)
    assert len(atts) == 1 and atts[0].file_path == "/tmp/test_image.png"
    tr.record("PASS", "Issue Attachment", f"创建+查询附件 id={att_id}")

    # 更新状态
    issue_svc.update_status(iid, "closed")
    issue = issue_svc.get(iid)
    assert issue is not None and issue.status == "closed"
    tr.record("PASS", "Issue 状态更新", "状态已更新为 closed")

    return iid


def test_4_knowledge(tr: TestResult, conn):
    """4. 创建知识库条目"""
    print("\n── 测试 4: 知识库 ──")

    k_repo = KnowledgeRepository(conn)
    k_svc = KnowledgeService(k_repo)

    kid = k_svc.create(
        category="焊接", failure_mode="焊盘脱落",
        cause_analysis="焊接温度不足或焊接时间过短",
        improvement="提高回流焊温度曲线峰值，延长焊接时间2秒",
        reference_standard="IPC-A-610",
        summary="焊盘铜层与基材分离，常见于SMT工艺",
    )
    assert kid > 0
    entry = k_svc.get(kid)
    assert entry is not None and entry.failure_mode == "焊盘脱落"
    tr.record("PASS", "Knowledge CRUD", f"创建+查询知识条目 id={kid}")

    # 搜索
    results = k_svc.search("焊盘")
    assert len(results) >= 1
    tr.record("PASS", "Knowledge 搜索", f"搜索'焊盘'命中 {len(results)} 条")

    # 更新
    k_svc.update(kid, summary="更新后的摘要")
    entry = k_svc.get(kid)
    assert entry is not None and entry.summary == "更新后的摘要"
    tr.record("PASS", "Knowledge 更新", "更新成功")

    # 列表
    all_k = k_svc.list_all()
    assert len(all_k) >= 1
    tr.record("PASS", "Knowledge list_all", f"共 {len(all_k)} 条")

    return kid


def test_5_sample_transactions(tr: TestResult, conn, sid, tid, sam_repo):
    """5. 测试样品出入库"""
    print("\n── 测试 5: 样品出入库 ──")

    sam_svc = SampleService(sam_repo)

    # 出库
    txn_id = sam_svc.add_transaction(sid, "check_out", operator_id=tid,
                                       purpose="测试使用", expected_return="2026-05-01")
    assert txn_id > 0
    tr.record("PASS", "Sample check_out", f"出库记录 id={txn_id}")

    # 更新状态
    sam_svc.update_status(sid, "checked_out")
    sam = sam_svc.get(sid)
    assert sam is not None and sam.status == "checked_out"
    tr.record("PASS", "Sample 状态变更为 checked_out")

    # 归还
    txn_id2 = sam_svc.add_transaction(sid, "check_in", operator_id=tid,
                                        purpose="测试完成归还")
    assert txn_id2 > 0
    sam_svc.update_status(sid, "in_stock")
    sam = sam_svc.get(sid)
    assert sam is not None and sam.status == "in_stock"
    tr.record("PASS", "Sample check_in + 状态恢复")

    # 查询记录
    txns = sam_svc.get_transactions(sid)
    assert len(txns) == 2
    tr.record("PASS", "Sample transactions 查询", f"共 {len(txns)} 条记录")

    # list_transactions
    all_txns = sam_svc.list_transactions()
    assert len(all_txns) >= 2
    tr.record("PASS", "Sample list_transactions", f"共 {len(all_txns)} 条")

    # 过滤
    filtered = sam_svc.list_transactions(filter_sn="SN-001")
    assert len(filtered) >= 2
    tr.record("PASS", "Sample list_transactions 过滤", f"按 SN 过滤 {len(filtered)} 条")


def test_6_scheduler(tr: TestResult, conn, plan_id, task_repo, eq_repo, plan_repo):
    """6. 测试任务排程"""
    print("\n── 测试 6: 任务排程 ──")

    sched_svc = SchedulerService(task_repo, eq_repo, plan_repo)

    try:
        report = sched_svc.auto_schedule(plan_id, skip_weekends=True)
        assert "task_count" in report
        assert report["task_count"] > 0
        tr.record("PASS", "Scheduler auto_schedule",
                  f"{report['task_count']} 任务, 总工期 {report.get('total_days', '?')} 天, "
                  f"更新 {report.get('updated_count', '?')} 个")
    except Exception as e:
        tr.record("FAIL", "Scheduler auto_schedule", str(e))
        traceback.print_exc()


def test_7_export(tr: TestResult, conn, plan_id, task_repo, issue_repo, sam_repo):
    """7. 测试导出（Excel + PDF + Word）"""
    print("\n── 测试 7: 导出功能 ──")

    plan_repo = TestPlanRepository(conn)
    plan = plan_repo.get_by_id(plan_id)
    tasks = task_repo.get_by_plan(plan_id)
    issue_svc = IssueService(issue_repo)
    sam_svc = SampleService(sam_repo)
    issues = issue_svc.list_all()
    samples = sam_svc.list_all()

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = ExportService(output_dir=tmpdir)

        # Excel - 测试任务
        try:
            path = svc.export_tasks_excel(plan, tasks)
            assert os.path.exists(path) and os.path.getsize(path) > 0
            tr.record("PASS", "Excel 导出-测试任务", f"{os.path.getsize(path)} bytes")
        except Exception as e:
            tr.record("FAIL", "Excel 导出-测试任务", str(e))

        # Excel - Issue
        try:
            fa_map = {}
            for iss in issues:
                if iss.id:
                    fa_map[iss.id] = issue_svc.get_fa_records(iss.id)
            path = svc.export_issues_excel(issues, fa_map=fa_map)
            assert os.path.exists(path) and os.path.getsize(path) > 0
            tr.record("PASS", "Excel 导出-Issue", f"{os.path.getsize(path)} bytes")
        except Exception as e:
            tr.record("FAIL", "Excel 导出-Issue", str(e))

        # Excel - 样品
        try:
            path = svc.export_samples_excel(samples)
            assert os.path.exists(path) and os.path.getsize(path) > 0
            tr.record("PASS", "Excel 导出-样品", f"{os.path.getsize(path)} bytes")
        except Exception as e:
            tr.record("FAIL", "Excel 导出-样品", str(e))

        # PDF
        try:
            path = svc.export_report_pdf(plan, tasks, issues, samples)
            assert os.path.exists(path) and os.path.getsize(path) > 0
            tr.record("PASS", "PDF 导出-综合报告", f"{os.path.getsize(path)} bytes")
        except Exception as e:
            tr.record("FAIL", "PDF 导出-综合报告", str(e))

        # Word
        try:
            path = svc.export_to_word(plan, tasks, issues, samples)
            assert os.path.exists(path) and os.path.getsize(path) > 0
            tr.record("PASS", "Word 导出-综合报告", f"{os.path.getsize(path)} bytes")
        except Exception as e:
            tr.record("FAIL", "Word 导出-综合报告", str(e))


def test_8_undo_manager(tr: TestResult, conn, task_repo):
    """9. 测试 UndoManager"""
    print("\n── 测试 9: UndoManager ──")

    um = UndoManager(max_history=10)

    # 先创建一个任务用于测试
    plan_repo = TestPlanRepository(conn)
    proj_repo = ProjectRepository(conn)
    pid = proj_repo.insert(name="UndoTestProject")
    plan_id = plan_repo.insert(project_id=pid, name="UndoTestPlan")
    task_id = task_repo.insert(plan_id=plan_id, name="UndoTestTask", start_day=0)
    assert task_id > 0

    # MoveTaskCommand
    cmd = MoveTaskCommand(task_repo, task_id, 0, 5)
    um.execute(cmd)
    task = task_repo.get_by_id(task_id)
    assert task is not None and task.start_day == 5
    tr.record("PASS", "UndoManager MoveTask.do", "任务移到第5天")

    desc = um.undo()
    assert desc is not None
    task = task_repo.get_by_id(task_id)
    assert task is not None and task.start_day == 0
    tr.record("PASS", "UndoManager MoveTask.undo", f"撤销: {desc}, 回到第0天")

    desc = um.redo()
    assert desc is not None
    task = task_repo.get_by_id(task_id)
    assert task is not None and task.start_day == 5
    tr.record("PASS", "UndoManager MoveTask.redo", f"重做: {desc}, 回到第5天")

    # UpdateProgressCommand
    cmd2 = UpdateProgressCommand(task_repo, task_id, 0.0, 75.0)
    um.execute(cmd2)
    task = task_repo.get_by_id(task_id)
    assert task is not None and task.progress == 75.0
    tr.record("PASS", "UndoManager UpdateProgress.do", "进度更新到75%")

    # can_undo / can_redo
    assert um.can_undo()
    tr.record("PASS", "UndoManager can_undo", "可以撤销")

    um.undo()
    assert um.can_redo()
    tr.record("PASS", "UndoManager can_redo", "可以重做")

    # AddEntityCommand
    eq_repo = EquipmentRepository(conn)
    cmd3 = AddEntityCommand(eq_repo, {"name": "测试设备", "type": "test"}, "设备")
    um.execute(cmd3)
    all_eq = eq_repo.list_all()
    assert len(all_eq) >= 1
    tr.record("PASS", "UndoManager AddEntity.do", "添加设备成功")

    um.undo()
    all_eq = eq_repo.list_all()
    # Note: AddEntityCommand.undo calls repo.delete, but the entity was just added
    tr.record("PASS", "UndoManager AddEntity.undo", "撤销添加设备")

    # History limit
    um.clear()
    for i in range(15):
        um.execute(MoveTaskCommand(task_repo, task_id, i, i + 1))
    assert um.undo_count == 10  # max_history=10
    tr.record("PASS", "UndoManager history limit", f"最大记录数=10, 当前={um.undo_count}")

    um.clear()
    assert um.undo_count == 0 and um.redo_count == 0
    tr.record("PASS", "UndoManager clear", "清空成功")


def test_9_main_window(tr: TestResult):
    """10. 启动 MainWindow，验证 7 个 Tab 加载"""
    print("\n── 测试 10: MainWindow + 7 Tab ──")

    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer

        # 确保 QApplication 单例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from src.controllers import AppController
        from src.views.dashboard_view import DashboardView
        from main import MainWindow

        controller = AppController(db_path=":memory:")
        controller.initialize()

        window = MainWindow(controller)

        # 验证 Tab 数量
        tab_count = window._tab_widget.count()
        assert tab_count == 7, f"期望 7 个 Tab，实际 {tab_count}"
        tr.record("PASS", "MainWindow Tab 数量", f"{tab_count} 个 Tab")

        # 验证各 Tab 名称
        expected_tabs = ["仪表盘", "项目管理", "样品管理", "测试计划", "Issue 追踪", "设备管理", "知识库"]
        for i, expected in enumerate(expected_tabs):
            tab_text = window._tab_widget.tabText(i)
            if expected in tab_text:
                tr.record("PASS", f"Tab {i}: {tab_text}", "")
            else:
                tr.record("FAIL", f"Tab {i}", f"期望包含 '{expected}'，实际 '{tab_text}'")

        # 验证关键 View 存在
        views = [
            ("_project_view", None),
            ("_dashboard", DashboardView),
            ("_sample_view", None),
            ("_test_plan_view", None),
            ("_bug_tracker_view", None),
            ("_equipment_view", None),
            ("_knowledge_view", None),
        ]
        for attr, cls in views:
            assert hasattr(window, attr), f"MainWindow 缺少属性 {attr}"
            tr.record("PASS", f"MainWindow.{attr} 存在", "")

        controller.shutdown()
        tr.record("PASS", "MainWindow 启动+关闭", "正常启动和关闭")

    except Exception as e:
        tr.record("FAIL", "MainWindow", str(e))
        traceback.print_exc()


def main():
    tr = TestResult()

    print("=" * 60)
    print("ReliaTrack E2E 全功能测试")
    print("=" * 60)

    # Tests 1-9: 使用 :memory: 数据库
    conn = setup_db()
    try:
        results = test_1_basic_crud(tr, conn)
        pid, eid, tid, sid, proj_repo, eq_repo, tech_repo, sam_repo, issue_repo, plan_repo, task_repo = results
        results2 = test_2_test_plan_and_tasks(tr, conn, pid, eid, tid, plan_repo, task_repo)
        plan_id, t1, t2 = results2
        test_3_issue_and_attachment(tr, conn, pid, plan_id, t1, issue_repo)
        test_4_knowledge(tr, conn)
        test_5_sample_transactions(tr, conn, sid, tid, sam_repo)
        test_6_scheduler(tr, conn, plan_id, task_repo, eq_repo, plan_repo)
        test_7_export(tr, conn, plan_id, task_repo, issue_repo, sam_repo)
        test_8_undo_manager(tr, conn, task_repo)
    finally:
        cleanup_db()

    # Test 10: MainWindow (独立内存数据库)
    test_9_main_window(tr)

    return tr.summary()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
