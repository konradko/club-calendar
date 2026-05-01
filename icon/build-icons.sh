#!/bin/bash
# Generate menubar icons from SVG

set -e
cd "$(dirname "$0")/.."

if ! command -v rsvg-convert &> /dev/null; then
    echo "Installing librsvg..."
    brew install librsvg
fi

if ! command -v magick &> /dev/null; then
    echo "Installing imagemagick..."
    brew install imagemagick
fi

echo "Generating icons from icon.svg..."

# Verify icon.svg exists
if [ ! -f "icon.svg" ]; then
    echo "ERROR: icon.svg not found in $(pwd)"
    echo "Please ensure icon.svg exists in the project root."
    exit 1
fi

# App icon (1024x1024 for .icns generation)
rsvg-convert -w 1024 -h 1024 icon.svg -o deploy/icon.png
echo "  Generated: deploy/icon.png (1024x1024)"

# Menubar icons: 18x18/36x36 centered in 22x22/44x44 canvas for proper padding
rsvg-convert -w 18 -h 18 icon.svg | magick - -gravity center -background none -extent 22x22 deploy/icon_menubarTemplate.png
rsvg-convert -w 36 -h 36 icon.svg | magick - -gravity center -background none -extent 44x44 deploy/icon_menubarTemplate@2x.png

# Set correct DPI for macOS (72 for 1x, 144 for 2x)
sips -s dpiWidth 72 -s dpiHeight 72 deploy/icon_menubarTemplate.png >/dev/null
sips -s dpiWidth 144 -s dpiHeight 144 deploy/icon_menubarTemplate@2x.png >/dev/null

echo "  Generated: deploy/icon_menubarTemplate.png (22x22)"
echo "  Generated: deploy/icon_menubarTemplate@2x.png (44x44)"

# Generate .icns from the high-res PNG
echo "Generating .icns..."
ICONSET_DIR="deploy/icon.iconset"
mkdir -p "$ICONSET_DIR"

# Generate icons with macOS iconset naming convention directly
# Format: icon_NxN.png and icon_NxN@2x.png
rsvg-convert -w 16 -h 16 icon.svg -o "$ICONSET_DIR/icon_16x16.png"
rsvg-convert -w 32 -h 32 icon.svg -o "$ICONSET_DIR/icon_16x16@2x.png"
rsvg-convert -w 32 -h 32 icon.svg -o "$ICONSET_DIR/icon_32x32.png"
rsvg-convert -w 64 -h 64 icon.svg -o "$ICONSET_DIR/icon_32x32@2x.png"
rsvg-convert -w 128 -h 128 icon.svg -o "$ICONSET_DIR/icon_128x128.png"
rsvg-convert -w 256 -h 256 icon.svg -o "$ICONSET_DIR/icon_128x128@2x.png"
rsvg-convert -w 256 -h 256 icon.svg -o "$ICONSET_DIR/icon_256x256.png"
rsvg-convert -w 512 -h 512 icon.svg -o "$ICONSET_DIR/icon_256x256@2x.png"
rsvg-convert -w 512 -h 512 icon.svg -o "$ICONSET_DIR/icon_512x512.png"
rsvg-convert -w 1024 -h 1024 icon.svg -o "$ICONSET_DIR/icon_512x512@2x.png"

# Convert iconset to icns
iconutil -c icns "$ICONSET_DIR" -o deploy/icon.icns
rm -rf "$ICONSET_DIR"
echo "  Generated: deploy/icon.icns"

echo "Done!"
