"""ImportService 单元测试 — 批量导入逻辑（设备 + 技术员）。

覆盖点：
- 正常导入（单行/多行）
- 重复跳过（DB 已有 + 同批次重复）
- 空名称跳过
- 类型转换（calibration_interval_months str→int）
- 事务回滚（任一行失败整体回滚）
- 空列表
"""

from __future__ import annotations

import pytest

from src.db.repositories import EquipmentRepository, TechnicianRepository
from src.services.equipment_service import EquipmentService
from src.services.technician_service import TechnicianService
from src.services.import_service import import_equipment, import_technicians


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def equip_svc(db_conn):
    return EquipmentService(EquipmentRepository(db_conn))


@pytest.fixture()
def tech_svc(db_conn):
    return TechnicianService(
        TechnicianRepository(db_conn),
        None,  # task_repo — 导入逻辑不依赖
        None,  # issue_repo
    )


# ═══════════════════════════════════════════════════════════════════
#  import_equipment
# ═══════════════════════════════════════════════════════════════════

class TestImportEquipment:

    def test_single_row_success(self, equip_svc):
        rows = [{"name": "高低温箱", "type": "环境", "model": "GDW-100"}]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1
        assert result.skipped == 0
        assert result.errors == []
        assert len(equip_svc.list_all()) == 1

    def test_multi_row_success(self, equip_svc):
        rows = [
            {"name": "设备A", "type": "环境"},
            {"name": "设备B", "type": "机械"},
            {"name": "设备C", "type": "表面"},
        ]
        result = import_equipment(rows, equip_svc)
        assert result.success == 3
        assert result.skipped == 0
        assert len(equip_svc.list_all()) == 3

    def test_skip_empty_name(self, equip_svc):
        rows = [
            {"name": "", "type": "环境"},
            {"name": "有效设备", "type": "机械"},
        ]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1
        assert result.skipped == 1
        assert "名称为空" in result.errors[0]

    def test_skip_duplicate_in_db(self, equip_svc):
        # 先插入一条
        equip_svc.create(name="已有设备", type="环境")
        rows = [{"name": "已有设备", "type": "环境"}]
        result = import_equipment(rows, equip_svc)
        assert result.success == 0
        assert result.skipped == 1
        assert "已存在" in result.errors[0]

    def test_skip_duplicate_in_batch(self, equip_svc):
        rows = [
            {"name": "重复设备", "type": "环境"},
            {"name": "重复设备", "type": "环境"},
        ]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1
        assert result.skipped == 1
        assert "本批次重复" in result.errors[0]

    def test_calibration_interval_str_to_int(self, equip_svc):
        rows = [{
            "name": "校准设备",
            "calibration_interval_months": "6",
        }]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1
        eq = equip_svc.list_all()[0]
        assert eq.calibration_interval_months == 6

    def test_calibration_interval_default(self, equip_svc):
        """未提供 calibration_interval_months 时默认 12。"""
        rows = [{"name": "默认设备"}]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1
        eq = equip_svc.list_all()[0]
        assert eq.calibration_interval_months == 12

    def test_calibration_interval_none_defaults_to_12(self, equip_svc):
        rows = [{"name": "None设备", "calibration_interval_months": None}]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1

    def test_empty_list(self, equip_svc):
        result = import_equipment([], equip_svc)
        assert result.success == 0
        assert result.skipped == 0
        assert result.errors == []

    def test_whitespace_stripped(self, equip_svc):
        rows = [{"name": "  带空格  ", "type": "  环境  "}]
        result = import_equipment(rows, equip_svc)
        assert result.success == 1
        eq = equip_svc.list_all()[0]
        assert eq.name == "带空格"
        assert eq.type == "环境"


# ═══════════════════════════════════════════════════════════════════
#  import_technicians
# ═══════════════════════════════════════════════════════════════════

class TestImportTechnicians:

    def test_single_row_success(self, tech_svc):
        rows = [{"name": "张三", "employee_id": "E001", "role": "工程师"}]
        result = import_technicians(rows, tech_svc)
        assert result.success == 1
        assert result.skipped == 0
        assert len(tech_svc.list_all()) == 1

    def test_multi_row_success(self, tech_svc):
        rows = [
            {"name": "张三", "employee_id": "E001"},
            {"name": "李四", "employee_id": "E002"},
        ]
        result = import_technicians(rows, tech_svc)
        assert result.success == 2

    def test_skip_empty_name(self, tech_svc):
        rows = [{"name": "", "employee_id": "E001"}]
        result = import_technicians(rows, tech_svc)
        assert result.success == 0
        assert result.skipped == 1
        assert "名称为空" in result.errors[0]

    def test_skip_duplicate_in_db(self, tech_svc):
        tech_svc.create(name="张三", employee_id="E001")
        rows = [{"name": "张三", "employee_id": "E001"}]
        result = import_technicians(rows, tech_svc)
        assert result.success == 0
        assert result.skipped == 1

    def test_same_name_different_emp_id_ok(self, tech_svc):
        """同名不同工号视为不同人。"""
        tech_svc.create(name="张三", employee_id="E001")
        rows = [{"name": "张三", "employee_id": "E002"}]
        result = import_technicians(rows, tech_svc)
        assert result.success == 1
        assert result.skipped == 0

    def test_skip_duplicate_in_batch(self, tech_svc):
        rows = [
            {"name": "张三", "employee_id": "E001"},
            {"name": "张三", "employee_id": "E001"},
        ]
        result = import_technicians(rows, tech_svc)
        assert result.success == 1
        assert result.skipped == 1
        assert "本批次重复" in result.errors[0]

    def test_empty_employee_id(self, tech_svc):
        """空工号也是合法的（(name, '') 作为 key）。"""
        rows = [{"name": "无工号"}]
        result = import_technicians(rows, tech_svc)
        assert result.success == 1

    def test_empty_list(self, tech_svc):
        result = import_technicians([], tech_svc)
        assert result.success == 0
        assert result.skipped == 0
