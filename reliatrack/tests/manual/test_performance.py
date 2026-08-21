"""性能基线测试 — 大数据量场景"""
import sys, os, time, tempfile, statistics
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
pytestmark = pytest.mark.skip(reason="Performance benchmark — run with: python tests/test_performance.py")

from PySide6.QtWidgets import QApplication
from src.controllers import AppController

app = QApplication(sys.argv)

# ---- 辅助 ----
results = []
def bench(label, fn, *args):
    """执行 fn 并记录耗时"""
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    results.append((label, elapsed))
    status = "✅" if elapsed < 1.0 else "⚠️" if elapsed < 3.0 else "❌"
    print(f"  {status} {label}: {elapsed:.3f}s")
    return result

# ---- 初始化 ----
print("═══ 初始化 ═══")
ctrl = AppController(':memory:')
bench("DB Schema 初始化 + migrate", ctrl.initialize)

# 先创建 5 个项目（FK 依赖）
for p in range(5):
    ctrl.project_service.create(name=f'项目{chr(65+p)}')

# ---- 1. 批量创建样品 (1000) ----
print("\n═══ 1. 样品管理 (1000 条) ═══")
def bulk_create_samples(n):
    ids = []
    for i in range(n):
        sid = ctrl.sample_service.create(
            sn=f'SMP-{i+1:04d}',
            batch_no=f'B{(i//50)+1:03d}',
            spec=f'TypeC-{i%10}',
            project_id=(i%5)+1 if i < 500 else None,
            status='in_stock' if i % 3 else 'checked_out' if i % 3 == 1 else 'in_test',
        )
        ids.append(sid)
    return ids

sample_ids = bench("创建 1000 个样品", bulk_create_samples, 1000)
bench("list_all 样品", ctrl.sample_service.list_all)
bench("get_by_sn (SMP-0500)", lambda: ctrl.sample_service.get_by_sn('SMP-0500'))
bench("list_all 过滤 in_stock", lambda: [s for s in ctrl.sample_service.list_all() if s.status == "in_stock"])
bench("get_by_project (project_id=1)", lambda: ctrl.sample_service.get_by_project(1))

# ---- 2. 批量创建测试计划 + 任务 ----
print("\n═══ 2. 测试计划 + 任务 (50 计划 × 20 任务 = 1000) ═══")
def bulk_create_plans_and_tasks(n_plans, tasks_per_plan):
    plan_ids = []
    for i in range(n_plans):
        pid = ctrl.test_plan_service.create_plan(
            project_id=(i % 5) + 1,
            name=f'计划-{i+1:03d}',
            test_standard=f'GB/T-{1000+i}',
            status='in_progress' if i % 2 else 'completed',
        )
        plan_ids.append(pid)
        for j in range(tasks_per_plan):
            ctrl.test_plan_service.create_task(
                plan_id=pid,
                name=f'任务-{i+1:03d}-{j+1:02d}',
                category=['高低温', '振动', '盐雾', 'EMC', '机械冲击'][j % 5],
                start_day=j * 3 + 1,
                duration=3 + (j % 5),
                priority=[1, 3, 5][j % 3],
                status='completed' if i < n_plans//2 else 'in_progress' if j < tasks_per_plan//2 else 'pending',
            )
    return plan_ids

plan_ids = bench("创建 50 计划 × 20 任务 = 1000 任务", bulk_create_plans_and_tasks, 50, 20)
bench("list_all_plans", ctrl.test_plan_service.list_all_plans)
bench("get_plan (id=25)", lambda: ctrl.test_plan_service.get_plan(25))
bench("get_tasks (plan_id=25)", lambda: ctrl.test_plan_service.get_tasks(25))

# ---- 3. 批量创建 Issue ----
print("\n═══ 3. Issue 追踪 (500 条) ═══")
def bulk_create_issues(n):
    ids = []
    for i in range(n):
        sid = ctrl.issue_service.create(
            title=f'Issue-{i+1:04d} 引脚断裂',
            priority=['critical', 'high', 'medium', 'low'][i % 4],
            status=['open', 'analyzing', 'verified', 'closed'][i % 4],
            plan_id=(i % 50) + 1,
            failure_mode=['短路', '断裂', '氧化', '变形', '漏电'][i % 5],
        )
        ids.append(sid)
    return ids

issue_ids = bench("创建 500 个 Issue", bulk_create_issues, 500)
bench("list_all Issues", ctrl.issue_service.list_all)

# ---- 4. 批量创建知识库条目 ----
print("\n═══ 4. 知识库 (200 条) ═══")
def bulk_create_knowledge(n):
    for i in range(n):
        ctrl.knowledge_service.create(
            category=['机械', '电气', '材料', '环境', '软件'][i % 5],
            failure_mode=f'失效模式-{i+1:03d}',
            cause_analysis=f'根因分析内容 {i} ' * 10,
            improvement=f'改进措施内容 {i} ' * 10,
        )

bench("创建 200 个知识库条目", bulk_create_knowledge, 200)
bench("知识库 list_all", ctrl.knowledge_service.list_all)
# 服务层无 search，生产为客户端过滤，等价基准
bench("知识库 客户端过滤('断裂')", lambda: [e for e in ctrl.knowledge_service.list_all() if "断裂" in (e.failure_mode or "")])
bench("知识库 客户端过滤('短路')", lambda: [e for e in ctrl.knowledge_service.list_all() if "短路" in (e.failure_mode or "")])

