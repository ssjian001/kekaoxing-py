"""tests/test_project_io.py — 项目导入导出测试。"""
import json
import tempfile
import os


class TestExportImport:
    def test_export_creates_file(self, db, sample_tasks, sample_resources):
        """export_project writes a .kekaoxing JSON file."""
        from src.core.project_io import export_project

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            assert os.path.exists(path)

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "tasks" in data
            assert "resources" in data
            assert len(data["tasks"]) == 5
            assert len(data["resources"]) == 3
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_contains_task_fields(self, db, sample_tasks):
        from src.core.project_io import export_project

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            task = data["tasks"][0]
            assert "id" in task
            assert "num" in task
            assert "name_cn" in task
            assert "dependencies" in task
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_contains_resource_fields(self, db, sample_resources):
        from src.core.project_io import export_project

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            res = data["resources"][0]
            assert "id" in res
            assert "name" in res
            assert "type" in res
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_round_trip_preserves_data(self, db, sample_tasks, sample_resources):
        """Export → clear → import, data should be fully restored."""
        from src.core.project_io import export_project, import_project

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            # Export
            export_project(db, path)
            old_tasks = {t.num: t for t in db.get_all_tasks()}
            old_resources = {r.name: r for r in db.get_all_resources()}

            # Clear
            db.conn.execute("DELETE FROM issue_history")
            db.conn.execute("DELETE FROM test_issues")
            db.conn.execute("DELETE FROM test_results")
            db.conn.execute("DELETE FROM tasks")
            db.conn.execute("DELETE FROM resources")
            assert len(db.get_all_tasks()) == 0

            # Import (merge=False = replace mode)
            result = import_project(db, path, merge=False)
            assert result["task_count"] == 5
            assert result["resource_count"] == 3

            new_tasks = {t.num: t for t in db.get_all_tasks()}
            new_resources = {r.name: r for r in db.get_all_resources()}

            assert set(new_tasks.keys()) == set(old_tasks.keys())
            assert set(new_resources.keys()) == set(old_resources.keys())
            for num in old_tasks:
                assert new_tasks[num].name_cn == old_tasks[num].name_cn
                assert new_tasks[num].duration == old_tasks[num].duration
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_import_with_sections(self, db):
        from src.core.project_io import export_project, import_project

        db.insert_section("SEC1", "分类1", "#89b4fa", 1)
        db.insert_section("SEC2", "分类2", "#a6e3a1", 2)

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            db.conn.execute("DELETE FROM sections")
            assert len(db.get_all_sections()) == 0

            result = import_project(db, path, merge=False)
            assert result["section_count"] == 2

            sections = db.get_all_sections()
            keys = {s["key"] for s in sections}
            assert "SEC1" in keys and "SEC2" in keys
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_import_with_test_results(self, db, sample_tasks):
        """Test results should be exported and imported with tasks."""
        from src.core.project_io import export_project, import_project

        task_id = sample_tasks[0].id
        db.insert_test_result(task_id=task_id, result="pass",
                              test_data="温度循环",
                              notes="合格", tester="张三")

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "test_results" in data
            assert len(data["test_results"]) == 1

            # Clear and reimport
            db.conn.execute("DELETE FROM issue_history")
            db.conn.execute("DELETE FROM test_issues")
            db.conn.execute("DELETE FROM test_results")
            db.conn.execute("DELETE FROM tasks")
            import_project(db, path, merge=False)

            new_tasks = db.get_all_tasks()
            assert len(new_tasks) > 0
            new_task_id = new_tasks[0].id
            results = db.get_test_results(new_task_id)
            assert len(results) == 1
            assert results[0]["result"] == "pass"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_import_with_issues(self, db, sample_tasks):
        """Issues and issue_history should be exported and imported."""
        from src.core.project_io import export_project, import_project

        task_id = sample_tasks[0].id
        issue_id = db.insert_issue(
            task_id=task_id, title="温度超限",
            description="超出规格",
            issue_type="bug", severity="major", status="open",
        )
        db.insert_issue_history(issue_id, "status", "open", "in_progress")

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "test_issues" in data
            assert "issue_history" in data
            assert len(data["test_issues"]) == 1
            assert len(data["issue_history"]) == 1

            # Clear and reimport
            db.conn.execute("DELETE FROM issue_history")
            db.conn.execute("DELETE FROM test_issues")
            db.conn.execute("DELETE FROM test_results")
            db.conn.execute("DELETE FROM tasks")
            result = import_project(db, path, merge=False)

            assert result["issue_count"] == 1
            new_tasks = db.get_all_tasks()
            issues = db.get_issues(task_id=new_tasks[0].id)
            assert len(issues) == 1
            assert issues[0]["title"] == "温度超限"
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestExportFormat:
    def test_export_has_version(self, db):
        from src.core.project_io import export_project

        path = str(db.db_path).replace(".db", "_export.kekaoxing")
        try:
            export_project(db, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "version" in data
            assert "exported_at" in data
            assert "magic" in data
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_import_invalid_magic_raises(self, db):
        """Importing a file with wrong magic should raise ValueError."""
        from src.core.project_io import import_project
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".kekaoxing",
                                         delete=False, encoding="utf-8") as f:
            json.dump({"magic": "wrong-magic", "tasks": [], "resources": []}, f)
            f.flush()
            fpath = f.name

        try:
            with pytest.raises(ValueError):
                import_project(db, fpath)
        finally:
            os.unlink(fpath)


import pytest
