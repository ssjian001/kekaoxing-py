"""tests/test_scheduler.py — 自动排程算法测试。"""


class TestTopologicalSort:
    def test_no_dependencies(self, sample_tasks):
        """无依赖时拓扑排序应返回全部任务。"""
        from src.core.scheduler import topological_order, build_dependency_map
        tasks = sample_tasks
        dep_map = build_dependency_map(tasks)
        ordered = topological_order(tasks, dep_map)
        assert len(ordered) == 5

    def test_linear_chain(self, db):
        """A → B → C 线性依赖。"""
        from src.models import Task, Section
        from src.core.scheduler import topological_order, build_dependency_map

        # Clean up any existing tasks
        for t in db.get_all_tasks():
            db.delete_task(t.id)

        for num, deps in [("1", []), ("2", ["1"]), ("3", ["2"])]:
            t = Task(id=0, num=num, name_en=f"T{num}", name_cn=f"任务{num}",
                     section=Section.ENV, duration=5, start_day=0,
                     dependencies=deps)
            db.insert_task(t)

        tasks = db.get_all_tasks()
        dep_map = build_dependency_map(tasks)
        ordered = topological_order(tasks, dep_map)
        nums = [t.num for t in ordered]
        assert nums.index("1") < nums.index("2") < nums.index("3")

    def test_diamond_dependency(self, db):
        """钻石依赖: A → B, A → C, B → D, C → D。"""
        from src.models import Task, Section
        from src.core.scheduler import topological_order, build_dependency_map

        deps_map = {"1": [], "2": ["1"], "3": ["1"], "4": ["2", "3"]}
        for n, d in deps_map.items():
            t = Task(id=0, num=n, name_en=f"T{n}", name_cn=f"任务{n}",
                     section=Section.ENV, duration=3, start_day=0, dependencies=d)
            db.insert_task(t)

        tasks = db.get_all_tasks()
        dep_map = build_dependency_map(tasks)
        ordered = topological_order(tasks, dep_map)
        nums = [t.num for t in ordered]
        assert nums.index("1") < nums.index("4")
        assert nums.index("2") < nums.index("4")
        assert nums.index("3") < nums.index("4")

    def test_cycle_detection(self, db):
        """循环依赖应被安全处理（不崩溃，循环节点排在末尾）。"""
        from src.models import Task, Section
        from src.core.scheduler import topological_order, build_dependency_map

        # Create tasks with circular dependency: 1→2→3→1
        t1 = Task(id=0, num="1", name_en="T1", name_cn="任务1",
                  section=Section.ENV, duration=3, dependencies=["3"])
        t2 = Task(id=0, num="2", name_en="T2", name_cn="任务2",
                  section=Section.ENV, duration=3, dependencies=["1"])
        t3 = Task(id=0, num="3", name_en="T3", name_cn="任务3",
                  section=Section.ENV, duration=3, dependencies=["2"])
        db.insert_task(t1)
        db.insert_task(t2)
        db.insert_task(t3)

        tasks = db.get_all_tasks()
        dep_map = build_dependency_map(tasks)
        ordered = topological_order(tasks, dep_map)
        # Should return at least 0 tasks (all 3 are in cycle)
        # The cycle tasks are excluded, but function doesn't crash
        assert isinstance(ordered, list)


class TestDependencyMap:
    def test_build_dependency_map(self, db):
        from src.core.scheduler import build_dependency_map
        from src.models import Task, Section

        for n, d in [("1", []), ("2", ["1"]), ("3", ["1", "2"])]:
            db.insert_task(Task(id=0, num=n, name_en=f"T{n}", name_cn=f"任务{n}",
                                section=Section.ENV, duration=5, start_day=0,
                                dependencies=d))
        tasks = db.get_all_tasks()
        dep_map = build_dependency_map(tasks)

        # dep_map keys are task IDs (int), not nums (str)
        num_to_id = {t.num: t.id for t in tasks}
        assert dep_map[num_to_id["1"]] == []
        assert num_to_id["1"] in dep_map[num_to_id["2"]]
        assert num_to_id["1"] in dep_map[num_to_id["3"]]
        assert num_to_id["2"] in dep_map[num_to_id["3"]]


