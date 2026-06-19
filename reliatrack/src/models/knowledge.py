"""知识库实体模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class KnowledgeEntry:
    """知识库条目。"""
    id: Optional[int] = None
    category: str = ""              # 类别
    title: str = ""                 # 标题
    failure_mode: str = ""          # 失效模式
    cause_analysis: str = ""        # 原因分析
    improvement: str = ""           # 改进措施
    reference_standard: str = ""    # 参考标准
    keywords: str = ""              # 关键词（DB 存 JSON 数组字符串如 '[]'，UI 按逗号分隔文本处理）
    summary: str = ""               # 摘要
    root_cause: str = ""            # 根因（旧字段，兼容）
    resolution: str = ""            # 解决方案（旧字段，兼容）
    related_issues: str = ""        # 关联 Issue
    created_at: str = ""

    def __post_init__(self):
        # 防御性验证：不 raise
        if self.category is None:
            self.category = ""
        if not self.title:
            import warnings
            warnings.warn("KnowledgeEntry.title is empty")
