# club-calendar-cli

Command-line interface for syncing Strava club events to ICS calendars.

## Usage

```bash
# From repo root, first install
make install  # or: uv sync --all-packages

# Then run commands
uv run club-calendar auth      # Authenticate with Strava
uv run club-calendar clubs     # List your clubs
uv run club-calendar sync      # Sync events to files
```

## Configuration

Set environment variables or use a `.env` file:

```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
STRAVA_CLUB_IDS=123,456,789
```
