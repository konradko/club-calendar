# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Club Calendar menu bar app."""

from pathlib import Path

# Get project root (deploy/macos-dmg -> project root)
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent.parent

block_cipher = None

# Include template icons in the app bundle
datas = []
for icon_file in ["icon_menubarTemplate.png", "icon_menubarTemplate@2x.png"]:
    icon_path = spec_dir / icon_file
    if icon_path.exists():
        datas.append((str(icon_path), "."))

a = Analysis(
    [str(project_root / "packages" / "macos" / "src" / "club_calendar_macos" / "menubar.py")],
    pathex=[str(project_root / "packages" / "macos" / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "rumps",
        "club_calendar_macos",
        "club_calendar_macos.config",
        "club_calendar_macos.models",
        "club_calendar_core",
        "club_calendar_core.strava",
        "club_calendar_core.calendar",
        "club_calendar_core.service",
        "club_calendar_cli",
        "httpx",
        "icalendar",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Club Calendar",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Club Calendar",
)

icon_icns = spec_dir / "icon.icns"
app = BUNDLE(
    coll,
    name="Club Calendar.app",
    icon=str(icon_icns) if icon_icns.exists() else None,
    bundle_identifier="com.club-calendar.menubar",
    info_plist={
        "LSUIElement": True,  # Hide from Dock
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
