"""E2E tests for core service module.

These tests use actual HTTP servers and real requests - true black-box testing.
"""

import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
from club_calendar_core.service import ClubCalendarService
from pytest_httpx import HTTPXMock


def find_free_port() -> int:
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class TestClubCalendarService:
    """Tests for ClubCalendarService class."""

    def test_create_client_without_refresh_token(self):
        """Test _create_client raises ValueError when require_token=True but no token."""
        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        with pytest.raises(ValueError, match="Refresh token required"):
            service._create_client(require_token=True)

    def test_create_client_without_token_not_required(self):
        """Test _create_client succeeds when require_token=False."""
        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        # Should not raise
        client = service._create_client(require_token=False)
        assert client is not None
        client.close()

    def test_get_club_events_without_refresh_token(self, tmp_path):
        """Test get_club_events handles missing refresh token."""
        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        # This uses require_token=True by default
        with pytest.raises(ValueError, match="Refresh token required"):
            service.get_club_events([123])


class TestOAuthFlowE2E:
    """True E2E tests for OAuth flow - spins up actual servers."""

    def test_callback_missing_code_returns_400(self):
        """Test OAuth callback returns 400 when code parameter is missing.

        This is a true E2E test - we start the actual OAuth server and make
        real HTTP requests to verify the response.
        """
        port = find_free_port()
        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        result_holder = {"result": None}

        def run_oauth():
            result_holder["result"] = service.run_oauth_flow(
                port=port, timeout=3, open_browser=False
            )

        oauth_thread = threading.Thread(target=run_oauth)
        oauth_thread.start()

        # Wait for server to start
        time.sleep(0.3)

        # Send callback WITHOUT code parameter - should get 400
        try:
            urllib.request.urlopen(f"http://localhost:{port}/callback")
            pytest.fail("Expected 400 error")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = e.read().decode()
            assert "Club Calendar" in body
            assert "Missing authorization code" in body

        oauth_thread.join(timeout=5)

        # Flow should timeout since we didn't provide a valid code
        result = result_holder["result"]
        assert result is not None
        assert result.success is False

    def test_callback_with_error_returns_400(self):
        """Test OAuth callback handles error parameter from Strava."""
        port = find_free_port()
        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        result_holder = {"result": None}

        def run_oauth():
            result_holder["result"] = service.run_oauth_flow(
                port=port, timeout=3, open_browser=False
            )

        oauth_thread = threading.Thread(target=run_oauth)
        oauth_thread.start()

        time.sleep(0.3)

        # Send callback with error parameter (user denied access)
        try:
            url = f"http://localhost:{port}/callback?error=access_denied&error_description=User+denied"
            urllib.request.urlopen(url)
            pytest.fail("Expected 400 error")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = e.read().decode()
            assert "User denied" in body or "Error" in body

        oauth_thread.join(timeout=5)

        result = result_holder["result"]
        assert result is not None
        assert result.success is False
        assert "denied" in result.message.lower()

    def test_callback_unknown_path_returns_404(self):
        """Test OAuth server returns 404 for unknown paths."""
        port = find_free_port()
        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        result_holder = {"result": None}

        def run_oauth():
            result_holder["result"] = service.run_oauth_flow(
                port=port, timeout=2, open_browser=False
            )

        oauth_thread = threading.Thread(target=run_oauth)
        oauth_thread.start()

        time.sleep(0.3)

        # Send request to unknown path
        try:
            urllib.request.urlopen(f"http://localhost:{port}/unknown")
            pytest.fail("Expected 404 error")
        except urllib.error.HTTPError as e:
            assert e.code == 404

        oauth_thread.join(timeout=5)

    def test_callback_success_with_valid_code(self, httpx_mock: HTTPXMock):
        """Test OAuth callback succeeds with valid code and token exchange."""
        port = find_free_port()

        # Mock the token exchange endpoint
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            json={
                "access_token": "test_access",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
            },
        )

        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        result_holder = {"result": None}

        def run_oauth():
            result_holder["result"] = service.run_oauth_flow(
                port=port, timeout=5, open_browser=False
            )

        oauth_thread = threading.Thread(target=run_oauth)
        oauth_thread.start()

        time.sleep(0.3)

        # Send callback WITH valid code
        response = urllib.request.urlopen(f"http://localhost:{port}/callback?code=valid_auth_code")
        assert response.status == 200
        body = response.read().decode()
        assert "Club Calendar" in body
        assert "Authentication successful" in body

        oauth_thread.join(timeout=5)

        result = result_holder["result"]
        assert result is not None
        assert result.success is True
        assert result.refresh_token == "test_refresh_token"

    def test_callback_token_exchange_failure(self, httpx_mock: HTTPXMock):
        """Test OAuth callback handles token exchange failure."""
        port = find_free_port()

        # Mock token exchange to fail
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            status_code=400,
            json={"error": "invalid_code"},
        )

        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token=None,
        )

        result_holder = {"result": None}

        def run_oauth():
            result_holder["result"] = service.run_oauth_flow(
                port=port, timeout=5, open_browser=False
            )

        oauth_thread = threading.Thread(target=run_oauth)
        oauth_thread.start()

        time.sleep(0.3)

        # Send callback with code, but token exchange will fail
        response = urllib.request.urlopen(f"http://localhost:{port}/callback?code=invalid_code")
        # Response is 200 (callback received) but body shows error
        assert response.status == 200
        body = response.read().decode()
        assert "Club Calendar" in body
        assert "Authentication failed" in body

        oauth_thread.join(timeout=5)

        result = result_holder["result"]
        assert result is not None
        assert result.success is False


