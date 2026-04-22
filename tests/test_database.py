"""tests/test_database.py — 数据库 CRUD 基础测试。"""
import json


# ── 任务 CRUD ──────────────────────────────────────────────

class TestTaskCRUD:
    def test_insert_and_get(self, db):
        from src.models import Task, Section
        t = Task(id=0, num="1", name_en="Thermal Cycle", name_cn="温度循环",
                 section=Section.ENV, duration=10, start_day=0,
                 progress=50.0, priority=1)
        db.insert_task(t)
        tasks = db.get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].num == "1"
        assert tasks[0].progress == 50.0
        assert tasks[0].done is False

    def test_insert_returns_id(self, db):
        from src.models import Task, Section
        t = Task(id=0, num="1", name_en="Test", name_cn="测试",
                 section=Section.ENV, duration=5)
        tid = db.insert_task(t)
        assert isinstance(tid, int)
        assert tid > 0

    def test_update_task(self, db, sample_tasks):
        t = sample_tasks[0]
        t.progress = 100.0
        t.done = True
        db.update_task(t)
        updated = db.get_task(t.id)
        assert updated.progress == 100.0
        assert updated.done is True

    def test_update_task_fields(self, db, sample_tasks):
        """update_task_fields partial update via dict."""
        t = sample_tasks[0]
        db.update_task_fields(t.id, {"progress": 75.0, "start_day": 20})
        updated = db.get_task(t.id)
        assert updated.progress == 75.0
        assert updated.start_day == 20

    def test_delete_task(self, db, sample_tasks):
        db.delete_task(sample_tasks[0].id)
        assert len(db.get_all_tasks()) == 4

    def test_get_task_by_id(self, db, sample_tasks):
        t = sample_tasks[0]
        found = db.get_task(t.id)
        assert found is not None
        assert found.num == t.num

    def test_get_nonexistent_task(self, db):
        found = db.get_task(999999)
        assert found is None

    def test_insert_task_with_dependencies(self, db):
        from src.models import Task, Section
        deps = ["1", "2"]
        t = Task(id=0, num="3", name_en="Dep Task", name_cn="依赖任务",
                 section=Section.MECH, duration=5, start_day=15,
                 dependencies=deps)
        db.insert_task(t)
        loaded = db.get_all_tasks()[0]
        assert loaded.dependencies == ["1", "2"]

    def test_insert_task_with_requirements(self, db, sample_resources):
        from src.models import Task, Section, EquipmentRequirement
        reqs = [EquipmentRequirement(resource_id=sample_resources[0].id, quantity=2)]
        t = Task(id=0, num="99", name_en="Req Task", name_cn="需求任务",
                 section=Section.ENV, duration=3, start_day=0, requirements=reqs)
        db.insert_task(t)
        loaded = db.get_all_tasks()[-1]
        assert len(loaded.requirements) == 1
        assert loaded.requirements[0].resource_id == sample_resources[0].id
        assert loaded.requirements[0].quantity == 2

    def test_task_count(self, db, sample_tasks):
        assert db.task_count() == 5

    def test_batch_update_schedule(self, db, sample_tasks):
        updates = [
            {"id": sample_tasks[0].id, "start_day": 5, "duration": 8},
            {"id": sample_tasks[1].id, "start_day": 15, "duration": 3},
        ]
        db.batch_update_schedule(updates)
        t0 = db.get_task(sample_tasks[0].id)
        t1 = db.get_task(sample_tasks[1].id)
        assert t0.start_day == 5
        assert t0.duration == 8
        assert t1.start_day == 15
        assert t1.duration == 3

    def test_insert_task_from_dict(self, db):
        """insert_task_from_dict used by undo system."""
        task_data = {
            "num": "10", "name_en": "Dict Task", "name_cn": "字典任务",
            "section": "env", "duration": 4, "start_day": 0,
        }
        tid = db.insert_task_from_dict(task_data)
        assert isinstance(tid, int)
        t = db.get_task(tid)
        assert t.num == "10"
        assert t.name_cn == "字典任务"

    def test_clear_done_tasks(self, db, sample_tasks):
        # sample_tasks[4] is done=True
        count = db.clear_done_tasks()
        assert count == 1
        assert db.task_count() == 4


# ── 资源 CRUD ──────────────────────────────────────────────

