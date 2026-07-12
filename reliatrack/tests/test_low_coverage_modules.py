"""低覆盖率模块补充测试。

覆盖：
- test_result_repo (35% → 目标 85%+)
- settings_service (46% → 目标 90%+)
- holiday_service (48% → 目标 85%+)
- knowledge_repo (58% → 目标 85%+)
- scheduler_service (58% → 目标 75%+)
"""

from __future__ import annotations

import pytest
import apsw

from src.db.repositories import (
    TestResultRepository,
    SettingsRepository,
    KnowledgeRepository,
    TestTaskRepository,
    TestPlanRepository,
    EquipmentRepository,
)
from src.services.settings_service import SettingsService
from src.services.holiday_service import HolidayService
from src.services.scheduler_service import SchedulerService


# ═══════════════════════════════════════════════════════════════════
#  共享 fixtures — 插入 task/plan 等测试前置数据
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def sample_plan(db_conn, sample_project):
    """插入测试计划。"""
    db_conn.execute(
        "INSERT INTO test_plans (name, project_id, start_date, status) VALUES (?, ?, ?, ?)",
        ("计划A", sample_project["id"], "2026-01-05", "active"),
    )
    row = db_conn.execute("SELECT * FROM test_plans WHERE name='计划A'").fetchone()
    return {"id": row[0], "name": row[1], "start_date": row[3], "status": row[4]}


@pytest.fixture()
def sample_task(db_conn, sample_plan):
    """插入测试任务。"""
    db_conn.execute(
        "INSERT INTO test_tasks (plan_id, name, duration, start_day, status) VALUES (?, ?, ?, ?, ?)",
        (sample_plan["id"], "高温测试", 3, 0, "pending"),
    )
    row = db_conn.execute(
        "SELECT id, plan_id, name, duration, start_day FROM test_tasks WHERE name='高温测试'"
    ).fetchone()
    return {"id": row[0], "plan_id": row[1], "name": row[2], "duration": row[3], "start_day": row[4]}


# ═══════════════════════════════════════════════════════════════════
#  TestResultRepository
# ═══════════════════════════════════════════════════════════════════

