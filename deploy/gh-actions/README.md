# club-calendar-gh-actions

GitHub Actions deployment for syncing Strava club events to ICS calendars.

## Quick Start

1. **Fork/clone this repository** to your GitHub account

2. **Get Strava API credentials** from [strava.com/settings/api](https://www.strava.com/settings/api)

3. **Create a `.env` file** with your credentials:
   ```bash
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   STRAVA_REFRESH_TOKEN=your_refresh_token
   STRAVA_CLUB_IDS=123456,789012
   ```

4. **Run setup script** (requires [GitHub CLI](https://cli.github.com/)):
   ```bash
   cd deploy/gh-actions
   chmod +x setup.sh
   ./setup.sh
   ```

5. **Copy the workflow file** to your repository:
   ```bash
   mkdir -p .github/workflows
   cp workflow-template.yml .github/workflows/sync.yml
   git add .github/workflows/sync.yml
   git commit -m "Add calendar sync workflow"
   git push
   ```

## Manual Setup

If you prefer to set up manually:

### Secrets (Settings > Secrets > Actions)
- `STRAVA_CLIENT_ID` - Your Strava API client ID
- `STRAVA_CLIENT_SECRET` - Your Strava API client secret
- `STRAVA_REFRESH_TOKEN` - Your OAuth refresh token

### Variables (Settings > Variables > Actions)
- `STRAVA_CLUB_IDS` - Comma-separated list of club IDs
- `CALENDAR_ID` - Optional unique ID for the calendar filename
- `CLUB_CITY_FILTER` - Optional city filter for club discovery

### GitHub Pages
1. Go to Settings > Pages
2. Source: GitHub Actions
3. Wait for first workflow run to complete

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

## Schedule

By default, the workflow syncs 4 times daily at 8:00, 12:00, 16:00, and 20:00 UTC.

Modify the cron schedule in `.github/workflows/sync.yml` to change this.

## Calendar URL

After successful deployment:

```
https://YOUR_USERNAME.github.io/YOUR_REPO/club-calendar.ics
```

Or with CALENDAR_ID:
```
https://YOUR_USERNAME.github.io/YOUR_REPO/club-calendar-YOUR_CALENDAR_ID.ics
```
