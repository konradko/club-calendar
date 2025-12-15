# club-calendar-macos

macOS menu bar app for syncing Strava club events to ICS calendars.

## Usage

```bash
# From repo root, first install
make install  # or: uv sync --all-packages

# Then run
cd packages/macos
make run    # Run in dev mode
make dmg    # Build DMG installer
```

## Features

- Status bar icon with sync status
- Setup wizard for credentials and clubs
- OAuth authentication flow
- Auto-sync every 4 hours
- macOS Keychain for secure credential storage
