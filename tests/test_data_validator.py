"""tests/test_data_validator.py — 数据校验测试。"""


class TestDataValidator:
    def test_empty_no_issues(self):
        """Empty tasks/resources list should produce no issues."""
        from src.core.data_validator import DataValidator
        v = DataValidator(tasks=[], resources=[])
        issues = v.validate_all()
        assert len(issues) == 0

    def test_orphan_dependency(self):
        """Dependency pointing to non-existent task num."""
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0,
                 dependencies=["99"]),  # "99" doesn't exist
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        # Should find an orphan dependency (referenced num not in task set)
        assert any(i.category == "孤立" for i in issues)

    def test_dependency_conflict(self):
        """Task starts before dependency finishes."""
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=10, start_day=0),
            Task(id=2, num="2", name_en="T2", name_cn="任务2",
                 section=Section.ENV, duration=5, start_day=5,
                 dependencies=["1"]),  # T1 ends at day 10, T2 starts at 5
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "冲突" for i in issues)

    def test_negative_duration(self):
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=-1, start_day=0),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "异常" for i in issues)

    def test_negative_progress(self):
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0,
                 progress=-10),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "异常" and "进度" in i.message for i in issues)

    def test_progress_over_100(self):
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0,
                 progress=150),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "异常" and "进度" in i.message for i in issues)

    def test_start_day_negative(self):
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=-5),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "异常" and "开始日" in i.message for i in issues)

    def test_duration_over_365(self):
        """Duration > 365 should produce a warning."""
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=500, start_day=0),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "异常" and "365" in i.message for i in issues)

    def test_sample_pool_mismatch(self):
        """Task references a sample pool not in resources."""
        from src.models import Task, Section, Resource, ResourceType
        from src.core.data_validator import DataValidator

        resources = [
            Resource(id=1, name="产品样机", type=ResourceType.SAMPLE_POOL,
                     available_qty=3),
        ]
        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0,
                 sample_pool="不存在的样品池"),
        ]
        v = DataValidator(tasks=tasks, resources=resources)
        issues = v.validate_all()
        assert any(i.category == "样品池" for i in issues)

    def test_resource_overload(self):
        """Equipment demand exceeds available quantity on same day."""
        from src.models import Task, Section, Resource, ResourceType, EquipmentRequirement
        from src.core.data_validator import DataValidator

        resources = [
            Resource(id=1, name="振动台", type=ResourceType.EQUIPMENT,
                     available_qty=1),
        ]
        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0,
                 requirements=[EquipmentRequirement(resource_id=1, quantity=1)]),
            Task(id=2, num="2", name_en="T2", name_cn="任务2",
                 section=Section.ENV, duration=5, start_day=0,
                 requirements=[EquipmentRequirement(resource_id=1, quantity=1)]),
        ]
        v = DataValidator(tasks=tasks, resources=resources)
        issues = v.validate_all()
        assert any(i.category == "超载" for i in issues)

    def test_orphan_task_no_deps_no_dependents(self):
        """Task with no deps and no dependents should be flagged as info."""
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        assert any(i.category == "孤立" and i.severity == "info" for i in issues)

    def test_valid_data_no_issues(self):
        """Properly configured tasks should produce zero issues."""
        from src.models import Task, Section
        from src.core.data_validator import DataValidator

        tasks = [
            Task(id=1, num="1", name_en="T1", name_cn="任务1",
                 section=Section.ENV, duration=5, start_day=0),
            Task(id=2, num="2", name_en="T2", name_cn="任务2",
                 section=Section.ENV, duration=3, start_day=5,
                 dependencies=["1"]),
        ]
        v = DataValidator(tasks=tasks, resources=[])
        issues = v.validate_all()
        # T2 starts at day 5, T1 ends at day 5, so no conflict
        assert not any(i.category == "冲突" for i in issues)
        # Both tasks are connected, no orphans
        assert not any(i.category == "孤立" and i.severity == "info" for i in issues)