class TestTestResultRepository:

    @pytest.fixture()
    def repo(self, db_conn):
        return TestResultRepository(db_conn)

    def test_insert_and_get_by_task(self, repo, sample_task):
        repo.insert(task_id=sample_task["id"], result="pass", test_date="2026-01-06")
        results = repo.get_by_task(sample_task["id"])
        assert len(results) == 1
        assert results[0].result == "pass"

    def test_get_by_sample(self, repo, sample_task, sample_sample):
        repo.insert(task_id=sample_task["id"], sample_id=sample_sample["id"], result="fail", test_date="2026-01-06")
        results = repo.get_by_sample(sample_sample["id"])
        assert len(results) == 1
        assert results[0].result == "fail"

    def test_get_task_result_for_sample(self, repo, sample_task, sample_sample):
        repo.insert(task_id=sample_task["id"], sample_id=sample_sample["id"], result="pass")
        result = repo.get_task_result_for_sample(sample_task["id"], sample_sample["id"])
        assert result is not None
        assert result.result == "pass"

    def test_get_task_result_for_none_sample(self, repo, sample_task):
        """sample_id=None 时查找整体结果。"""
        repo.insert(task_id=sample_task["id"], sample_id=None, result="pass")
        result = repo.get_task_result_for_sample(sample_task["id"], None)
        assert result is not None
        assert result.result == "pass"

    def test_get_task_result_not_found(self, repo, sample_task):
        assert repo.get_task_result_for_sample(sample_task["id"], None) is None

    def test_upsert_insert_new(self, repo, sample_task):
        rid = repo.upsert(sample_task["id"], None, result="pass")
        assert rid > 0
        assert repo.count_by_task(sample_task["id"]) == 1

    def test_upsert_update_existing(self, repo, sample_task):
        """已有记录时 upsert 应更新而非插入。"""
        rid = repo.upsert(sample_task["id"], None, result="pass")
        rid2 = repo.upsert(sample_task["id"], None, result="fail")
        assert rid == rid2
        assert repo.count_by_task(sample_task["id"]) == 1
        result = repo.get_task_result_for_sample(sample_task["id"], None)
        assert result.result == "fail"

    def test_delete_by_task(self, repo, sample_task):
        repo.insert(task_id=sample_task["id"], result="pass")
        repo.insert(task_id=sample_task["id"], result="fail")
        count = repo.delete_by_task(sample_task["id"])
        assert count == 2
        assert repo.count_by_task(sample_task["id"]) == 0

    def test_count_by_task(self, repo, sample_task):
        repo.insert(task_id=sample_task["id"], result="pass")
        repo.insert(task_id=sample_task["id"], result="fail")
        assert repo.count_by_task(sample_task["id"]) == 2

    def test_count_by_sample(self, repo, sample_task, sample_sample):
        repo.insert(task_id=sample_task["id"], sample_id=sample_sample["id"], result="pass")
        assert repo.count_by_sample(sample_sample["id"]) == 1

    def test_get_all_by_tasks(self, repo, sample_task):
        repo.insert(task_id=sample_task["id"], result="pass")
        repo.insert(task_id=sample_task["id"], result="fail")
        results = repo.get_all_by_tasks([sample_task["id"]])
        assert len(results) == 2

    def test_get_all_by_tasks_empty(self, repo):
        assert repo.get_all_by_tasks([]) == []

    def test_get_pass_counts_by_tasks(self, repo, sample_task):
        repo.insert(task_id=sample_task["id"], result="pass")
        repo.insert(task_id=sample_task["id"], result="pass")
        repo.insert(task_id=sample_task["id"], result="fail")
        counts = repo.get_pass_counts_by_tasks([sample_task["id"]])
        assert counts[sample_task["id"]] == (2, 3)

    def test_get_pass_counts_empty(self, repo):
        assert repo.get_pass_counts_by_tasks([]) == {}


# ═══════════════════════════════════════════════════════════════════
#  SettingsService
# ═══════════════════════════════════════════════════════════════════

class TestSettingsService:

    @pytest.fixture()
    def svc(self, db_conn):
        return SettingsService(SettingsRepository(db_conn))

    def test_set_and_get(self, svc):
        svc.set("theme", "dark")
        assert svc.get("theme") == "dark"

    def test_get_missing_returns_none(self, svc):
        assert svc.get("nonexistent") is None

    def test_get_bool_true(self, svc):
        svc.set("flag1", "true")
        svc.set("flag2", "1")
        svc.set("flag3", "yes")
        svc.set("flag4", "TRUE")
        assert svc.get_bool("flag1") is True
        assert svc.get_bool("flag2") is True
        assert svc.get_bool("flag3") is True
        assert svc.get_bool("flag4") is True

    def test_get_bool_false(self, svc):
        svc.set("flag", "false")
        assert svc.get_bool("flag") is False

    def test_get_bool_default_when_missing(self, svc):
        assert svc.get_bool("missing", default=True) is True
        assert svc.get_bool("missing") is False

    def test_get_int_valid(self, svc):
        svc.set("count", "42")
        assert svc.get_int("count") == 42

    def test_get_int_default_when_missing(self, svc):
        assert svc.get_int("missing", default=10) == 10
        assert svc.get_int("missing") == 0

    def test_get_int_invalid_fallback(self, svc):
        svc.set("bad", "not_a_number")
        assert svc.get_int("bad", default=5) == 5

    def test_overwrite(self, svc):
        svc.set("key", "v1")
        svc.set("key", "v2")
        assert svc.get("key") == "v2"


# ═══════════════════════════════════════════════════════════════════
#  HolidayService
# ═══════════════════════════════════════════════════════════════════

