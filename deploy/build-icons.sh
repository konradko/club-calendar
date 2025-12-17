#!/bin/bash
# Generate menubar icons from SVG

set -e
cd "$(dirname "$0")/../.."

if ! command -v rsvg-convert &> /dev/null; then
    echo "Installing librsvg..."
    brew install librsvg
fi

if ! command -v magick &> /dev/null; then
    echo "Installing imagemagick..."
    brew install imagemagick
fi

echo "Generating menubar icons from icon.svg..."
# Render at 18x18/36x36 and center in 22x22/44x44 canvas for proper padding
# DPI must be 72 for 1x and 144 for 2x for crisp Retina rendering
rsvg-convert -w 18 -h 18 icon.svg | magick - -gravity center -background none -extent 22x22 deploy/icon_menubarTemplate.png
rsvg-convert -w 36 -h 36 icon.svg | magick - -gravity center -background none -extent 44x44 deploy/icon_menubarTemplate@2x.png

# Set correct DPI for macOS (72 for 1x, 144 for 2x)
sips -s dpiWidth 72 -s dpiHeight 72 deploy/icon_menubarTemplate.png
sips -s dpiWidth 144 -s dpiHeight 144 deploy/icon_menubarTemplate@2x.png

echo "Generated:"
ls -la deploy/icon_menubarTemplate*.png
