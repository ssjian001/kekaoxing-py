"""测试主题系统（Theme System）— 明暗主题切换与全局变量同步。"""

import pytest
import src.styles.theme as theme


def test_theme_switch_light_and_dark():
    """测试主题在 light 和 dark 之间切换。"""
    theme.set_theme("dark")
    assert theme.current_theme() == "dark"
    assert theme.BASE == "#1E1E2E"

    theme.set_theme("light")
    assert theme.current_theme() == "light"
    assert theme.BASE == "#F7F8FC"


def test_theme_signal_emission():
    """测试主题切换时发射 theme_changed 信号。"""
    emitted = []

    def on_theme(name: str):
        emitted.append(name)

    theme.theme_host.theme_changed.connect(on_theme)

    theme.set_theme("dark")
    assert emitted == ["dark"]

    theme.set_theme("light")
    assert emitted == ["dark", "light"]

    theme.theme_host.theme_changed.disconnect(on_theme)