class TestResourceCRUD:
    def test_insert_and_get(self, db):
        from src.models import Resource, ResourceType
        r = Resource(id=0, name="振动台", type=ResourceType.EQUIPMENT,
                     category="机械", unit="台", available_qty=3, icon="📳")
        db.insert_resource(r)
        resources = db.get_all_resources()
        assert len(resources) == 1
        assert resources[0].available_qty == 3

    def test_insert_returns_id(self, db):
        from src.models import Resource, ResourceType
        r = Resource(id=0, name="设备", type=ResourceType.EQUIPMENT)
        rid = db.insert_resource(r)
        assert isinstance(rid, int)
        assert rid > 0

    def test_update_resource(self, db, sample_resources):
        r = sample_resources[0]
        r.available_qty = 99
        db.update_resource(r)
        assert db.get_resource(r.id).available_qty == 99

    def test_delete_resource(self, db, sample_resources):
        db.delete_resource(sample_resources[0].id)
        assert len(db.get_all_resources()) == 2

    def test_get_resource_by_id(self, db, sample_resources):
        r = sample_resources[0]
        found = db.get_resource(r.id)
        assert found is not None
        assert found.name == r.name

    def test_resource_types(self, sample_resources):
        from src.models import ResourceType
        types = {r.type for r in sample_resources}
        assert ResourceType.EQUIPMENT in types
        assert ResourceType.SAMPLE_POOL in types

    def test_unavailable_periods_roundtrip(self, db):
        from src.models import Resource, ResourceType, UnavailablePeriod
        periods = [UnavailablePeriod(start_day=10, end_day=15, reason="维护")]
        r = Resource(id=0, name="设备", type=ResourceType.EQUIPMENT,
                     unavailable_periods=periods)
        rid = db.insert_resource(r)
        loaded = db.get_resource(rid)
        assert len(loaded.unavailable_periods) == 1
        assert loaded.unavailable_periods[0].start_day == 10
        assert loaded.unavailable_periods[0].reason == "维护"


# ── 分类 CRUD ──────────────────────────────────────────────

class TestSectionCRUD:
    def test_insert_and_get(self, db):
        db.insert_section("ELEC", "电气", "#89b4fa", 5)
        sections = db.get_all_sections()
        assert len(sections) == 1
        assert sections[0]["key"] == "ELEC"

    def test_insert_returns_id(self, db):
        sid = db.insert_section("ELEC", "电气", "#89b4fa", 5)
        assert isinstance(sid, int)

    def test_update_section(self, db):
        sid = db.insert_section("ELEC", "电气", "#89b4fa", 5)
        db.update_section(sid, "ELEC2", "电气安全", "#f38ba8", 10)
        s = db.get_all_sections()[0]
        assert s["key"] == "ELEC2"
        assert s["label"] == "电气安全"

    def test_delete_section(self, db):
        sid = db.insert_section("ELEC", "电气", "#89b4fa", 5)
        db.delete_section(sid)
        assert len(db.get_all_sections()) == 0

    def test_get_section_labels(self, db):
        db.insert_section("A", "Alpha", "#fff", 1)
        db.insert_section("B", "Beta", "#000", 2)
        labels = db.get_section_labels()
        assert labels["A"] == "Alpha"
        assert labels["B"] == "Beta"

    def test_get_section_colors(self, db):
        db.insert_section("A", "Alpha", "#ff0000", 1)
        colors = db.get_section_colors()
        assert colors["A"] == "#ff0000"

    def test_section_task_count(self, db):
        from src.models import Task, Section
        db.insert_task(Task(id=0, num="X", name_en="X", name_cn="X",
                            section=Section.ENV, duration=1))
        db.insert_task(Task(id=0, num="Y", name_en="Y", name_cn="Y",
                            section=Section.ENV, duration=1))
        db.insert_task(Task(id=0, num="Z", name_en="Z", name_cn="Z",
                            section=Section.MECH, duration=1))
        assert db.section_task_count("env") == 2
        assert db.section_task_count("mech") == 1


# ── 项目设置 ───────────────────────────────────────────────

class TestProjectSettings:
    def test_set_and_get(self, db):
        db.set_setting("start_date", "2025-01-01")
        assert db.get_setting("start_date") == "2025-01-01"

    def test_get_nonexistent(self, db):
        # get_setting returns empty string for nonexistent keys, not None
        result = db.get_setting("nonexistent")
        assert result == ""

    def test_get_nonexistent_with_custom_default(self, db):
        assert db.get_setting("nonexistent", "fallback") == "fallback"

    def test_update_setting(self, db):
        db.set_setting("key1", "val1")
        db.set_setting("key1", "val2")
        assert db.get_setting("key1") == "val2"


# ── 测试结果 ───────────────────────────────────────────────

