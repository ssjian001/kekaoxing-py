"""样品管理视图 — 三个子 Tab。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from src.styles.constants import VIEW_MARGINS
from src.views.widgets.segmented_widget import SegmentedWidget
from src.views.widgets.sample_pool_tab import _SamplePoolTab
from src.views.widgets.sample_usage_tab import _SampleUsageTab
from src.views.widgets.sample_ledger_tab import _SampleLedgerTab
from src.models.sample import Sample


class SampleView(QWidget):
    """样品管理视图 — 三个子 Tab。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*VIEW_MARGINS)

        self._segmented = SegmentedWidget()

        self._stack = QStackedWidget()
        self._pool_tab = _SamplePoolTab()
        self._ledger_tab = _SampleLedgerTab()
        self._usage_tab = _SampleUsageTab()

        self._stack.addWidget(self._pool_tab)
        self._stack.addWidget(self._ledger_tab)
        self._stack.addWidget(self._usage_tab)

        self._segmented.addSegment("样品池", self._pool_tab)
        self._segmented.addSegment("样品台账", self._ledger_tab)
        self._segmented.addSegment("出入库记录", self._usage_tab)
        self._segmented.setStackedWidget(self._stack)
        self._segmented.setCurrentIndex(0)

        layout.addWidget(self._segmented)
        layout.addWidget(self._stack)

    def refresh_pool(self, samples: list[Sample]) -> None:
        self._pool_tab.refresh(samples)

    def refresh_ledger(self, samples: list[Sample]) -> None:
        self._ledger_tab.refresh(samples)

    def refresh_usage(self, data: list[dict]) -> None:
        self._usage_tab.refresh(data)

    @property
    def pool_tab(self) -> _SamplePoolTab:
        return self._pool_tab

    @property
    def ledger_tab(self) -> _SampleLedgerTab:
        return self._ledger_tab

    @property
    def usage_tab(self) -> _SampleUsageTab:
        return self._usage_tab
