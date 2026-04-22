"""tests/test_undo_manager.py — 撤销管理器测试。"""
import pytest
from unittest.mock import MagicMock


class TestUndoManager:
    def test_execute_and_undo(self):
        """execute runs command.do(), undo() runs command.undo()."""
        from src.core.undo_manager import UndoManager, Command

        class IncCmd(Command):
            description = "increment"
            def __init__(self, state):
                self.state = state
            def do(self):
                self.state["n"] += 1
            def undo(self):
                self.state["n"] -= 1

        um = UndoManager()
        state = {"n": 0}
        um.execute(IncCmd(state))
        assert state["n"] == 1

        result = um.undo()
        assert state["n"] == 0
        assert result == "increment"

    def test_redo(self):
        from src.core.undo_manager import UndoManager, Command

        class IncCmd(Command):
            description = "increment"
            def __init__(self, state):
                self.state = state
            def do(self):
                self.state["n"] += 1
            def undo(self):
                self.state["n"] -= 1

        um = UndoManager()
        state = {"n": 0}
        um.execute(IncCmd(state))

        um.undo()
        assert state["n"] == 0

        result = um.redo()
        assert state["n"] == 1
        assert result == "increment"

    def test_history_limit(self):
        from src.core.undo_manager import UndoManager, Command

        class CountCmd(Command):
            description = "inc"
            def __init__(self, counter):
                self.counter = counter
            def do(self):
                self.counter["n"] += 1
            def undo(self):
                self.counter["n"] -= 1

        um = UndoManager(max_history=3)
        counter = {"n": 0}

        for _ in range(5):
            um.execute(CountCmd(counter))

        assert counter["n"] == 5
        # Only 3 commands retained in undo stack
        assert um.undo_count == 3

        # Undo 3 times → back to 2
        um.undo()
        um.undo()
        um.undo()
        assert counter["n"] == 2
        assert um.undo_count == 0

    def test_undo_empty_stack(self):
        from src.core.undo_manager import UndoManager
        um = UndoManager()
        result = um.undo()  # should return None, not crash
        assert result is None

    def test_redo_empty_stack(self):
        from src.core.undo_manager import UndoManager
        um = UndoManager()
        result = um.redo()
        assert result is None

    def test_can_undo_can_redo(self):
        from src.core.undo_manager import UndoManager, Command

        class NoopCmd(Command):
            description = "noop"
            def do(self):
                pass
            def undo(self):
                pass

        um = UndoManager()
        assert um.can_undo() is False
        assert um.can_redo() is False

        um.execute(NoopCmd())
        assert um.can_undo() is True
        assert um.can_redo() is False

        um.undo()
        assert um.can_undo() is False
        assert um.can_redo() is True

    def test_execute_clears_redo_stack(self):
        """After a new execute, redo stack should be cleared."""
        from src.core.undo_manager import UndoManager, Command

        class IncCmd(Command):
            description = "inc"
            def __init__(self, state):
                self.state = state
            def do(self):
                self.state["n"] += 1
            def undo(self):
                self.state["n"] -= 1

        um = UndoManager()
        state = {"n": 0}
        um.execute(IncCmd(state))
        um.undo()
        assert um.can_redo() is True

        # New execute clears redo
        um.execute(IncCmd(state))
        assert um.can_redo() is False

    def test_undo_redo_count(self):
        from src.core.undo_manager import UndoManager, Command

        class NoopCmd(Command):
            description = "noop"
            def do(self): pass
            def undo(self): pass

        um = UndoManager()
        assert um.undo_count == 0
        assert um.redo_count == 0

        um.execute(NoopCmd())
        um.execute(NoopCmd())
        assert um.undo_count == 2

        um.undo()
        assert um.undo_count == 1
        assert um.redo_count == 1

    def test_clear(self):
        from src.core.undo_manager import UndoManager, Command

        class NoopCmd(Command):
            description = "noop"
            def do(self): pass
            def undo(self): pass

        um = UndoManager()
        um.execute(NoopCmd())
        um.execute(NoopCmd())
        um.clear()
        assert um.undo_count == 0
        assert um.redo_count == 0

    def test_undo_description(self):
        from src.core.undo_manager import UndoManager, Command

        class MyCmd(Command):
            description = "move task to day 5"
            def do(self): pass
            def undo(self): pass

        um = UndoManager()
        assert um.undo_description() is None
        um.execute(MyCmd())
        assert um.undo_description() == "move task to day 5"

    def test_redo_description(self):
        from src.core.undo_manager import UndoManager, Command

        class MyCmd(Command):
            description = "move task to day 5"
            def do(self): pass
            def undo(self): pass

        um = UndoManager()
        assert um.redo_description() is None
        um.execute(MyCmd())
        um.undo()
        assert um.redo_description() == "move task to day 5"


class TestMoveTaskCommand:
    def test_move_and_undo(self, db, sample_tasks):
        from src.core.undo_manager import UndoManager, MoveTaskCommand

        t = sample_tasks[0]
        old_day = t.start_day
        new_day = 42

        cmd = MoveTaskCommand(db, t.id, old_day, new_day)
        um = UndoManager()
        um.execute(cmd)

        updated = db.get_task(t.id)
        assert updated.start_day == new_day

        um.undo()
        reverted = db.get_task(t.id)
        assert reverted.start_day == old_day


class TestUpdateTaskCommand:
    def test_update_progress(self, db, sample_tasks):
        from src.core.undo_manager import UndoManager, UpdateTaskCommand

        t = sample_tasks[0]
        cmd = UpdateTaskCommand(db, t.id, "progress", 0.0, 80.0)
        um = UndoManager()
        um.execute(cmd)

        updated = db.get_task(t.id)
        assert updated.progress == 80.0

        um.undo()
        reverted = db.get_task(t.id)
        assert reverted.progress == 0.0


class TestDeleteTasksCommand:
    def test_delete_and_undo(self, db, sample_tasks):
        from src.core.undo_manager import UndoManager, DeleteTasksCommand

        # Collect task data before deletion
        tasks = db.get_all_tasks()
        tasks_data = []
        for t in tasks:
            from src.core.project_io import _task_to_dict
            tasks_data.append(_task_to_dict(t))

        cmd = DeleteTasksCommand(db, tasks_data)
        um = UndoManager()
        um.execute(cmd)

        assert db.task_count() == 0

        um.undo()
        assert db.task_count() == len(tasks)


class TestAddTaskCommand:
    def test_add_and_undo(self, db):
        from src.core.undo_manager import UndoManager, AddTaskCommand

        task_data = {
            "num": "NEW", "name_en": "New Task", "name_cn": "新任务",
            "section": "env", "duration": 3, "start_day": 0,
            "dependencies": [], "requirements": [],
        }
        cmd = AddTaskCommand(db, task_data)
        um = UndoManager()
        um.execute(cmd)

        assert db.task_count() == 1
        assert cmd.created_id is not None

        um.undo()
        assert db.task_count() == 0
