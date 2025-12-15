"""Shared test fixtures for core package."""

from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

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
