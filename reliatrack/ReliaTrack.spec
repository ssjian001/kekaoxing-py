# -*- mode: python ; coding: utf-8 -*-
"""ReliaTrack PyInstaller 打包配置（--onedir --windowed --noupx）。

用法：cd reliatrack && pyinstaller --noconfirm ReliaTrack.spec
产物：dist/ReliaTrack/（目录模式，入口 dist/ReliaTrack/ReliaTrack[.exe]）

本文件与 release.yml 2026-08-30 前内联的打包参数等价：
hiddenimports 覆盖 apsw/openpyxl/docx/reportlab/lxml（docx→lxml 为间接依赖），
apsw 走 collect_all 打全自带数据与二进制（等价 --collect-all）。
"""
from PyInstaller.utils.hooks import collect_all

_apsw_datas, _apsw_binaries, _apsw_hidden = collect_all('apsw')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_apsw_binaries,
    datas=_apsw_datas,
    hiddenimports=[
        'apsw',
        'openpyxl',
        'docx',
        'reportlab',
        'reportlab.lib',
        'reportlab.pdfgen',
        'reportlab.platypus',
        'lxml',
    ] + _apsw_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ReliaTrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # --windowed（GUI 应用，无控制台）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ReliaTrack',      # --onedir
)