class TestHolidayService:

    @pytest.fixture()
    def svc(self, db_conn):
        return HolidayService(db_conn)

    def test_get_holidays_set_all(self, svc):
        # schema init 已种入 2025/2026 种子数据
        holidays = svc.get_holidays_set()
        assert len(holidays) > 0
        # 种子数据中有国庆
        assert any("10-01" in h for h in holidays)

    def test_get_holidays_set_by_year(self, svc):
        h2026 = svc.get_holidays_set(year=2026)
        assert len(h2026) > 0
        # 2026 年没有 2025 的日期
        assert all("2025" not in h for h in h2026)

    def test_get_holidays_list(self, svc):
        holidays = svc.get_holidays(year=2026)
        assert len(holidays) > 0
        assert "date" in holidays[0]
        assert "name" in holidays[0]
        assert "source" in holidays[0]

    def test_get_holidays_list_all_years(self, svc):
        holidays = svc.get_holidays()
        assert len(holidays) > 0

    def test_add_holiday(self, svc):
        rid = svc.add_holiday("2027-01-01", "元旦", "custom")
        assert rid > 0
        result = svc.get_holidays(year=2027)
        assert len(result) == 1
        assert result[0]["name"] == "元旦"

    def test_add_duplicate_returns_zero(self, svc):
        svc.add_holiday("2027-05-01", "劳动节", "custom")
        rid2 = svc.add_holiday("2027-05-01", "重复", "custom")
        assert rid2 == 0

    def test_delete_holiday(self, svc):
        rid = svc.add_holiday("2027-06-01", "测试节", "custom")
        svc.delete_holiday(rid)
        holidays = svc.get_holidays(year=2027)
        assert all(h["date"] != "2027-06-01" for h in holidays)

    def test_import_holidays(self, svc):
        records = [
            ("2027-01-01", "元旦", "builtin"),
            ("2027-05-01", "劳动节", "builtin"),
        ]
        count = svc.import_holidays(records)
        assert count == 2

    def test_import_duplicates(self, svc):
        """重复导入的日期被 IGNORE，不计入插入数。"""
        svc.add_holiday("2027-03-01", "已有", "custom")
        count = svc.import_holidays([
            ("2027-03-01", "重复", "builtin"),
            ("2027-03-02", "新的", "builtin"),
        ])
        assert count == 1

    def test_import_empty(self, svc):
        assert svc.import_holidays([]) == 0

    def test_seed_year_if_missing(self, svc):
        records = [("2028-01-01", "元旦"), ("2028-05-01", "劳动节")]
        count = svc.seed_year_if_missing(2028, records)
        assert count == 2

    def test_seed_year_skips_if_has_data(self, svc):
        svc.add_holiday("2029-01-01", "已有", "custom")
        records = [("2029-01-01", "元旦")]
        count = svc.seed_year_if_missing(2029, records)
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
#  KnowledgeRepository
# ═══════════════════════════════════════════════════════════════════

class TestKnowledgeRepository:

    @pytest.fixture()
    def repo(self, db_conn):
        return KnowledgeRepository(db_conn)

    def test_create_and_get(self, repo):
        rid = repo.create({
            "category": "环境试验",
            "failure_mode": "焊点开裂",
            "cause_analysis": "热循环应力",
            "improvement": "加锡量",
        })
        assert rid > 0
        entry = repo.get(rid)
        assert entry is not None
        assert entry.failure_mode == "焊点开裂"

    def test_get_nonexistent(self, repo):
        assert repo.get(99999) is None

    def test_list_all_desc(self, repo):
        repo.create({"category": "机械", "failure_mode": "A"})
        repo.create({"category": "环境", "failure_mode": "B"})
        entries = repo.list_all()
        assert len(entries) >= 2
        # DESC 排序——后插入的在前
        assert entries[0].id > entries[1].id

    def test_list_all_with_filter(self, repo):
        repo.create({"category": "环境", "failure_mode": "A"})
        repo.create({"category": "机械", "failure_mode": "B"})
        entries = repo.list_all(category="环境")
        assert len(entries) == 1
        assert entries[0].category == "环境"

    def test_search(self, repo):
        repo.create({"category": "环境试验", "failure_mode": "焊点开裂", "cause_analysis": "热循环"})
        repo.create({"category": "机械", "failure_mode": "冲击断裂", "cause_analysis": "跌落"})
        results = repo.search("焊点")
        assert len(results) >= 1
        assert any(r.failure_mode == "焊点开裂" for r in results)

    def test_search_no_match(self, repo):
        repo.create({"failure_mode": "已知模式"})
        results = repo.search("不存在的关键词XYZ")
        assert len(results) == 0

    def test_search_special_chars(self, repo):
        """LIKE 特殊字符（% _ \）在搜索词中应被正确转义，不崩溃。"""
        repo.create({"failure_mode": "50%不良"})
        # % 被转义为字面量匹配，所以搜 "50" 能匹配到
        results = repo.search("50")
        assert len(results) >= 1
        # 搜纯数字+百分号不崩溃
        results2 = repo.search("50%")
        assert isinstance(results2, list)


