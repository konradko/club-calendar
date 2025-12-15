#!/bin/sh
set -e

mkdir -p /output

# Create cron job
echo "$SYNC_SCHEDULE cd /app && uv run club-calendar sync --output /output >> /proc/1/fd/1 2>&1" > /etc/crontabs/root

# Initial sync
echo "$(date): Running initial sync..."
uv run club-calendar sync --output /output

# Start cron daemon
crond -l 2

# Start web server (foreground)
echo "$(date): Serving calendar on port $PORT"
cd /output && exec python -m http.server "$PORT"
