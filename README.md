# Club Calendar

Sync Strava club events to ICS calendar feeds.

## Quick Start

```bash
# Clone and install
git clone <repo>
cd club-calendar
uv sync

# Authenticate with Strava
club-calendar auth

# List and save your clubs
club-calendar clubs --save

# Sync events to ICS files
club-calendar sync
```

## Installation Options

### 1. DMG Install (Recommended)

Download and install the standalone app:

```bash
# Build the DMG
./macos/menubar/build-dmg.sh

# Or install from pre-built DMG:
# 1. Open dist/ClubCalendar-0.1.0.dmg
# 2. Drag Club Calendar to Applications
# 3. Open from Applications
```

The menu bar app provides:
- One-click sync
- Full setup wizard (no CLI required):
  - Configure Strava API credentials
  - OAuth authentication
  - Club selection
- Status indicator
- macOS notifications

### 2. Development Install

For development or if you prefer running from source:

```bash
# Install dependencies
./macos/menubar/install.sh

# Install with startup at login
./macos/menubar/install.sh --startup

# Check status
./macos/menubar/install.sh --status

# Remove startup
./macos/menubar/install.sh --uninstall
```

Run manually: `uv run club-calendar-menubar`

### 3. Background Sync (launchd)

For automatic daily syncs without user interaction:

```bash
# Install launchd service (syncs daily at 6am)
./macos/launchd/install.sh --hour 6 --minute 0

# Uninstall
./macos/launchd/uninstall.sh
```

### 4. CLI Only

```bash
uv sync
club-calendar --help
```

## Setup

### Using the Menu Bar App (Recommended)

The menu bar app has a built-in Setup menu that handles everything:
1. **Setup > Configure Strava API...** - Enter your Client ID and Secret
2. **Setup > Authenticate with Strava...** - Opens browser for OAuth
3. **Setup > Select Clubs...** - Choose which clubs to sync

### Manual Setup (CLI)

#### 1. Create Strava API App

1. Go to https://www.strava.com/settings/api
2. Create an application
3. Note your Client ID and Client Secret

#### 2. Configure

Create a `.env` file:

```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

#### 3. Authenticate

```bash
club-calendar auth
```

This opens a browser for OAuth and saves the refresh token to `.env`.

#### 4. Select Clubs

```bash
# List your clubs
club-calendar clubs

# Save club IDs to .env
club-calendar clubs --save
```

## CLI Commands

```bash
club-calendar auth          # OAuth flow to get Strava refresh token
club-calendar clubs         # List clubs you belong to
club-calendar clubs --save  # Save local club IDs to .env
club-calendar sync          # Generate ICS files
club-calendar sync --stdout # Output combined ICS to stdout
```

## Output

Calendar files are written to `~/.club-calendar/`:
- `combined.ics` - All events from all clubs
- `club-{id}.ics` - Per-club calendar

Subscribe to these files from any calendar app that supports ICS files.

## Project Structure

```
club-calendar/
├── src/club_calendar/   # Python package
│   ├── strava.py        # Strava API client
│   ├── calendar.py      # ICS generation
│   ├── services.py      # Business logic
│   ├── config.py        # Settings
│   ├── cli.py           # CLI commands
│   └── menubar.py       # Menu bar app
├── tests/               # 100% test coverage
├── macos/
│   ├── launchd/         # Background sync service
│   └── menubar/         # Menu bar app installer
└── pyproject.toml
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check --fix
```

## License

MIT
