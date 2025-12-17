"""Core service for Club Calendar - encapsulates all business logic."""

import json
import logging
from collections import Counter
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

import httpx

from club_calendar.core.strava import Club, ClubEvent, StravaClient, StravaError, TokenResponse

logger = logging.getLogger(__name__)


@dataclass
class OAuthResult:
    """Result of OAuth flow."""

    success: bool
    message: str
    refresh_token: str | None = None


def filter_local_clubs(
    clubs: list[Club],
    cities: list[str] | None = None,
    max_members: int = 100000,
) -> tuple[list[Club], list[str]]:
    """Filter clubs to local ones based on city.

    This is a pure function - no side effects, no dependencies.

    Args:
        clubs: List of all clubs
        cities: Explicit city filter, or None to auto-detect from most common
        max_members: Maximum member count (filters out mega-clubs)

    Returns:
        Tuple of (filtered clubs, cities used for filtering)
    """
    # Auto-detect most common city if not specified
    if not cities:
        all_cities = [c.city for c in clubs if c.city]
        if all_cities:
            cities = [Counter(all_cities).most_common(1)[0][0]]
        else:
            cities = []

    # Filter by city and member count
    local = [c for c in clubs if c.city in cities and c.member_count < max_members]
    return local, cities


class ClubCalendarService:
    """Main service for Club Calendar operations.

    This service encapsulates all business logic and can be used by
    both the CLI and menubar apps. Dependencies are injected via constructor.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str | None = None,
        api_url: str | None = None,
        token_url: str | None = None,
        auth_url: str | None = None,
    ):
        """Initialize the service.

        Args:
            client_id: Strava API client ID
            client_secret: Strava API client secret
            refresh_token: OAuth refresh token
            api_url: Override Strava API URL (for testing)
            token_url: Override Strava token URL (for testing)
            auth_url: Override Strava auth URL (for testing)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self._refresh_token = refresh_token
        self._api_url = api_url
        self._token_url = token_url
        self._auth_url = auth_url

    @property
    def refresh_token(self) -> str | None:
        """Get the current refresh token."""
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        """Set the refresh token."""
        self._refresh_token = value

    def _create_client(self, require_token: bool = True) -> StravaClient:
        """Create a Strava client instance.

        Args:
            require_token: Whether refresh token is required

        Returns:
            Configured StravaClient

        Raises:
            ValueError: If token required but not set
        """
        token = self.refresh_token
        if require_token and not token:
            raise ValueError("Refresh token required but not set")

        return StravaClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=token,
            api_url=self._api_url,
            token_url=self._token_url,
            auth_url=self._auth_url,
        )

    # =========================================================================
    # OAuth Operations
    # =========================================================================

    def get_authorization_url(self, redirect_uri: str = "http://localhost:8000/callback") -> str:
        """Get OAuth authorization URL for user to visit.

        Args:
            redirect_uri: Where Strava should redirect after auth

        Returns:
            Authorization URL to open in browser
        """
        client = self._create_client(require_token=False)
        try:
            return client.get_authorization_url(redirect_uri)
        finally:
            client.close()

    def exchange_code(self, code: str) -> OAuthResult:
        """Exchange authorization code for refresh token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            OAuthResult with success status and refresh token
        """
        client = self._create_client(require_token=False)
        try:
            tokens: TokenResponse = client.exchange_code(code)
            self.refresh_token = tokens.refresh_token
            return OAuthResult(
                success=True,
                message="Authentication complete",
                refresh_token=tokens.refresh_token,
            )
        except StravaError as e:
            logger.error(f"OAuth exchange failed: {e}")
            return OAuthResult(success=False, message=str(e))
        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as e:
            logger.error(f"OAuth exchange error: {e}")
            return OAuthResult(success=False, message=str(e)[:100])
        except Exception as e:
            # Catch any unexpected errors
            logger.error(f"OAuth exchange error (unexpected): {e}")
            return OAuthResult(success=False, message=str(e)[:100])
        finally:
            client.close()

    def run_oauth_flow(
        self,
        redirect_uri: str = "http://localhost:8000/callback",
        port: int = 8000,
        timeout: float = 120,
        open_browser: bool = True,
    ) -> OAuthResult:
        """Run complete OAuth flow with callback server.

        Args:
            redirect_uri: OAuth redirect URI
            port: Port for callback server
            timeout: Timeout in seconds for waiting for callback
            open_browser: Whether to automatically open browser

        Returns:
            OAuthResult with success status and refresh token
        """
        import webbrowser

        auth_url = self.get_authorization_url(redirect_uri)
        logger.info(f"Starting OAuth flow, redirect_uri={redirect_uri}")

        # Captured values from callback
        callback_result: OAuthResult | None = None

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(handler_self) -> None:  # noqa: N802, N805
                nonlocal callback_result
                parsed = urlparse(handler_self.path)
                params = parse_qs(parsed.query)

                if parsed.path == "/callback":
                    if "code" in params:
                        code = params["code"][0]
                        callback_result = self.exchange_code(code)
                        handler_self.send_response(200)
                        handler_self.send_header("Content-type", "text/html")
                        handler_self.end_headers()
                        if callback_result.success:
                            handler_self.wfile.write(
                                b"<html><body>"
                                b"<h1>Club Calendar</h1>"
                                b"<p><strong>Authentication successful!</strong></p>"
                                b"<p>You can close this window.</p>"
                                b"</body></html>"
                            )
                        else:
                            msg = callback_result.message
                            handler_self.wfile.write(
                                f"<html><body>"
                                f"<h1>Club Calendar</h1>"
                                f"<p><strong>Authentication failed</strong></p>"
                                f"<p>{msg}</p>"
                                f"</body></html>".encode()
                            )
                    elif "error" in params:
                        error_msg = params.get("error_description", params["error"])[0]
                        callback_result = OAuthResult(success=False, message=error_msg)
                        handler_self.send_response(400)
                        handler_self.send_header("Content-type", "text/html")
                        handler_self.end_headers()
                        handler_self.wfile.write(
                            f"<html><body>"
                            f"<h1>Club Calendar</h1>"
                            f"<p><strong>Authentication failed</strong></p>"
                            f"<p>{error_msg}</p>"
                            f"</body></html>".encode()
                        )
                    else:
                        handler_self.send_response(400)
                        handler_self.send_header("Content-type", "text/html")
                        handler_self.end_headers()
                        handler_self.wfile.write(
                            b"<html><body>"
                            b"<h1>Club Calendar</h1>"
                            b"<p><strong>Authentication failed</strong></p>"
                            b"<p>Missing authorization code</p>"
                            b"</body></html>"
                        )
                else:
                    handler_self.send_response(404)
                    handler_self.end_headers()

            def log_message(handler_self, format: str, *args: object) -> None:  # noqa: N805
                pass  # Suppress HTTP server logs

        # Start callback server
        server = HTTPServer(("localhost", port), CallbackHandler)
        server.timeout = timeout
        server_thread = Thread(target=server.handle_request)
        server_thread.start()

        # Open browser
        if open_browser:
            webbrowser.open(auth_url)

        # Wait for callback
        server_thread.join(timeout=timeout)
        server.server_close()

        if callback_result:
            return callback_result
        return OAuthResult(success=False, message="OAuth callback timed out")

    # =========================================================================
    # Club Operations
    # =========================================================================

    def get_clubs(self) -> list[Club]:
        """Fetch clubs the user belongs to.

        Returns:
            List of clubs

        Raises:
            StravaError: On API errors
        """
        with self._create_client() as client:
            return client.get_athlete_clubs()

    # =========================================================================
    # Event Operations
    # =========================================================================

    def get_club_events(self, club_ids: list[int]) -> list[ClubEvent]:
        """Fetch events for given clubs.

        Args:
            club_ids: List of club IDs to fetch events for

        Returns:
            List of club events

        Raises:
            StravaError: On API errors
        """
        with self._create_client() as client:
            return client.get_all_club_events(club_ids)
