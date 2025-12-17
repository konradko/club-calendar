"""Strava API client for fetching club events."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from httpx import HTTPTransport

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3

# Production Strava URLs
DEFAULT_AUTH_URL = "https://www.strava.com/oauth/authorize"
DEFAULT_TOKEN_URL = "https://www.strava.com/oauth/token"
DEFAULT_API_URL = "https://www.strava.com/api/v3"


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
        api_url: Override API URL (for testing with mock server)
        token_url: Override token URL (for testing with mock server)
        auth_url: Override auth URL (for testing with mock server)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str | None = None,
        access_token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        api_url: str | None = None,
        token_url: str | None = None,
        auth_url: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token = access_token
        self._token_expires_at = 0
        # URLs with defaults
        self._api_url = (api_url.rstrip("/") if api_url else DEFAULT_API_URL).rstrip("/")
        self._token_url = token_url or DEFAULT_TOKEN_URL
        self._auth_url = auth_url or DEFAULT_AUTH_URL
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
        return f"{self._auth_url}?" + "&".join(f"{k}={v}" for k, v in params.items())

    def _process_token_response(self, data: dict) -> TokenResponse:
        """Process token response data and update internal state.

        Args:
            data: Token response data from Strava API

        Returns:
            TokenResponse with the token data
        """
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._token_expires_at = data["expires_at"]
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
        )

    def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for tokens."""
        response = self._http.post(
            self._token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        self._handle_response_errors(response)
        return self._process_token_response(response.json())

    def refresh_access_token(self) -> TokenResponse:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise StravaAuthError("No refresh token available")

        response = self._http.post(
            self._token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
        )
        self._handle_response_errors(response)
        return self._process_token_response(response.json())

    @property
    def refresh_token(self) -> str | None:
        """Get the current refresh token."""
        return self._refresh_token

    def _ensure_access_token(self) -> str:
        """Ensure we have a valid access token."""
        if self._access_token and self._token_expires_at > datetime.now(UTC).timestamp() + 60:
            return self._access_token
        if self._refresh_token:
            self.refresh_access_token()
            if self._access_token is None:
                raise StravaAuthError("Failed to obtain access token after refresh")
            return self._access_token
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
            f"{self._api_url}/{endpoint}",
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

    def get_all_club_events(
        self, club_ids: list[int]
    ) -> tuple[list[ClubEvent], list[tuple[int, Exception]]]:
        """Get events from multiple clubs concurrently.

        Uses a thread pool to fetch events from all clubs in parallel,
        significantly reducing total sync time for users with many clubs.

        Returns:
            Tuple of (events, errors) where errors is a list of (club_id, exception)
            tuples for any clubs that failed to fetch. Callers should check errors
            to determine if the sync was complete.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        all_events: list[ClubEvent] = []
        errors: list[tuple[int, Exception]] = []

        def fetch_club(club_id: int) -> tuple[int, list[ClubEvent] | Exception]:
            try:
                return (club_id, self.get_club_events(club_id))
            except (StravaError, httpx.HTTPError, httpx.TimeoutException) as e:
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
                    # Non-auth errors - log and continue with partial results
                    logger.warning(f"Failed to fetch events for club {club_id}: {result}")
                    errors.append((club_id, result))
                else:
                    all_events.extend(result)

        return all_events, errors
