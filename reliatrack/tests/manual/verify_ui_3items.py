"""UI 实测三项验证脚本（2026-10-06）。

1. 甘特图 Ctrl+滚轮缩放（普通滚轮不再被劫持）
2. 看板卡片拖拽期间看板刷新导致卡片被销毁 → isValid 守卫
3. 出库弹窗手输操作人按名字反查 + 校验拦截

运行：cd reliatrack && QT_QPA_PLATFORM=offscreen ../.venv/bin/python tests/manual/verify_ui_3items.py
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QMessageBox

PASS = "PASS"
FAIL = "FAIL"
_results: list[tuple[str, str, str]] = []


def record(ok: bool, name: str, detail: str = "") -> None:
    _results.append((PASS if ok else FAIL, name, detail))
    print(f"  {'✅' if ok else '❌'} [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def _wheel(widget, delta_y: int, ctrl: bool) -> QWheelEvent:
    mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    ev = QWheelEvent(
        QPointF(50, 50), QPointF(50, 50),
        QPoint(0, 0), QPoint(0, delta_y),
        Qt.MouseButton.NoButton, mods,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    widget.wheelEvent(ev)
    return ev


def test_gantt_zoom(app) -> None:
    print("\n[1] 甘特图 Ctrl+滚轮缩放")
    from src.views.widgets.gantt_widget import _GanttWidget

    g = _GanttWidget()
    w0 = g._day_w

    ev_plain = _wheel(g, 120, ctrl=False)
    ok1 = (g._day_w == w0) and not ev_plain.isAccepted()
    record(ok1, "普通滚轮不缩放且事件被忽略（交还父级滚动）", f"day_w {w0} -> {g._day_w}, accepted={ev_plain.isAccepted()}")

    ev_ctrl = _wheel(g, 120, ctrl=True)
    ok2 = g._day_w > w0 and ev_ctrl.isAccepted()
    record(ok2, "Ctrl+滚轮放大", f"day_w {w0} -> {g._day_w}")

    w1 = g._day_w
    ev_ctrl2 = _wheel(g, -120, ctrl=True)
    ok3 = g._day_w < w1 and ev_ctrl2.isAccepted()
    record(ok3, "Ctrl+滚轮缩小", f"day_w {w1} -> {g._day_w}")

    zooms: list[float] = []
    g.zoom_changed.connect(zooms.append)
    _wheel(g, 120, ctrl=True)
    ok4 = len(zooms) == 1 and abs(zooms[0] - g._day_w) < 1e-9
    record(ok4, "zoom_changed 信号携带新 day_w", f"got {zooms}")


def test_kanban_drag_guard(app) -> None:
    print("\n[2] 看板卡片拖拽后 isValid 守卫")
    from src.models.issue import Issue
    from src.views.widgets.kanban_card import _KanbanCard
    import src.views.widgets.kanban_card as kc_mod

    issue = Issue(id=1, title="测试 issue", status="open")
    card = _KanbanCard(issue)
    card.resize(180, 68)
    card.show()

    # 模拟“放下后看板全量刷新、卡片随之 deleteLater”
    def fake_exec(self, *args, **kwargs):
        card.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return 0

    orig_exec = kc_mod.QDrag.exec
    kc_mod.QDrag.exec = fake_exec
    try:
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication as QApp

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(10, 10),
                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        card.mousePressEvent(press)
        move = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(60, 60),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        try:
            card.mouseMoveEvent(move)
            from shiboken6 import isValid
            ok = not isValid(card)
            record(ok, "拖拽后卡片被销毁，isValid=False 且无 RuntimeError")
        except RuntimeError as exc:
            record(False, "拖拽后卡片被销毁", f"RuntimeError: {exc}")
    finally:
        kc_mod.QDrag.exec = orig_exec


def test_checkout_manual_operator(app) -> None:
    print("\n[3] 出库弹窗手输操作人")
    from src.models.common import Technician
    from src.models.sample import Sample
    from src.views.dialogs.sample_checkout_dialog import SampleCheckoutDialog

    techs = [Technician(id=7, name="张三"), Technician(id=9, name="李四")]
    sample = Sample(id=1, sn="SN-001", spec="PCB", status="in_stock")
    dlg = SampleCheckoutDialog(sample, technicians=techs, task_list=[])

    # 3a 手输名字反查 id
    dlg._operator_combo.setEditText("张三")
    data = dlg.get_data()
    record(data["operator_id"] == 7, "手输技术员名字反查到 id=7", f"got {data['operator_id']}")

    # 3b 下拉项 "id: name" 直接解析
    dlg._operator_combo.setEditText("9: 李四")
    data2 = dlg.get_data()
    record(data2["operator_id"] == 9, "下拉项格式 9: 李四 → id=9", f"got {data2['operator_id']}")

    # 3c 手输不存在的名字 → accept 拦截
    warnings: list[str] = []
    orig_warning = QMessageBox.warning
    QMessageBox.warning = staticmethod(lambda *a, **k: warnings.append(str(a[2]) if len(a) > 2 else ""))
    try:
        dlg._operator_combo.setEditText("王五")
        dlg._purpose_edit.setText("测试")
        dlg.accept()
        record(bool(warnings) and "未找到技术员" in warnings[-1] and dlg.result() == 0,
               "手输不存在的技术员 → WARNING 拦截", warnings[-1] if warnings else "无提示")

        # 3d 空操作人 → 必填拦截
        warnings.clear()
        dlg._operator_combo.setEditText("")
        dlg.accept()
        record(bool(warnings) and "操作人为必填项" in warnings[-1], "空操作人 → 必填拦截",
               warnings[-1] if warnings else "无提示")
    finally:
        QMessageBox.warning = orig_warning


def main() -> int:
    app = QApplication(sys.argv)
    test_gantt_zoom(app)
    test_kanban_drag_guard(app)
    test_checkout_manual_operator(app)
    failed = sum(1 for s, _, _ in _results if s == FAIL)
    print(f"\n合计: {len(_results) - failed}/{len(_results)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
