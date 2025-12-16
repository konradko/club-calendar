"""Strava API client for fetching club events."""

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from httpx import HTTPTransport

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3

# Strava URLs - can be overridden via env vars for testing
STRAVA_AUTH_URL = os.environ.get("STRAVA_AUTH_URL", "https://www.strava.com/oauth/authorize")
STRAVA_TOKEN_URL = os.environ.get("STRAVA_TOKEN_URL", "https://www.strava.com/oauth/token")
STRAVA_API_URL = os.environ.get("STRAVA_API_URL", "https://www.strava.com/api/v3")


class StravaError(Exception):
    """Base exception for Strava API errors."""


class StravaAuthError(StravaError):
    """Authentication or authorization error."""


class StravaRateLimitError(StravaError):
    """Rate limit exceeded."""


@dataclass
class TokenResponse:
    """OAuth token response from Strava."""

    access_token: str
    refresh_token: str
    expires_at: int


@dataclass
class Club:
    """Strava club info."""

    id: int
    name: str
    member_count: int
    city: str | None
    state: str | None
    country: str | None


@dataclass
class ClubEvent:
    """Strava club event.

    Fields from Strava API:
    https://developers.strava.com/playground/
    """

    id: int
    title: str
    description: str | None
    club_id: int
    club_name: str
    start_datetime: datetime
    address: str | None
    route_id: int | None
    organizer_name: str | None
    activity_type: str | None = None  # e.g., "Ride", "Run"
    zone: str | None = None  # Timezone, e.g., "Europe/Warsaw"
    women_only: bool = False
    private: bool = False
    start_latlng: tuple[float, float] | None = None  # (lat, lng) coordinates


class StravaClient:
    """Client for interacting with the Strava API.

    Args:
        client_id: Strava API client ID
        client_secret: Strava API client secret
        refresh_token: OAuth refresh token (optional)
        access_token: OAuth access token (optional)
        timeout: Request timeout in seconds (default: 30.0)
        retries: Number of retries for transient failures (default: 3)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str | None = None,
        access_token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token = access_token
        self._token_expires_at = 0
        # Use transport with retry for transient network failures
        transport = HTTPTransport(retries=retries)
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> "StravaClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def get_authorization_url(self, redirect_uri: str = "http://localhost:8000/callback") -> str:
        """Get the OAuth authorization URL for user to visit."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "read",
            "approval_prompt": "auto",
        }
        return f"{STRAVA_AUTH_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())

    def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for tokens."""
        response = self._http.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        self._handle_response_errors(response)
        data = response.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._token_expires_at = data["expires_at"]
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
        )

    def refresh_access_token(self) -> TokenResponse:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise StravaAuthError("No refresh token available")

        response = self._http.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
        )
        self._handle_response_errors(response)
        data = response.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._token_expires_at = data["expires_at"]
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
        )

    @property
    def refresh_token(self) -> str | None:
        """Get the current refresh token."""
        return self._refresh_token

    def _ensure_access_token(self) -> str:
        """Ensure we have a valid access token."""
        if self._access_token and self._token_expires_at > datetime.now().timestamp() + 60:
            return self._access_token
        if self._refresh_token:
            self.refresh_access_token()
            return self._access_token  # type: ignore
        raise StravaAuthError("No valid access token and no refresh token to obtain one")

    def _handle_response_errors(self, response: httpx.Response) -> None:
        """Handle API response errors."""
        if response.status_code == 401:
            raise StravaAuthError("Invalid or expired credentials")
        if response.status_code == 403:
            raise StravaAuthError("Access forbidden - check scopes")
        if response.status_code == 429:
            raise StravaRateLimitError("Rate limit exceeded - try again later")
        if response.status_code >= 400:
            raise StravaError(f"API error {response.status_code}: {response.text}")

    def _get(self, endpoint: str) -> Any:
        """Make authenticated GET request to Strava API."""
        token = self._ensure_access_token()
        response = self._http.get(
            f"{STRAVA_API_URL}/{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self._handle_response_errors(response)
        return response.json()

    def get_athlete_clubs(self) -> list[Club]:
        """Get list of clubs the authenticated athlete belongs to."""
        data = self._get("athlete/clubs")
        return [
            Club(
                id=club["id"],
                name=club["name"],
                member_count=club.get("member_count", 0),
                city=club.get("city"),
                state=club.get("state"),
                country=club.get("country"),
            )
            for club in data
        ]

    def get_club_events(self, club_id: int) -> list[ClubEvent]:
        """Get future events for a specific club."""

        data = self._get(f"clubs/{club_id}/group_events")
        events = []
        now = datetime.now(UTC)

        for event in data:
            # Parse datetime - Strava returns ISO format
            occurrence = event["upcoming_occurrences"][0].replace("Z", "+00:00")
            start_dt = datetime.fromisoformat(occurrence)

            # Skip events before today (but keep today's events even if past start time)
            if start_dt.date() < now.date():
                continue

            # Get club name from event if available (handle None explicitly)
            club_data = event.get("club") or {}
            club_name = club_data.get("name", f"Club {club_id}")

            # Get organizer name if available (handle None explicitly)
            organizer_data = event.get("organizing_athlete") or {}
            organizer_name = organizer_data.get("firstname")

            # Parse coordinates if available
            latlng = event.get("start_latlng")
            start_latlng = tuple(latlng) if latlng and len(latlng) == 2 else None

            events.append(
                ClubEvent(
                    id=event["id"],
                    title=event["title"],
                    description=event.get("description"),
                    club_id=club_id,
                    club_name=club_name,
                    start_datetime=start_dt,
                    address=event.get("address"),
                    route_id=event.get("route_id"),
                    organizer_name=organizer_name,
                    activity_type=event.get("activity_type") or event.get("sport_type"),
                    zone=event.get("zone"),
                    women_only=event.get("women_only", False),
                    private=event.get("private", False),
                    start_latlng=start_latlng,
                )
            )
        return events

    def get_all_club_events(self, club_ids: list[int]) -> list[ClubEvent]:
        """Get events from multiple clubs concurrently.

        Uses a thread pool to fetch events from all clubs in parallel,
        significantly reducing total sync time for users with many clubs.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        all_events: list[ClubEvent] = []
        errors: list[tuple[int, Exception]] = []

        def fetch_club(club_id: int) -> tuple[int, list[ClubEvent] | Exception]:
            try:
                return (club_id, self.get_club_events(club_id))
            except Exception as e:
                return (club_id, e)

        # Use thread pool for concurrent fetching (httpx.Client is thread-safe)
        # Limit workers to avoid rate limiting
        max_workers = min(len(club_ids), 5)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_club, cid): cid for cid in club_ids}

            for future in as_completed(futures):
                club_id, result = future.result()

                if isinstance(result, StravaAuthError):
                    # Auth errors should fail the whole sync
                    raise result
                elif isinstance(result, Exception):
                    # Non-auth errors - log and continue
                    logger.warning(f"Failed to fetch events for club {club_id}: {result}")
                    errors.append((club_id, result))
                else:
                    all_events.extend(result)

        return all_events