class TestTestResults:
    def test_insert_and_get(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        rid = db.insert_test_result(task_id=task_id, result="pass",
                                    test_data="温度循环",
                                    notes="合格", tester="张三")
        assert isinstance(rid, int)
        results = db.get_test_results(task_id)
        assert len(results) == 1
        assert results[0]["result"] == "pass"
        assert results[0]["tester"] == "张三"

    def test_get_latest_test_result(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        # Insert two results with explicit test_date ordering
        rid1 = db.insert_test_result(task_id=task_id, result="pending",
                                     test_data="first")
        rid2 = db.insert_test_result(task_id=task_id, result="pass",
                                     test_data="second")
        # Set test_dates to ensure ordering
        db.update_test_result(rid1, test_date="2025-01-01")
        db.update_test_result(rid2, test_date="2025-03-01")
        latest = db.get_latest_test_result(task_id)
        assert latest is not None
        assert latest["result"] == "pass"
        assert latest["id"] == rid2

    def test_update_test_result(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        rid = db.insert_test_result(task_id=task_id, result="pending")
        db.update_test_result(rid, result="fail", notes="不合格")
        results = db.get_test_results(task_id)
        assert results[0]["result"] == "fail"
        assert results[0]["notes"] == "不合格"

    def test_delete_test_result(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        rid = db.insert_test_result(task_id=task_id, result="pass")
        db.delete_test_result(rid)
        assert len(db.get_test_results(task_id)) == 0

    def test_insert_with_attachments(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        attachments = ["/path/to/file1.pdf", "/path/to/file2.png"]
        db.insert_test_result(task_id=task_id, result="pass",
                              attachments=attachments)
        results = db.get_test_results(task_id)
        # Attachments are stored as JSON string
        att = results[0]["attachments"]
        parsed = json.loads(att) if isinstance(att, str) else att
        assert len(parsed) == 2


# ── Issue 追踪 ─────────────────────────────────────────────

class TestIssueTracker:
    def test_insert_and_get(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        issue_id = db.insert_issue(
            task_id=task_id, title="温度超限",
            description="超出规格",
            issue_type="bug", severity="major",
            status="open", priority=3,
        )
        assert isinstance(issue_id, int)
        issues = db.get_issues(task_id=task_id)
        assert len(issues) == 1
        assert issues[0]["title"] == "温度超限"

    def test_get_issues_no_filter(self, db, sample_tasks):
        db.insert_issue(task_id=sample_tasks[0].id, title="Issue 1")
        db.insert_issue(task_id=sample_tasks[1].id, title="Issue 2")
        issues = db.get_issues()
        assert len(issues) == 2

    def test_get_issue_by_id(self, db, sample_tasks):
        iid = db.insert_issue(task_id=sample_tasks[0].id, title="Test")
        issue = db.get_issue(iid)
        assert issue is not None
        assert issue["title"] == "Test"

    def test_update_issue(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        issue_id = db.insert_issue(
            task_id=task_id, title="标题",
            description="desc", issue_type="bug",
            severity="major", status="open",
        )
        db.update_issue(issue_id, status="fixed")
        issues = db.get_issues(task_id=task_id)
        assert issues[0]["status"] == "fixed"

    def test_delete_issue(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        iid = db.insert_issue(task_id=task_id, title="Delete me")
        db.delete_issue(iid)
        assert len(db.get_issues(task_id=task_id)) == 0

    def test_issue_history(self, db, sample_tasks):
        task_id = sample_tasks[0].id
        issue_id = db.insert_issue(
            task_id=task_id, title="标题",
            severity="minor", status="open",
        )
        db.insert_issue_history(issue_id, "status", "open", "in_progress")
        db.insert_issue_history(issue_id, "assignee", "", "张三")
        history = db.get_issue_history(issue_id)
        assert len(history) == 2
        assert history[0]["new_value"] == "in_progress"

    def test_issue_stats(self, db, sample_tasks):
        db.insert_issue(task_id=sample_tasks[0].id, title="Bug 1",
                        severity="critical", status="open")
        db.insert_issue(task_id=sample_tasks[1].id, title="Bug 2",
                        severity="major", status="fixed")
        stats = db.get_issue_stats()
        assert stats["total"] == 2
        assert stats["open"] == 1
        assert stats["fixed"] == 1
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_severity"]["major"] == 1


# ── 边界 / 异常 ────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_db_returns_empty(self, db):
        assert db.get_all_tasks() == []
        assert db.get_all_resources() == []
        assert db.get_all_sections() == []

    def test_duplicate_section_key(self, db):
        db.insert_section("KEY1", "标签1", "#fff", 1)
        # 重复 key 应该失败（UNIQUE 约束），不影响已有数据
        with pytest.raises(Exception):
            db.insert_section("KEY1", "标签2", "#000", 2)
        sections = db.get_all_sections()
        assert len(sections) == 1

    def test_delete_nonexistent_task(self, db):
        """删除不存在的 id 不应抛异常。"""
        db.delete_task(999999)

    def test_unicode_content(self, db):
        from src.models import Task, Section
        t = Task(id=0, num="1", name_en="Thermal 🌡️", name_cn="温度循环📊",
                 section=Section.ENV, duration=5)
        db.insert_task(t)
        loaded = db.get_all_tasks()[0]
        assert "🌡️" in loaded.name_en
        assert "📊" in loaded.name_cn

    def test_insert_task_dict_for_import(self, db):
        """insert_task_dict (Excel import) uses defaults for missing fields."""
        d = {"num": "E1", "name_en": "Excel Task", "name_cn": "导入任务",
             "duration": 7, "section": "mech"}
        tid = db.insert_task_dict(d)
        t = db.get_task(tid)
        assert t.num == "E1"
        assert t.duration == 7
        assert t.dependencies == []
        assert t.is_serial is False


# Need pytest import for raises check
import pytest
