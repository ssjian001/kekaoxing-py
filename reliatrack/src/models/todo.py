"""待办事项实体模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TodoItem:
    """待办事项。"""
    id: Optional[int] = None
    project_id: Optional[int] = None
    title: str = ""
    description: str = ""
    priority: str = "medium"        # high / medium / low
    status: str = "pending"         # pending / in_progress / done
    category: str = ""
    due_date: str = ""
    remind_at: str = ""
    reminded: bool = False
    quadrant: int = 0
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def priority_label(self) -> str:
        return {"high": "高", "medium": "中", "low": "低"}.get(self.priority, self.priority)

    @property
    def status_label(self) -> str:
        return {"pending": "待处理", "in_progress": "进行中", "done": "已完成"}.get(self.status, self.status)

    @property
    def quadrant_label(self) -> str:
        return {1: "重要紧急", 2: "重要不紧急", 3: "不重要紧急", 4: "不重要不紧急"}.get(self.quadrant, "未分类")
