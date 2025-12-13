"""Tests for service layer."""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from club_calendar.services import (
    fetch_club_events,
    fetch_clubs,
    get_local_clubs,
    save_club_ids_to_config,
    save_refresh_token_to_config,
)
from club_calendar.strava import Club


@pytest.fixture
def sample_clubs() -> list[Club]:
    """Sample clubs for testing."""
    return [
        Club(
            id=1, name="Local Club 1", member_count=100, city="Portland", state="OR", country="US"
        ),
        Club(id=2, name="Local Club 2", member_count=50, city="Portland", state="OR", country="US"),
        Club(id=3, name="Seattle Club", member_count=75, city="Seattle", state="WA", country="US"),
        Club(
            id=4, name="Mega Club", member_count=500000, city="Portland", state="OR", country="US"
        ),
        Club(id=5, name="No City Club", member_count=25, city=None, state=None, country=None),
    ]


def test_get_local_clubs_auto_detect(sample_clubs):
    """Test auto-detection of local city."""
    local, cities = get_local_clubs(sample_clubs)

    assert cities == ["Portland"]
    assert len(local) == 2  # Excludes mega club and Seattle
    assert all(c.city == "Portland" for c in local)
    assert all(c.member_count < 100000 for c in local)


def test_get_local_clubs_explicit_cities(sample_clubs):
    """Test explicit city filter."""
    local, cities = get_local_clubs(sample_clubs, cities=["Seattle"])

    assert cities == ["Seattle"]
    assert len(local) == 1
    assert local[0].name == "Seattle Club"


def test_get_local_clubs_multiple_cities(sample_clubs):
    """Test filtering by multiple cities."""
    local, cities = get_local_clubs(sample_clubs, cities=["Portland", "Seattle"])

    assert cities == ["Portland", "Seattle"]
    assert len(local) == 3  # 2 Portland + 1 Seattle (excludes mega club)


def test_get_local_clubs_no_cities():
    """Test with clubs that have no city."""
    clubs = [
        Club(id=1, name="No City 1", member_count=10, city=None, state=None, country=None),
        Club(id=2, name="No City 2", member_count=20, city=None, state=None, country=None),
    ]
    local, cities = get_local_clubs(clubs)

    assert cities == []
    assert local == []


def test_get_local_clubs_custom_max_members(sample_clubs):
    """Test custom max_members threshold."""
    local, cities = get_local_clubs(sample_clubs, max_members=1000000)

    # Now includes the mega club
    assert len(local) == 3
    assert any(c.name == "Mega Club" for c in local)


def test_save_club_ids_to_config(tmp_path, monkeypatch):
    """Test saving club IDs to config."""
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("club_calendar.config.get_config_file", lambda: config_file)

    save_club_ids_to_config([123, 456, 789])

    import json

    config = json.loads(config_file.read_text())
    assert config["club_ids"] == [123, 456, 789]


def test_save_refresh_token_to_config(mock_keychain):
    """Test saving refresh token to keychain."""
    save_refresh_token_to_config("test_token_123")

    # Refresh token is stored in keychain, not JSON config
    assert mock_keychain["club-calendar:refresh_token"] == "test_token_123"


def test_fetch_club_events(httpx_mock: HTTPXMock):
    """Test fetch_club_events backwards-compat wrapper."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/oauth/token" in url:
            return httpx.Response(
                200,
                json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999},
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

    httpx_mock.add_callback(handler, is_reusable=True)

    events = fetch_club_events(
        client_id="test_id",
        client_secret="test_secret",
        refresh_token="test_token",
        club_ids=[123],
    )

    assert len(events) == 1
    assert events[0].title == "Test Event"


def test_fetch_clubs(httpx_mock: HTTPXMock):
    """Test fetch_clubs backwards-compat wrapper."""

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
                    {"id": 123, "name": "Test Club", "member_count": 50},
                ],
            )
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True)

    clubs = fetch_clubs(
        client_id="test_id",
        client_secret="test_secret",
        refresh_token="test_token",
    )

    assert len(clubs) == 1
    assert clubs[0].name == "Test Club"
