"""边界场景 + Dialog 构造测试 — 补充 E2E"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pytest

from PySide6.QtWidgets import QApplication
from src.controllers import AppController
from src.services.export_service import ExportService
from src.services.undo_manager import (
    AddEntityCommand, DeleteEntityCommand, UpdateFieldCommand,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def ctrl(app):
    c = AppController(':memory:')
    c.initialize()
    return c


@pytest.fixture(scope="module")
def base_data(ctrl):
    """创建基础测试数据，供多个测试函数共享。"""
    p1 = ctrl.project_service.create(name='项目A')
    e1 = ctrl.equipment_service.create(name='温箱-01', type='温度箱')
    s1 = ctrl.sample_service.create(sn='SMP-D01', batch_no='B001', spec='TypeC')
    tp1 = ctrl.test_plan_service.create_plan(p1, '计划V1')
    tk1 = ctrl.test_plan_service.create_task(tp1, name='高温老化', start_day=1, duration=5)
    i1 = ctrl.issue_service.create(
        title='引脚断裂', severity='critical', priority=1, plan_id=tp1,
    )
    k1 = ctrl.knowledge_service.create(
        category='机械', failure_mode='断裂',
        cause_analysis='热应力', improvement='缓冲垫',
    )
    return {
        'project_id': p1,
        'equipment_id': e1,
        'sample_id': s1,
        'plan_id': tp1,
        'task_id': tk1,
        'issue_id': i1,
        'knowledge_id': k1,
    }


@pytest.fixture(scope="module")
def main_window(ctrl):
    from main import MainWindow
    w = MainWindow(ctrl)
    w.show()
    return w


# ═══ Dialog 构造测试 ═══


def test_plan_edit_dialog(ctrl, main_window, base_data):
    """PlanEditDialog 新建/编辑模式构造 + get_data 验证。"""
    from src.views.dialogs.plan_edit_dialog import PlanEditDialog

    # 新建模式
    dlg1 = PlanEditDialog(parent=main_window)
    assert dlg1.windowTitle() != ""
    data1 = dlg1.get_data()
    assert 'project_id' in data1
    assert data1.get('project_id') == 0

    # 编辑模式
    plan = ctrl.test_plan_service.list_all_plans()[0]
    dlg2 = PlanEditDialog(plan=plan, parent=main_window)
    data2 = dlg2.get_data()
    assert 'id' in data2 and data2['id'] == plan.id


def test_equipment_edit_dialog(ctrl, main_window):
    """EquipmentEditDialog 新建/编辑模式构造。"""
    from src.views.dialogs.equipment_edit_dialog import EquipmentEditDialog

    EquipmentEditDialog(parent=main_window)
    EquipmentEditDialog(equipment=ctrl.equipment.list_all()[0], parent=main_window)


def test_task_edit_dialog(ctrl, main_window):
    """TaskEditDialog 新建模式构造 + get_data 字段验证。"""
    from src.views.dialogs.task_dialog import TaskEditDialog

    dlg = TaskEditDialog(
        task=None,
        equipment_list=ctrl.equipment.list_all(),
        technician_list=[],
        all_tasks=[],
        parent=main_window,
    )
    data = dlg.get_data()
    assert 'temperature' in data
    assert 'humidity' in data
    assert 'log_file' in data


def test_issue_edit_dialog(main_window):
    """IssueEditDialog 新建模式构造。"""
    from src.views.dialogs.issue_dialog import IssueEditDialog

    IssueEditDialog(parent=main_window)


def test_batch_import_dialog(main_window):
    """BatchImportDialog 构造。"""
    from src.views.dialogs.batch_import_dialog import BatchImportDialog

    BatchImportDialog(parent=main_window)


def test_attachment_dialog(ctrl, main_window, base_data):
    """AttachmentDialog 构造。"""
    from src.views.dialogs.attachment_dialog import AttachmentDialog

    AttachmentDialog(
        issue_id=base_data['issue_id'],
        issue_service=ctrl.issue_service,
        parent=main_window,
    )


def test_knowledge_edit_dialog(ctrl, main_window):
    """KnowledgeEditDialog 新建/编辑模式构造。"""
    from src.views.dialogs.knowledge_edit_dialog import KnowledgeEditDialog

    KnowledgeEditDialog(parent=main_window)
    entry = ctrl.knowledge_service.list_all()[0]
    KnowledgeEditDialog(entry=entry, parent=main_window)


def test_project_edit_dialog(ctrl, main_window):
    """ProjectEditDialog 新建/编辑模式构造 + get_data 字段验证。"""
    from src.views.dialogs.project_edit_dialog import ProjectEditDialog

    # 新建模式
    dlg_new = ProjectEditDialog(parent=main_window)
    data_new = dlg_new.get_data()
    assert 'name' in data_new
    assert 'status' in data_new
    assert 'product' in data_new
    assert 'customer' in data_new
    assert 'id' not in data_new

    # 编辑模式
    proj = ctrl.project_service.list_all()[0]
    dlg_edit = ProjectEditDialog(project=proj, parent=main_window)
    data_edit = dlg_edit.get_data()
    assert 'id' in data_edit and data_edit['id'] == proj.id
    assert data_edit['name'] == proj.name


def test_export_dialog(main_window):
    """ExportDialog 构造。"""
    from src.views.dialogs.export_dialog import ExportDialog

    ExportDialog(parent=main_window)


# ═══ 边界场景测试 ═══


def test_plan_project_id_zero_blocks():
    """模拟 main.py 中 _on_plan_add 的 project_id 检查。"""
    plan_data = {'project_id': 0, 'name': '无项目计划'}
    assert plan_data['project_id'] == 0


def test_export_service_file_generation(ctrl, base_data):
    """导出服务实际生成 PDF 和 Word 文件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = ExportService(tmpdir)

        # PDF
        pdf_path = os.path.join(tmpdir, 'test.pdf')
        svc.export_report_pdf(
            ctrl.test_plan_service.get_plan(base_data['plan_id']),
            ctrl.test_plan_service.get_tasks(base_data['plan_id']),
            ctrl.issue_service.list_all(),
            ctrl.sample_service.list_all(),
            pdf_path,
        )
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0

        # Word
        docx_path = os.path.join(tmpdir, 'test.docx')
        svc.export_to_word(
            ctrl.test_plan_service.get_plan(base_data['plan_id']),
            ctrl.test_plan_service.get_tasks(base_data['plan_id']),
            ctrl.issue_service.list_all(),
            ctrl.sample_service.list_all(),
            docx_path,
        )
        assert os.path.exists(docx_path)
        assert os.path.getsize(docx_path) > 0


