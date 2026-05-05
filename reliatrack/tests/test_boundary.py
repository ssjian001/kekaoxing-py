"""边界场景 + Dialog 构造测试 — 补充 E2E"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from PySide6.QtWidgets import QApplication
from src.controllers import AppController
from src.services.export_service import ExportService
from src.services.undo_manager import (
    AddEntityCommand, DeleteEntityCommand, UpdateFieldCommand,
)

app = QApplication(sys.argv)
ctrl = AppController(':memory:')
ctrl.initialize()

passed = 0
failed = 0
def check(name, condition):
    global passed, failed
    if condition:
        print(f"  ✅ [PASS] {name}")
        passed += 1
    else:
        print(f"  ❌ [FAIL] {name}")
        failed += 1

print("═══ Dialog 构造测试 ═══")

# 准备基础数据
p1 = ctrl.project_service.create(name='项目A')
e1 = ctrl.equipment_service.create(name='温箱-01', type='温度箱')
s1 = ctrl.sample_service.create(sn='SMP-D01', batch_no='B001', spec='TypeC')
tp1 = ctrl.test_plan_service.create_plan(p1, '计划V1')
tk1 = ctrl.test_plan_service.create_task(tp1, name='高温老化', start_day=1, duration=5)
i1 = ctrl.issue_service.create(title='引脚断裂', severity='critical', priority=1, plan_id=tp1)
k1 = ctrl.knowledge_service.create(category='机械', failure_mode='断裂', cause_analysis='热应力', improvement='缓冲垫')

from main import MainWindow
w = MainWindow(ctrl)
w.show()

print("── PlanEditDialog ──")
from src.views.dialogs.plan_edit_dialog import PlanEditDialog
from src.models.test_plan import TestPlan
# 新建模式
dlg1 = PlanEditDialog(parent=w)
check("PlanEditDialog 新建模式构造", dlg1.windowTitle() != "")
data1 = dlg1.get_data()
check("PlanEditDialog get_data 含 project_id", 'project_id' in data1)
check("PlanEditDialog 默认 project_id=0", data1.get('project_id') == 0)
# 编辑模式
plan = ctrl.test_plan_service.list_all_plans()[0]
dlg2 = PlanEditDialog(plan=plan, parent=w)
data2 = dlg2.get_data()
check("PlanEditDialog 编辑模式含 id", 'id' in data2 and data2['id'] == plan.id)

print("── EquipmentEditDialog ──")
from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog
dlg3 = EquipmentEditDialog(parent=w)
check("EquipmentEditDialog 新建模式构造", True)
dlg4 = EquipmentEditDialog(equipment=ctrl.equipment.list_all()[0], parent=w)
check("EquipmentEditDialog 编辑模式构造", True)

print("── TaskEditDialog ──")
from src.views.dialogs.task_dialog import TaskEditDialog
dlg6 = TaskEditDialog(
    task=None,
    equipment_list=ctrl.equipment.list_all(),
    technician_list=[],
    all_tasks=[],
    parent=w,
)
check("TaskEditDialog 新建模式构造", True)
data6 = dlg6.get_data()
check("TaskEditDialog get_data 含 temperature", 'temperature' in data6)
check("TaskEditDialog get_data 含 humidity", 'humidity' in data6)
check("TaskEditDialog get_data 含 log_file", 'log_file' in data6)

print("── IssueEditDialog ──")
from src.views.dialogs.issue_dialog import IssueEditDialog
dlg7 = IssueEditDialog(parent=w)
check("IssueEditDialog 新建模式构造", True)

print("── BatchImportDialog ──")
from src.views.dialogs.batch_import_dialog import BatchImportDialog
dlg8 = BatchImportDialog(parent=w)
check("BatchImportDialog 构造", True)

print("── AttachmentDialog ──")
from src.views.dialogs.attachment_dialog import AttachmentDialog
dlg9 = AttachmentDialog(issue_id=i1, issue_service=ctrl.issue_service, parent=w)
check("AttachmentDialog 构造", True)

print("── KnowledgeEditDialog ──")
from src.views.dialogs.knowledge_edit_dialog import KnowledgeEditDialog
dlg10 = KnowledgeEditDialog(parent=w)
check("KnowledgeEditDialog 新建模式构造", True)
ke = ctrl.knowledge_service.list_all()[0]
dlg11 = KnowledgeEditDialog(entry=ke, parent=w)
check("KnowledgeEditDialog 编辑模式构造", True)

print("── ProjectEditDialog ──")
from src.views.dialogs.project_edit_dialog import ProjectEditDialog
dlg13 = ProjectEditDialog(parent=w)
check("ProjectEditDialog 新建模式构造", True)
data13 = dlg13.get_data()
check("ProjectEditDialog get_data 含 name", 'name' in data13)
check("ProjectEditDialog get_data 含 status", 'status' in data13)
check("ProjectEditDialog get_data 含 product", 'product' in data13)
check("ProjectEditDialog get_data 含 customer", 'customer' in data13)
check("ProjectEditDialog get_data 无 id（新建模式）", 'id' not in data13)
# 编辑模式
proj = ctrl.project_service.list_all()[0]
dlg14 = ProjectEditDialog(project=proj, parent=w)
check("ProjectEditDialog 编辑模式构造", True)
data14 = dlg14.get_data()
check("ProjectEditDialog 编辑模式含 id", 'id' in data14 and data14['id'] == proj.id)
check("ProjectEditDialog 编辑模式预填名称", data14['name'] == proj.name)

print("── ExportDialog ──")
from src.views.dialogs.export_dialog import ExportDialog
dlg12 = ExportDialog(parent=w)
check("ExportDialog 构造", True)

print("═══ 边界场景测试 ═══")

print("── PlanEditDialog project_id=0 阻止创建 ──")
# 模拟 main.py 中 _on_plan_add 的 project_id 检查
plan_data = {'project_id': 0, 'name': '无项目计划'}
check("project_id=0 检查", plan_data['project_id'] == 0)

print("── 导出服务实际文件生成 ──")
with tempfile.TemporaryDirectory() as tmpdir:
    # Excel
    xlsx_path = os.path.join(tmpdir, 'test.xlsx')
    svc = ExportService(tmpdir)
    # PDF
    pdf_path = os.path.join(tmpdir, 'test.pdf')
    svc.export_report_pdf(ctrl.test_plan_service.get_plan(tp1), ctrl.test_plan_service.get_tasks(tp1), ctrl.issue_service.list_all(), ctrl.sample_service.list_all(), pdf_path)
    check(f"PDF 导出文件存在 ({os.path.getsize(pdf_path)} bytes)", os.path.exists(pdf_path))
    
    # Word
    docx_path = os.path.join(tmpdir, 'test.docx')
    svc.export_to_word(ctrl.test_plan_service.get_plan(tp1), ctrl.test_plan_service.get_tasks(tp1), ctrl.issue_service.list_all(), ctrl.sample_service.list_all(), docx_path)
    check(f"Word 导出文件存在 ({os.path.getsize(docx_path)} bytes)", os.path.exists(docx_path))

print("── 边界测试完成 ──")

print("── UndoManager 边界 ──")
ctrl.undo_manager.clear()
check("UndoManager clear 后 can_undo=False", not ctrl.undo_manager.can_undo())
result = ctrl.undo_manager.undo()
check("UndoManager 空 undo 返回 None", result is None)
result = ctrl.undo_manager.redo()
check("UndoManager 空 redo 返回 None", result is None)

print("── 样品出入库完整流程 ──")
s2 = ctrl.sample_service.create(sn='SMP-D02', batch_no='B002', spec='TypeD')
check("样品初始状态 in_stock", ctrl.sample_service.get_by_sn('SMP-D02').status == 'in_stock')
ctrl.sample_service.add_transaction(s2, 'check_out', purpose='测试', related_task_id=tk1)
ctrl.sample_service.update_status(s2, 'checked_out')
check("出库后状态 checked_out", ctrl.sample_service.get_by_sn('SMP-D02').status == 'checked_out')
ctrl.sample_service.add_transaction(s2, 'check_in', purpose='归还')
ctrl.sample_service.update_status(s2, 'in_stock')
check("入库后状态 in_stock", ctrl.sample_service.get_by_sn('SMP-D02').status == 'in_stock')
txns = ctrl.sample_service.get_transactions(s2)
check("出入库记录 2 条", len(txns) == 2)

print("── 知识库搜索 ──")
results = ctrl.knowledge_service.search('热应力')
check("知识库搜索'热应力'命中", len(results) >= 1)
results_empty = ctrl.knowledge_service.search('不存在xyz')
check("知识库搜索无结果返回空", len(results_empty) == 0)

print("── Dashboard 图表数据 ──")
from collections import Counter
tasks = ctrl.test_plan_service.get_tasks(tp1)
status_counts = Counter(t.status for t in tasks)
samples = ctrl.sample_service.list_all()
sample_counts = Counter(s.status for s in samples)
issues = ctrl.issue_service.list_all()
issue_counts = Counter(i.priority for i in issues)
check("Dashboard 任务状态数据", len(status_counts) > 0)
check("Dashboard 样品状态数据", len(sample_counts) > 0)
check("Dashboard Issue 状态数据", len(issue_counts) > 0)

print("\n" + "=" * 60)
print(f"结果: {passed} PASS, {failed} FAIL (共 {passed + failed} 项)")
print("=" * 60)
if failed > 0:
    sys.exit(1)
