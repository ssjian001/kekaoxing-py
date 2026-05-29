"""批量迁移视图/对话框/控件：删除 theme_changed.connect + 内联样式转类选择器"""

import re
import sys

REPLACEMENTS = {
    # theme_changed.connect lines
    r'^\s+_theme\.theme_host\.theme_changed\.connect\(self\.update\)\s*\n': '',
    r'^\s+_theme\.theme_host\.theme_changed\.connect\(self\._refresh_theme\)\s*\n': '',
    r'^\s+_theme\.theme_host\.theme_changed\.connect\(self\._on_theme_changed\)\s*\n': '',
    r'^\s+_theme\.theme_host\.theme_changed\.connect\(self\._refresh_theme_styles\)\s*\n': '',
    
    # Multi-line: setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 12px;...
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_t\.SUBTEXT0\};\s*font-size:\s*12px;\s*font-weight:\s*500;"\s*\n\s*\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*12px;"\s*\n\s*\)': 
        'setProperty("class", "subtext")',
    
    # Multi-line: setStyleSheet(f"color: {_t.TEXT}; font-size: 13px; font-weight: bold;"
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_t\.TEXT\};\s*font-size:\s*13px;\s*font-weight:\s*bold;"\s*\n\s*\)': 
        'setProperty("class", "panel-header")',
    
    # Single-line: setStyleSheet(f"color: {_t.SUBTEXT0}; font-size: 12px;"
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT0\};\s*font-size:\s*12px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT0\};\s*font-size:\s*11px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT0\};\s*font-size:\s*13px;"\)': 
        'setProperty("class", "subtext")',
    
    # Single-line: setStyleSheet(f"color: {_t.TEXT}; font-size: 13px;"
    r'setStyleSheet\(f"color:\s*\{_t\.TEXT\};\s*font-size:\s*13px;"\)': 
        'setProperty("class", "text-bold")',
    
    # Single-line: setStyleSheet(f"color: {_t.TEXT}; font-size: 12px; font-weight: bold;"
    r'setStyleSheet\(f"color:\s*\{_t\.TEXT\};\s*font-size:\s*12px;\s*font-weight:\s*bold;"\)': 
        'setProperty("class", "panel-header")',
    
    # SUBTEXT0 + 11px + padding
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT0\};\s*font-size:\s*11px;\s*padding:\s*2px\s*4px;"\)': 
        'setProperty("class", "hint-label")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT0\};\s*font-size:\s*11px;\s*padding:\s*2px\s*0;"\)': 
        'setProperty("class", "hint-label")',
    
    # SUBTEXT1 + font-size 11px
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*11px;\s*border:\s*none;"\)': 
        'setProperty("class", "hint-label")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*11px;"\)': 
        'setProperty("class", "hint-label")',
    r'setStyleSheet\(f"color:\s*\{_theme\.SUBTEXT1\};\s*font-size:\s*11px;"\)': 
        'setProperty("class", "hint-label")',
    
    # SUBTEXT1 + font-size 13px
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*13px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*13px;\s*padding:\s*12px;"\)': 
        'setProperty("class", "subtext")',
    
    # SUBTEXT1 + font-size 12px
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*12px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*12px;\s*padding:\s*16px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*12px;\s*padding:\s*4px\s*8px;"\)': 
        'setProperty("class", "subtext")',
    
    # SUBTEXT1 + FONT_SIZE_SMALL
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*\{FONT_SIZE_SMALL\}px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*\{FONT_SIZE_SMALL\}px;\s*padding:\s*24px;"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*\{FONT_SIZE_SMALL\}px;\s*padding:\s*4px\s*8px;"\)': 
        'setProperty("class", "subtext")',
    
    # SURFACE1 color (separator lines, usually thin)
    r'setStyleSheet\(f"color:\s*\{_theme\.SURFACE1\};"\)': 
        'setProperty("class", "separator")',
    r'setStyleSheet\(f"color:\s*\{_t\.SURFACE1\};"\)': 
        'setProperty("class", "separator")',
    
    # BLUE color
    r'setStyleSheet\(f"color:\s*\{_t\.BLUE\};\s*font-size:\s*12px;\s*font-weight:\s*bold;"\)': 
        'setProperty("class", "accent-label")',
    r'setStyleSheet\(f"color:\s*\{_t\.BLUE\};\s*font-size:\s*\{FONT_SIZE_SMALL\}px;"\)': 
        'setProperty("class", "highlight-blue")',
    
    # LAVENDER
    r'setStyleSheet\(f"color:\s*\{_t\.LAVENDER\};\s*font-weight:\s*bold;"\)': 
        'setProperty("class", "accent-label")',
    
    # Separator
    r'setStyleSheet\(f"background-color:\s*\{_t\.SURFACE1\};\s*border:\s*none;"\)': 
        'setProperty("class", "separator")',
    
    # SUBTEXT1 (only color)
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};"\)': 
        'setProperty("class", "subtext")',
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT1\};\s*font-size:\s*10px;"\)': 
        'setProperty("class", "subtext")',
    
    # OVERLAY0 (empty state labels)
    r'setStyleSheet\(f"color:\s*\{_t\.OVERLAY0\};\s*font-size:\s*14px;"\)': 
        'setProperty("class", "empty-label")',
    r'setStyleSheet\(f"color:\s*\{_t\.OVERLAY0\};\s*font-size:\s*14px;\s*background:\s*transparent;"\)': 
        'setProperty("class", "empty-label")',
    r'setStyleSheet\(f"color:\s*\{_t\.OVERLAY0\};\s*font-size:\s*14px;\s*background:\s*transparent;\s*border:\s*none;"\)': 
        'setProperty("class", "empty-label")',
    r'setStyleSheet\(f"color:\s*\{_theme\.OVERLAY0\};\s*font-size:\s*14px;"\)': 
        'setProperty("class", "empty-label")',
    
    # QFrame separator with SURFACE1 background
    r'setStyleSheet\(f"background-color:\s*\{_t\.SURFACE1\};"\)': 
        'setProperty("class", "separator")',
    r'setStyleSheet\(f"background-color:\s*\{_t\.SURFACE1\};\s*max-height:\s*1px;\s*margin:\s*0;"\)': 
        'setProperty("class", "separator")',
    
    # background-color BASE for gantt/test_plan
    r'setStyleSheet\(f"background-color:\s*\{_t\.BASE\};"\)': 
        'setProperty("class", "bg-base")',
    r'setStyleSheet\(f"background-color:\s*\{_t\.BASE\};\s*border:\s*1px\s*solid\s*\{_t\.SURFACE1\};\s*border-radius:\s*6px;"\)': 
        'setProperty("class", "bg-base")',
    r'setStyleSheet\(f"QWidget\s*\{\s*background-color:\s*\{_t\.BASE\};\s*\}\s*"\)': 
        'setProperty("class", "container-base")',
    
    # Count/subtle labels
    r'setStyleSheet\(f"color:\s*\{_t\.SUBTEXT0\};"\)': 
        'setProperty("class", "count-label")',
    
    # Text bold in dialogs
    r'setStyleSheet\(f"color:\s*\{_t\.TEXT\};\s*font-size:\s*13px;"\)': 
        'setProperty("class", "text-bold")',
    r'setStyleSheet\(f"color:\s*\{_t\.TEXT\};\s*font-size:\s*12px;\s*font-weight:\s*bold;"\)': 
        'setProperty("class", "text-bold")',
}

