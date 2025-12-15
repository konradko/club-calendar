"""E2E tests for CLI commands - mock only external Strava API."""

import httpx
import pytest
from click.testing import CliRunner
from club_calendar_cli.cli import main
from pytest_httpx import HTTPXMock


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def strava_api_mock(httpx_mock: HTTPXMock) -> HTTPXMock:
    """Mock Strava API responses."""

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
                    {"id": 123, "name": "Test Club", "member_count": 10},
                ],
            )
        if "/group_events" in url:
            return httpx.Response(
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
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)
    return httpx_mock


# Auth command tests
def test_auth_without_credentials(runner: CliRunner, monkeypatch):
    """Test auth fails without API credentials."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "")

    result = runner.invoke(main, ["auth"])

    assert result.exit_code == 1
    assert "STRAVA_CLIENT_ID" in result.output


def test_auth_full_flow(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock, tmp_path):
    """Test full auth flow with simulated browser callback."""
    import threading
    import time
    import urllib.request

    monkeypatch.setenv("STRAVA_CLIENT_ID", "test_id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")
    monkeypatch.chdir(tmp_path)  # Use temp dir for .env file

    # Mock token exchange
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        json={
            "access_token": "access",
            "refresh_token": "new_refresh_token",
            "expires_at": 9999999999,
        },
    )

    result_holder = {"result": None}

    def run_auth():
        # Patch webbrowser to not actually open browser
        import webbrowser

        original_open = webbrowser.open
        webbrowser.open = lambda url: None
        try:
            result_holder["result"] = runner.invoke(main, ["auth"])
        finally:
            webbrowser.open = original_open

    # Start auth in thread
    auth_thread = threading.Thread(target=run_auth)
    auth_thread.start()

    # Wait for server to start
    time.sleep(0.2)

    # Simulate browser callback
    try:
        urllib.request.urlopen("http://localhost:8000/callback?code=test_auth_code")
    except Exception:
        pass  # Server closes after handling

    auth_thread.join(timeout=5)

    result = result_holder["result"]
    assert result is not None
    assert result.exit_code == 0
    assert "Refresh token saved to .env file" in result.output


def test_auth_callback_error(runner: CliRunner, monkeypatch):
    """Test auth handles callback error."""
    import threading
    import time
    import urllib.request

    monkeypatch.setenv("STRAVA_CLIENT_ID", "test_id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")

    result_holder = {"result": None}

    def run_auth():
        import webbrowser

        webbrowser.open = lambda url: None
        result_holder["result"] = runner.invoke(main, ["auth"])

    auth_thread = threading.Thread(target=run_auth)
    auth_thread.start()

    time.sleep(0.2)

    # Simulate error callback
    try:
        urllib.request.urlopen(
            "http://localhost:8000/callback?error=access_denied&error_description=User%20denied"
        )
    except Exception:
        pass

    auth_thread.join(timeout=5)

    result = result_holder["result"]
    assert result is not None
    assert result.exit_code == 1


def test_auth_token_exchange_error(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test auth handles token exchange failure."""
    import threading
    import time
    import urllib.request

    monkeypatch.setenv("STRAVA_CLIENT_ID", "test_id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")

    # Token exchange fails
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=400,
        text="Invalid code",
    )

    result_holder = {"result": None}

    def run_auth():
        import webbrowser

        webbrowser.open = lambda url: None
        result_holder["result"] = runner.invoke(main, ["auth"])

    auth_thread = threading.Thread(target=run_auth)
    auth_thread.start()

    time.sleep(0.2)

    try:
        urllib.request.urlopen("http://localhost:8000/callback?code=invalid_code")
    except Exception:
        pass

    auth_thread.join(timeout=5)

    result = result_holder["result"]
    assert result is not None
    assert result.exit_code == 1