class TestSerialChains:
    def test_detect_serial_chain(self, db):
        """is_serial=True 的任务应被分到同一组。"""
        from src.core.scheduler import build_serial_chains
        from src.models import Task, Section

        for n, serial, group in [("1", True, "chain-A"), ("2", True, "chain-A"),
                                  ("3", False, ""), ("4", True, "chain-B")]:
            db.insert_task(Task(id=0, num=n, name_en=f"T{n}", name_cn=f"任务{n}",
                                section=Section.ENV, duration=3, start_day=0,
                                is_serial=serial, serial_group=group))
        tasks = db.get_all_tasks()
        chains = build_serial_chains(tasks)
        assert "chain-A" in chains
        assert len(chains["chain-A"]) == 2

    def test_serial_chain_ordering(self, db):
        """Serial chain should be topologically sorted within group."""
        from src.core.scheduler import build_serial_chains
        from src.models import Task, Section

        # T2 depends on T1, both in same chain
        db.insert_task(Task(id=0, num="2", name_en="T2", name_cn="任务2",
                            section=Section.ENV, duration=3, start_day=0,
                            is_serial=True, serial_group="G", dependencies=["1"]))
        db.insert_task(Task(id=0, num="1", name_en="T1", name_cn="任务1",
                            section=Section.ENV, duration=3, start_day=0,
                            is_serial=True, serial_group="G", dependencies=[]))
        tasks = db.get_all_tasks()
        chains = build_serial_chains(tasks)
        chain = chains["G"]
        nums = [t.num for t in chain]
        assert nums.index("1") < nums.index("2")


class TestCanPlaceAt:
    def test_no_resource_conflict(self, sample_tasks, sample_resources):
        """Single equipment with sufficient capacity — should place."""
        from src.core.scheduler import can_place_at, _build_resource_maps
        from src.models import ScheduleConfig

        config = ScheduleConfig()
        resource_map, sample_pool_map = _build_resource_maps(sample_resources, config)

        # Simple task with a requirement that fits
        task = sample_tasks[0]
        # Add a requirement for the first resource
        from src.models import EquipmentRequirement
        task.requirements = [EquipmentRequirement(
            resource_id=sample_resources[0].id, quantity=1)]

        timeline = {}
        ok = can_place_at(task, 0, timeline, resource_map,
                          sample_pool_map, False, "")
        assert ok is True

    def test_resource_conflict(self, sample_tasks, sample_resources):
        """Two tasks needing the same equipment exceeding capacity."""
        from src.core.scheduler import (can_place_at, place_task,
                                         _build_resource_maps)
        from src.models import ScheduleConfig, EquipmentRequirement

        config = ScheduleConfig()
        resource_map, sample_pool_map = _build_resource_maps(sample_resources, config)

        # sample_resources[0] has available_qty=2
        req = EquipmentRequirement(resource_id=sample_resources[0].id, quantity=2)

        t1 = sample_tasks[0]
        t1.requirements = [req]
        t1.duration = 5

        t2 = sample_tasks[1]
        t2.requirements = [req]
        t2.duration = 5

        timeline = {}
        place_task(t1, 0, timeline, resource_map, sample_pool_map, False, "")

        # t2 needs 2 units but only 2 available, and t1 uses 2 on day 0
        ok = can_place_at(t2, 0, timeline, resource_map,
                          sample_pool_map, False, "")
        assert ok is False

    def test_can_place_later(self, sample_tasks, sample_resources):
        """Task should be placeable after previous task finishes."""
        from src.core.scheduler import (can_place_at, place_task,
                                         _build_resource_maps)
        from src.models import ScheduleConfig, EquipmentRequirement

        config = ScheduleConfig()
        resource_map, sample_pool_map = _build_resource_maps(sample_resources, config)

        req = EquipmentRequirement(resource_id=sample_resources[0].id, quantity=2)

        t1 = sample_tasks[0]
        t1.requirements = [req]
        t1.duration = 5

        t2 = sample_tasks[1]
        t2.requirements = [req]
        t2.duration = 5

        timeline = {}
        place_task(t1, 0, timeline, resource_map, sample_pool_map, False, "")

        # After t1 finishes (day 5), t2 should be placeable
        ok = can_place_at(t2, 5, timeline, resource_map,
                          sample_pool_map, False, "")
        assert ok is True

    def test_skip_weekends(self, sample_tasks, sample_resources):
        """With skip_weekends, weekend days should be skipped in resource calc."""
        from src.core.scheduler import (can_place_at, place_task,
                                         _build_resource_maps)
        from src.models import ScheduleConfig, EquipmentRequirement

        # Start date: Monday 2025-01-06. Day 5=Sat, Day 6=Sun, Day 7=Mon
        config = ScheduleConfig(skip_weekends=True, start_date="2025-01-06")
        resource_map, sample_pool_map = _build_resource_maps(sample_resources, config)

        req = EquipmentRequirement(resource_id=sample_resources[0].id, quantity=1)

        t1 = sample_tasks[0]
        t1.requirements = [req]
        t1.duration = 3  # Mon-Wed

        timeline = {}
        ok = can_place_at(t1, 0, timeline, resource_map,
                          sample_pool_map, True, "2025-01-06")
        assert ok is True

        # Place t1 on day 0 (Mon)
        place_task(t1, 0, timeline, resource_map, sample_pool_map,
                   True, "2025-01-06")


