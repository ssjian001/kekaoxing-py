# Agent Instructions

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->

## Tab 增删/重排 — 索引全局同步

移除或重排 QTabWidget 的 Tab 时，tab 索引在多处以**魔法数字**出现，
分散在不同文件和抽象层级中。只搜 `addTab` / `currentIndex` 不够。

**必须全局搜索以下模式**（跨整个项目）：
- `_StatCard(` / `tab_index=` — 仪表盘卡片跳转
- `search_map` / `_on_shortcut_` — 快捷键索引映射
- `setCurrentIndex(` — 直接索引调用
- `card_clicked` — 仪表盘信号携带的索引值

**原则**：改 Tab 结构 = 改索引。列出所有引用点 → 逐个更新 → 确认 → 提交。

## UI 交互回调语义验证

修改或新增任何 UI 交互回调（双击、右键、快捷键、就地编辑）前，必须：

1. **追溯回调连接点** — 找到该 callback 在 handler 层连接到哪个方法，
   确认它的实际语义（"打开对话框" vs "直接写 DB" vs "刷新视图"）。
   不要按名字猜行为。

2. **就地编辑必须走写 DB 路径** — 任何 `_edit_inline_*` 方法的 commit
   逻辑必须用批量更新 / repository 写入，不能复用"打开编辑对话框"的回调。
   复用会导致：对话框 + 就地编辑器同时弹出 → modal 冲突 → 崩溃。

3. **交互路径写完必须亲自触发一次** — 双击、右键、快捷键、粘贴，
   每条改过的路径必须在运行的应用里实际操作一次。测试套件覆盖不到 UI 交互，
   py_compile / pytest 全过 ≠ UI 没问题。

## 新增 API 接线验证

新增任何 `set_*` / `setup_*` 方法或构造参数后，必须：

1. **追踪调用链** — 从定义点搜索调用点，确认每一层都接上了。
   "方法已定义" ≠ "功能已接通"。定义了 `set_reference_data()`
   但没人调用 = 功能静默失效。

2. **实际触发** — 在运行的应用里亲自操作一次对应交互路径
   （右键、双击、快捷键），确认不是静默 return。

3. **双主题验证** — 涉及颜色/样式的改动，亮色和暗色各测一次。
   `QColor()` 等无效值在亮色下视觉正常，暗色下才暴露。

4. **警惕静默 guard** — `if not self._xxx: return` 是静默失败的温床。
   新增这类 guard 时，必须确认 `_xxx` 在启动流程中被正确注入。
