"""QTableWidget 行高亮 Delegate — hover/pressed/selected 三態 + 左側指示器。

移植自 qfluentwidgets TableItemDelegate，適配 PySide6 + Catppuccin 色板。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

import src.styles.theme as _t


class RowHighlightDelegate(QStyledItemDelegate):
    """自繪行背景高亮 Delegate。

    支持 hover/pressed/selected 三態，圓角行背景，左側指示色條。
    替代 QSS 的 ::item:selected 和 setAlternatingRowColors。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hover_row = -1
        self.pressed_row = -1
        self.selected_rows: set[int] = set()
        self.margin = 2          # 行間垂直間距
        self.indicator_width = 3  # 左側指示條寬度

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        row = index.row()
        col = index.column()
        rect = option.rect.adjusted(0, self.margin, 0, -self.margin)
        last_col = index.model().columnCount() - 1 if index.model() else 0
        is_dark = _t.current_theme() == "dark"
        r = 6  # 圓角半徑

        # ── 判斷狀態，計算背景色 alpha ──
        is_hover = self.hover_row == row
        is_pressed = self.pressed_row == row
        is_selected = row in self.selected_rows

        if is_selected:
            if is_pressed:      alpha = 15 if is_dark else 9
            elif is_hover:      alpha = 25
            else:               alpha = 17
        else:
            if is_pressed:      alpha = 9 if is_dark else 6
            elif is_hover:      alpha = 12
            else:               alpha = 0

        # ── 繪製背景 ──
        if alpha > 0:
            c = 255 if is_dark else 0
            painter.setBrush(QColor(c, c, c, alpha))
            if col == 0:
                bg_rect = rect.adjusted(4, 0, r + 1, 0)
            elif col == last_col:
                bg_rect = rect.adjusted(-r - 1, 0, -4, 0)
            else:
                bg_rect = rect.adjusted(-1, 0, 1, 0)
            painter.drawRoundedRect(bg_rect, r, r)

        # ── 左側指示條（選中行） ──
        if is_selected and col == 0:
            ph = int(round(0.35 * rect.height() if is_pressed else 0.257 * rect.height()))
            indicator_color = _t.ACCENT
            painter.setBrush(QColor(indicator_color))
            painter.drawRoundedRect(
                4, rect.y() + ph,
                self.indicator_width, rect.height() - 2 * ph,
                1.5, 1.5
            )

        painter.restore()

        # 讓 Qt 繼續繪製文字/圖標
        super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        return None  # 不啟用就地編輯（彈窗編輯）

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(size.height() + self.margin * 2)
        return size
