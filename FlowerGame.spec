# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/easytier/easytier-core.exe', 'resources/easytier'),
        ('resources/easytier/easytier-cli.exe', 'resources/easytier'),
        ('resources/easytier/wintun.dll', 'resources/easytier'),
        ('resources/easytier/Packet.dll', 'resources/easytier'),
        ('resources/syncthing/syncthing.exe', 'resources/syncthing'),
        # ('resources/icons/*', 'resources/icons'), # 图标文件夹已删除
        ('resources/logo.ico', 'resources'),
        ('resources/logo.png', 'resources'),
    ],  # 打包所有必要的资源文件
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
              'numpy', 'cv2', 'bcrypt', 'cryptography', 'Pillow', 'sip'],
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
    name='FlowerGame',
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
    uac_admin=True,  # 强制管理员权限启动
    icon='resources/logo.ico',
)
