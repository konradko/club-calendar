#!/bin/bash
# Sync wrapper with macOS notifications
# Uses native osascript - no dependencies

set -e

# Navigate to cli/ directory (script is in macos/launchd/)
CLI_DIR="$(cd "$(dirname "$0")/../../cli" && pwd)"
LOG_FILE="$HOME/.club-calendar.log"

cd "$CLI_DIR"

# Run sync and capture output
if output=$(uv run club-calendar sync 2>&1); then
    # Success - silent by default, uncomment to notify
    # osascript -e 'display notification "Calendar sync completed" with title "Club Calendar"'
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS" >> "$LOG_FILE"
    echo "$output" >> "$LOG_FILE"
else
    # Error - show notification
    error_msg=$(echo "$output" | tail -1 | cut -c1-100)
    osascript -e "display notification \"$error_msg\" with title \"Club Calendar Failed\" sound name \"Basso\""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAILED" >> "$LOG_FILE"
    echo "$output" >> "$LOG_FILE"
    exit 1
fi