class TestFilterLocalClubs:
    """Tests for filter_local_clubs function."""

    def test_auto_detect_city_from_most_common(self):
        """Test auto-detecting city from most common club city."""
        from club_calendar_core.service import filter_local_clubs
        from club_calendar_core.strava import Club

        clubs = [
            Club(id=1, name="Club 1", member_count=50, city="Portland", state="OR", country="US"),
            Club(id=2, name="Club 2", member_count=30, city="Portland", state="OR", country="US"),
            Club(id=3, name="Club 3", member_count=20, city="Seattle", state="WA", country="US"),
        ]

        local, cities = filter_local_clubs(clubs)

        assert cities == ["Portland"]
        assert len(local) == 2
        assert all(c.city == "Portland" for c in local)

    def test_explicit_city_filter(self):
        """Test filtering with explicit city list."""
        from club_calendar_core.service import filter_local_clubs
        from club_calendar_core.strava import Club

        clubs = [
            Club(id=1, name="Club 1", member_count=50, city="Portland", state="OR", country="US"),
            Club(id=2, name="Club 2", member_count=30, city="Seattle", state="WA", country="US"),
        ]

        local, cities = filter_local_clubs(clubs, cities=["Seattle"])

        assert cities == ["Seattle"]
        assert len(local) == 1
        assert local[0].city == "Seattle"

    def test_no_cities_in_clubs(self):
        """Test when clubs have no city data."""
        from club_calendar_core.service import filter_local_clubs
        from club_calendar_core.strava import Club

        clubs = [
            Club(id=1, name="Club 1", member_count=50, city=None, state=None, country=None),
            Club(id=2, name="Club 2", member_count=30, city=None, state=None, country=None),
        ]

        local, cities = filter_local_clubs(clubs)

        assert cities == []
        assert len(local) == 0

    def test_max_members_filter(self):
        """Test filtering out mega-clubs by member count."""
        from club_calendar_core.service import filter_local_clubs
        from club_calendar_core.strava import Club

        clubs = [
            Club(
                id=1, name="Small Club", member_count=50, city="Portland", state="OR", country="US"
            ),
            Club(
                id=2,
                name="Huge Club",
                member_count=200000,
                city="Portland",
                state="OR",
                country="US",
            ),
        ]

        local, _ = filter_local_clubs(clubs, cities=["Portland"], max_members=1000)

        assert len(local) == 1
        assert local[0].name == "Small Club"


class TestTokenStoreIntegration:
    """Tests for TokenStore integration in service."""

    def test_refresh_token_getter_with_store(self):
        """Test refresh_token property reads from token store."""
        from unittest.mock import MagicMock

        mock_store = MagicMock()
        mock_store.get_refresh_token.return_value = "stored_token"

        service = ClubCalendarService(
            client_id="id",
            client_secret="secret",
            token_store=mock_store,
        )

        assert service.refresh_token == "stored_token"
        mock_store.get_refresh_token.assert_called_once()

    def test_refresh_token_setter_with_store(self):
        """Test refresh_token setter saves to token store."""
        from unittest.mock import MagicMock

        mock_store = MagicMock()

        service = ClubCalendarService(
            client_id="id",
            client_secret="secret",
            token_store=mock_store,
        )

        service.refresh_token = "new_token"

        mock_store.save_refresh_token.assert_called_once_with("new_token")
        assert service._refresh_token == "new_token"

    def test_refresh_token_setter_with_none_value(self):
        """Test refresh_token setter with None value doesn't save to store."""
        from unittest.mock import MagicMock

        mock_store = MagicMock()

        service = ClubCalendarService(
            client_id="id",
            client_secret="secret",
            token_store=mock_store,
        )

        service.refresh_token = None

        mock_store.save_refresh_token.assert_not_called()
        assert service._refresh_token is None


class TestServiceFilterLocalClubsMethod:
    """Tests for service.filter_local_clubs method (delegation)."""

    def test_filter_local_clubs_delegates_to_function(self):
        """Test that service method delegates to module function."""
        from club_calendar_core.strava import Club

        service = ClubCalendarService(client_id="id", client_secret="secret", refresh_token="token")

        clubs = [
            Club(id=1, name="Club", member_count=50, city="Portland", state="OR", country="US")
        ]
        local, cities = service.filter_local_clubs(clubs, cities=["Portland"])

        assert len(local) == 1
        assert cities == ["Portland"]


