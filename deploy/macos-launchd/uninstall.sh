#!/bin/bash
# Uninstall launchd service for club-calendar

set -e

PLIST_NAME="com.club-calendar.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Uninstalling club-calendar launchd service..."

# Unload if loaded
if launchctl list | grep -q "com.club-calendar"; then
    launchctl unload "$PLIST_DST"
    echo "Service unloaded"
fi

# Remove plist
if [ -f "$PLIST_DST" ]; then
    rm "$PLIST_DST"
    echo "Removed $PLIST_DST"
fi

echo ""
echo "Uninstalled. Log file remains at ~/.club-calendar.log"
