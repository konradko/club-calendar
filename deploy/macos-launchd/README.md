# club-calendar-launchd

macOS launchd service for automatic background calendar syncing.

## Quick Start

```bash
# Install service (syncs daily at 6am)
./deploy/macos-launchd/install.sh

# Or specify a custom time
./deploy/macos-launchd/install.sh --hour 8 --minute 30

# Run immediately after install
./deploy/macos-launchd/install.sh --run-now
```

## Prerequisites

You must have authenticated with Strava first:

```bash
# From repo root
uv sync
uv run club-calendar auth
uv run club-calendar clubs --save
```

This stores credentials in the macOS Keychain.

## Commands

```bash
# Manual sync
launchctl start com.club-calendar

# View logs
tail -f ~/.club-calendar.log

# Check status
launchctl list | grep club-calendar

# Uninstall
./deploy/macos-launchd/uninstall.sh
```

## How It Works

1. `install.sh` creates a launchd plist in `~/Library/LaunchAgents/`
2. The plist runs `sync-notify.sh` on schedule
3. `sync-notify.sh` runs `club-calendar sync` and shows macOS notifications on failure
4. Calendar files are written to `~/.club-calendar/`

## Output Files

```
~/.club-calendar/
  club-calendar.ics             # All events
  club-calendar-{id}.ics        # Per-club calendar
```

Subscribe to these files from any calendar app.
