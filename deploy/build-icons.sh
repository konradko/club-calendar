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
