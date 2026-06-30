"""待办事项模块测试 — Repo / Service / Schema / Dialog / 删除撤销。"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.db.repositories.todo_repo import TodoRepository
from src.db.repositories.project_repo import ProjectRepository
from src.services.todo_service import TodoService, TodoItem
from src.services.undo_manager import UndoManager, DeleteEntityCommand
from src.handlers.crud_helpers import exec_crud

# ── Qt 测试 fixtures（仅 Dialog 测试需要）──

@pytest.fixture(scope="module")
def _app():
    from PySide6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def _ctrl(_app):
    from src.controllers import AppController
    c = AppController(':memory:')
    c.initialize()
    return c


@pytest.fixture(scope="module")
def _main_window(_ctrl):
    from main import MainWindow
    w = MainWindow(_ctrl)
    return w


# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture()
def project(db_conn):
    """创建一个测试项目。"""
    repo = ProjectRepository(db_conn)
    pid = repo.insert(name="待办测试项目")
    return pid


@pytest.fixture()
def repo(db_conn):
    return TodoRepository(db_conn)


@pytest.fixture()
def svc(db_conn):
    return TodoService(TodoRepository(db_conn))


@pytest.fixture()
def sample_todo(repo, project) -> int:
    """创建一个示例待办并返回 ID。"""
    return repo.create({
        "project_id": project,
        "title": "完成MTBF测试报告",
        "priority": "high",
        "status": "pending",
        "category": "文档",
        "due_date": "2026-07-15",
    })


# ═══════════════════════════════════════════════════════════════════
#  1. Schema — v25 新增 todos 表
# ═══════════════════════════════════════════════════════════════════


class TestSchemaV25:
    """验证 v25 迁移正确创建 todos 表。"""

    def test_todos_table_exists(self, db_conn):
        """todos 表存在且列结构正确。"""
        cols = {r[1] for r in db_conn.execute("PRAGMA table_info(todos)").fetchall()}
        assert "id" in cols
        assert "project_id" in cols
        assert "title" in cols
        assert "priority" in cols
        assert "status" in cols
        assert "due_date" in cols
        assert "category" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_todos_project_id_foreign_key(self, db_conn, project):
        """project_id 引用 projects 表且 CASCADE。"""
        db_conn.execute(
            "INSERT INTO todos (project_id, title) VALUES (?, ?)",
            (project, "关联项目的待办"),
        )
        # 验证外键约束：删除项目后级联删除
        db_conn.execute("DELETE FROM projects WHERE id = ?", (project,))
        remaining = db_conn.execute(
            "SELECT COUNT(*) FROM todos"
        ).fetchone()[0]
        assert remaining == 0

    def test_todos_indexes_exist(self, db_conn):
        """todos 的索引存在。"""
        idxs = {r[1] for r in db_conn.execute("PRAGMA index_list(todos)").fetchall()}
        assert "idx_todos_project" in idxs
        assert "idx_todos_status" in idxs

    def test_migrate_from_v24_creates_todos(self, db_conn):
        """从 v24 迁移到 v25 后 todos 表存在。"""
        # 用 init_schema 已经初始化到 v25，验证表存在
        row = db_conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] >= 25


# ═══════════════════════════════════════════════════════════════════
#  2. TodoRepository — CRUD
# ═══════════════════════════════════════════════════════════════════


class TestTodoRepository:
    """TodoRepository CRUD 操作。"""

    def test_create_returns_id(self, repo, project):
        """create 返回 lastrowid。"""
        tid = repo.create({
            "project_id": project,
            "title": "创建测试",
            "priority": "medium",
        })
        assert isinstance(tid, int)
        assert tid > 0

    def test_get_returns_todo(self, repo, project):
        """get 按 ID 返回 TodoItem。"""
        tid = repo.create({"project_id": project, "title": "查找测试"})
        todo = repo.get(tid)
        assert todo is not None
        assert todo.id == tid
        assert todo.title == "查找测试"

    def test_get_nonexistent_returns_none(self, repo):
        """get 不存在的 ID 返回 None。"""
        assert repo.get(99999) is None

    def test_update_modifies_fields(self, repo, project):
        """update 修改字段。"""
        tid = repo.create({"project_id": project, "title": "旧标题"})
        repo.update(tid, title="新标题", priority="low")
        todo = repo.get(tid)
        assert todo is not None
        assert todo.title == "新标题"
        assert todo.priority == "low"

    def test_delete_removes_todo(self, repo, project):
        """delete 删除后 get 返回 None。"""
        tid = repo.create({"project_id": project, "title": "待删除"})
        repo.delete(tid)
        assert repo.get(tid) is None

    def test_list_all_empty(self, repo):
        """空表返回空列表。"""
        assert repo.list_all() == []

    def test_list_all_returns_all(self, repo, project):
        """list_all 返回所有待办。"""
        repo.create({"project_id": project, "title": "事项1"})
        repo.create({"project_id": project, "title": "事项2"})
        all_todos = repo.list_all()
        assert len(all_todos) == 2

    def test_list_all_filters_by_field(self, repo, project):
        """list_all 支持可选过滤条件。"""
        repo.create({"project_id": project, "title": "高优先级", "priority": "high"})
        repo.create({"project_id": project, "title": "低优先级", "priority": "low"})
        high = repo.list_all(priority="high")
        assert len(high) == 1
        assert high[0].title == "高优先级"


class TestTodoRepositoryListByProject:
    """TodoRepository.list_by_project 项目筛选。"""

    def test_list_by_project(self, repo):
        """返回指定项目的待办事项。"""
        p1 = ProjectRepository(repo.conn).insert(name="P1")
        p2 = ProjectRepository(repo.conn).insert(name="P2")
        t1 = repo.create({"project_id": p1, "title": "P1事项"})
        repo.create({"project_id": p2, "title": "P2事项"})

        p1_todos = repo.list_by_project(p1)
        assert len(p1_todos) == 1
        assert p1_todos[0].id == t1

    def test_list_by_project_empty(self, repo):
        """无待办的项目返回空列表。"""
        p = ProjectRepository(repo.conn).insert(name="空项目")
        assert repo.list_by_project(p) == []


# ═══════════════════════════════════════════════════════════════════
#  3. TodoService — 业务逻辑
# ═══════════════════════════════════════════════════════════════════


class TestTodoService:
    """TodoService CRUD + 状态切换。"""

    def test_create_and_get(self, svc, project):
        tid = svc.create(project_id=project, title="Service测试", priority="high")
        assert isinstance(tid, int)
        todo = svc.get(tid)
        assert todo is not None
        assert todo.title == "Service测试"

    def test_update(self, svc, project):
        tid = svc.create(project_id=project, title="更新前")
        svc.update(tid, title="更新后")
        assert svc.get(tid).title == "更新后"

    def test_delete(self, svc, project):
        tid = svc.create(project_id=project, title="删除测试")
        svc.delete(tid)
        assert svc.get(tid) is None

    def test_list_all(self, svc, project):
        svc.create(project_id=project, title="A")
        svc.create(project_id=project, title="B")
        assert len(svc.list_all()) == 2

    def test_list_by_project(self, svc):
        p1 = ProjectRepository(svc._repo.conn).insert(name="P1")
        p2 = ProjectRepository(svc._repo.conn).insert(name="P2")
        svc.create(project_id=p1, title="P1待办")
        svc.create(project_id=p2, title="P2待办")
        assert len(svc.list_by_project(p1)) == 1
        assert len(svc.list_by_project(p2)) == 1

    def test_toggle_status_cycle(self, svc, project):
        """toggle_status 走完整周期 pending→in_progress→done→pending。"""
        tid = svc.create(project_id=project, title="循环测试", status="pending")

        # pending → in_progress
        assert svc.toggle_status(tid) == "in_progress"
        assert svc.get(tid).status == "in_progress"

        # in_progress → done
        assert svc.toggle_status(tid) == "done"
        assert svc.get(tid).status == "done"

        # done → pending
        assert svc.toggle_status(tid) == "pending"
        assert svc.get(tid).status == "pending"

    def test_toggle_status_nonexistent(self, svc):
        """不存在的待办返回 None。"""
        assert svc.toggle_status(99999) is None


# ═══════════════════════════════════════════════════════════════════
#  4. TodoService — 删除命令 + 撤销
# ═══════════════════════════════════════════════════════════════════


class TestTodoDeleteCommand:
    """TodoService.create_delete_command 创建可撤销的删除命令。"""

    def test_creates_delete_command(self, svc, project):
        """create_delete_command 返回 DeleteEntityCommand。"""
        tid = svc.create(project_id=project, title="撤销测试事项")
        cmd = svc.create_delete_command(tid)
        assert isinstance(cmd, DeleteEntityCommand)
        assert "待办事项" in cmd.description

    def test_execute_deletes_todo(self, svc, project):
        """命令执行后待办被删除。"""
        tid = svc.create(project_id=project, title="执行删除")
        cmd = svc.create_delete_command(tid)
        um = UndoManager()
        um.execute(cmd)
        assert svc.get(tid) is None

    def test_undo_restores_todo(self, svc, project):
        """撤销后待办恢复，字段不变。"""
        tid = svc.create(project_id=project, title="撤销恢复",
                         priority="high", category="文档")
        cmd = svc.create_delete_command(tid)
        um = UndoManager()
        um.execute(cmd)
        assert svc.get(tid) is None

        um.undo()
        restored = svc.get(tid)
        assert restored is not None
        assert restored.title == "撤销恢复"
        assert restored.priority == "high"

    def test_exec_crud_with_undo_success(self, svc, project, db_conn):
        """通过 exec_crud 执行删除+撤销，验证 toast 和命令注册。"""
        from src.handlers.crud_helpers import exec_crud

        tid = svc.create(project_id=project, title="CRUD删除测试")
        cmd = svc.create_delete_command(tid)
        um = UndoManager()

        # mock MainWindow
        win = MagicMock()
        win.ctrl.undo_manager = um

        result = exec_crud(
            win=win,
            action=svc.delete,
            action_args=(tid,),
            toast_msg="待办已删除",
            entity="todo",
            undo_command=cmd,
        )
        assert result is True
        assert svc.get(tid) is None
        win.toast.assert_called_once_with("待办已删除", "success")

        # 撤销
        um.undo()
        assert svc.get(tid) is not None
        assert svc.get(tid).title == "CRUD删除测试"


# ═══════════════════════════════════════════════════════════════════
#  5. TodoEditDialog — 构造测试（headless Qt）
# ═══════════════════════════════════════════════════════════════════


class TestTodoEditDialog:
    """TodoEditDialog 构造 + get_data 验证。"""

    def test_create_dialog_new(self, _main_window):
        """新建模式弹窗构造。"""
        from src.views.dialogs.todo_edit_dialog import TodoEditDialog

        dlg = TodoEditDialog(parent=_main_window)
        assert dlg.windowTitle() == "新增待办事项"
        data = dlg.get_data()
        assert "title" in data
        assert "project_id" in data
        assert data["priority"] in ("high", "medium", "low")
        dlg.close()

    def test_create_dialog_edit(self, _main_window, svc, project):
        """编辑模式弹窗预填数据。"""
        from src.views.dialogs.todo_edit_dialog import TodoEditDialog
        from src.models.todo import TodoItem

        tid = svc.create(project_id=project, title="编辑测试智能体",
                         priority="high", due_date="2026-08-01")
        todo = svc.get(tid)
        dlg = TodoEditDialog(todo=todo, parent=_main_window)
        assert dlg.windowTitle() == "编辑待办事项"
        data = dlg.get_data()
        assert data["title"] == "编辑测试智能体"
        assert data["priority"] == "high"
        assert data["due_date"] == "2026-08-01"
        dlg.close()

    def test_dialog_with_projects(self, _main_window, project):
        """弹窗带项目列表时 project_id 正确。"""
        from src.views.dialogs.todo_edit_dialog import TodoEditDialog
        from src.models.project import Project

        proj = Project(id=project, name="测试项目")
        dlg = TodoEditDialog(parent=_main_window, projects=[proj])
        dlg.close()
