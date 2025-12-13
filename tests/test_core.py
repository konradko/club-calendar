"""E2E tests for core service module.

These tests use actual HTTP servers and real requests - true black-box testing.
"""

import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
from pytest_httpx import HTTPXMock

from club_calendar.core import ClubCalendarService


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
            assert "Missing code" in body

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
        response = urllib.request.urlopen(
            f"http://localhost:{port}/callback?code=valid_auth_code"
        )
        assert response.status == 200
        body = response.read().decode()
        assert "Success" in body

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
        response = urllib.request.urlopen(
            f"http://localhost:{port}/callback?code=invalid_code"
        )
        # Response is 200 (callback received) but body shows error
        assert response.status == 200
        body = response.read().decode()
        assert "Error" in body

        oauth_thread.join(timeout=5)

        result = result_holder["result"]
        assert result is not None
        assert result.success is False


class TestSyncErrorHandling:
    """Tests for sync error handling in core module."""

    def test_sync_to_files_handles_strava_error(self, httpx_mock: HTTPXMock, tmp_path):
        """Test sync_to_files catches StravaError and returns failure."""
        # Token exchange fails
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            status_code=401,
            json={"error": "invalid_token"},
        )

        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token="test_token",
        )

        result = service.sync_to_files([123], tmp_path)

        assert result.success is False
        assert "Invalid" in result.message or "expired" in result.message

    def test_sync_to_stdout_handles_strava_error(self, httpx_mock: HTTPXMock):
        """Test sync_to_stdout catches StravaError and returns failure."""
        # Token exchange fails
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            status_code=401,
            json={"error": "invalid_token"},
        )

        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token="test_token",
        )

        ics_data, result = service.sync_to_stdout([123])

        assert result.success is False
        assert ics_data == b""
        assert "Invalid" in result.message or "expired" in result.message


class TestSyncFileSystemE2E:
    """E2E tests for file system error handling."""

    def test_sync_to_files_handles_permission_error(self, httpx_mock: HTTPXMock, tmp_path):
        """Test sync_to_files handles file permission errors gracefully.

        True E2E test - creates a read-only directory to trigger actual OSError.
        """
        import os
        import stat

        # Mock successful API responses
        def handler(request):
            import httpx as httpx_mod

            url = str(request.url)
            if "/oauth/token" in url:
                return httpx_mod.Response(
                    200,
                    json={
                        "access_token": "t",
                        "refresh_token": "r",
                        "expires_at": 9999999999,
                    },
                )
            if "/group_events" in url:
                return httpx_mod.Response(
                    200,
                    json=[
                        {
                            "id": 1,
                            "title": "Test Event",
                            "upcoming_occurrences": ["2099-01-15T08:00:00Z"],
                            "club": {"name": "Test Club"},
                        }
                    ],
                )
            return httpx_mod.Response(404)

        httpx_mock.add_callback(handler, is_reusable=True)

        service = ClubCalendarService(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token="test_token",
        )

        # Create a read-only directory to trigger permission error
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, stat.S_IRUSR | stat.S_IXUSR)  # read + execute only

        try:
            result = service.sync_to_files([123], readonly_dir)

            assert result.success is False
            assert "File error" in result.message or "Permission" in result.message
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, stat.S_IRWXU)

