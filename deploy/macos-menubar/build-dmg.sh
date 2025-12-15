#!/bin/bash
# Build Club Calendar menu bar app as a DMG
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"
DMG_NAME="ClubCalendar"
APP_NAME="Club Calendar.app"
VERSION="0.1.0"

echo "Building Club Calendar menu bar app..."
echo "======================================="

# Change to project root
cd "$PROJECT_ROOT"

# Sync all packages and dev dependencies (includes rumps, pyinstaller)
echo ""
echo "Installing dependencies..."
uv sync --all-packages

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR"

# Run PyInstaller
echo ""
echo "Running PyInstaller..."
uv run pyinstaller --clean --noconfirm "$SCRIPT_DIR/ClubCalendar.spec"

# Verify app was built
if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
    echo "ERROR: App bundle not found at $DIST_DIR/$APP_NAME"
    exit 1
fi

echo ""
echo "App built successfully at: $DIST_DIR/$APP_NAME"

# Create DMG
echo ""
echo "Creating DMG..."

DMG_PATH="$DIST_DIR/${DMG_NAME}-${VERSION}.dmg"
DMG_TEMP="$DIST_DIR/${DMG_NAME}-temp.dmg"

# Remove old DMG if exists
rm -f "$DMG_PATH" "$DMG_TEMP"

# Create temporary DMG
hdiutil create -srcfolder "$DIST_DIR/$APP_NAME" -volname "$DMG_NAME" -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" -format UDRW "$DMG_TEMP"

# Convert to compressed, read-only DMG
hdiutil convert "$DMG_TEMP" -format UDZO -imagekey zlib-level=9 -o "$DMG_PATH"
rm -f "$DMG_TEMP"

echo ""
echo "======================================="
echo "Build complete!"
echo ""
echo "DMG: $DMG_PATH"
echo ""
echo "To install:"
echo "  1. Open the DMG"
echo "  2. Drag 'Club Calendar' to Applications"
echo "  3. Open from Applications"
echo ""
echo "The app runs as a menu bar app (look for 📅 in your menu bar)"
