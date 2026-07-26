"""样品流转生命周期履历树弹窗 (Sample Lifecycle Timeline Dialog)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
)

import src.styles.theme as _theme
from src.styles.constants import (
    add_shadow,
    DASH_PRIMARY,
    DASH_SUCCESS,
    DASH_WARNING,
    DASH_DANGER,
    FONT_FAMILY,
)
from src.models.sample import Sample



class SampleLifecycleTimelineDialog(QDialog):
    """样品从入库、测试到归档的全生命周期履历弹窗。"""

    def __init__(self, sample: Sample, parent: QWidget | None = None):
        super().__init__(parent)
        self._sample = sample
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(620, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("lifecycle-container")
        container.setStyleSheet(
            f"QFrame#lifecycle-container {{"
            f"  background: {_theme.BASE};"
            f"  border: 1px solid {_theme.SURFACE1};"
            f"  border-radius: 12px;"
            f"}}"
        )
        add_shadow(container)

        clay = QVBoxLayout(container)
        clay.setContentsMargins(20, 16, 20, 16)
        clay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(f"📜 样品全生命周期履历 — S/N: {self._sample.sn}")
        title.setStyleSheet(f"color: {_theme.TEXT}; font-size: 15px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        btn_close = QPushButton("✖ 关闭", self)
        btn_close.setStyleSheet(
            f"background: {_theme.SURFACE0}; color: {_theme.TEXT}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 12px;"
        )
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        clay.addLayout(header)

        # 详细元数据
        info_card = QFrame()
        info_card.setStyleSheet(f"background: {_theme.SURFACE0}; border-radius: 8px; padding: 8px;")
        ilay = QHBoxLayout(info_card)
        ilay.setContentsMargins(12, 6, 12, 6)
        ilay.setSpacing(16)

        m1 = QLabel(f"规格型号: {self._sample.spec or '未录入'}")

        m2 = QLabel(f"批次: {self._sample.batch_no or '标准批次'}")
        m3 = QLabel(f"当前状态: {self._sample.status}")
        for m in (m1, m2, m3):
            m.setStyleSheet(f"color: {_theme.TEXT}; font-size: 12px;")
            ilay.addWidget(m)
        ilay.addStretch()
        clay.addWidget(info_card)

        # 垂直时间轴滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        timeline_content = _TimelineWidget(self._sample)
        scroll.setWidget(timeline_content)
        clay.addWidget(scroll, 1)

        root.addWidget(container)

    def show_centered(self) -> None:
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, max(y, 100))
        self.exec()


class _TimelineWidget(QWidget):
    """时间轴主渲染区。"""

    def __init__(self, sample: Sample, parent: QWidget | None = None):
        super().__init__(parent)
        self._sample = sample
        self.setMinimumHeight(320)

        # 模拟/真实履历节点
        self._events = [
            ("📦 1. 样品入库与登记", "2026-07-01 09:30", "样品完成物理外显检查并分配唯一的 S/N 编号登记入库。", DASH_SUCCESS),
            ("🔬 2. 高低温循环试验", "2026-07-05 14:00", "投入环境试验箱，执行 -40℃ ~ 85℃ 步进温度循环试验 (工期 5 天)。", DASH_PRIMARY),
            ("📉 3. 机械跌落与冲击测试", "2026-07-12 10:15", "完成 1.2m 自由落体冲击测试，检测六面防跌落性能。", DASH_PRIMARY),
            ("🔍 4. FA 失效剖析与检测", "2026-07-18 16:20", "显微镜下未见焊点剥离与壳体开裂，各项功能性指标正常通过。", DASH_SUCCESS),
            ("✅ 5. 试验结案与归档入库", "2026-07-22 11:00", "样品完成测试任务，转入样品库归档保管。", DASH_PRIMARY),
        ]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(14)

        for title, time_str, desc, color in self._events:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{"
                f"  background: {_theme.SURFACE0};"
                f"  border-left: 4px solid {color};"
                f"  border-radius: 6px;"
                f"  padding: 8px 12px;"
                f"}}"
            )
            vlay = QVBoxLayout(card)
            vlay.setContentsMargins(10, 6, 10, 6)
            vlay.setSpacing(4)

            hlay = QHBoxLayout()
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet(f"color: {_theme.TEXT}; font-size: 13px; font-weight: bold;")
            hlay.addWidget(lbl_t)

            hlay.addStretch()

            lbl_time = QLabel(time_str)
            lbl_time.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 11px;")
            hlay.addWidget(lbl_time)
            vlay.addLayout(hlay)

            lbl_d = QLabel(desc)
            lbl_d.setWordWrap(True)
            lbl_d.setStyleSheet(f"color: {_theme.SUBTEXT0}; font-size: 12px;")
            vlay.addWidget(lbl_d)

            lay.addWidget(card)
