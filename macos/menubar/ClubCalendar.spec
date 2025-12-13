# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Club Calendar menu bar app."""

import os
import sys
from pathlib import Path

# Get project root
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent.parent

block_cipher = None

# Include icon in the app bundle
icon_path = project_root / "icon.png"
datas = []
if icon_path.exists():
    datas.append((str(icon_path), "."))

a = Analysis(
    [str(project_root / "src" / "club_calendar" / "menubar.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "rumps",
        "club_calendar",
        "club_calendar.config",
        "club_calendar.strava",
        "club_calendar.calendar",
        "club_calendar.services",
        "httpx",
        "icalendar",
        "pydantic",
        "pydantic_settings",
        "dotenv",
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

app = BUNDLE(
    coll,
    name="Club Calendar.app",
    icon=str(project_root / "icon.icns") if (project_root / "icon.icns").exists() else None,
    bundle_identifier="com.club-calendar.menubar",
    info_plist={
        "LSUIElement": True,  # Hide from Dock
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
