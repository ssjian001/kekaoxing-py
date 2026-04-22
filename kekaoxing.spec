# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 可靠性测试甘特图
用法:
  pyinstaller kekaoxing.spec          (当前平台)
  或通过 .github/workflows/build.yml 在 Windows 上自动构建
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # 如果以后有 assets/ 目录，在此添加
        # (str(PROJECT_ROOT / 'assets'), 'assets'),
    ],
    hiddenimports=[
        'apsw',
        'openpyxl',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtPrintSupport',
        'PySide6.QtCharts',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'IPython',
        'jupyter',
        'pytest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='可测排程',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI 程序，不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows 特有
    icon=str(PROJECT_ROOT / 'icon.ico') if (PROJECT_ROOT / 'icon.ico').exists() else None,
)
