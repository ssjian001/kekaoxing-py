"""数据模型定义 - 对应原 TypeScript 类型"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Section(str, Enum):
    """内置默认分类，兼容旧数据。新增分类存入数据库 sections 表。"""
    ENV = "env"       # 环境测试
    MECH = "mech"     # 机械测试
    SURF = "surf"     # 表面/材料测试
    PACK = "pack"     # 包装测试


# ── 内置默认分类（数据库为空时的回退值）──
DEFAULT_SECTION_LABELS: dict[str, str] = {
    "env": "环境测试",
    "mech": "机械测试",
    "surf": "表面/材料测试",
    "pack": "包装测试",
}

DEFAULT_SECTION_COLORS: dict[str, str] = {
    "env": "#4FC3F7",
    "mech": "#81C784",
    "surf": "#FFB74D",
    "pack": "#BA68C8",
}

# 预设可用颜色（新建分类时轮换使用）
PRESET_COLORS = [
    "#4FC3F7", "#81C784", "#FFB74D", "#BA68C8",
    "#F06292", "#4DB6AC", "#FFD54F", "#7986CB",
    "#E57373", "#A1887F", "#90A4AE", "#AED581",
]


def get_section_label(section: Section | str, labels: dict[str, str] | None = None) -> str:
    """获取分类显示名称，优先从外部 labels 字典查询，回退到内置默认值。"""
    key = section.value if isinstance(section, Section) else section
    if labels and key in labels:
        return labels[key]
    return DEFAULT_SECTION_LABELS.get(key, key)


def get_section_color(section: Section | str, colors: dict[str, str] | None = None) -> str:
    """获取分类颜色，优先从外部 colors 字典查询，回退到内置默认值。"""
    key = section.value if isinstance(section, Section) else section
    if colors and key in colors:
        return colors[key]
    return DEFAULT_SECTION_COLORS.get(key, "#89b4fa")


# 保留旧名称兼容 import
SECTION_LABELS = DEFAULT_SECTION_LABELS
SECTION_COLORS = DEFAULT_SECTION_COLORS


class ResourceType(str, Enum):
    SAMPLE_POOL = "sample_pool"
    EQUIPMENT = "equipment"


class ScheduleMode(str, Enum):
    FASTEST = "fastest"
    BALANCED = "balanced"
    MINIMAL = "minimal"
    DEADLINE = "deadline"


@dataclass
class EquipmentRequirement:
    resource_id: int
    quantity: int = 1


@dataclass
class UnavailablePeriod:
    start_day: int
    end_day: int
    reason: str = ""


@dataclass
class Task:
    id: int
    num: str                          # "1.1", "2.3" 等
    name_en: str
    name_cn: str
    section: Section
    duration: int                     # 天数
    start_day: int = 0
    progress: float = 0.0             # 0~100
    priority: int = 3
    done: bool = False
    is_serial: bool = False
    serial_group: str = ""
    sample_pool: str = "product"
    sample_qty: int = 3
    setup_time: int = 0
    teardown_time: int = 0
    dependencies: list[str] = field(default_factory=list)
    requirements: list[EquipmentRequirement] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Resource:
    id: int
    name: str
    type: ResourceType
    category: str = ""
    unit: str = "台"
    available_qty: int = 1
    icon: str = "📦"
    description: str = ""
    unavailable_periods: list[UnavailablePeriod] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ScheduleConfig:
    mode: ScheduleMode = ScheduleMode.BALANCED
    skip_weekends: bool = False
    start_date: str = ""              # YYYY-MM-DD
    deadline: str = ""
    lock_existing: bool = False
    sample_pool_config: dict[str, int] = field(default_factory=dict)
    equipment_config: dict[int, int] = field(default_factory=dict)


@dataclass
class ScheduleOutput:
    total_days: int = 0
    parallel_peak: int = 0
    resource_conflicts: int = 0
    warnings: list[str] = field(default_factory=list)
