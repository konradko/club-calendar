#!/bin/bash
# Install launchd service for club-calendar
# Usage: ./install.sh [--hour 6] [--minute 0] [--run-now]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST_NAME="com.club-calendar.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
SYNC_SCRIPT="$SCRIPT_DIR/sync-notify.sh"
LOG_PATH="$HOME/.club-calendar.log"

# Default schedule: 6:00 AM
HOUR=6
MINUTE=0
RUN_NOW=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hour) HOUR="$2"; shift 2 ;;
        --minute) MINUTE="$2"; shift 2 ;;
        --run-now) RUN_NOW=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "Installing club-calendar launchd service..."

# Unload if already loaded
if launchctl list | grep -q "com.club-calendar"; then
    echo "Unloading existing service..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Make sync script executable
chmod +x "$SYNC_SCRIPT"

# Create LaunchAgents directory if needed
mkdir -p "$HOME/Library/LaunchAgents"

# Generate plist with actual paths and schedule
sed -e "s|__SCRIPT_PATH__|$SYNC_SCRIPT|g" \
    -e "s|__WORKING_DIR__|$PROJECT_ROOT|g" \
    -e "s|__LOG_PATH__|$LOG_PATH|g" \
    -e "s|__HOME__|$HOME|g" \
    -e "s|<integer>6</integer>|<integer>$HOUR</integer>|" \
    -e "s|<key>Minute</key>|<key>Minute</key>|" \
    "$PLIST_SRC" > "$PLIST_DST"

# Update minute in plist
sed -i '' "/<key>Minute<\/key>/,/<integer>/{s/<integer>[0-9]*<\/integer>/<integer>$MINUTE<\/integer>/}" "$PLIST_DST"

# Load the service
launchctl load "$PLIST_DST"

echo ""
echo "Installed! Service will run daily at $(printf '%02d:%02d' $HOUR $MINUTE)"
echo ""
echo "Commands:"
echo "  View logs:     tail -f ~/.club-calendar.log"
echo "  Run now:       launchctl start com.club-calendar"
echo "  Uninstall:     $SCRIPT_DIR/uninstall.sh"
echo ""

if [ "$RUN_NOW" = true ]; then
    echo "Running sync now..."
    launchctl start com.club-calendar
fi