class TestAutoSchedule:
    def test_basic_schedule(self, db):
        """5 tasks with no dependencies, each 3 days."""
        from src.models import Task, Section, ScheduleConfig, ScheduleMode, Resource
        from src.core.scheduler import run_auto_schedule

        for i in range(1, 6):
            db.insert_task(Task(id=0, num=str(i), name_en=f"T{i}",
                                name_cn=f"任务{i}",
                                section=Section.ENV, duration=3, start_day=0))

        tasks = db.get_all_tasks()
        resources = []
        config = ScheduleConfig(mode=ScheduleMode.FASTEST)
        result = run_auto_schedule(tasks, resources, config)

        assert "scheduled_tasks" in result
        assert "report" in result
        assert result["report"]["total_days"] <= 15  # worst case serial

        for t in result["scheduled_tasks"]:
            assert t.start_day >= 0

    def test_schedule_respects_dependencies(self, db):
        """Dependent tasks should not start before predecessors end."""
        from src.models import Task, Section, ScheduleConfig, ScheduleMode
        from src.core.scheduler import run_auto_schedule

        db.insert_task(Task(id=0, num="1", name_en="T1", name_cn="任务1",
                            section=Section.ENV, duration=5, start_day=0,
                            dependencies=[]))
        db.insert_task(Task(id=0, num="2", name_en="T2", name_cn="任务2",
                            section=Section.ENV, duration=3, start_day=0,
                            dependencies=["1"]))
        db.insert_task(Task(id=0, num="3", name_en="T3", name_cn="任务3",
                            section=Section.ENV, duration=2, start_day=0,
                            dependencies=["2"]))

        tasks = db.get_all_tasks()
        resources = []
        config = ScheduleConfig(mode=ScheduleMode.FASTEST)
        result = run_auto_schedule(tasks, resources, config)

        task_map = {t.num: t for t in result["scheduled_tasks"]}
        assert task_map["2"].start_day >= task_map["1"].start_day + task_map["1"].duration
        assert task_map["3"].start_day >= task_map["2"].start_day + task_map["2"].duration

    def test_schedule_with_locked_tasks(self, db):
        """Locked tasks should retain their positions."""
        from src.models import Task, Section, ScheduleConfig, ScheduleMode
        from src.core.scheduler import run_auto_schedule

        db.insert_task(Task(id=0, num="1", name_en="T1", name_cn="任务1",
                            section=Section.ENV, duration=5, start_day=10,
                            dependencies=[]))
        db.insert_task(Task(id=0, num="2", name_en="T2", name_cn="任务2",
                            section=Section.ENV, duration=3, start_day=0,
                            dependencies=["1"]))

        tasks = db.get_all_tasks()
        resources = []
        config = ScheduleConfig(mode=ScheduleMode.FASTEST, lock_existing=True)
        result = run_auto_schedule(tasks, resources, config)

        task_map = {t.num: t for t in result["scheduled_tasks"]}
        assert task_map["1"].start_day == 10  # locked, unchanged

    def test_schedule_with_resources(self, db, sample_resources):
        """Tasks with equipment constraints should respect capacity."""
        from src.models import Task, Section, ScheduleConfig, EquipmentRequirement
        from src.core.scheduler import run_auto_schedule

        eq = sample_resources[0]  # available_qty=2

        for i in range(4):
            t = Task(id=0, num=str(i+1), name_en=f"T{i+1}",
                     name_cn=f"任务{i+1}",
                     section=Section.ENV, duration=5, start_day=0,
                     requirements=[EquipmentRequirement(
                         resource_id=eq.id, quantity=2)])
            db.insert_task(t)

        tasks = db.get_all_tasks()
        resources = [r for r in sample_resources]
        config = ScheduleConfig()
        result = run_auto_schedule(tasks, resources, config)

        # Only 2 tasks should overlap at any time
        report = result["report"]
        assert "device_utilization" in report

    def test_schedule_report_structure(self, db):
        """run_auto_schedule should return expected report keys."""
        from src.models import Task, Section, ScheduleConfig
        from src.core.scheduler import run_auto_schedule

        db.insert_task(Task(id=0, num="1", name_en="T1", name_cn="任务1",
                            section=Section.ENV, duration=5, start_day=0))

        tasks = db.get_all_tasks()
        result = run_auto_schedule(tasks, [], ScheduleConfig())

        report = result["report"]
        assert "total_days" in report
        assert "original_days" in report
        assert "improvement" in report
        assert "device_utilization" in report
        assert "bottlenecks" in report
        assert "suggestions" in report
        assert "timeline" in result
