# 待办归档功能规划

## 设计决策

- 仅 `status=done` 的待办可以归档
- 已归档默认隐藏，工具栏加「显示已归档」复选框切换
- 归档可撤销（取消归档回到 done 状态）
- 提醒定时器跳过已归档待办
- 四象限视图同步过滤

## 文件改动

### 1. `src/db/schema.py` — Schema v27

- **SCHEMA_VERSION = 26 → 27**
- **`_DDL_TABLES`** 的 todos CREATE TABLE 在 `reminded` 后加 `archived INTEGER NOT NULL DEFAULT 0` 列
- **`_DDL_INDEXES`** 加 `idx_todos_archived ON todos(archived)`
- **新增 `_migrate_v27`**（幂等 ALTER TABLE + CREATE INDEX）
- 注册到 `_MIGRATORS` + `init_schema`

### 2. `src/models/todo.py` — 加字段

```python
archived: bool = False
```

加属性：
```python
@property
def is_archived(self) -> bool:
    return self.archived
```

### 3. `src/db/repositories/todo_repo.py` — 加方法

```python
def archive(self, todo_id: int) -> None:
    """归档指定待办。"""
    self._conn.execute("UPDATE [todos] SET archived = 1 WHERE id = ?", (todo_id,))

def unarchive(self, todo_id: int) -> None:
    """取消归档。"""
    self._conn.execute("UPDATE [todos] SET archived = 0 WHERE id = ?", (todo_id,))
```

`list_all()` 暂不改——过滤逻辑放在 service/view 层更灵活（支持显示/隐藏已归档切换）。

### 4. `src/services/todo_service.py` — 加方法

```python
def archive(self, todo_id: int) -> None:
    self._repo.archive(todo_id)

def unarchive(self, todo_id: int) -> None:
    self._repo.unarchive(todo_id)
```

### 5. `src/views/todo_view.py` — UI 改造

**a) `_build_toolbar()` 加「归档」按钮 + 「显示已归档」复选框**

在 `btn_delete` 和 `sep` 之间加归档按钮：
```python
self.btn_archive = QPushButton("归档")
self._style_tool_btn(self.btn_archive, f"color:{_t.SUBTEXT1};border:1px solid {_t.BORDER};background:{_t.BG_INPUT};")
```

在 `tb.addStretch()` 之前加复选框：
```python
self._show_archived_cb = QCheckBox("显示已归档")
self._show_archived_cb.setProperty("class", "filter-checkbox")
self._show_archived_cb.toggled.connect(self._refresh_current_view)
```

导入加 `QCheckBox`。

**b) `_filter_todos()` 加归档过滤**

```python
def _filter_todos(self, todo_list):
    ...
    # 归档过滤（除非勾选显示已归档）
    show_archived = hasattr(self, '_show_archived_cb') and self._show_archived_cb.isChecked()
    if not show_archived:
        filtered = [t for t in filtered if not t.archived]
    return filtered
```

**c) 信号加一个**
```python
archive_requested = Signal(int)  # todo_id
```

**d) `_build_kanban_view()` 加列级归档**

在 `done` 列中，已完成卡片下方或 hover 时加归档按钮较复杂。
简化方案：选中 done 列卡片后，点工具栏归档按钮即可。
只在选中卡片且状态为 done 时启用归档按钮。

### 6. `src/handlers/todo_handlers.py` — 连接

```python
v.btn_archive.clicked.connect(self._on_todo_archive)
```

```python
def _on_todo_archive(self) -> None:
    ctrl = self._win.ctrl
    if not ctrl or not ctrl.todo_service:
        return
    todo = self._win.todo_view.get_selected_todo()
    if todo is None:
        self._win.toast("请先选中一个待办事项", "info")
        return
    if todo.status != "done":
        self._win.toast("仅已完成的待办可以归档", "info")
        return
    if todo.id is None:
        return
    if todo.archived:
        ctrl.todo_service.unarchive(todo.id)
        self._win.toast(f"待办「{todo.title}」已取消归档", "success")
    else:
        ctrl.todo_service.archive(todo.id)
        self._win.toast(f"待办「{todo.title}」已归档", "success")
    self._win.schedule_throttled_refresh("todo")
```

### 7. `main.py` — 提示定时器过滤

`_check_todo_reminders` 中 `list_due_reminders` 需要排除已归档的。

修改 repo 的 `list_due_reminders` SQL：
```sql
AND [archived] = 0
```

### 8. `tests/test_todo.py` — 更新

- `test_todos_table_exists` 加 `assert "archived" in cols`
- `test_todos_indexes_exist` 加 `assert "idx_todos_archived" in idxs`
- `test_migrate_from_v25_creates_reminder_quadrant` 改版本断言 ≥27
- 新增 `test_archive_todo`

### 9. `src/views/quadrant_view.py`

`refresh()` 中的 `hasattr(t, 'archived')` 过滤已归档（和看板共用同一份 filtered 数据——`_filter_todos` 已在 `_refresh_current_view` 中处理，象限视图拿到的已经是过滤后的数据，不用改）

### 10. `reliatrack/CLAUDE.md`

Schema v26→v27

## 实现顺序

1. Schema + Model + Repo + Service（数据层）
2. todo_view.py 工具栏改造（归档按钮 + 复选框）
3. todo_handlers.py 连接信号
4. repo.list_due_reminders 加 archived=0 过滤
5. 测试 + 文档

## 注意

- 归档按钮只在选中 done 卡片时可用（`_on_card_selected` 中更新按钮状态）
- 勾选「显示已归档」后，归档卡片恢复可见，可选中后点归档按钮取消归档
- `_filter_todos` 在 refresh → _refresh_current_view 链中自动应用，看板和象限视图都不需要额外改动
