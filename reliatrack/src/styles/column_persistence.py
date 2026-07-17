"""表格列宽持久化工具 — 基于 QSettings 保存/恢复列宽。"""

from __future__ import annotations

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget


_SETTINGS_KEY_PREFIX = "ReliaTrack/column_widths/"

# 全局 debounce timer — 每个 key 一个 timer
_debounce_timers: dict[str, tuple[QTimer, QTableWidget, str]] = {}


def save_column_widths(table: QTableWidget, key: str) -> None:
    """保存表格列宽到 QSettings。在 closeEvent 或 timer 中调用。

    Args:
        table: 需要保存列宽的 QTableWidget
        key: 唯一标识符，如 "task_table"、"sample_pool"
    """
    settings = QSettings()
    header = table.horizontalHeader()
    widths: list[int] = []
    for col in range(table.columnCount()):
        if header.sectionResizeMode(col) == QHeaderView.ResizeMode.Interactive:
            widths.append(table.columnWidth(col))
        else:
            widths.append(-1)  # 标记非 Interactive 列（Fixed/Stretch 等）
    settings.setValue(f"{_SETTINGS_KEY_PREFIX}{key}", widths)


def save_column_widths_debounced(table: QTableWidget, key: str) -> None:
    """debounce 版 — 300ms 内多次 sectionResized 只写一次。"""
    if key in _debounce_timers:
        timer, _, _ = _debounce_timers[key]
    else:
        timer = QTimer()
        timer.setSingleShot(True)
        _debounce_timers[key] = (timer, table, key)
        timer.timeout.connect(
            lambda: save_column_widths(_debounce_timers[key][1], key)
        )
    # 更新 table 引用（表格可能被重建）
    _debounce_timers[key] = (timer, table, key)
    timer.start(300)


def restore_column_widths(table: QTableWidget, key: str) -> None:
    """从 QSettings 恢复表格列宽。在数据填充后调用。

    只恢复 Interactive 模式的列，Fixed/Stretch 列保持原有设置。

    Args:
        table: 需要恢复列宽的 QTableWidget
        key: 与 save_column_widths 相同的标识符
    """
    settings = QSettings()
    widths = settings.value(f"{_SETTINGS_KEY_PREFIX}{key}")
    if not widths:
        return
    # QSettings 可能返回字符串列表
    if isinstance(widths, str):
        return
    try:
        int_widths = [int(w) for w in widths]
    except (ValueError, TypeError):
        return
    header = table.horizontalHeader()
    for col, w in enumerate(int_widths):
        if col >= table.columnCount():
            break
        if w > 0 and header.sectionResizeMode(col) == QHeaderView.ResizeMode.Interactive:
            table.setColumnWidth(col, w)


_SORT_KEY_PREFIX = "ReliaTrack/column_sort/"


def save_sort_state(table: QTableWidget, key: str) -> None:
    """保存表格排序状态（排序列索引 + 升/降序）到 QSettings。

    注意：PySide6 6.5+ 默认启用 scoped enum，Qt.SortOrder 不再是 int 子类。
    order.value 取整数值跨版本兼容。
    """
    header = table.horizontalHeader()
    col = header.sortIndicatorSection()
    order = header.sortIndicatorOrder()
    settings = QSettings()
    settings.setValue(f"{_SORT_KEY_PREFIX}{key}", [col, order.value])


def restore_sort_state(table: QTableWidget, key: str) -> None:
    """从 QSettings 恢复表格排序状态。需表格有数据时调用。"""
    settings = QSettings()
    raw = settings.value(f"{_SORT_KEY_PREFIX}{key}")
    if not raw or not isinstance(raw, list) or len(raw) < 2:
        return
    try:
        col, order = int(raw[0]), int(raw[1])
    except (ValueError, TypeError):
        return
    if 0 <= col < table.columnCount():
        table.sortItems(col, Qt.SortOrder(int(order)))
