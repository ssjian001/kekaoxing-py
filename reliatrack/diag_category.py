# -*- coding: utf-8 -*-
"""诊断:双击类别列就地编辑在哪一环断掉(分层 + 定时器间隔等待)。
用法: cd reliatrack 目录后,用启动 main.py 的同一个 python 运行本文件:
    python diag_category.py
所有结果打印到控制台,跑完自动退出,把完整输出发回。
"""
import os, sys, sqlite3, traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt, QEvent, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

print("=" * 60, flush=True)
print("Python:", sys.version.split()[0], "| PySide6:", end=" ", flush=True)
import PySide6; print(PySide6.__version__)
print("CWD:", os.getcwd())
try:
    import subprocess
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, timeout=10).stdout.strip()
    print("Git HEAD:", head or "(unknown)")
except Exception:
    print("Git HEAD: 无 .git(zip 解压版) → 无法自动确认版本,请对照代码!")
print("=" * 60, flush=True)

app = QApplication(sys.argv)
from src.styles.theme import apply_palette, get_stylesheet, set_theme
set_theme('light'); apply_palette(); app.setStyleSheet(get_stylesheet())

from src.controllers import AppController
controller = AppController('data/reliatrack.db')
controller.initialize()
from main import MainWindow
window = MainWindow(controller)
window.resize(1280, 800)
window.show()

tv = window._test_plan_view
tb = tv._task_table

state = {"tid": None, "orig": None, "conn": None}


def db_cat():
    return state["conn"].execute(
        "SELECT category FROM test_tasks WHERE id=?", (state["tid"],)).fetchone()[0]


def cell_text():
    it = tb.item(0, 2)
    return it.text() if it else "(无item)"


def find_ph():
    for attr in dir(window):
        v = getattr(window, attr, None)
        if v.__class__.__name__ == 'PlanHandlers':
            return v
    return None


def step_a():
    """A: handler 层直接写"""
    try:
        conn = state["conn"] = sqlite3.connect('data/reliatrack.db')
        window._tab_widget.setCurrentIndex(3)
        app.processEvents()
        task = tb.get_task_at_row(0)
        if not task or task.id is None:
            print("!! 表格无任务,无法诊断"); app.quit(); return
        state["tid"] = task.id
        state["orig"] = db_cat()
        print(f"目标 id={task.id} {task.name!r} category={state['orig']!r}")
        print("回调注入:", tb._batch_value_callback is not None)
        print("\n[A] 直接调 _on_batch_value 写 '包装'", flush=True)
        h = find_ph()
        h._on_batch_value([task.id], 2, "包装")
        app.processEvents()
        v = db_cat()
        print(f"    DB={v!r} → {'✅A通过' if v == '包装' else '❌A断:handler/服务/undo写库失败'}", flush=True)
    except Exception:
        print("    ❌A异常:"); traceback.print_exc()
    QTimer.singleShot(100, step_b)


def step_b():
    """B: 就地编辑器 + activated.emit(程序级,验证编辑器信号/commit)"""
    try:
        print("\n[B] _edit_inline_category + 选值 + activated.emit", flush=True)
        conn = state["conn"]
        conn.execute("UPDATE test_tasks SET category=? WHERE id=?", (state["orig"], state["tid"]))
        conn.commit()
        controller.notify_data_changed('task')
        app.processEvents()
        task = tb.get_task_at_row(0)
        tb._edit_inline_category(0, task)
        app.processEvents()
        combo = tb.cellWidget(0, 2)
        if combo is None:
            print("    ❌B断: combo 未创建", flush=True)
        else:
            tgt = '机械试验' if task.category != '机械试验' else '表面处理'
            combo.setCurrentIndex(combo.findText(tgt))
            combo.activated.emit(combo.currentIndex())
            app.processEvents()
            v = db_cat()
            print(f"    目标={tgt!r} DB={v!r} → {'✅B通过' if v == tgt else '❌B断:编辑器commit失败'}", flush=True)
    except Exception:
        print("    ❌B异常:"); traceback.print_exc()
    QTimer.singleShot(600, step_d)   # 等 100ms 防抖刷新走完


def step_d():
    """D: 显示层 — B 之后 DB vs 表格文本"""
    try:
        v = db_cat()
        shown = cell_text()
        print(f"[D] 600ms后: DB={v!r} 表格={shown!r} → "
              f"{'✅显示已刷新' if shown == v else '❌D断:DB已改但表格没刷新!(用户看到的「无效」其实是显示残留)'}",
              flush=True)
    except Exception:
        print("    ❌D异常:"); traceback.print_exc()
    QTimer.singleShot(100, step_e)


def step_e():
    """E: 真实双击分派(press→dblclick)→ combo 是否创建"""
    try:
        print("\n[E] 真实鼠标双击类别单元格", flush=True)
        if tb.cellWidget(0, 2) is not None:
            tb.removeCellWidget(0, 2); app.processEvents()
        hits = []
        tb.cellDoubleClicked.connect(lambda r, c: hits.append((r, c)))
        rect = tb.visualItemRect(tb.item(0, 2)); c = rect.center()
        vp = tb.viewport()
        QTest.mouseClick(vp, Qt.MouseButton.LeftButton, pos=c)
        app.processEvents()
        ev = QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(c), QPointF(c),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(vp, ev)
        app.processEvents()
        combo = tb.cellWidget(0, 2)
        print(f"    cellDoubleClicked={hits or '未触发'} combo={'已创建' if combo else '未创建'}", flush=True)
        if hits and combo is not None:
            print("    ✅E通过", flush=True)
            QTimer.singleShot(300, step_f)  # 等 popup 稳定
        else:
            print("    ❌E断: 双击分派失败", flush=True)
            QTimer.singleShot(200, finish)
    except Exception:
        print("    ❌E异常:"); traceback.print_exc()
        QTimer.singleShot(200, finish)


def step_f():
    """F: 真实点击 popup 选项(最接近用户操作)→ 等 800ms → DB + 显示"""
    try:
        print("\n[F] QTest 点击 popup 选项(模拟用户选值)", flush=True)
        combo = tb.cellWidget(0, 2)
        cur = combo.currentText()
        tgt = '表面处理' if cur != '表面处理' else '工艺试验'
        idx = combo.findText(tgt)
        print(f"    当前={cur!r} 点击目标={tgt!r}(idx={idx})", flush=True)
        view = combo.view(); model = view.model()
        rect = view.visualRect(model.index(idx, 0))
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        app.processEvents()
        QTest.qWait(800)
        app.processEvents()
        v = db_cat()
        shown = cell_text()
        print(f"    DB={v!r} 表格={shown!r}", flush=True)
        if v == tgt and shown == tgt:
            print("    ✅F通过(全链路正常)", flush=True)
        elif v == tgt:
            print("    ❌F断: DB已写但表格没刷新 → 显示层问题", flush=True)
        else:
            print("    ❌F断: DB没写 → 真实点击路径 commit 失败(焦点/信号时序问题)", flush=True)
    except Exception:
        print("    ❌F异常:"); traceback.print_exc()
    QTimer.singleShot(200, finish)


def finish():
    try:
        state["conn"].execute("UPDATE test_tasks SET category=? WHERE id=?",
                              (state["orig"], state["tid"]))
        state["conn"].commit(); state["conn"].close()
    except Exception:
        pass
    print("\n诊断完成,自动退出。请把以上全部输出发回。", flush=True)
    app.quit()


QTimer.singleShot(1500, step_a)
QTimer.singleShot(90000, app.quit)  # 90s 兜底
app.exec()
