"""表格列宽持久化工具 — 基于 QSettings 保存/恢复列宽。"""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QHeaderView, QTableWidget


_SETTINGS_KEY_PREFIX = "ReliaTrack/column_widths/"


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