def _remove_dead_methods(src):
    """Remove `def _refresh_theme` / `def _refresh_theme_styles` methods (dead code)."""
    # Remove def _refresh_theme(self) -> None: ... up to next def or class
    src = re.sub(
        r'\n\s+def _refresh_theme_styles\(self\).*?(?=\n\s+def |\n\s+class |\n\S)',
        '',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'\n\s+def _refresh_theme\(self\).*?(?=\n\s+def |\n\s+class |\n\S)',
        '',
        src,
        flags=re.DOTALL,
    )
    return src

def migrate_file(filepath):
    with open(filepath) as f:
        src = f.read()
    
    for pattern, replacement in REPLACEMENTS.items():
        src = re.sub(pattern, replacement, src, flags=re.MULTILINE)
    
    src = _remove_dead_methods(src)
    
    with open(filepath, 'w') as f:
        f.write(src)
    
    # Syntax check
    import subprocess
    result = subprocess.run(['python3', '-m', 'py_compile', filepath], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  ✅ {filepath}")
    else:
        print(f"  ❌ {filepath}: {result.stderr[:200]}")

# Files to migrate
files = [
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/project_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/sample_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/equipment_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/technician_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/knowledge_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/widgets/analysis_widget.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/test_plan_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/issue_view.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/styles/toast.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/widgets/gantt_widget.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/widgets/result_matrix.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/widgets/task_table.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/attachment_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/backup_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/base_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/batch_import_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/holiday_manage_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/import_tasks_from_plan_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/schedule_config_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/schedule_preview_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/schedule_report_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/task_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/sample_select_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/test_result_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/plan_edit_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/issue_dialog.py",
    "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dialogs/export_dialog.py",
]

for f in files:
    migrate_file(f)

print("\nDone! Check failures above.")
