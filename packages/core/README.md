# club-calendar-core

Core library for syncing Strava club events to ICS calendars.

## Usage

```python
from club_calendar_core.service import ClubCalendarService

service = ClubCalendarService(
    client_id="your_client_id",
    client_secret="your_client_secret",
    refresh_token="your_refresh_token",
)

# Get clubs
clubs = service.get_clubs()

# Sync events to files
result = service.sync_to_files([club.id for club in clubs], Path("./output"))
```

## Modules

- `service.py` - ClubCalendarService, OAuthResult, SyncResult
- `strava.py` - StravaClient, Club, ClubEvent, error classes
- `calendar.py` - ICS generation functions
- `ports.py` - TokenStore protocol for DI