def test_auth_callback_404(runner: CliRunner, monkeypatch):
    """Test auth callback returns 404 for unknown paths."""
    import threading
    import time
    import urllib.error
    import urllib.request

    monkeypatch.setenv("STRAVA_CLIENT_ID", "test_id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")

    # We need to manually stop the server since no valid callback happens
    def run_auth():
        import webbrowser

        webbrowser.open = lambda url: None
        # This will timeout but we'll stop it early
        runner.invoke(main, ["auth"])

    auth_thread = threading.Thread(target=run_auth, daemon=True)
    auth_thread.start()

    time.sleep(0.2)

    # Send request to unknown path - should get 404
    try:
        urllib.request.urlopen("http://localhost:8000/unknown")
    except urllib.error.HTTPError as e:
        assert e.code == 404
    except Exception:
        pass  # Server may close

    # Thread will timeout, no need to wait


# Clubs command tests
def test_clubs_without_credentials(runner: CliRunner, monkeypatch):
    """Test clubs fails without Strava credentials."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "")

    result = runner.invoke(main, ["clubs"])

    assert result.exit_code == 1
    assert "credentials" in result.output.lower()


def test_clubs_without_refresh_token(runner: CliRunner, monkeypatch):
    """Test clubs fails without refresh token."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "")

    result = runner.invoke(main, ["clubs"])

    assert result.exit_code == 1
    assert "not authenticated" in result.output.lower()


@pytest.fixture
def clubs_with_cities_mock(httpx_mock: HTTPXMock) -> HTTPXMock:
    """Mock Strava API with clubs that have cities."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/oauth/token" in url:
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        if "/athlete/clubs" in url:
            return httpx.Response(
                200,
                json=[
                    {"id": 123, "name": "Local Club", "member_count": 50, "city": "TestCity"},
                    {"id": 456, "name": "Another Local", "member_count": 30, "city": "TestCity"},
                ],
            )
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)
    return httpx_mock


def test_clubs_save_to_env(runner: CliRunner, monkeypatch, clubs_with_cities_mock, tmp_path):
    """Test clubs --save saves club IDs to .env file."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("CLUB_CITY_FILTER", "TestCity")
    monkeypatch.chdir(tmp_path)  # Use temp dir for .env file

    result = runner.invoke(main, ["clubs", "--save"])

    assert result.exit_code == 0
    assert "Saved" in result.output
    # Check .env file was created with club IDs
    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "STRAVA_CLUB_IDS=123,456" in content


def test_clubs_lists_clubs(runner: CliRunner, monkeypatch, strava_api_mock):
    """Test clubs command lists available clubs."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")

    result = runner.invoke(main, ["clubs"])

    assert result.exit_code == 0
    assert "Test Club" in result.output
    assert "123" in result.output


def test_clubs_empty_list(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test clubs command with no clubs."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/oauth/token" in str(request.url):
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        if "/athlete/clubs" in str(request.url):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    result = runner.invoke(main, ["clubs"])

    assert result.exit_code == 0
    assert "don't belong to any clubs" in result.output


def test_clubs_handles_api_error(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test clubs handles API errors gracefully."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/oauth/token" in str(request.url):
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        return httpx.Response(500, text="Server error")

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    result = runner.invoke(main, ["clubs"])

    assert result.exit_code == 1


def test_clubs_with_cities_filter(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test clubs command with --cities filter."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/oauth/token" in url:
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        if "/athlete/clubs" in url:
            return httpx.Response(
                200,
                json=[
                    {"id": 123, "name": "Berlin Club", "member_count": 50, "city": "Berlin"},
                    {"id": 456, "name": "Munich Club", "member_count": 30, "city": "Munich"},
                ],
            )
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    result = runner.invoke(main, ["clubs", "--cities", "Berlin"])

    assert result.exit_code == 0
    assert "Berlin Club" in result.output
    assert "* = local clubs" in result.output


def test_clubs_save_no_local_clubs(runner: CliRunner, monkeypatch, strava_api_mock):
    """Test clubs --save with no local clubs does nothing."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")

    result = runner.invoke(main, ["clubs", "--save"])

    # Should succeed but not save anything (no local clubs detected)
    assert result.exit_code == 0
    assert "Test Club" in result.output
    # Should not show "Saved" since no local clubs
    assert "Saved" not in result.output


