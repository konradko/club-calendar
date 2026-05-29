#!/bin/bash
# Generate the iOS app icon: the "cc" calendar mark (icon.png, the same art as
# the macOS menu-bar glyph) recolored white over a deep indigo gradient, so it
# stands out instead of fading into a same-hue background. Requires ImageMagick.
#
#   ./icon/build-ios-appicon.sh
#
set -e
cd "$(dirname "$0")/.."

SRC="icon/icon.png"
DEST="ClubCalendar-iOS/Sources/Assets.xcassets/AppIcon.appiconset/icon-1024.png"
TMP="$(mktemp -d)"

if ! command -v magick &>/dev/null; then
    echo "ERROR: ImageMagick (magick) not found. brew install imagemagick"
    exit 1
fi

# Deep indigo -> navy vertical gradient, full bleed (opaque).
magick -size 1024x1024 gradient:'#3F4A78'-'#1A1F3A' "$TMP/bg.png"

# Recolor the (grayscale-on-transparent) mark to pure white, preserving alpha.
magick "$SRC" -alpha extract "$TMP/alpha.png"
magick -size 1024x1024 xc:white "$TMP/alpha.png" -alpha off \
    -compose CopyOpacity -composite "$TMP/mark_white.png"

# Center the mark at ~80% with breathing room, flatten to an opaque icon
# (iOS rejects app icons that carry an alpha channel).
magick "$TMP/bg.png" \( "$TMP/mark_white.png" -resize 815x815 \) \
    -gravity center -compose over -composite -alpha off "$DEST"

rm -rf "$TMP"
echo "Wrote $DEST"
