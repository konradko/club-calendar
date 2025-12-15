# Club Calendar

Sync Strava club events to ICS calendar feeds.

## Quick Start

```bash
# Clone and install
git clone <repo>
cd club-calendar
make install

# Authenticate with Strava
uv run club-calendar auth

# List and save your clubs
uv run club-calendar clubs --save

# Sync events to ICS files
uv run club-calendar sync
```

## Deployment Options

### 1. macOS Menu Bar App (Recommended)

One-click sync with a setup wizard - no CLI required.

```bash
# Build the DMG
cd packages/macos && make dmg

# Or run in dev mode
cd packages/macos && make run
```

See [deploy/macos-menubar/README.md](deploy/macos-menubar/README.md) for details.

### 2. macOS Background Sync (launchd)

Automatic daily syncs without user interaction.

```bash
# Install service (syncs daily at 6am)
./deploy/macos-launchd/install.sh

# Or specify a custom time
./deploy/macos-launchd/install.sh --hour 8 --minute 30
```

See [deploy/macos-launchd/README.md](deploy/macos-launchd/README.md) for details.

### 3. Docker

Self-hosted with cron sync and HTTP server.

```bash
cd deploy/docker
cp .env.example .env
# Edit .env with your credentials
docker compose up -d
```

See [deploy/docker/README.md](deploy/docker/README.md) for details.

### 4. GitHub Actions

Sync to GitHub Pages for public calendar URLs.

```bash
cd deploy/gh-actions
./setup.sh
```

See [deploy/gh-actions/README.md](deploy/gh-actions/README.md) for details.

### 5. CLI Only

```bash
uv sync
uv run club-calendar --help
```

## Setup

### Getting Strava Credentials

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an application (use `localhost` for callback URL)
3. Note your **Client ID** and **Client Secret**

### Configure

Create a `.env` file in the repo root:

```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

### Authenticate

```bash
uv run club-calendar auth
```

This opens a browser for OAuth and saves the refresh token to `.env`.

### Select Clubs

```bash
# List your clubs
uv run club-calendar clubs

# Save club IDs to .env
uv run club-calendar clubs --save
```

## CLI Commands

```bash
club-calendar auth          # OAuth flow to get Strava refresh token
club-calendar clubs         # List clubs you belong to
club-calendar clubs --save  # Save local club IDs to .env
club-calendar sync          # Generate ICS files
club-calendar sync --stdout # Output combined ICS to stdout
```

## Output Files

Calendar files are written to `~/.club-calendar/`:
- `club-calendar.ics` - All events from all clubs
- `club-calendar-{id}.ics` - Per-club calendar

Subscribe to these files from any calendar app.

## Project Structure

```
club-calendar/
├── packages/
│   ├── core/               # club-calendar-core: business logic
│   ├── cli/                # club-calendar-cli: command-line interface
│   └── macos/              # club-calendar-macos: menu bar app
├── deploy/
│   ├── docker/             # Docker deployment
│   ├── gh-actions/         # GitHub Actions deployment
│   ├── macos-launchd/      # macOS background sync
│   └── macos-menubar/      # DMG build scripts
├── .github/workflows/      # CI (lint, test)
├── Makefile
└── pyproject.toml          # Workspace config
```

## Development

```bash
# Install deps and pre-commit hooks
make install

# Run all tests
make test

# Run pre-commit hooks
make pre-commit
```

## Testing Deploy Mechanisms

Each deploy mechanism can be tested locally before production use.

### macOS Menu Bar (dev mode)

```bash
cd packages/macos && make run
```

The app runs from source. Use Setup menu to configure and test.

### macOS launchd

```bash
# Install and run immediately
./deploy/macos-launchd/install.sh --run-now

# Check logs
tail -f ~/.club-calendar.log

# Uninstall when done
./deploy/macos-launchd/uninstall.sh
```

### Docker

```bash
cd deploy/docker

# Create test .env with your credentials
cp .env.example .env
# Edit .env...

# Build and run
docker compose up --build

# Test the endpoint
curl http://localhost:51470/club-calendar.ics

# Stop
docker compose down
```

### GitHub Actions

Test the workflow locally with [act](https://github.com/nektos/act):

```bash
# Dry run
act -n

# Or push to a test branch and check Actions tab
```

## License

MIT
