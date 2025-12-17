<p align="center">
  <img src="icon.png" alt="Club Calendar" width="128" height="128">
</p>

# Club Calendar

A macOS menu bar app that syncs your Strava club events to Apple Calendar.

## Features

- Syncs events from all your Strava clubs
- Native Apple Calendar integration
- Auto-sync in the background (configurable interval)
- Filter clubs by city
- Flood protection (limit events per club)

## Installation

### Download DMG

Download the latest release from the [Releases](https://github.com/your-repo/club-calendar/releases) page.

1. Open the DMG
2. Drag "Club Calendar" to Applications
3. Open from Applications (look for the icon in your menu bar)

### Build from Source

```bash
git clone <repo>
cd club-calendar
make install
make dmg
```

## Setup

1. **Get Strava API credentials:**
   - Go to [strava.com/settings/api](https://www.strava.com/settings/api)
   - Create an application (use `localhost` for callback URL)
   - Note your **Client ID** and **Client Secret**

2. **Configure the app:**
   - Click the menu bar icon
   - Select "Edit config..." to add your credentials
   - Click "Authenticate with Strava..."
   - Click "Sync Now" to fetch your clubs and events

## Configuration

Config file location: `~/Library/Application Support/Club Calendar/config.yaml`

```yaml
# Strava credentials
strava_client_id: "your_client_id"
strava_client_secret: "your_client_secret"

# City filter (auto-enable clubs in these cities)
cities:
  - London
  - Manchester

# Sync settings
sync_interval_minutes: 60  # 0 = disabled
sync_weeks: 8              # How far ahead to sync
max_events_per_club_per_week: 10

# Clubs (populated after first sync)
clubs:
  123456:
    name: "My Running Club"
    city: "London"
    enabled: true
```

## Development

```bash
# Install dependencies
make install

# Run with hot reload and mock Strava server
make dev
# Run tests
make test

# Build DMG
make dmg
```

## Project Structure

```
club-calendar/
├── src/club_calendar/
│   ├── core/           # Pure Python logic (strava, service, models)
│   └── menubar/        # macOS-specific (app, config, eventkit, utils)
├── tests/              # All tests (unified)
├── deploy/             # Build scripts (dmg, icons)
└── Makefile
```

## License

MIT