# ---- 5. 设备和技术员 ----
print("\n═══ 5. 设备/技术员 ═══")
def bulk_create_equipment(n):
    for i in range(n):
        ctrl.equipment_service.create(
            name=f'设备-{i+1:03d}',
            type=['温度箱', '振动台', '盐雾箱', 'EMC暗室', '冲击台'][i % 5],
            model=f'MODEL-{i:04d}',
        )

def bulk_create_technicians(n):
    for i in range(n):
        ctrl.technicians.insert(
            name=f'技术员-{i+1:03d}',
            department=['测试一部', '测试二部', '可靠性部'][i % 3],
            employee_id=f'E{i+1:05d}',
        )

bench("创建 50 台设备", bulk_create_equipment, 50)
bench("设备 list_all", ctrl.equipment.list_all)
bench("创建 30 名技术员", bulk_create_technicians, 30)
bench("技术员 list_all", ctrl.technicians.list_all)

# ---- 6. 样品出入库事务 ----
print("\n═══ 6. 样品出入库事务 (500 条) ═══")
def bulk_transactions(n):
    for i in range(n):
        ctrl.sample_service.add_transaction(
            sample_id=sample_ids[i],
            txn_type='check_out' if i % 2 == 0 else 'check_in',
            operator_id=(i % 30) + 1,
            purpose='测试' if i % 2 == 0 else '归还',
        )

bench("创建 500 条出入库事务", bulk_transactions, 500)
bench("list_transactions 全量", lambda: ctrl.sample_service.list_transactions())

# ---- 7. MainWindow 启动 + 各 Tab 加载 ----
print("\n═══ 7. MainWindow 启动 + Tab 加载 ═══")
def create_mainwindow():
    from main import MainWindow
    w = MainWindow(ctrl)
    w.show()
    return w

w = bench("MainWindow 构造", create_mainwindow)

# 各 Tab 切换（触发 lazy load）
from PySide6.QtCore import Qt
tab_widget = w.findChild(type(w).__mro__[0])  # fallback
for child in w.centralWidget().children():
    if hasattr(child, 'currentIndex'):
        tab_widget = child
        break

if tab_widget:
    for i in range(tab_widget.count()):
        bench(f"Tab[{i}] {tab_widget.tabText(i)} 切换", lambda idx=i: tab_widget.setCurrentIndex(idx))

# ---- 8. 导出性能 ----
print("\n═══ 8. 导出性能 ═══")
from src.services.export_service import ExportService

def test_exports():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = ExportService(tmpdir)

        # Excel
        xlsx_path = os.path.join(tmpdir, 'perf_issues.xlsx')
        t0 = time.perf_counter()
        svc.export_issues_excel(ctrl.issue_service.list_all(), filepath=xlsx_path)
        xlsx_t = time.perf_counter() - t0
        results.append(("导出 500 Issues Excel", xlsx_t))
        print(f"  {'✅' if xlsx_t < 2 else '⚠️'} 导出 500 Issues Excel: {xlsx_t:.3f}s")

        xlsx2_path = os.path.join(tmpdir, 'perf_samples.xlsx')
        t0 = time.perf_counter()
        svc.export_samples_excel(ctrl.sample_service.list_all(), xlsx2_path)
        xlsx2_t = time.perf_counter() - t0
        results.append(("导出 1000 样品 Excel", xlsx2_t))
        print(f"  {'✅' if xlsx2_t < 2 else '⚠️'} 导出 1000 样品 Excel: {xlsx2_t:.3f}s")

        # PDF
        plan = ctrl.test_plan_service.get_plan(25)
        tasks = ctrl.test_plan_service.get_tasks(25)
        pdf_path = os.path.join(tmpdir, 'perf_report.pdf')
        t0 = time.perf_counter()
        svc.export_report_pdf(plan, tasks, ctrl.issue_service.list_all(), ctrl.sample_service.list_all(), pdf_path)
        pdf_t = time.perf_counter() - t0
        results.append(("导出综合 PDF (含 1000 样品)", pdf_t))
        print(f"  {'✅' if pdf_t < 3 else '⚠️'} 导出综合 PDF (含 1000 样品): {pdf_t:.3f}s")

        # Word
        docx_path = os.path.join(tmpdir, 'perf_report.docx')
        t0 = time.perf_counter()
        svc.export_to_word(plan, tasks, ctrl.issue_service.list_all(), ctrl.sample_service.list_all(), docx_path)
        docx_t = time.perf_counter() - t0
        results.append(("导出综合 Word (含 1000 样品)", docx_t))
        print(f"  {'✅' if docx_t < 3 else '⚠️'} 导出综合 Word (含 1000 样品): {docx_t:.3f}s")

bench("全部导出测试", test_exports)

# ---- 汇总 ----
print("\n" + "=" * 60)
total = sum(t for _, t in results)
slow = [(l, t) for l, t in results if t >= 1.0]
fast = [(l, t) for l, t in results if t < 1.0]
print(f"总操作: {len(results)}, 总耗时: {total:.3f}s")
print(f"快速 (<1s): {len(fast)}, 需优化 (≥1s): {len(slow)}")
if slow:
    print("\n⚠️ 需要优化:")
    for l, t in sorted(slow, key=lambda x: -x[1]):
        print(f"  ❌ {l}: {t:.3f}s")
else:
    print("\n✅ 全部操作 < 1s，性能达标")
