"""Service layer for club calendar sync business logic.

This module provides backwards-compatible functions that delegate to
ClubCalendarService. For new code, prefer using ClubCalendarService directly.
"""

from club_calendar.core import ClubCalendarService
from club_calendar.core import filter_local_clubs as _filter_local_clubs
from club_calendar.strava import Club, ClubEvent


def get_local_clubs(
    clubs: list[Club],
    cities: list[str] | None = None,
    max_members: int = 100000,
) -> tuple[list[Club], list[str]]:
    """Filter clubs to local ones based on city.

    This is a pure function that doesn't require credentials.

    Args:
        clubs: List of all clubs
        cities: Explicit city filter, or None to auto-detect
        max_members: Maximum member count (filters out mega-clubs)

    Returns:
        Tuple of (filtered clubs, cities used for filtering)
    """
    return _filter_local_clubs(clubs, cities, max_members)


def save_club_ids_to_config(club_ids: list[int]) -> None:
    """Save club IDs to config file.

    Args:
        club_ids: List of club IDs to save
    """
    from club_calendar.config import get_settings

    settings = get_settings()
    settings.club_ids = club_ids
    settings.save()


def save_refresh_token_to_config(refresh_token: str) -> None:
    """Save refresh token to config file.

    Args:
        refresh_token: OAuth refresh token to save
    """
    from club_calendar.config import get_settings

    settings = get_settings()
    settings.strava_refresh_token = refresh_token
    settings.save()


def fetch_club_events(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    club_ids: list[int],
) -> list[ClubEvent]:
    """Fetch events from Strava for given clubs.

    Args:
        client_id: Strava API client ID
        client_secret: Strava API client secret
        refresh_token: OAuth refresh token
        club_ids: List of club IDs to fetch events for

    Returns:
        List of club events
    """
    service = ClubCalendarService(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )
    return service.get_club_events(club_ids)


def fetch_clubs(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> list[Club]:
    """Fetch clubs the user belongs to.

    Args:
        client_id: Strava API client ID
        client_secret: Strava API client secret
        refresh_token: OAuth refresh token

    Returns:
        List of clubs
    """
    service = ClubCalendarService(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )
    return service.get_clubs()
