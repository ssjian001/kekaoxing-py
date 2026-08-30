# 待办事项增强：提醒 + 四象限规划

## 设计决策

- **quadrant=0（未分类）**：在四象限视图底部灰色「未分类」区显示，不隐藏
- **提醒精度**：分钟，格式 `YYYY-MM-DD HH:MM`
- **象限颜色**：① RED(重要紧急) ② BLUE(重要不紧急) ③ WARNING(不重要紧急) ④ SURFACE1(不重要不紧急)
- **默认值**：quadrant=0, remind_at='', reminded=0
- **新建顺序**：先 Schema + Model + Repo + Service，再 UI（Dialog → QuadrantView → TodoView），最后集成（main.py + handler）

## 文件清单

### 1. `src/db/schema.py` — Schema v26 迁移

**DDL 更新**（在 `_DDL_TABLES` 的 todos CREATE TABLE 中加 3 列）：
```sql
remind_at   TEXT    NOT NULL DEFAULT '',
reminded    INTEGER NOT NULL DEFAULT 0,
quadrant    INTEGER NOT NULL DEFAULT 0,
```

插入位置：`due_date` 行之后，`created_at` 行之前。

**新增索引**（在 `_DDL_INDEXES` 中加）：
```sql
"CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at)",
"CREATE INDEX IF NOT EXISTS idx_todos_quadrant ON todos(quadrant)",
```

**新增迁移函数 `_migrate_v26`**：
```python
def _migrate_v26(conn: apsw.Connection) -> None:
    """v25→v26: todos 表加提醒 + 四象限字段。"""
    alterations = [
        "ALTER TABLE todos ADD COLUMN remind_at TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE todos ADD COLUMN reminded INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE todos ADD COLUMN quadrant INTEGER NOT NULL DEFAULT 0",
    ]
    for ddl in alterations:
        conn.execute(ddl)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_quadrant ON todos(quadrant)")
```

注册到迁移调度表（`_MIGRATIONS` dict）。

### 2. `src/models/todo.py` — 加 3 个字段

```python
remind_at: str = ""
reminded: bool = False
quadrant: int = 0
```

加一个属性（可选）：
```python
@property
def quadrant_label(self) -> str:
    return {1: "重要紧急", 2: "重要不紧急", 3: "不重要紧急", 4: "不重要不紧急"}.get(self.quadrant, "未分类")
```

### 3. `src/db/repositories/todo_repo.py` — 加 2 个方法

```python
def list_due_reminders(self, now: str) -> list[TodoItem]:
    """查询 remind_at <= now AND reminded=0 的待办。"""
    cols_sql = self._columns_sql()
    sql = f"SELECT {cols_sql} FROM [todos] WHERE [remind_at] != '' AND [remind_at] <= ? AND [reminded] = 0"
    rows = self._conn.execute(sql, (now,)).fetchall()
    return self._rows_to_models(rows, cols=self._columns())

def mark_reminded(self, todo_id: int) -> None:
    """标记提醒已触发。"""
    self._conn.execute("UPDATE [todos] SET reminded = 1 WHERE id = ?", (todo_id,))
```

### 4. `src/services/todo_service.py` — 加 2 个方法

```python
def list_due_reminders(self, now: str) -> list[TodoItem]:
    return self._repo.list_due_reminders(now)

def mark_reminded(self, todo_id: int) -> None:
    self._repo.mark_reminded(todo_id)
```

### 5. `src/views/dialogs/todo_edit_dialog.py` — 表单加字段

**在 _status_combo 后加象限选择**：
```python
# ── 四象限 ──
self._quadrant_combo = self._add_combo_field(
    "优先级象限",
    items=["未分类", "① 重要且紧急", "② 重要不紧急", "③ 不重要但紧急", "④ 不重要不紧急"],
    default={0: "未分类", 1: "① 重要且紧急", 2: "② 重要不紧急", 3: "③ 不重要但紧急", 4: "④ 不重要不紧急"}
        .get(todo.quadrant if todo else 0, "未分类"),
)
```

**在 _due_date_edit 后加提醒时间**：
```python
# ── 提醒时间 ──
self._remind_at_edit = self._add_text_field(
    "提醒时间",
    default=todo.remind_at if todo else "",
    placeholder="可选，如：2026-07-15 14:00",
)
```

**`get_data()` 返回值加**：
```python
"remind_at": self._remind_at_edit.text().strip(),
"quadrant": self._QUADRANT_MAP.get(self._quadrant_combo.currentText(), 0),
```
常量：`_QUADRANT_MAP = {"未分类": 0, "① 重要且紧急": 1, ...}`

### 6. NEW: `src/views/quadrant_view.py` — 四象限视图

**结构**：QWidget → QVBoxLayout → 2×2 QGridLayout + 底部「未分类」水平栏

