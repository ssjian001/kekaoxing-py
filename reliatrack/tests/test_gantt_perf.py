"""甘特图性能基准测试 — 测量 paintEvent + hit_test 在不同任务数量下的耗时。

运行: .venv/bin/python -m pytest tests/test_gantt_perf.py -v -s --tb=short
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from datetime import date, timedelta
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPaintEvent
from PySide6.QtCore import QPoint, QRect

from src.models.test_plan import TestTask
from src.views.widgets.gantt_widget import _GanttWidget


app = QApplication.instance() or QApplication([])


def _make_tasks(n: int) -> list[TestTask]:
    """生成 n 个测试任务。"""
    tasks = []
    for i in range(n):
        tasks.append(TestTask(
            id=i + 1,
            plan_id=1,
            name=f"Task-{i:04d} — 可靠性测试项目",
            category="环境试验" if i % 3 == 0 else "机械试验",
            start_day=i * 2,
            duration=5 + (i % 10),
            progress=min(i * 5 % 100, 100),
            status="pending" if i % 2 == 0 else "in_progress",
            equipment_id=(i % 5) + 1,
        ))
    return tasks


def _benchmark_paint(widget: _GanttWidget, iterations: int = 20) -> float:
    """测量 paintEvent 平均耗时 (ms)。"""
    # 强制 layout 计算
    widget.resize(1200, 800)

    times = []
    for _ in range(iterations):
        ev = QPaintEvent(QRect(0, 0, 1200, 800))
        t0 = time.perf_counter()
        widget.paintEvent(ev)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    times.sort()
    # 去掉最高和最低，取中位数
    return times[len(times) // 2]


def _benchmark_hit_test(widget: _GanttWidget, iterations: int = 200) -> float:
    """测量 _hit_test 平均耗时 (μs)。"""
    times = []
    for i in range(iterations):
        # 模拟鼠标在不同位置移动
        x = 300 + (i * 7) % 800
        y = 30 + (i * 11) % 600
        pos = QPoint(x, y)
        t0 = time.perf_counter()
        widget._hit_test(pos)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1_000_000)  # μs

    times.sort()
    return times[len(times) // 2]


def test_gantt_paint_perf():
    """测量不同任务数量下 paintEvent 耗时。"""
    print("\n" + "=" * 60)
    print("甘特图 paintEvent 性能基准")
    print("=" * 60)

    for n in [10, 50, 100, 200, 500]:
        widget = _GanttWidget()
        widget.set_tasks(
            _make_tasks(n),
            total_days=90,
            start_date=date.today().isoformat(),
            equipment_map={eid: f"设备-{eid}" for eid in range(1, 6)},
        )
        ms = _benchmark_paint(widget, iterations=20)
        status = "✅" if ms < 16 else "⚠️" if ms < 33 else "🔴"
        print(f"  {status} {n:4d} tasks → {ms:7.2f} ms/frame ({1000/ms:.0f} FPS)")
        widget.deleteLater()

    print()


def test_gantt_hit_test_perf():
    """测量不同任务数量下 _hit_test 耗时。"""
    print("\n" + "=" * 60)
    print("甘特图 _hit_test 性能基准")
    print("=" * 60)

    for n in [10, 50, 100, 200, 500]:
        widget = _GanttWidget()
        widget.set_tasks(
            _make_tasks(n),
            total_days=90,
            start_date=date.today().isoformat(),
            equipment_map={eid: f"设备-{eid}" for eid in range(1, 6)},
        )
        us = _benchmark_hit_test(widget, iterations=200)
        status = "✅" if us < 100 else "⚠️" if us < 500 else "🔴"
        print(f"  {status} {n:4d} tasks → {us:7.1f} μs/call")
        widget.deleteLater()

    print()


if __name__ == "__main__":
    test_gantt_paint_perf()
    test_gantt_hit_test_perf()
