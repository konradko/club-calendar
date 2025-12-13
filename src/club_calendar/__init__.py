"""Club Calendar - Sync Strava club events to ICS calendar feeds."""

from club_calendar.calendar import (
    create_calendar,
    generate_combined_calendar,
    generate_per_club_calendars,
    write_calendars,
)
from club_calendar.config import Settings, get_settings
from club_calendar.services import (
    fetch_club_events,
    fetch_clubs,
    get_local_clubs,
    save_club_ids_to_config,
    save_refresh_token_to_config,
)
from club_calendar.strava import (
    Club,
    ClubEvent,
    StravaClient,
    StravaError,
)

__version__ = "0.1.0"

__all__ = [
    # Strava
    "StravaClient",
    "StravaError",
    "Club",
    "ClubEvent",
    # Calendar
    "create_calendar",
    "generate_combined_calendar",
    "generate_per_club_calendars",
    "write_calendars",
    # Services
    "fetch_clubs",
    "fetch_club_events",
    "get_local_clubs",
    "save_club_ids_to_config",
    "save_refresh_token_to_config",
    # Config
    "Settings",
    "get_settings",
]
