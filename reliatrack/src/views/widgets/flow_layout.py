"""流式佈局 FlowLayout — 自動換行佈局。

移植自 qfluentwidgets FlowLayout，適配 PySide6。
容器寬度變化時自動將子控件換行。
"""
from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtWidgets import QLayout, QWidgetItem, QStyle


class FlowLayout(QLayout):
    """流式佈局 — 子控件超出容器寬度時自動換行。"""

    def __init__(self, parent=None, need_ani=False, is_tight=False):
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._need_ani = need_ani
        self._is_tight = is_tight
        self._h_spacing = 6
        self._v_spacing = 6

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self):
        if self._h_spacing >= 0:
            return self._h_spacing
        return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._v_spacing >= 0:
            return self._v_spacing
        return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, move: bool) -> int:
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        row_height = 0
        space_x = self.horizontalSpacing()
        space_y = self.verticalSpacing()

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + space_x
            if next_x - space_x > rect.right() - m.right() and row_height > 0:
                x = rect.x() + m.left()
                y = y + row_height + space_y
                row_height = 0

            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x = next_x
            row_height = max(row_height, hint.height())

        return y + row_height + m.bottom() - rect.y()

    def smartSpacing(self, pm):
        parent = self.parent()
        if parent is None:
            return -1
        if parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        return parent.spacing()
