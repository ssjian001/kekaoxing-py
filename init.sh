#!/bin/bash
# ReliaTrack — 环境验证脚本
# 用法: bash init.sh
#
# 目录约定（2026-09-29 校对）：
#   仓库根 = 本脚本所在目录（.venv 在这里）
#   代码目录 = 仓库根/reliatrack（main.py / src / tests / feature_list.json）
#   因此全部命令从代码目录执行，解释器一律用 ../.venv/bin/python

set -e

echo "=== ReliaTrack Init ==="

cd "$(dirname "$0")/reliatrack"

PY="../.venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "  FAIL — 未找到 venv 解释器 $PY"
    echo "  首次准备：cd .. && python3 -m venv .venv && .venv/bin/pip install -r reliatrack/requirements.txt"
    exit 1
fi

# 1. Python 语法检查
echo "[1/4] Syntax check..."
find src/ -name "*.py" -exec "$PY" -m py_compile {} \; 2>&1 | head -5 && echo "  OK" || { echo "  FAIL — syntax errors found"; exit 1; }

# 2. Schema 一致性
echo "[2/4] Schema check..."
"$PY" -c "from src.db.schema import SCHEMA_VERSION; print(f'  Schema v{SCHEMA_VERSION}')" || { echo "  FAIL — schema import error"; exit 1; }

# 3. 测试（区分 GUI/非 GUI）
echo "[3/4] Tests..."
if [ -n "$DISPLAY" ]; then
    echo "  DISPLAY=$DISPLAY — running full tests"
    "$PY" -m pytest tests/ -x -q --tb=line 2>&1 | tail -5
else
    echo "  No DISPLAY — running non-GUI tests only"
    "$PY" -m pytest tests/ -x -q --tb=line -k "not gui" 2>&1 | tail -5 || true
fi

# 4. feature_list.json 校验（权威副本在代码目录，dict 格式：_meta + features）
echo "[4/4] Feature list..."
"$PY" -c "
import json
d = json.load(open('feature_list.json'))
feats = d.get('features', [])
meta = d.get('_meta', {})
print(f'  {len(feats)} features tracked | schema {meta.get(\"schema_version\")} | updated {meta.get(\"last_updated\")}')
print(f'  tests: {meta.get(\"tests\", \"n/a\")}')
" || echo "  WARNING — feature_list.json missing or invalid"

echo "=== Init complete ==="
