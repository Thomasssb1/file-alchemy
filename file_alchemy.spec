# -*- mode: python ; coding: utf-8 -*-
import os
import sys

app_script = os.path.join('src', 'file_alchemy', 'app.py')

# Platform-agnostic icon selection
if sys.platform == 'darwin':
    icon_file = 'logo.icns'
elif sys.platform == 'win32':
    icon_file = 'logo.ico'
else:
    icon_file = 'logo.png'

icon_path = os.path.join('assets', icon_file)
if not os.path.exists(icon_path):
    icon_path = os.path.join('assets', 'logo.ico')


a = Analysis(
    [app_script],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='File Alchemy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_path],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='File Alchemy',
)