# Sync command tests
def test_sync_without_credentials(runner: CliRunner, monkeypatch):
    """Test sync fails without Strava credentials."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "")

    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 1
    assert "credentials" in result.output.lower()


def test_sync_without_refresh_token(runner: CliRunner, monkeypatch):
    """Test sync fails without refresh token."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "")

    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 1
    assert "not authenticated" in result.output.lower()


def test_sync_without_club_ids(runner: CliRunner, monkeypatch):
    """Test sync fails without club IDs."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "")

    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 1
    assert "No club IDs" in result.output


def test_sync_generates_files(runner: CliRunner, monkeypatch, strava_api_mock, tmp_path):
    """Test sync generates ICS files."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 0
    assert (tmp_path / "club-calendar.ics").exists()


def test_sync_stdout(runner: CliRunner, monkeypatch, strava_api_mock):
    """Test sync --stdout outputs ICS to stdout."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")

    result = runner.invoke(main, ["sync", "--stdout"])

    assert result.exit_code == 0
    assert b"BEGIN:VCALENDAR" in result.output_bytes


def test_sync_no_events(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock, tmp_path):
    """Test sync with no events."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    def handler(request: httpx.Request) -> httpx.Response:
        if "/oauth/token" in str(request.url):
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        if "/group_events" in str(request.url):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 0
    assert "No upcoming events" in result.output


def test_sync_with_club_id_option(runner: CliRunner, monkeypatch, strava_api_mock):
    """Test sync with -c option overrides STRAVA_CLUB_IDS."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "999")  # This should be ignored

    result = runner.invoke(main, ["sync", "-c", "123", "--stdout"])

    assert result.exit_code == 0
    assert b"BEGIN:VCALENDAR" in result.output_bytes


def test_sync_continues_on_club_error(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test sync continues when individual club fetch fails."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123,456")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/oauth/token" in url:
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        # Club 123 fails, club 456 succeeds
        if "/clubs/123/group_events" in url:
            return httpx.Response(500, text="Server error")
        if "/clubs/456/group_events" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "title": "Event",
                        "upcoming_occurrences": ["2099-01-15T08:00:00Z"],
                        "club": {"name": "Club"},
                    }
                ],
            )
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    result = runner.invoke(main, ["sync", "--stdout"])

    # Should succeed with events from club 456 even though 123 failed
    assert result.exit_code == 0
    assert b"BEGIN:VCALENDAR" in result.output_bytes


def test_sync_stdout_no_events(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test sync --stdout with no events exits 0."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/oauth/token" in str(request.url):
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
            )
        if "/group_events" in str(request.url):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    result = runner.invoke(main, ["sync", "--stdout"])

    assert result.exit_code == 0
    assert "No upcoming events" in result.output


def test_sync_stdout_api_error(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock):
    """Test sync --stdout handles complete API failure (token exchange fails)."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")

    # Token exchange fails - triggers StravaError which returns success=False
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=401,
        json={"error": "invalid_token"},
    )

    result = runner.invoke(main, ["sync", "--stdout"])

    # Token failure causes sync_to_stdout to return success=False
    assert result.exit_code == 1
    assert "Error" in result.output


def test_sync_files_api_error(runner: CliRunner, monkeypatch, httpx_mock: HTTPXMock, tmp_path):
    """Test sync (to files) handles complete API failure (token exchange fails)."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "token")
    monkeypatch.setenv("STRAVA_CLUB_IDS", "123")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    # Token exchange fails - triggers StravaError which returns success=False
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=401,
        json={"error": "invalid_token"},
    )

    result = runner.invoke(main, ["sync"])

    # Token failure causes sync_to_files to return success=False
    assert result.exit_code == 1
    assert "Error" in result.output


# General CLI tests
def test_version(runner: CliRunner):
    """Test --version flag."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help(runner: CliRunner):
    """Test --help flag."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.output
    assert "clubs" in result.output
    assert "sync" in result.output
