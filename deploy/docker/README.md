# club-calendar-docker

Docker deployment for syncing Strava club events to ICS calendars.

## Quick Start

```bash
cd deploy/docker

# Configure credentials (see below for how to get them)
cp .env.example .env
# Edit .env with your Strava credentials

# Build and run
docker compose up -d

# Access calendar
curl http://localhost:51470/club-calendar.ics
```

## Configuration

Create a `.env` file with:

```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
STRAVA_CLUB_IDS=123,456,789
SYNC_SCHEDULE="0 8,12,16,20 * * *"
TZ=Europe/London
PORT=51470
```

## Getting Strava Credentials

### 1. Create Strava API App

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an application (use `localhost` for callback URL)
3. Note your **Client ID** and **Client Secret**

### 2. Get Refresh Token

Run the CLI locally to authenticate:

```bash
# From the club-calendar repo root
uv sync
export STRAVA_CLIENT_ID=your_client_id
export STRAVA_CLIENT_SECRET=your_client_secret
uv run club-calendar auth
```

This opens a browser for OAuth. The refresh token will be saved to your `.env` file.

### 3. Get Club IDs

```bash
uv run club-calendar clubs
```

Note the IDs of clubs you want to sync.

## Commands

```bash
# Start container
docker compose up -d

# View logs
docker compose logs -f

# Force sync now
docker compose exec club-calendar uv run club-calendar sync --output /output

# Stop
docker compose down
```

## Calendar URL

The container serves ICS files via HTTP:

```
http://localhost:51470/club-calendar.ics
http://localhost:51470/club-calendar-{id}.ics
```

Subscribe to these URLs from any calendar app.