# ═══════════════════════════════════════════════════════════════════
#  SchedulerService
# ═══════════════════════════════════════════════════════════════════

class TestSchedulerService:

    @pytest.fixture()
    def svc(self, db_conn):
        return SchedulerService(
            TestTaskRepository(db_conn),
            EquipmentRepository(db_conn),
            TestPlanRepository(db_conn),
        )

    def test_preview_empty_plan(self, svc, sample_plan):
        """没有任务的计划应返回空预览。"""
        result = svc.preview_schedule(sample_plan["id"])
        assert result["tasks"] == []
        assert result["report"]["task_count"] == 0

    def test_preview_with_task(self, svc, sample_plan, sample_task):
        result = svc.preview_schedule(sample_plan["id"])
        assert result["report"]["task_count"] == 1
        assert len(result["tasks"]) == 1
        assert "original_start_days" in result
        assert sample_task["id"] in result["original_start_days"]

    def test_preview_returns_equipment(self, svc, sample_plan, sample_task, sample_equipment):
        result = svc.preview_schedule(sample_plan["id"])
        assert len(result["equipment"]) >= 1

    def test_preview_nonexistent_plan(self, svc):
        """不存在的 plan_id 不崩溃，返回空。"""
        result = svc.preview_schedule(99999)
        assert result["tasks"] == []

    def test_apply_empty_changes(self, svc):
        assert svc.apply_schedule(1, []) == 0

    def test_apply_schedule_writes_db(self, svc, sample_plan, sample_task):
        """apply 后 DB 中 task 的 start_day 应更新。"""
        old_day = sample_task["start_day"]
        new_day = old_day + 5
        count = svc.apply_schedule(sample_plan["id"], [(sample_task["id"], new_day)])
        assert count == 1
        # 从 DB 读回验证
        task_repo = TestTaskRepository(svc._task_repo.conn)
        task = task_repo.get_by_id(sample_task["id"])
        assert task is not None
        assert task.start_day == new_day

    def test_auto_schedule_empty_plan(self, svc, sample_plan):
        report = svc.auto_schedule(sample_plan["id"])
        assert report["task_count"] == 0
        assert report["total_days"] == 0

    def test_auto_schedule_with_task(self, svc, sample_plan, sample_task):
        report = svc.auto_schedule(sample_plan["id"])
        assert report["task_count"] == 1
        assert "total_days" in report
        assert "updated_count" in report

    def test_auto_schedule_with_holidays(self, db_conn, sample_plan, sample_task):
        """有 holiday_service 时排程不崩溃。"""
        holiday_svc = HolidayService(db_conn)
        svc = SchedulerService(
            TestTaskRepository(db_conn),
            EquipmentRepository(db_conn),
            TestPlanRepository(db_conn),
            holiday_service=holiday_svc,
        )
        report = svc.auto_schedule(sample_plan["id"])
        assert report["task_count"] == 1
