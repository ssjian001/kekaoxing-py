"""测试 视图偏好与主题融合设置中心 (ViewThemeSettingsDialog) 与 全景简报打包导出 (ReportBundleDialog)。"""
from __future__ import annotations

import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.views.widgets.view_theme_settings_dialog import ViewThemeSettingsDialog
from src.views.widgets.report_bundle_dialog import ReportBundleDialog
import src.styles.theme as _theme


def test_view_theme_settings_dialog_instantiation(qtbot) -> None:
    """测试 ViewThemeSettingsDialog 的实例化与主题切换逻辑。"""
    dlg = ViewThemeSettingsDialog()
    qtbot.addWidget(dlg)

    assert dlg is not None
    assert _theme.current_theme() in ("light", "dark")

    # 模拟切换暗黑与明亮
    dlg._switch_theme("dark")
    assert _theme.current_theme() == "dark"

    dlg._switch_theme("light")
    assert _theme.current_theme() == "light"

    # 模拟应用品牌强调色
    dlg._apply_accent("#1e66f5")
    assert _theme.ACCENT == "#1e66f5"


def test_report_bundle_dialog_export(qtbot, tmp_path) -> None:
    """测试 ReportBundleDialog 构造与 controller 注入。

    _do_export 接入真实 ExportService 引擎，需要 controller + QFileDialog，
    此处只验证 dialog 可正确构造并接收 controller 参数。
    真实导出路径由集成测试覆盖。
    """
    # 无 controller 时仍可构造（UI 层）
    dlg = ReportBundleDialog()
    qtbot.addWidget(dlg)
    assert dlg is not None
    assert dlg._ctrl is None

    # 有 controller 时注入成功
    class _FakeCtrl:
        pass
    fake_ctrl = _FakeCtrl()
    dlg2 = ReportBundleDialog(controller=fake_ctrl, get_plan_id=lambda: 42)  # type: ignore[arg-type]
    qtbot.addWidget(dlg2)
    assert dlg2._ctrl is fake_ctrl
    assert dlg2._get_plan_id() == 42
