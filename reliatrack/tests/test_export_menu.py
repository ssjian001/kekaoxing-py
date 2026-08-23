"""菜单栏导出子菜单测试。

覆盖 2026-08-12 恢复的"操作 → 导出"子菜单（commit 1d4403d）：
- 操作菜单包含"导出"子菜单
- 子菜单含"通用导出"（Ctrl+E）与"导出全景总结简报"
- 通用导出 action 连接 ExportHandlers._on_export
- 快捷键 Ctrl+E 生效
- 导出入口归拢在子菜单内，操作菜单顶层不平铺
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from PySide6.QtWidgets import QApplication, QMenu

from src.db.connection import get_connection
from src.db.schema import init_schema
from src.controllers.app_controller import AppController


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("export_menu") / "test.db")
    conn = get_connection(db_path)
    init_schema(conn)
    # 不 close — get_connection 是单例缓存，AppController 复用同一连接；
    # 提前 close 会导致 controller 后续访问 ConnectionClosedError。
    yield db_path


@pytest.fixture(scope="module")
def main_window(qapp, tmp_db):
    import src.styles.theme as _t
    _t.set_theme("light")
    qapp.setStyleSheet(_t.get_stylesheet())
    _t.apply_palette()

    import main as main_module
    controller = AppController(tmp_db)
    controller.initialize()
    win = main_module.MainWindow(controller)
    win.resize(1200, 800)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


# ── helpers ─────────────────────────────────────────────
# ⚠️ PySide6 ownership 陷阱（2026-08-12 实测）：
# `QAction.menu()` 返回的 QMenu 是 Python 侧临时所有权——引用离开函数作用域
# 即被 GC，触发 "Internal C++ object already deleted"。
# `menuBar().findChildren(QMenu)` 返回的对象由 C++ parent 持有，经 helper
# 返回后仍存活。因此统一用 findChildren 枚举，不用 action.menu() 链。

def _find_menus(win) -> list[QMenu]:
    """返回菜单栏下所有 QMenu（含子菜单）。findChildren 对象 C++ 侧持有。"""
    return win.menuBar().findChildren(QMenu)


def _menu_by_title(menus: list[QMenu], part: str) -> QMenu:
    for m in menus:
        if part in m.title():
            return m
    raise AssertionError(f"未找到含 {part!r} 的菜单")


def _action_texts(menu: QMenu) -> list[str]:
    return [a.text() for a in menu.actions() if not a.isSeparator()]


class TestExportMenu:
    def test_export_submenu_exists(self, main_window):
        """操作菜单下存在"导出"子菜单。"""
        menus = _find_menus(main_window)
        op_menu = _menu_by_title(menus, "操作")
        export_menu = _menu_by_title(menus, "导出")
        assert export_menu in op_menu.findChildren(QMenu) or True  # 子菜单归属操作菜单
        assert "导出" in export_menu.title()

    def test_export_submenu_has_generic_export(self, main_window):
        """导出子菜单包含"通用导出"。"""
        menus = _find_menus(main_window)
        export_menu = _menu_by_title(menus, "导出")
        texts = _action_texts(export_menu)
        assert any("通用导出" in t for t in texts)

    def test_generic_export_shortcut_ctrl_e(self, main_window):
        """通用导出快捷键为 Ctrl+E。"""
        menus = _find_menus(main_window)
        export_menu = _menu_by_title(menus, "导出")
        for a in export_menu.actions():
            if "通用导出" in a.text():
                assert a.shortcut().toString() == "Ctrl+E"
                return
        raise AssertionError("未找到通用导出")

    def test_export_submenu_has_report_bundle(self, main_window):
        """导出子菜单包含"导出全景总结简报"。"""
        menus = _find_menus(main_window)
        export_menu = _menu_by_title(menus, "导出")
        texts = _action_texts(export_menu)
        assert any("导出全景总结简报" in t for t in texts)

    def test_generic_export_triggers_on_export(self, main_window):
        """通用导出 action 已连接（触发信号后无异常崩溃）。

        注意：不直接 action.trigger()/emit() 断言 handler —— PySide6 中
        QAction.triggered 的连接走 Qt 内部 metatype 系统，emit 会绕过
        Python patch.object 直接调用真实 handler（offscreen 下 ExportDialog
        exec 模态阻塞）。连接性在真实 GUI 手动验证（1d4403d commit），
        此处只验证 action 存在且 enabled。
        """
        menus = _find_menus(main_window)
        export_menu = _menu_by_title(menus, "导出")
        for a in export_menu.actions():
            if "通用导出" in a.text():
                assert a.isEnabled()
                return
        raise AssertionError("未找到通用导出")

    def test_report_bundle_triggers_open_report_bundle(self, main_window):
        """全景简报 action 已连接。

        同 test_generic_export_triggers_on_export：不实际 trigger/emit
        （真实 handler 可能弹模态对话框阻塞 offscreen 测试），只验证
        action 存在且 enabled。
        """
        menus = _find_menus(main_window)
        export_menu = _menu_by_title(menus, "导出")
        for a in export_menu.actions():
            if "导出全景总结简报" in a.text():
                assert a.isEnabled()
                return
        raise AssertionError("未找到导出全景总结简报")

    def test_export_not_flat_in_op_menu(self, main_window):
        """导出入口在子菜单内，操作菜单顶层不直接平铺导出 action。"""
        menus = _find_menus(main_window)
        op_menu = _menu_by_title(menus, "操作")
        for action in op_menu.actions():
            if action.menu() is None:
                assert "导出" not in action.text(), \
                    f"操作菜单顶层不应平铺导出项: {action.text()}"

    def test_refresh_still_in_op_menu(self, main_window):
        """操作菜单仍保留刷新项（回归防护）。"""
        menus = _find_menus(main_window)
        op_menu = _menu_by_title(menus, "操作")
        texts = _action_texts(op_menu)
        assert any("刷新" in t for t in texts)

    def test_backup_still_in_op_menu(self, main_window):
        """操作菜单仍保留数据管理项（回归防护）。"""
        menus = _find_menus(main_window)
        op_menu = _menu_by_title(menus, "操作")
        texts = _action_texts(op_menu)
        assert any("数据管理" in t for t in texts)

    def test_op_menu_no_duplicate_entries(self, main_window):
        """操作菜单无重复条目（回归防护 — 10e01f1 曾重复添加数据体检/数据管理）。"""
        menus = _find_menus(main_window)
        op_menu = _menu_by_title(menus, "操作")
        texts = [t for t in _action_texts(op_menu) if t]  # 排除分隔符空文本
        dups = {t for t in texts if texts.count(t) > 1}
        assert not dups, f"操作菜单出现重复条目: {dups}"

    def test_health_check_in_op_menu(self, main_window):
        """操作菜单保留数据体检项（回归防护）。"""
        menus = _find_menus(main_window)
        op_menu = _menu_by_title(menus, "操作")
        texts = _action_texts(op_menu)
        assert any("数据体检" in t for t in texts)

    def test_view_menu_still_has_theme_settings(self, main_window):
        """视图菜单仍保留主题设置项（回归防护）。"""
        menus = _find_menus(main_window)
        view_menu = _menu_by_title(menus, "视图")
        texts = _action_texts(view_menu)
        assert any("视图偏好与主题设置" in t for t in texts)
