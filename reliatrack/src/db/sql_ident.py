"""SQL 标识符安全引用。

表名/列名来源包括 PRAGMA 自省 — 当应用打开外部构造或损坏的 .db 文件时
这些标识符不可信，直接 f-string 内插可被含 `]` 的列名越狱注入 SQL 结构。
统一经 quote_ident() 白名单校验后再引用，从源头杜绝该向量。
"""
from __future__ import annotations

import re

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_safe_ident(name: str) -> bool:
    """判断是否为常规 SQL 标识符（字母/下划线开头，仅字母数字下划线）。"""
    return bool(_IDENT_RE.match(str(name)))


def quote_ident(name: str) -> str:
    """校验并以方括号引用 SQL 标识符，非法标识符直接抛错。"""
    if not is_safe_ident(name):
        raise ValueError(f"非法 SQL 标识符: {name!r}")
    return f"[{name}]"
