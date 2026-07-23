"""全局待办信号（避免循环 import）。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _GlobalSignals(QObject):
    edit_requested = Signal(int)

_global_signals = _GlobalSignals()
