"""Tests for Strava API client."""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from club_calendar.core.strava import (
    StravaAuthError,
    StravaClient,
    StravaError,
    StravaRateLimitError,
)


@pytest.fixture
def client() -> StravaClient:
    """Create a Strava client for testing."""
    return StravaClient(
        client_id="test_id",
        client_secret="test_secret",
        refresh_token="test_refresh",
    )


def test_get_authorization_url(client: StravaClient):
    """Test OAuth authorization URL generation."""
    url = client.get_authorization_url()
    assert "https://www.strava.com/oauth/authorize" in url
    assert "client_id=test_id" in url
    assert "response_type=code" in url
    assert "scope=read" in url


def test_get_authorization_url_custom_redirect(client: StravaClient):
    """Test OAuth URL with custom redirect."""
    url = client.get_authorization_url(redirect_uri="http://localhost:9000/cb")
    assert "redirect_uri=http://localhost:9000/cb" in url


def test_exchange_code(client: StravaClient, httpx_mock: HTTPXMock):
    """Test exchanging authorization code for tokens."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        json={
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_at": 9999999999,
        },
    )

    tokens = client.exchange_code("auth_code_123")

    assert tokens.access_token == "new_access"
    assert tokens.refresh_token == "new_refresh"
    assert client.refresh_token == "new_refresh"


def test_refresh_access_token(client: StravaClient, httpx_mock: HTTPXMock):
    """Test refreshing access token."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        json={
            "access_token": "refreshed_access",
            "refresh_token": "refreshed_refresh",
            "expires_at": 9999999999,
        },
    )

    tokens = client.refresh_access_token()

    assert tokens.access_token == "refreshed_access"
    assert client.refresh_token == "refreshed_refresh"


def test_refresh_without_token_raises():
    """Test that refresh fails without a refresh token."""
    client = StravaClient(client_id="id", client_secret="secret")

    with pytest.raises(StravaAuthError, match="No refresh token"):
        client.refresh_access_token()


def test_ensure_access_token_without_any_token():
    """Test that _ensure_access_token fails without tokens."""
    client = StravaClient(client_id="id", client_secret="secret")

    with pytest.raises(StravaAuthError, match="No valid access token"):
        client._ensure_access_token()


def test_handle_401_error(client: StravaClient, httpx_mock: HTTPXMock):
    """Test handling of 401 unauthorized errors."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=401,
    )

    with pytest.raises(StravaAuthError, match="Invalid or expired"):
        client.refresh_access_token()


def test_handle_403_error(client: StravaClient, httpx_mock: HTTPXMock):
    """Test handling of 403 forbidden errors."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=403,
    )

    with pytest.raises(StravaAuthError, match="Access forbidden"):
        client.refresh_access_token()


def test_handle_429_rate_limit(client: StravaClient, httpx_mock: HTTPXMock):
    """Test handling of 429 rate limit errors."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=429,
    )

    with pytest.raises(StravaRateLimitError, match="Rate limit"):
        client.refresh_access_token()


def test_handle_generic_error(client: StravaClient, httpx_mock: HTTPXMock):
    """Test handling of generic API errors."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        status_code=500,
        text="Internal Server Error",
    )

    with pytest.raises(StravaError, match="API error 500"):
        client.refresh_access_token()


def test_context_manager(httpx_mock: HTTPXMock):
    """Test using client as context manager."""
    httpx_mock.add_response(
        url="https://www.strava.com/oauth/token",
        method="POST",
        json={
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 9999999999,
        },
    )

    with StravaClient("id", "secret", refresh_token="token") as client:
        client.refresh_access_token()
    # Client should be closed after context


def test_get_club_events_filters_past_events(httpx_mock: HTTPXMock):
    """Test that past events are filtered out."""

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
                        "title": "Past Event",
                        "upcoming_occurrences": ["2020-01-15T08:00:00Z"],
                        "club": {"name": "Club"},
                    },
                    {
                        "id": 2,
                        "title": "Future Event",
                        "upcoming_occurrences": ["2099-01-15T08:00:00Z"],
                        "club": {"name": "Club"},
                    },
                ],
            )
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True, is_optional=True)

    with StravaClient("id", "secret", refresh_token="token") as client:
        events = client.get_club_events(123)

    # Only future event should be returned
    assert len(events) == 1
    assert events[0].title == "Future Event"


def test_get_all_club_events_handles_errors(httpx_mock: HTTPXMock):
    """Test that get_all_club_events continues on individual club errors."""

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

    with StravaClient("id", "secret", refresh_token="token") as client:
        events = client.get_all_club_events([123, 456])

    # Should get events from club 456 even though 123 failed
    assert len(events) == 1
    assert events[0].title == "Event"
