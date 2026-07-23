"""空数据占位控件 (Empty State Widget) — Fluent SaaS 风格空状态。

当表格/看板/列表无数据时显示统一的图标、标题、说明文案及可选快捷操作按钮。
"""

from __future__ import annotations

from typing import Callable
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import src.styles.theme as _t
from src.styles.icon import RI_ADD, RI_FOLDER, RI_SEARCH


class EmptyStateWidget(QFrame):
    """SaaS 风格优雅空状态占位控件。"""

    def __init__(
        self,
        title: str = "暂无数据",
        description: str = "没有找到相关记录，您可以尝试调整筛选条件或添加新数据",
        icon: QIcon | str | None = None,
        action_text: str | None = None,
        action_callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("emptyStateWidget")
        self.setStyleSheet("""
            QFrame#emptyStateWidget {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(12)

        # 1. 图标容器
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if isinstance(icon, QIcon) and not icon.isNull():
            pixmap = icon.pixmap(QSize(48, 48))
            self.icon_label.setPixmap(pixmap)
        else:
            # 默认 SVG 文件夹图标
            self.icon_label.setPixmap(RI_FOLDER.icon().pixmap(QSize(48, 48)))

        layout.addWidget(self.icon_label)

        # 2. 标题
        self.title_label = QLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {_t.FG_PRIMARY};
                font-size: 14px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.title_label)

        # 3. 描述
        if description:
            self.desc_label = QLabel(description, self)
            self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.desc_label.setWordWrap(True)
            self.desc_label.setStyleSheet(f"""
                QLabel {{
                    color: {_t.FG_SECONDARY};
                    font-size: 12px;
                }}
            """)
            layout.addWidget(self.desc_label)

        # 4. 可选操作按钮
        if action_text and action_callback:
            self.action_btn = QPushButton(action_text, self)
            self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_btn.setIcon(RI_ADD.icon())
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {_t.BLUE};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 16px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {_t.BLUE_HOVER if hasattr(_t, 'BLUE_HOVER') else _t.BLUE};
                }}
            """)
            self.action_btn.clicked.connect(action_callback)
            
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(self.action_btn)
            layout.addLayout(btn_layout)

    def set_content(self, title: str, description: str = ""):
        """动态更新标题与描述。"""
        self.title_label.setText(title)
        if hasattr(self, "desc_label") and self.desc_label:
            self.desc_label.setText(description)
