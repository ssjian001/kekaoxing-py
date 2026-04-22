"""tests/test_models.py — 数据模型测试。"""
from dataclasses import asdict


class TestTask:
    def test_default_values(self):
        from src.models import Task, Section
        t = Task(id=1, num="1", name_en="Test", name_cn="测试",
                 section=Section.ENV, duration=1)
        assert t.duration == 1
        assert t.progress == 0.0
        assert t.done is False
        assert t.priority == 3
        assert t.dependencies == []
        assert t.requirements == []
        assert t.start_day == 0
        assert t.is_serial is False
        assert t.serial_group == ""
        assert t.sample_pool == "product"
        assert t.sample_qty == 3

    def test_task_to_dict(self):
        from src.models import Task, Section
        t = Task(id=1, num="1", name_en="Test", name_cn="测试",
                 section=Section.ENV, duration=10, progress=50.0)
        d = asdict(t)
        assert d["num"] == "1"
        assert d["duration"] == 10
        assert d["progress"] == 50.0

    def test_id_required(self):
        """Task requires id as positional argument."""
        from src.models import Task, Section
        t = Task(id=99, num="1", name_en="T", name_cn="测试",
                 section=Section.ENV, duration=1)
        assert t.id == 99

    def test_equality(self):
        """Two tasks with same fields should be equal (dataclass eq)."""
        from src.models import Task, Section
        t1 = Task(id=1, num="1", name_en="T1", name_cn="测试",
                  section=Section.ENV, duration=5)
        t2 = Task(id=1, num="1", name_en="T1", name_cn="测试",
                  section=Section.ENV, duration=5)
        assert t1 == t2


class TestResource:
    def test_resource_types(self):
        from src.models import ResourceType
        assert ResourceType.EQUIPMENT == "equipment"
        assert ResourceType.SAMPLE_POOL == "sample_pool"

    def test_resource_default_values(self):
        from src.models import Resource, ResourceType
        r = Resource(id=1, name="设备A", type=ResourceType.EQUIPMENT)
        assert r.available_qty == 1
        assert r.unit == "台"
        assert r.icon == "📦"
        assert r.unavailable_periods == []
        assert r.category == ""

    def test_id_required(self):
        """Resource requires id as positional argument."""
        from src.models import Resource, ResourceType
        r = Resource(id=42, name="设备A", type=ResourceType.EQUIPMENT)
        assert r.id == 42


class TestSection:
    def test_section_enum(self):
        from src.models import Section
        assert Section.ENV == "env"
        assert Section.MECH == "mech"
        assert Section.SURF == "surf"
        assert Section.PACK == "pack"

    def test_section_labels(self):
        from src.models import DEFAULT_SECTION_LABELS
        assert "env" in DEFAULT_SECTION_LABELS
        assert DEFAULT_SECTION_LABELS["env"] == "环境测试"

    def test_section_colors(self):
        from src.models import DEFAULT_SECTION_COLORS
        assert "env" in DEFAULT_SECTION_COLORS
        assert DEFAULT_SECTION_COLORS["env"] == "#4FC3F7"


class TestScheduleConfig:
    def test_default_config(self):
        from src.models import ScheduleConfig, ScheduleMode
        cfg = ScheduleConfig()
        assert cfg.mode == ScheduleMode.BALANCED
        assert cfg.skip_weekends is False
        assert cfg.lock_existing is False

    def test_custom_config(self):
        from src.models import ScheduleConfig, ScheduleMode
        cfg = ScheduleConfig(mode=ScheduleMode.FASTEST, skip_weekends=True,
                             deadline="2025-12-31")
        assert cfg.mode == ScheduleMode.FASTEST
        assert cfg.skip_weekends is True
        assert cfg.deadline == "2025-12-31"


class TestScheduleOutput:
    def test_default_values(self):
        from src.models import ScheduleOutput
        out = ScheduleOutput()
        assert out.total_days == 0
        assert out.parallel_peak == 0
        assert out.resource_conflicts == 0
        assert out.warnings == []


class TestUnavailablePeriod:
    def test_create(self):
        from src.models import UnavailablePeriod
        p = UnavailablePeriod(start_day=10, end_day=15, reason="维护")
        assert p.start_day == 10
        assert p.end_day == 15
        assert p.reason == "维护"

    def test_default_reason(self):
        from src.models import UnavailablePeriod
        p = UnavailablePeriod(start_day=1, end_day=5)
        assert p.reason == ""


class TestEquipmentRequirement:
    def test_create(self):
        from src.models import EquipmentRequirement
        eq = EquipmentRequirement(resource_id=10, quantity=2)
        assert eq.resource_id == 10
        assert eq.quantity == 2

    def test_default_quantity(self):
        from src.models import EquipmentRequirement
        eq = EquipmentRequirement(resource_id=5)
        assert eq.quantity == 1


class TestValidationIssue:
    def test_create_full(self):
        from src.core.data_validator import ValidationIssue
        vi = ValidationIssue(severity="error", category="冲突",
                             message="missing dep", task_id=1)
        assert vi.severity == "error"
        assert vi.category == "冲突"
        assert vi.task_id == 1

    def test_defaults(self):
        from src.core.data_validator import ValidationIssue
        vi = ValidationIssue(severity="warning", category="超载",
                             message="overloaded")
        assert vi.task_id is None
        assert vi.day is None
        assert vi.resource_name == ""


class TestHelperFunctions:
    def test_get_section_label_default(self):
        from src.models import get_section_label, Section
        assert get_section_label(Section.ENV) == "环境测试"

    def test_get_section_label_custom(self):
        from src.models import get_section_label, Section
        custom = {"env": "环境类"}
        assert get_section_label(Section.ENV, custom) == "环境类"

    def test_get_section_color_default(self):
        from src.models import get_section_color, Section
        assert get_section_color(Section.ENV) == "#4FC3F7"

    def test_get_section_color_custom(self):
        from src.models import get_section_color
        custom = {"env": "#FF0000"}
        assert get_section_color("env", custom) == "#FF0000"