class TestGetClubs:
    """Tests for get_clubs method."""

    def test_get_clubs_returns_clubs(self, httpx_mock: HTTPXMock):
        """Test get_clubs fetches and returns clubs."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/oauth/token" in url:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "token",
                        "refresh_token": "refresh",
                        "expires_at": 9999999999,
                    },
                )
            if "/athlete/clubs" in url:
                return httpx.Response(
                    200,
                    json=[
                        {"id": 123, "name": "Test Club", "member_count": 50, "city": "Portland"},
                    ],
                )
            return httpx.Response(404)

        httpx_mock.add_callback(handler, is_reusable=True)

        service = ClubCalendarService(client_id="id", client_secret="secret", refresh_token="token")

        clubs = service.get_clubs()

        assert len(clubs) == 1
        assert clubs[0].name == "Test Club"
        assert clubs[0].city == "Portland"


class TestGetClubEvents:
    """Tests for get_club_events method."""

    def test_get_club_events_success(self, httpx_mock: HTTPXMock):
        """Test get_club_events fetches and returns events."""
        from datetime import datetime, timedelta

        import httpx

        future_date = datetime.now() + timedelta(days=7)
        future_iso = future_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/oauth/token" in url:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "token",
                        "refresh_token": "refresh",
                        "expires_at": 9999999999,
                    },
                )
            if "/group_events" in url:
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": 1,
                            "title": "Morning Ride",
                            "club_id": 123,
                            "upcoming_occurrences": [future_iso],
                        },
                    ],
                )
            return httpx.Response(404)

        httpx_mock.add_callback(handler, is_reusable=True)

        service = ClubCalendarService(client_id="id", client_secret="secret", refresh_token="token")

        events = service.get_club_events([123])

        assert len(events) == 1
        assert events[0].title == "Morning Ride"

    def test_get_club_events_auth_error_reraises(self, httpx_mock: HTTPXMock):
        """Test get_club_events re-raises auth errors."""
        import httpx
        from club_calendar_core.strava import StravaAuthError

        call_count = {"token": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/oauth/token" in url:
                call_count["token"] += 1
                if call_count["token"] == 1:
                    # First call succeeds (initial token)
                    return httpx.Response(
                        200,
                        json={
                            "access_token": "token",
                            "refresh_token": "refresh",
                            "expires_at": 9999999999,
                        },
                    )
                # Subsequent calls fail (token refresh fails)
                return httpx.Response(401, json={"error": "invalid_token"})
            if "/group_events" in url:
                # Return 401 to trigger auth error
                return httpx.Response(401, json={"error": "Unauthorized"})
            return httpx.Response(404)

        httpx_mock.add_callback(handler, is_reusable=True)

        service = ClubCalendarService(client_id="id", client_secret="secret", refresh_token="token")

        with pytest.raises(StravaAuthError):
            service.get_club_events([123])


class TestExchangeCodeExceptions:
    """Tests for exchange_code exception handling."""

    def test_exchange_code_generic_exception(self, httpx_mock: HTTPXMock):
        """Test exchange_code handles generic exceptions."""
        # Make httpx raise a connection error
        httpx_mock.add_exception(ConnectionError("Network failure"))

        service = ClubCalendarService(client_id="id", client_secret="secret", refresh_token=None)

        result = service.exchange_code("some_code")

        assert result.success is False
        assert "Network failure" in result.message


class TestOAuthWithBrowser:
    """Tests for OAuth flow with browser opening."""

    def test_oauth_flow_opens_browser(self, httpx_mock: HTTPXMock):
        """Test run_oauth_flow opens browser when open_browser=True."""
        from unittest.mock import patch

        port = find_free_port()

        # Mock token exchange
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at": 9999999999,
            },
        )

        service = ClubCalendarService(client_id="id", client_secret="secret", refresh_token=None)

        result_holder = {"result": None}
        browser_opened = {"url": None}

        def mock_open(url):
            browser_opened["url"] = url

        def run_oauth():
            with patch("webbrowser.open", side_effect=mock_open):
                result_holder["result"] = service.run_oauth_flow(
                    port=port, timeout=3, open_browser=True
                )

        oauth_thread = threading.Thread(target=run_oauth)
        oauth_thread.start()

        time.sleep(0.3)

        # Send callback to complete the flow
        try:
            urllib.request.urlopen(f"http://localhost:{port}/callback?code=test_code")
        except Exception:
            pass

        oauth_thread.join(timeout=5)

        # Verify browser was opened with correct URL
        assert browser_opened["url"] is not None
        assert "strava.com/oauth/authorize" in browser_opened["url"]
        assert "client_id=id" in browser_opened["url"]
