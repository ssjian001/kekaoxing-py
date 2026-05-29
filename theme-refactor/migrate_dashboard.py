"""迁移 dashboard_view.py：内联样式 → QSS 类选择器"""
import re

path = "/home/zouxp/Desktop/AI/xiangmu/kekaoxing-py/reliatrack/src/views/dashboard_view.py"
with open(path) as f:
    src = f.read()

# 1. Delete all theme_changed.connect lines
src = re.sub(
    r'^\s+_theme\.theme_host\.theme_changed\.connect\(self\.[^)]+\)\s*\n',
    '',
    src,
    flags=re.MULTILINE,
)

# 2. Multi-line setStyleSheet for SUBTEXT0 + 12px + 500 weight → subtext
src = re.sub(
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*12px;\s*font-weight:\s*500;"\s*\n\s*\)',
    'setProperty("class", "subtext")',
    src,
)

# 3. Multi-line setStyleSheet for TEXT + 13px + bold → panel-header
src = re.sub(
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_theme\.TEXT\};\s*font-size:\s*13px;\s*font-weight:\s*bold;"\s*\n\s*\)',
    'setProperty("class", "panel-header")',
    src,
)

# 4. SUBTEXT0 + 11px + border none + background transparent → hint-label
src = re.sub(
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*11px;\s*border:\s*none;\s*background:\s*transparent;"\s*\n\s*\)',
    'setProperty("class", "hint-label")',
    src,
)

# 5. SUBTEXT0 + 10px → hint-label  
src = re.sub(
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*10px;\s*border:\s*none;\s*background:\s*transparent;"\s*\n\s*\)',
    'setProperty("class", "hint-label")',
    src,
)

# 6. QScrollArea with background-color BASE + border none → scroll-base
src = re.sub(
    r'setStyleSheet\(\s*\n\s*f"QScrollArea\s*\{\s*background-color:\s*\{_theme\.BASE\};\s*border:\s*none;\s*\}"\s*\n\s*\)',
    'setProperty("class", "scroll-base")',
    src,
)

# 7. QWidget/QFrame with background-color BASE → bg-base
src = re.sub(
    r'setStyleSheet\(\s*\n?\s*f"background-color:\s*\{_theme\.BASE\};"\s*\n?\s*\)',
    'setProperty("class", "bg-base")',
    src,
)

# 8. Container/widget with MANTLE + SURFACE1 border → filter-chip
src = re.sub(
    r'setStyleSheet\(\s*\n\s*f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*12px;\s*font-weight:\s*500;\s*\n\s*f"background-color:\s*\{_theme\.MANTLE\};\s*border:\s*1px\s*solid\s*\{_theme\.SURFACE1\};"\s*\n\s*\)',
    'setProperty("class", "filter-chip")',
    src,
)

# 9. Single-line color: TEXT + size + weight → various
src = re.sub(
    r'setStyleSheet\(f"color:\s*\{_theme\.TEXT\};\s*font-size:\s*13px;\s*font-weight:\s*bold;"\)',
    'setProperty("class", "panel-header")',
    src,
)

# 10. SUBTEXT0 single-line variants
src = re.sub(
    r'setStyleSheet\(f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*12px;\s*font-weight:\s*500;"\)',
    'setProperty("class", "subtext")',
    src,
)

# 11. Time label: SUBTEXT0 + 11px
src = re.sub(
    r'setStyleSheet\(f"color:\s*\{_theme\.SUBTEXT0\};\s*font-size:\s*11px;"\)',
    'setProperty("class", "subtext")',
    src,
)

# Write back
with open(path, 'w') as f:
    f.write(src)

print("dashboard_view.py migrated successfully")