**行1（重要）**：row=0 → ① 重要紧急(左) / ② 重要不紧急(右)
**行2（不重要）**：row=1 → ③ 不重要紧急(左) / ④ 不重要不紧急(右)
**行3（未分类）**：row=2 → 居中单行

**每个象限是一个 QuadrantCell(QFrame)**，包含：
- 标题 QLabel（象限名 + 计数）
- QScrollArea 内部 vertical layout
- 支持 dropEvent（接收 `_MIME_TODO_ID`，更新 quadrant）

**信号**：
- `quadrant_changed = Signal(int, int)` → (todo_id, new_quadrant)
- `card_selected = Signal(int)` → (todo_id)，复用 TodoCard 的 selected 信号

**方法**：
- `refresh(todos: list[TodoItem])` → 按 quadrant 分组填充
- `refresh_theme()` → 更新背景色

**拖拽逻辑**：
- 复用 TodoCard 的 `_start_drag()`（使用 `_MIME_TODO_ID`）
- QuadrantCell.dropEvent → 解析 todo_id → 更新 quadrant → emit `quadrant_changed`
- 注意：QuadrantCell 需要 `setAcceptDrops(True)` + 实现 `dragEnterEvent`/`dropEvent`

**QSS class 选择器**（在 theme.py 中定义）：
```css
QFrame[class="quadrant-cell-q1"] { background: {QUAD1_BG}; border-radius: 8px; }
QFrame[class="quadrant-cell-q2"] { background: {QUAD2_BG}; border-radius: 8px; }
QFrame[class="quadrant-cell-q3"] { background: {QUAD3_BG}; border-radius: 8px; }
QFrame[class="quadrant-cell-q4"] { background: {QUAD4_BG}; border-radius: 8px; }
QFrame[class="quadrant-cell-unset"] { background: {SURFACE0}; border-radius: 8px; }
```

**颜色变量（在 theme.py 的 Latte/Dark 色板中定义）**：
- `QUAD1_BG = RED` theme 变量，加透明度 `rgba(r,g,b,0.15)`
- `QUAD2_BG = BLUE` theme 变量，加透明度
- `QUAD3_BG = WARNING` theme 变量，加透明度
- `QUAD4_BG = SURFACE1`
实际用 QSS `background: rgba(...)` 即可，不要新建色板变量，使用现有变量拼 rgba。

### 7. `src/views/todo_view.py` — 子 Tab 切换看板/四象限

**改动**：

a) **在 _setup_ui 中加子 Tab**：
```python
self._sub_tabs = QTabBar()  # 或 QTabWidget
self._stack = QStackedWidget()
self._stack.addWidget(self._kanban_widget)    # 现有看板内容包成 QWidget
self._stack.addWidget(self._quadrant_view)    # 新建 QuadrantView
self._sub_tabs.addTab("看板")
self._sub_tabs.addTab("四象限")
self._sub_tabs.currentChanged.connect(self._stack.setCurrentIndex)
```

b) **`_setup_ui` 结构调整**：
- 把现有看板内容（columns + layout）移到 `_kanban_widget` 内部
- 新建 `self._quadrant_view = QuadrantView()` 
- `self._quadrant_view.quadrant_changed.connect(self._on_quadrant_changed)`

c) **`refresh()` 方法加同步**：
```python
def refresh(self, todo_list, projects=None):
    ...
    filtered = self._get_filtered(todo_list)  # 提取共有过滤逻辑
    self._populate_kanban(filtered)
    self._quadrant_view.refresh(filtered)
```

d) **`_build_toolbar()` 加搜索输入框**（修复 main.py search_map bug）：
```python
self._search_edit = QLineEdit()
self._search_edit.setPlaceholderText("搜索待办…")
self._search_edit.setProperty("class", "search-input")
self._search_edit.textChanged.connect(self._on_search)
```
搜索逻辑：过滤 title/description 匹配的待办，传给 refresh。

e) **`refresh_theme()` 链式调用加象限视图**：
```python
self._quadrant_view.refresh_theme()
```

f) **`_on_quadrant_changed(todo_id, new_quadrant)`** → 调用 service 更新 + toast

### 8. `src/handlers/todo_handlers.py` — 连接象限信号

```python
v.quadrant_changed.connect(self._on_todo_quadrant_changed)
```

新方法：
```python
def _on_todo_quadrant_changed(self, todo_id: int, new_quadrant: int) -> None:
    ctrl = self._win.ctrl
    if not ctrl or not ctrl.todo_service:
        return
    ctrl.todo_service.update(todo_id, quadrant=new_quadrant)
    quadrant_label = {0: "未分类", 1: "重要紧急", 2: "重要不紧急", 3: "不重要紧急", 4: "不重要不紧急"}.get(new_quadrant, "未分类")
    self._win.toast(f"象限已更新为 {quadrant_label}", "success")
    self._win.schedule_throttled_refresh("todo")
```

