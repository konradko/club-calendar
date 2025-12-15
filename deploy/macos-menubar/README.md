# club-calendar-menubar

macOS menu bar app with one-click sync and setup wizard.

## Quick Start (DMG)

```bash
# From packages/macos directory
make dmg

# Or directly
./deploy/macos-menubar/build-dmg.sh
```

Then:
1. Open `dist/ClubCalendar-0.1.0.dmg`
2. Drag Club Calendar to Applications
3. Open from Applications

## Development Mode

Run from source without building:

```bash
# From packages/macos directory
make run

# Or directly
uv run club-calendar-menubar
```

## Install from Source (with Startup)

To run from source with optional startup at login:

```bash
# Install dependencies only
./deploy/macos-menubar/install.sh

# Install with startup at login
./deploy/macos-menubar/install.sh --startup

# Check status
./deploy/macos-menubar/install.sh --status

# Remove startup
./deploy/macos-menubar/install.sh --uninstall
```

## Features

- One-click calendar sync
- Setup wizard (no CLI required):
  - Configure Strava API credentials
  - OAuth authentication
  - Club selection
- Auto-sync every 4 hours
- Status indicator in menu bar
- macOS notifications

## Getting Strava Credentials

Before using the app, get your Strava API credentials:

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an application (use `localhost` for callback URL)
3. Note your **Client ID** and **Client Secret**

Then in the menu bar app:
1. Click Setup > Configure Strava API...
2. Enter your Client ID and Secret
3. Click Setup > Authenticate with Strava...
4. Click Setup > Select Clubs...

## Build Requirements

- macOS
- PyInstaller (`uv sync --extra menubar` installs it)
- Xcode Command Line Tools (for `hdiutil`)

## Output

The DMG is created at `dist/ClubCalendar-{version}.dmg`

Calendar files are written to `~/.club-calendar/`:
```
club-calendar.ics             # All events
club-calendar-{id}.ics        # Per-club calendar
```
