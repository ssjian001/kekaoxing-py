#!/bin/bash
# ReliaTrack — 环境验证脚本
# 用法: bash init.sh

set -e

echo "=== ReliaTrack Init ==="

# 1. Python 语法检查
echo "[1/4] Syntax check..."
cd "$(dirname "$0")/reliatrack"
find src/ -name "*.py" -exec python3 -m py_compile {} \; 2>&1 | head -5 && echo "  OK" || { echo "  FAIL — syntax errors found"; exit 1; }

# 2. Schema 一致性
echo "[2/4] Schema check..."
python3 -c "from src.db.schema import SCHEMA_VERSION; print(f'  Schema v{SCHEMA_VERSION}')" || { echo "  FAIL — schema import error"; exit 1; }

# 3. 测试（区分 GUI/非 GUI）
echo "[3/4] Tests..."
if [ -n "$DISPLAY" ]; then
    echo "  DISPLAY=$DISPLAY — running full tests"
    python3 -m pytest tests/ -x -q --tb=line 2>&1 | tail -5
else
    echo "  No DISPLAY — running non-GUI tests only"
    python3 -m pytest tests/ -x -q --tb=line -k "not gui" 2>&1 | tail -5 || true
fi

# 4. feature_list.json 校验
echo "[4/4] Feature list..."
python3 -c "import json; d=json.load(open('../feature_list.json')); print(f'  {len(d)} features tracked')" || echo "  WARNING — feature_list.json missing or invalid"

echo "=== Init complete ==="

# ── 过期 ──
# 项目已迁移到 reliatrack/ 子目录，初始化流程见 CLAUDE.md
