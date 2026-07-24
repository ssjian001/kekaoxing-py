# 測試覆蓋率報告 — 2026-07-24

總體覆蓋率：56% (18,391 行，8,108 未覆蓋)

## 亟需補測試的底層模組（< 30%）

| 模組 | 行數 | 覆蓋率 | 未覆蓋行 |
|:-----|:---:|:------:|:---------|
| `task_dialog.py` | 469 | **7%** | 任務編輯彈窗 — 含排序/批量操作/複製 |
| `batch_import_dialog.py` | 256 | **9%** | Excel 批量導入 |
| `test_result_dialog.py` | 326 | **10%** | 測試結果錄入 |
| `plan_handlers.py` | 764 | **11%** | 測試計劃事件處理（最大檔） |
| `schedule_preview_dialog.py` | 344 | **11%** | 自動排程預覽 |
| `attachment_dialog.py` | 164 | **14%** | 附件管理對話框 |
| `sample_handlers.py` | 254 | **18%** | 樣品管理事件處理 |
| `analysis_widget.py` | 164 | **18%** | 數據分析元件 |
| `result_matrix.py` | 235 | **29%** | 結果矩陣 |
| `export_handlers.py` | 265 | **27%** | 匯出事件處理 |

## 邊緣模組（30-60%）

| 模組 | 覆蓋率 | 說明 |
|:-----|:------:|:------|
| `export_handlers.py` | 27% | |
| `result_matrix.py` | 29% | |
| `kanban_column.py` | 63% | |
| `undo_manager.py` | 78% | 核心功能，覆蓋不錯 |
| `dashboard_view.py` | 85% | 較好 |
| `scheduler.py` | 88% | 最好之一 |

## 改善建議（ROI 排序）

1. **plan_handlers.py (11%)** → 最大檔案 764 行，測試成本最低的做法是加整合測試（呼叫 handler → service → repo 全鏈路）
2. **task_dialog.py (7%)** → 任務編輯是核心 UX，加測試需要 mock 對話框生命週期
3. **dialogs 群組 (7-14%)** → 可用 pytest-qt 加基本測試（只是驗證初始化不 crash）
4. **sample_handlers.py (18%)** → 樣品操作是常用功能