### 9. `src/styles/theme.py` — QSS 选择器

在 `kanban-col-*` 块后加（约 line 755 附近）：
```css
/* ── 四象限单元格 ── */
QFrame[class="quadrant-cell-q1"]  { background: rgba(210,15,57,0.12); border-radius: 8px; }
QFrame[class="quadrant-cell-q2"]  { background: rgba(30,102,245,0.12); border-radius: 8px; }
QFrame[class="quadrant-cell-q3"]  { background: rgba(254,100,11,0.12); border-radius: 8px; }
QFrame[class="quadrant-cell-q4"]  { background: {SURFACE0}; border-radius: 8px; }
QFrame[class="quadrant-cell-unset"] { background: {BG_INPUT}; border-radius: 8px; border: 1px dashed {BORDER}; }

/* ── 四象限标题 ── */
QLabel[class="quadrant-title"] {
    color: {TEXT}; font-size: 13px; font-weight: 700; border: none;
}
```

### 10. `main.py` — 提醒定时器 + 子 Tab 注册

**在 `_setup_central_widget()` 末尾加（before 恢复上次 Tab 选择）**：
```python
# ── 待办提醒定时器 ──
self._reminder_timer = QTimer(self)
self._reminder_timer.setInterval(30_000)  # 30s
self._reminder_timer.timeout.connect(self._check_todo_reminders)
self._reminder_timer.start()
```

**新方法**：
```python
def _check_todo_reminders(self) -> None:
    """检查到期待办提醒。"""
    from datetime import datetime
    ctrl = self._ctrl
    if not ctrl or not ctrl.todo_service:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    due = ctrl.todo_service.list_due_reminders(now)
    for todo in due:
        if todo.id is not None:
            self.toast(f"⏰ 待办提醒：{todo.title}", "info")
            ctrl.todo_service.mark_reminded(todo.id)
    if due:
        self.schedule_throttled_refresh("todo")
```

**`search_map[7]` 修复**：todo_view 已有 `_search_edit`，无需改 main.py 的引用。

**`_refresh_remaining_inline_styles()` 的 `for view in (...)` 元组**：加 `self._todo_view` 已存在，todo_view.refresh_theme() 会链式调用 quadrant_view.refresh_theme()。

### 11. `tests/test_todo.py` — 更新测试

**`test_todos_table_exists`** 加 3 个断言：
```python
assert "remind_at" in cols
assert "reminded" in cols
assert "quadrant" in cols
```

**新增 `test_migrate_from_v25_creates_reminder_quadrant`**：
- 构建 v25 schema（不包含新列）
- 运行 `_migrate_v26`
- 验证 3 列存在且默认值正确

**新增 `test_list_due_reminders`**：
- 插入 3 条 todo（remind_at 在过去/将来/空）
- 验证只返回到期未提醒的记录

### 12. `feature_list.json` — 加新功能条目

```json
{
    "id": "F021",
    "name": "待办提醒 + 四象限",
    "description": "待办事项提醒定时器、Eisenhower 四象限视图、象限拖拽切换",
    "status": "in_progress",
    "dependencies": ["F020"],
    "priority": "medium"
}
```

（F020 是 todo 看板功能，检查实际 ID 并调整）

### 13. `reliatrack/CLAUDE.md` — Schema 版本更新

v25→v26，表数 20→20（仍是 todos 表，只是加列）。更新注释。

### 14. `progress/current.md` — 更新最近完成 + 下一步

加提醒+象限到最近完成。

## 实现顺序

1. Schema + Model + Repo + Service（数据层，独立可测）
2. theme.py QSS 选择器（样式层）
3. Dialog 表单（编辑弹窗）
4. QuadrantView（新视图，核心 UI）
5. TodoView 改造（子 Tab + 搜索框 + 刷新联动）
6. handler 象限信号连接
7. main.py 提醒定时器
8. 测试 + 文档

## 已知陷阱

1. `_rows_to_models` 自动发现列 → 模型字段名必须与列名一致
2. QuadrantCell 的 dropEvent 需要 `setAcceptDrops(True)` + `dragEnterEvent` 接受 `_MIME_TODO_ID`
3. 提醒时间比较用 SQLite 字符串比较，`YYYY-MM-DD HH:MM` 格式天然字典序可比
4. 主题切换：quadrant_view.refresh_theme() 须在 todo_view.refresh_theme() 中链式调用
5. 项目筛选联动：`_populate()` 抽取出 `_get_filtered()` 方法，看板和象限共用
6. TodoCard 的 `_MIME_TODO_ID` 常量需要从 `todo_view.py` import——已在当前文件中定义
7. `test_todos_table_exists` 的列断言是硬编码的，不通过 `PRAGMA` 自动获取——加 3 行即可
