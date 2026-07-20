# Session Handoff — 2026-07-20

## 完成的工作

### UI 優化
- **Issue 列表**：篩選行放上層（全部狀態▾ / 全部嚴重度▾ / 全部優先級▾ / DRI…）、操作按鈕靠右（全選 / 批量操作 / 刷新 + 統計）
- **待辦事項**：同樣兩行佈局 — 篩選行（項目▾ / 搜索 / 顯示歸檔）+ 操作行（快速添加靠左 / 編輯/刪除/歸檔靠右）
- **移除 DynamicFilterPanel**（Issue 列表和待辦兩處都改成固定篩選下拉）

### 測試優化（本輪核心）
- **新增 4 個測試文件**：`test_ui_refactor.py`(16), `test_dialog_smoke.py`(8), `test_widgets_more.py`(13), `test_dialog_coverage.py`(12) = 共 49 個新測試
- **測試數**：553 → **587** (+34)
- **覆蓋率**：54% → **57%**（含 test_boundary）/ 53.6% → **55.7%**（不含）

### 關鍵模塊覆蓋提升
- quick_create.py: 12% → **95%**
- resolve_dialog.py: 18% → **94%**
- column_persistence.py: 26% → **88%**
- filter_row.py: 0% → 62%
- undo_manager: 0% → 78%
- import_tasks_from_plan_dialog: 0% → 74%
- issue_dialog.py: 8% → 57%
- plan_edit_dialog.py: 13% → 59%

### 清理
- `test_e2e_full.py` / `test_performance.py` → `tests/manual/`
- `test_session_20260512.py` → `test_import_and_schema.py`
- `test_new_features.py` → `test_service_edge_cases.py`

### CI
- 添加 `--cov-fail-under=50` + coverage artifact
- 更新 E2E/performance 測試路徑
- 添加 `pytest.ini`（排除 manual/、過濾 warning）

## 最新提交
`7683036` test: 補低覆蓋 dialog 測試 — quick_create 12%→95%, resolve 18%→94%

## 覆蓋缺口（仍可補）
- `proxy_style.py`: 0% (249 行，Qt proxy style，較難測)
- `plan_handlers.py`: 11% (763 行，需 Qt mocking)
- `batch_import_dialog.py`: 9% (255 行)
- `kanban_view.py`: 58% (489 行)
- `dashboard_view.py`: 58% (584 行)
- `fa_capa_panels.py`: 25% (253 行)

## 阻塞 / 注意事項
- test_boundary.py CI-only bug 仍未修復（本地 553 passed，CI 上 init_schema 空表）
