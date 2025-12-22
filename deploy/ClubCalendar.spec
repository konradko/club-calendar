# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Club Calendar menu bar app."""

from pathlib import Path

# Get project root (deploy -> project root)
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent

block_cipher = None

# Use pre-generated menubar icons from build-dmg.sh (rsvg-convert + ImageMagick)
# These are proper grayscale template icons that work correctly with macOS menu bar
datas = []
for suffix in ["", "@2x"]:
    icon_path = spec_dir / f"icon_menubarTemplate{suffix}.png"
    if icon_path.exists():
        datas.append((str(icon_path), "."))
        print(f"  Using pre-generated: {icon_path.name}")
    else:
        print(f"  WARNING: {icon_path.name} not found - run build-dmg.sh first")

a = Analysis(
    [str(project_root / "src" / "club_calendar" / "menubar" / "__main__.py")],
    pathex=[
        str(project_root / "src"),
        str(project_root / "packages" / "core" / "src"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "rumps",
        "club_calendar",
        "club_calendar.config",
        "club_calendar.models",
        "club_calendar.eventkit",
        "club_calendar_core",
        "club_calendar_core.strava",
        "club_calendar_core.service",
        "club_calendar_core.ports",
        "httpx",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Build-time only dependencies (not needed at runtime)
        "PIL",
        "pillow",
        "Pillow",
        # Test dependencies
        "pytest",
        "pytest_httpx",
        "_pytest",
        "coverage",
        # Dev tools
        "ruff",
        "mypy",
        "pyinstaller",
        "PyInstaller",
        # Unused stdlib modules (saves ~500KB in base_library.zip)
        "tkinter",
        "sqlite3",
        "unittest",
        "pydoc",
        "doctest",
        "lib2to3",
        "xmlrpc",
        "multiprocessing",
        "concurrent",
        "asyncio.windows_events",
        "asyncio.windows_utils",
        # Unused network protocols
        "ftplib",
        "imaplib",
        "nntplib",
        "poplib",
        "smtplib",
        "telnetlib",
        # Other unused
        "curses",
        "distutils",
        "ensurepip",
        "idlelib",
        "turtledemo",
        "turtle",
    ],
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
    strip=True,  # Strip debug symbols
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
    strip=True,  # Strip debug symbols from binaries
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
        "NSCalendarsUsageDescription": "Club Calendar syncs Strava club events to your calendar.",
    },
)
