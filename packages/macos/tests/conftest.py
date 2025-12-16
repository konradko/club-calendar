"""Shared test fixtures for macOS package."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pytest_httpx import HTTPXMock


# Mock token store for all tests (autouse)
@pytest.fixture(autouse=True)
def mock_token_store():
    """Mock token store to return test refresh token."""
    mock_store = MagicMock()
    mock_store.get_refresh_token.return_value = "test_refresh_token"
    mock_store.get_access_token.return_value = None

    with patch("club_calendar_macos.menubar.get_token_store", return_value=mock_store):
        yield mock_store


# Mock config and logs directories for all tests (autouse)
@pytest.fixture(autouse=True)
def mock_config_file(tmp_path: Path):
    """Mock config/logs paths for all tests to ensure isolation."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.yaml"

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(exist_ok=True)

    with (
        patch("club_calendar_macos.config.get_config_file", return_value=config_file),
        patch("club_calendar_macos.config.get_config_dir", return_value=config_dir),
        patch("club_calendar_macos.config.get_logs_dir", return_value=logs_dir),
    ):
        yield config_file


# Mock external calls (webbrowser, subprocess) for all tests (autouse)
@pytest.fixture(autouse=True)
def mock_external_calls():
    """Mock webbrowser and subprocess to prevent real external calls."""
    with (
        patch("webbrowser.open") as mock_browser,
        patch("subprocess.run") as mock_subprocess,
    ):
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="")
        yield {"webbrowser": mock_browser, "subprocess": mock_subprocess}


# Sample API responses (duplicated across packages due to per-package pytest roots)
CLUBS_RESPONSE = [
    {
        "id": 123,
        "name": "Test Cycling Club",
        "member_count": 50,
        "city": "Portland",
        "state": "Oregon",
        "country": "United States",
    },
    {
        "id": 456,
        "name": "Running Group",
        "member_count": 25,
        "city": "Seattle",
        "state": "Washington",
        "country": "United States",
    },
]

EVENTS_RESPONSE = [
    {
        "id": 1001,
        "title": "Saturday Morning Ride",
        "description": "Casual 30 mile loop through the hills",
        "upcoming_occurrences": ["2099-01-15T08:00:00Z"],
        "address": "Pioneer Courthouse Square, Portland, OR",
        "route_id": 789,
        "organizing_athlete": {"firstname": "Alice"},
        "club": {"name": "Test Cycling Club"},
    },
    {
        "id": 1002,
        "title": "Recovery Spin",
        "description": None,
        "upcoming_occurrences": ["2099-01-17T18:00:00Z"],
        "address": None,
        "route_id": None,
        "organizing_athlete": None,
        "club": {"name": "Test Cycling Club"},
    },
]

TOKEN_RESPONSE = {
    "access_token": "test_access_token",
    "refresh_token": "test_refresh_token",
    "expires_at": 9999999999,
    "token_type": "Bearer",
}


@pytest.fixture
def mock_strava_api(httpx_mock: HTTPXMock) -> HTTPXMock:
    """Mock all Strava API endpoints."""

    def strava_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and "/oauth/token" in url:
            return httpx.Response(200, json=TOKEN_RESPONSE)
        if "/athlete/clubs" in url:
            return httpx.Response(200, json=CLUBS_RESPONSE)
        if "/group_events" in url:
            return httpx.Response(200, json=EVENTS_RESPONSE)
        return httpx.Response(404, text="Not found")

    httpx_mock.add_callback(strava_handler, is_reusable=True, is_optional=True)
    return httpx_mock


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Temporary output directory for tests."""
    output = tmp_path / "output"
    output.mkdir()
    return output
