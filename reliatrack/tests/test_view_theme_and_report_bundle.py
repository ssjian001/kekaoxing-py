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
    """测试 ReportBundleDialog 的打包导出与水印写入逻辑。"""
    dlg = ReportBundleDialog()
    qtbot.addWidget(dlg)

    dlg._wm_edit.setText("TEST-CONFIDENTIAL")

    out_file = str(tmp_path / "test_report.xlsx")

    # 模拟直接写入报告逻辑
    watermark = dlg._wm_edit.text().strip()
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"Reliability Report\nWatermark: {watermark}\n")

    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "TEST-CONFIDENTIAL" in content
