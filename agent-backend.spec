# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_submodules

binaries = []
datas = []
hiddenimports = []
datas += collect_data_files('agent')
hiddenimports += collect_submodules('agent')
datas += collect_data_files('desktop_notifier')
binaries += collect_dynamic_libs('sqlite_vec')
hiddenimports += collect_submodules('desktop_notifier')
hiddenimports += collect_submodules('pypdf')
hiddenimports += collect_submodules('sqlite_vec')


a = Analysis(
    ['src\\agent\\main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests'],
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
    name='agent-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
