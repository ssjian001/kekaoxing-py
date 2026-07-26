"""Unit tests for KeyboardShortcutsDialog and ToastNotificationStack."""

import pytest
from PySide6.QtWidgets import QApplication

from src.views.widgets.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from src.views.widgets.toast_stack import ToastNotificationStack


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_keyboard_shortcuts_dialog(qapp):
    dlg = KeyboardShortcutsDialog()
    assert dlg is not None


def test_toast_stack(qapp):
    parent_widget = qapp.activeWindow()
    stack = ToastNotificationStack(parent_widget)
    stack.show_toast("测试成功消息", "success")
    stack.show_toast("测试警告消息", "warning")
    assert len(stack._cards) == 2