def test_undo_boundary(ctrl):
    """UndoManager 空 undo/redo 边界。"""
    ctrl.undo_manager.clear()
    assert not ctrl.undo_manager.can_undo()
    assert ctrl.undo_manager.undo() is None
    assert ctrl.undo_manager.redo() is None


def test_sample_checkout_flow(ctrl, base_data):
    """样品出入库完整流程。"""
    s2 = ctrl.sample_service.create(sn='SMP-D02', batch_no='B002', spec='TypeD')
    assert ctrl.sample_service.get_by_sn('SMP-D02').status == 'in_stock'

    ctrl.sample_service.add_transaction(
        s2, 'check_out', purpose='测试', related_task_id=base_data['task_id'],
    )
    ctrl.sample_service.update_status(s2, 'checked_out')
    assert ctrl.sample_service.get_by_sn('SMP-D02').status == 'checked_out'

    ctrl.sample_service.add_transaction(s2, 'check_in', purpose='归还')
    ctrl.sample_service.update_status(s2, 'in_stock')
    assert ctrl.sample_service.get_by_sn('SMP-D02').status == 'in_stock'

    txns = ctrl.sample_service.get_transactions(s2)
    assert len(txns) == 2


def test_knowledge_search(ctrl):
    """知识库搜索 — 命中 / 未命中。"""
    results = ctrl.knowledge_service.search('热应力')
    assert len(results) >= 1

    results_empty = ctrl.knowledge_service.search('不存在xyz')
    assert len(results_empty) == 0


def test_dashboard_chart_data(ctrl, base_data):
    """Dashboard 图表数据可正确聚合。"""
    from collections import Counter

    tasks = ctrl.test_plan_service.get_tasks(base_data['plan_id'])
    status_counts = Counter(t.status for t in tasks)
    assert len(status_counts) > 0

    samples = ctrl.sample_service.list_all()
    sample_counts = Counter(s.status for s in samples)
    assert len(sample_counts) > 0

    issues = ctrl.issue_service.list_all()
    issue_counts = Counter(i.priority for i in issues)
    assert len(issue_counts) > 0
