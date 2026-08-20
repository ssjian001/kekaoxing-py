"""回归测试：项目状态常量必须与 ProjectStatus Enum 一致，防止再漂移。

背景：PROJECT_STATUS_LABELS / PROJECT_STATUS_COLORS 曾含 completed/archived 两个
永不命中的 key，而 ProjectStatus Enum 只有 {active, paused, closed}。
删除后固化此一致性，任何一方再增加/减少都必须成对同步。
"""
import pytest

from src.constants import (
    PROJECT_STATUS_LABELS,
    PROJECT_STATUS_MAP,
    PROJECT_STATUS_OPTIONS,
    PROJECT_STATUS_REVERSE,
)
from src.models.project import ProjectStatus
from src.styles.constants import PROJECT_STATUS_COLORS


def _enum_values() -> set[str]:
    return {s.value for s in ProjectStatus}


def test_labels_keys_match_enum():
    """PROJECT_STATUS_LABELS 的 key 必须与 Enum 值完全一致（不多不少）。"""
    assert set(PROJECT_STATUS_LABELS.keys()) == _enum_values()


def test_colors_keys_match_enum():
    """PROJECT_STATUS_COLORS 的 key 必须与 Enum 值完全一致。"""
    assert set(PROJECT_STATUS_COLORS.keys()) == _enum_values()


def test_map_matches_enum():
    """PROJECT_STATUS_MAP 的 value 集合必须与 Enum 值完全一致。"""
    assert set(PROJECT_STATUS_MAP.values()) == _enum_values()


def test_reverse_is_exact_inverse_of_map():
    """PROJECT_STATUS_REVERSE = MAP 的精确反转。"""
    assert PROJECT_STATUS_REVERSE == {v: k for k, v in PROJECT_STATUS_MAP.items()}


def test_options_labels_map_bidirectional():
    """OPTIONS(显示文本) ↔ MAP(内部值) 双向闭环，且每个内部值都有中文显示。"""
    assert len(PROJECT_STATUS_OPTIONS) == len(PROJECT_STATUS_MAP)
    # 每个 option 文本都能映射到 Enum 内值
    for label in PROJECT_STATUS_OPTIONS:
        assert PROJECT_STATUS_MAP[label] in _enum_values()
    # 每个 Enum 值在 OPTIONS 中都有对应显示文本
    display_values = {PROJECT_STATUS_MAP[l] for l in PROJECT_STATUS_OPTIONS}
    assert display_values == _enum_values()


def test_status_model_defensive_warn_on_unknown(recwarn):
    """Project 对未知状态只 warn 不 raise（消费端 .get 有默认值兜底）。"""
    from src.models.project import Project

    Project(name="x", status="completed")
    assert any("Unknown Project.status" in str(w.message) for w in recwarn)
