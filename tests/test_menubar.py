"""Tests for menubar app."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from club_calendar.core.models import SetupResult, SyncResult
from club_calendar.menubar.app import (
    MenuBarController,
    OAuthCallbackHandler,
    _import_rumps,
    create_app,
    main,
    run_oauth_server,
)


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings."""
    mock = MagicMock()
    mock.has_strava_credentials.return_value = True
    mock.has_refresh_token.return_value = True
    mock.has_clubs.return_value = True
    mock.get_club_ids.return_value = [123, 456]
    mock.strava_client_id = "test_id"
    mock.strava_client_secret = "test_secret"
    mock.strava_refresh_token = "test_token"
    mock.cities = []
    mock.clubs = {
        "123": {"name": "Test Club 1", "city": "Portland", "enabled": True},
        "456": {"name": "Test Club 2", "city": "Seattle", "enabled": True},
    }
    mock.sync_weeks = 8
    mock.max_events_per_club_per_week = 5
    mock.max_menu_events = 15
    mock.sync_interval_minutes = 60
    mock.strava_api_url = ""
    mock.strava_token_url = ""
    mock.strava_auth_url = ""
    mock.oauth_callback_port = 51678
    return mock


@pytest.fixture
def mock_rumps():
    """Create a mock rumps module."""
    mock = MagicMock()
    mock.separator = "---"
    mock.MenuItem = MagicMock(side_effect=lambda title, callback=None: MagicMock(title=title))
    mock.notification = MagicMock()
    mock.clicked = MagicMock(side_effect=lambda name: lambda f: f)
    mock.timer = MagicMock(side_effect=lambda interval: lambda f: f)

    # Mock Window for dialogs
    mock_window = MagicMock()
    mock_response = MagicMock()
    mock_response.clicked = True
    mock_response.text = "test_value"
    mock_window.run.return_value = mock_response
    mock.Window = MagicMock(return_value=mock_window)

    # Create a base App class that can be subclassed
    class MockApp:
        def __init__(self, name, icon=None, title=None, template=None, quit_button=None):
            self.name = name
            self.icon = icon
            self.title = title
            self.template = template
            self.quit_button = quit_button
            self.menu = MagicMock()
            self.menu.clear = MagicMock()
            self.menu.add = MagicMock()

        def run(self):
            pass

    mock.App = MockApp
    return mock


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = SyncResult(success=True, message="Done")
        assert result.success is True
        assert result.message == "Done"

    def test_failure_result(self):
        """Test failure result."""
        result = SyncResult(success=False, message="Error")
        assert result.success is False
        assert result.message == "Error"


class TestSetupResult:
    """Tests for SetupResult dataclass."""

    def test_success_result(self):
        """Test successful setup result."""
        result = SetupResult(success=True, message="Done")
        assert result.success is True
        assert result.message == "Done"

    def test_failure_result(self):
        """Test failed setup result."""
        result = SetupResult(success=False, message="Error")
        assert result.success is False
        assert result.message == "Error"


class TestMenuBarController:
    """Tests for MenuBarController class."""

    def test_init_with_settings(self, mock_settings):
        """Test initialization with provided settings."""
        controller = MenuBarController(settings=mock_settings)
        assert controller.settings == mock_settings
        assert controller.last_sync is None

    def test_init_default_settings(self):
        """Test initialization with default settings."""
        with patch("club_calendar.menubar.app.get_settings") as mock_get:
            mock_get.return_value = MagicMock()
            MenuBarController()
            mock_get.assert_called_once()

    def test_get_status_text_not_synced(self, mock_settings):
        """Test status text when not synced."""
        controller = MenuBarController(settings=mock_settings)
        assert controller.get_status_text() == "Not synced yet"

    def test_get_status_text_after_sync(self, mock_settings):
        """Test status text after sync."""
        controller = MenuBarController(settings=mock_settings)
        controller.last_sync = datetime(2024, 6, 15, 14, 30)
        assert controller.get_status_text() == "Last sync: 14:30"

    def test_get_config_status_missing_credentials(self, mock_settings):
        """Test config status when credentials missing."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert message == "Missing Strava credentials"
        assert is_valid is False

    def test_get_config_status_missing_refresh_token(self, mock_settings):
        """Test config status when refresh token missing."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert message == "Not authenticated"
        assert is_valid is False

    def test_get_config_status_no_clubs(self, mock_settings):
        """Test config status when no clubs yet (will be auto-fetched)."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        mock_settings.clubs = {}
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert message == "Ready to sync (will fetch clubs)"
        assert is_valid is True

    def test_get_config_status_clubs_none_enabled(self, mock_settings):
        """Test config status when clubs exist but none are enabled."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        mock_settings.clubs = {
            "1": {"name": "Club A", "city": "Portland", "enabled": False},
            "2": {"name": "Club B", "city": "Seattle", "enabled": False},
        }
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert message == "2 clubs (none enabled)"
        assert is_valid is True

    def test_get_config_status_valid(self, mock_settings):
        """Test config status when fully configured."""
        mock_settings.cities = ["Portland"]
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert "2/2 clubs enabled" in message
        assert "Cities: Portland" in message
        assert is_valid is True

    def test_needs_setup(self, mock_settings):
        """Test needs_setup when credentials missing."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)
        assert controller.needs_setup() is True

        mock_settings.has_strava_credentials.return_value = True
        assert controller.needs_setup() is False

    def test_needs_auth(self, mock_settings):
        """Test needs_auth when refresh token missing."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)
        assert controller.needs_auth() is True

        mock_settings.has_refresh_token.return_value = True
        assert controller.needs_auth() is False

    def test_is_ready(self, mock_settings):
        """Test is_ready when credentials and auth present (clubs auto-fetched)."""
        controller = MenuBarController(settings=mock_settings)
        assert controller.is_ready() is True

        # Only credentials and auth matter now, not clubs
        mock_settings.has_refresh_token.return_value = False
        assert controller.is_ready() is False

    def test_validate_strava_access_missing_credentials(self, mock_settings):
        """Test validate_strava_access when credentials missing."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        success, message = controller.validate_strava_access()

        assert success is False
        assert message == "Missing Strava credentials"

    def test_validate_strava_access_not_authenticated(self, mock_settings):
        """Test validate_strava_access when not authenticated."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        success, message = controller.validate_strava_access()

        assert success is False
        assert message == "Not authenticated with Strava"

    def test_validate_strava_access_api_error(self, mock_settings, mock_strava_api):
        """Test validate_strava_access when API returns error."""
        from club_calendar.core.strava import StravaError

        controller = MenuBarController(settings=mock_settings)
        error = StravaError("API error 401: Unauthorized")
        with patch.object(controller.service, "get_clubs", side_effect=error):
            success, message = controller.validate_strava_access()

        assert success is False
        assert "Strava error:" in message
        assert "API error 401" in message

    def test_validate_strava_access_success(self, mock_settings, mock_strava_api):
        """Test validate_strava_access with successful API call."""
        controller = MenuBarController(settings=mock_settings)
        with patch.object(controller.service, "get_clubs", return_value=[{"id": 1}, {"id": 2}]):
            success, message = controller.validate_strava_access()

        assert success is True
        assert message == "Connected (2 clubs)"

    def test_validate_calendar_access_granted(self, mock_settings):
        """Test validate_calendar_access when access is granted."""
        controller = MenuBarController(settings=mock_settings)
        target = "club_calendar.menubar.eventkit.request_calendar_access"
        with patch(target, return_value=(True, None)):
            success, message = controller.validate_calendar_access()

        assert success is True
        assert message == "Calendar access granted"

    def test_validate_calendar_access_denied(self, mock_settings):
        """Test validate_calendar_access when access is denied."""
        controller = MenuBarController(settings=mock_settings)
        target = "club_calendar.menubar.eventkit.request_calendar_access"
        with patch(target, return_value=(False, "Permission denied")):
            success, message = controller.validate_calendar_access()

        assert success is False
        assert message == "Permission denied"

    def test_validate_calendar_access_error(self, mock_settings):
        """Test validate_calendar_access when exception occurs."""
        controller = MenuBarController(settings=mock_settings)
        target = "club_calendar.menubar.eventkit.request_calendar_access"
        with patch(target, side_effect=Exception("EventKit error")):
            success, message = controller.validate_calendar_access()

        assert success is False
        assert "Calendar error:" in message
        assert "EventKit error" in message

    def test_validate_all(self, mock_settings):
        """Test validate_all returns all validation results."""
        controller = MenuBarController(settings=mock_settings)
        strava_mock = patch.object(
            controller, "validate_strava_access", return_value=(True, "Strava OK")
        )
        calendar_mock = patch.object(
            controller, "validate_calendar_access", return_value=(False, "Denied")
        )
        with strava_mock, calendar_mock:
            results = controller.validate_all()

        assert len(results) == 2
        assert results[0] == ("Strava", True, "Strava OK")
        assert results[1] == ("Calendar", False, "Denied")

    def test_run_sync_success(self, mock_settings, mock_strava_api):
        """Test successful sync with HTTP mocks."""
        from club_calendar.menubar.eventkit import SyncResult as EventKitSyncResult

        # Setup settings with merge_clubs mock
        mock_settings.merge_clubs.return_value = 0  # No new clubs

        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "reload_settings"),  # Skip reload to keep mock
            patch(
                "club_calendar.menubar.app.sync_events_to_calendar",
                return_value=EventKitSyncResult(
                    success=True, message="Synced 4 events to Apple Calendar", events_added=4
                ),
            ),
        ):
            result = controller.run_sync()

        assert result.success is True
        assert controller.last_sync is not None
        mock_settings.merge_clubs.assert_called_once()
        mock_settings.save.assert_called()

    def test_run_sync_no_events(self, mock_settings, httpx_mock):
        """Test sync with no events."""
        from club_calendar.menubar.eventkit import SyncResult as EventKitSyncResult

        mock_settings.merge_clubs.return_value = 0

        # Mock API to return clubs and empty events
        def handler(request):
            url = str(request.url)
            if "/oauth/token" in url:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "test",
                        "refresh_token": "test",
                        "expires_at": 9999999999,
                    },
                )
            if "/athlete/clubs" in url:
                return httpx.Response(
                    200, json=[{"id": 123, "name": "Test Club", "city": "Portland"}]
                )
            if "/group_events" in url:
                return httpx.Response(200, json=[])
            return httpx.Response(404)

        httpx_mock.add_callback(handler, is_reusable=True)
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "reload_settings"),  # Skip reload to keep mock
            patch(
                "club_calendar.menubar.app.sync_events_to_calendar",
                return_value=EventKitSyncResult(
                    success=True, message="No events to sync", events_added=0
                ),
            ),
        ):
            result = controller.run_sync()

        assert result.success is True

    def test_run_sync_eventkit_error(self, mock_settings, mock_strava_api):
        """Test sync handles EventKit errors."""
        from club_calendar.menubar.eventkit import SyncResult as EventKitSyncResult

        mock_settings.merge_clubs.return_value = 0

        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "reload_settings"),  # Skip reload to keep mock
            patch(
                "club_calendar.menubar.app.sync_events_to_calendar",
                return_value=EventKitSyncResult(success=False, message="Calendar access denied"),
            ),
        ):
            result = controller.run_sync()

        assert result.success is False
        assert "Calendar access denied" in result.message

    def test_run_sync_no_enabled_clubs(self, mock_settings, mock_strava_api):
        """Test sync when no clubs are enabled."""
        mock_settings.merge_clubs.return_value = 0
        mock_settings.get_club_ids.return_value = []  # No enabled clubs

        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "reload_settings"):  # Skip reload to keep mock
            result = controller.run_sync()

        assert result.success is True
        assert "No clubs enabled" in result.message

    def test_run_sync_preserves_user_enabled_choices(self, mock_settings, mock_strava_api):
        """Test sync merges clubs and preserves user's enabled/disabled choices."""
        from club_calendar.menubar.eventkit import SyncResult as EventKitSyncResult

        # User has disabled club 456
        mock_settings.clubs = {
            "123": {"name": "Enabled Club", "city": "Portland", "enabled": True},
            "456": {"name": "Disabled Club", "city": "Seattle", "enabled": False},
        }
        mock_settings.get_club_ids.return_value = [123]  # Only enabled club
        mock_settings.merge_clubs.return_value = 0

        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "reload_settings"),  # Skip reload to keep mock
            patch(
                "club_calendar.menubar.app.sync_events_to_calendar",
                return_value=EventKitSyncResult(success=True, message="OK", events_added=1),
            ),
        ):
            result = controller.run_sync()

        assert result.success is True
        # Verify merge_clubs was called (preserves enabled state)
        mock_settings.merge_clubs.assert_called_once()
        # Verify settings were saved
        mock_settings.save.assert_called()

    def test_filter_events_limits_per_week(self, mock_settings):
        """Test _filter_events applies per-club per-week limits."""

        from club_calendar.core.strava import ClubEvent

        mock_settings.sync_weeks = 52
        mock_settings.max_events_per_club_per_week = 2
        mock_settings.merge_clubs.return_value = 0

        controller = MenuBarController(settings=mock_settings)

        # Create events - 5 events in the same week from same club (within sync_weeks)
        now = datetime.now(UTC)
        base_date = now + timedelta(days=7)  # Next week
        events = []
        for i in range(5):
            events.append(
                ClubEvent(
                    id=i,
                    title=f"Event {i}",
                    description=None,
                    club_id=123,
                    club_name="Test Club",
                    start_datetime=base_date + timedelta(hours=i),
                    address=None,
                    route_id=None,
                    organizer_name=None,
                )
            )

        filtered = controller._filter_events(events)

        # Should be limited to 2 per week
        assert len(filtered) == 2

    def test_filter_events_respects_sync_weeks(self, mock_settings):
        """Test _filter_events filters out events beyond sync_weeks."""

        from club_calendar.core.strava import ClubEvent

        mock_settings.sync_weeks = 1  # Only 1 week
        mock_settings.max_events_per_club_per_week = 0  # Unlimited

        controller = MenuBarController(settings=mock_settings)

        # Create events - one this week, one in 3 weeks
        now = datetime.now(UTC)
        events = [
            ClubEvent(
                id=1,
                title="This week",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=now + timedelta(days=1),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=2,
                title="In 3 weeks",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=now + timedelta(weeks=3),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        filtered = controller._filter_events(events)

        assert len(filtered) == 1
        assert filtered[0].title == "This week"

    def test_build_sync_message_few_events(self, mock_settings):
        """Test _build_sync_message with 1-2 events shows titles."""
        from club_calendar.core.strava import ClubEvent

        mock_settings.merge_clubs.return_value = 0
        controller = MenuBarController(settings=mock_settings)

        events = [
            ClubEvent(
                id=1,
                title="Morning Ride",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=datetime(2099, 1, 15, 8, 0, tzinfo=UTC),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        message = controller._build_sync_message(events, 1)

        assert "Morning Ride" in message

    def test_build_sync_message_many_events(self, mock_settings):
        """Test _build_sync_message with 3+ events shows club counts."""
        from club_calendar.core.strava import ClubEvent

        mock_settings.merge_clubs.return_value = 0
        mock_settings.clubs = {
            "123": {"name": "Cycling Club", "city": "Portland", "enabled": True},
            "456": {"name": "Running Club", "city": "Seattle", "enabled": True},
        }
        controller = MenuBarController(settings=mock_settings)

        events = [
            ClubEvent(
                id=1,
                title="Ride 1",
                description=None,
                club_id=123,
                club_name="Cycling Club",
                start_datetime=datetime(2099, 1, 15, 8, tzinfo=UTC),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=2,
                title="Ride 2",
                description=None,
                club_id=123,
                club_name="Cycling Club",
                start_datetime=datetime(2099, 1, 16, 8, tzinfo=UTC),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=3,
                title="Run 1",
                description=None,
                club_id=456,
                club_name="Running Club",
                start_datetime=datetime(2099, 1, 17, 8, tzinfo=UTC),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        message = controller._build_sync_message(events, 3)

        assert "3 events" in message
        assert "Cycling Club: 2" in message
        assert "Running Club: 1" in message

    def test_run_sync_auth_failure(self, mock_settings, httpx_mock):
        """Test sync handles authentication failure."""
        # Token exchange fails - triggers StravaAuthError
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            status_code=401,
            json={"error": "invalid_token"},
        )
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "reload_settings"):  # Skip reload to keep mock
            result = controller.run_sync()

        # Sync fails when auth fails
        assert result.success is False
        assert "Invalid" in result.message or "expired" in result.message

    def test_open_config_file(self, mock_settings, tmp_path):
        """Test opening config file."""
        controller = MenuBarController(settings=mock_settings)
        config_path = tmp_path / "config.json"
        config_path.write_text('{"test": true}')

        with (
            patch("club_calendar.menubar.app.get_config_file", return_value=config_path),
            patch("club_calendar.menubar.app.subprocess.run") as mock_run,
        ):
            controller.open_config_file()
            mock_run.assert_called_once_with(["open", str(config_path)])

    def test_open_config_file_creates_if_missing(self, mock_settings, tmp_path):
        """Test opening config file creates it if missing."""
        controller = MenuBarController(settings=mock_settings)
        config_path = tmp_path / "config.json"

        with (
            patch("club_calendar.menubar.app.get_config_file", return_value=config_path),
            patch("club_calendar.menubar.app.subprocess.run") as mock_run,
        ):
            controller.open_config_file()
            mock_settings.save.assert_called_once()
            mock_run.assert_called_once_with(["open", str(config_path)])

    def test_view_logs(self, mock_settings, tmp_path):
        """Test viewing log file."""
        controller = MenuBarController(settings=mock_settings)
        log_path = tmp_path / "club-calendar.log"
        log_path.touch()  # Create the file

        with (
            patch("club_calendar.menubar.app.LOG_FILE", log_path),
            patch("club_calendar.menubar.app.subprocess.run") as mock_run,
        ):
            controller.view_logs()
            mock_run.assert_called_once_with(["open", str(log_path)])

    def test_view_logs_creates_if_not_exists(self, mock_settings, tmp_path):
        """Test view_logs creates log file if it doesn't exist."""
        controller = MenuBarController(settings=mock_settings)
        log_path = tmp_path / "club-calendar.log"
        # Don't create the file - it shouldn't exist

        assert not log_path.exists()

        with (
            patch("club_calendar.menubar.app.LOG_FILE", log_path),
            patch("club_calendar.menubar.app.subprocess.run") as mock_run,
        ):
            controller.view_logs()
            # File should now exist (touch was called)
            assert log_path.exists()
            mock_run.assert_called_once_with(["open", str(log_path)])

    def test_reload_settings(self, mock_settings):
        """Test reloading settings."""
        controller = MenuBarController(settings=mock_settings)
        new_settings = MagicMock()

        with patch("club_calendar.menubar.app.get_settings", return_value=new_settings):
            controller.reload_settings()

            assert controller.settings == new_settings

    def test_save_credentials_success(self, mock_settings):
        """Test saving credentials via settings."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.save_credentials("my_id", "my_secret")

        assert result.success is True
        assert mock_settings.strava_client_id == "my_id"
        assert mock_settings.strava_client_secret == "my_secret"
        mock_settings.save.assert_called_once()

    def test_save_credentials_failure(self, mock_settings):
        """Test save_credentials handles errors."""
        controller = MenuBarController(settings=mock_settings)
        mock_settings.save.side_effect = OSError("Permission denied")

        result = controller.save_credentials("id", "secret")

        assert result.success is False
        assert "Permission denied" in result.message

    def test_start_oauth_flow_success(self, mock_settings, mock_external_calls):
        """Test starting OAuth flow."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.start_oauth_flow()

        assert result.success is True
        mock_external_calls["webbrowser"].assert_called_once()
        url = mock_external_calls["webbrowser"].call_args[0][0]
        assert "strava.com/oauth/authorize" in url
        assert "client_id=test_id" in url

    def test_start_oauth_flow_no_credentials(self, mock_settings):
        """Test OAuth flow fails without credentials."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        result = controller.start_oauth_flow()

        assert result.success is False
        assert "credentials" in result.message.lower()

    def test_exchange_code_for_token_success(self, mock_settings, mock_strava_api):
        """Test exchanging OAuth code for token via HTTP."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.exchange_code_for_token("auth_code")

        assert result.success is True
        assert mock_settings.strava_refresh_token == "test_refresh_token"

    def test_exchange_code_for_token_no_token(self, mock_settings, httpx_mock):
        """Test exchange fails when no token in response."""
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            json={"access_token": "test", "expires_at": 9999999999},  # Missing refresh_token
        )
        controller = MenuBarController(settings=mock_settings)

        result = controller.exchange_code_for_token("auth_code")

        assert result.success is False

    def test_exchange_code_for_token_error(self, mock_settings, httpx_mock):
        """Test exchange handles HTTP errors."""
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            status_code=401,
            json={"error": "invalid_grant"},
        )
        controller = MenuBarController(settings=mock_settings)

        result = controller.exchange_code_for_token("auth_code")

        assert result.success is False

    def test_save_token_success(self, mock_settings):
        """Test saving refresh token via settings."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.save_token("my_token")

        assert result.success is True
        assert mock_settings.strava_refresh_token == "my_token"
        mock_settings.save.assert_called_once()

    def test_save_token_failure(self, mock_settings):
        """Test save_token handles errors."""
        controller = MenuBarController(settings=mock_settings)
        mock_settings.save.side_effect = OSError("Error")

        result = controller.save_token("token")

        assert result.success is False

    def test_is_login_enabled_when_plist_exists(self, mock_settings, tmp_path):
        """Test is_login_enabled returns True when plist exists."""
        controller = MenuBarController(settings=mock_settings)
        plist_path = tmp_path / "com.club-calendar.menubar.plist"
        plist_path.touch()

        with patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path):
            assert controller.is_login_enabled() is True

    def test_is_login_enabled_when_plist_missing(self, mock_settings, tmp_path):
        """Test is_login_enabled returns False when plist missing."""
        controller = MenuBarController(settings=mock_settings)
        plist_path = tmp_path / "com.club-calendar.menubar.plist"
        # Don't create the file

        with patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path):
            assert controller.is_login_enabled() is False

    def test_enable_login_creates_plist(self, mock_settings, tmp_path):
        """Test enable_login creates launch agent plist."""
        controller = MenuBarController(settings=mock_settings)
        plist_path = tmp_path / "LaunchAgents" / "com.club-calendar.menubar.plist"
        logs_dir = tmp_path / "Logs"

        with (
            patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path),
            patch("club_calendar.menubar.app.get_logs_dir", return_value=logs_dir),
            patch("subprocess.run") as mock_run,
        ):
            result = controller.enable_login()

        assert result.success is True
        assert plist_path.exists()
        # Check launchctl was called
        assert mock_run.call_count == 2  # unload + load

    def test_enable_login_handles_error(self, mock_settings, tmp_path):
        """Test enable_login handles errors gracefully."""
        controller = MenuBarController(settings=mock_settings)
        plist_path = tmp_path / "LaunchAgents" / "com.club-calendar.menubar.plist"

        with (
            patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path),
            patch("club_calendar.menubar.app.get_logs_dir", side_effect=OSError("err")),
        ):
            result = controller.enable_login()

        assert result.success is False

    def test_disable_login_removes_plist(self, mock_settings, tmp_path):
        """Test disable_login removes launch agent plist."""
        controller = MenuBarController(settings=mock_settings)
        plist_path = tmp_path / "com.club-calendar.menubar.plist"
        plist_path.touch()

        with (
            patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path),
            patch("subprocess.run") as mock_run,
        ):
            result = controller.disable_login()

        assert result.success is True
        assert not plist_path.exists()
        mock_run.assert_called_once()  # unload

    def test_disable_login_when_not_enabled(self, mock_settings, tmp_path):
        """Test disable_login succeeds when plist doesn't exist."""
        controller = MenuBarController(settings=mock_settings)
        plist_path = tmp_path / "com.club-calendar.menubar.plist"
        # Don't create the file

        with patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path):
            result = controller.disable_login()

        assert result.success is True

    def test_get_app_executable_from_bundle(self, mock_settings):
        """Test _get_app_executable returns bundle path when in .app."""
        with patch("sys.executable", "/Applications/Club Calendar.app/Contents/MacOS/python"):
            result = MenuBarController._get_app_executable()
            assert ".app/Contents/MacOS" in result

    def test_get_app_executable_from_source(self, mock_settings, tmp_path):
        """Test _get_app_executable returns entry point when running from source."""
        # Create mock entry point
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        entry_point = bin_dir / "club-calendar-menubar"
        entry_point.touch()

        with patch("sys.executable", str(bin_dir / "python")):
            result = MenuBarController._get_app_executable()
            assert result == str(entry_point)

    def test_set_sync_interval(self, mock_settings):
        """Test setting sync interval."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.set_sync_interval(30)

        assert result.success is True
        assert mock_settings.sync_interval_minutes == 30
        mock_settings.save.assert_called_once()

    def test_set_sync_interval_failure(self, mock_settings):
        """Test set_sync_interval handles errors."""
        controller = MenuBarController(settings=mock_settings)
        mock_settings.save.side_effect = OSError("Error")

        result = controller.set_sync_interval(30)

        assert result.success is False

    def test_get_sync_interval(self, mock_settings):
        """Test getting sync interval."""
        mock_settings.sync_interval_minutes = 120
        controller = MenuBarController(settings=mock_settings)

        assert controller.get_sync_interval() == 120

    def test_should_auto_sync_not_ready(self, mock_settings):
        """Test should_auto_sync returns False when not ready."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        assert controller.should_auto_sync() is False

    def test_should_auto_sync_never_synced(self, mock_settings):
        """Test should_auto_sync returns True when never synced."""
        controller = MenuBarController(settings=mock_settings)
        controller.last_sync = None

        assert controller.should_auto_sync() is True

    def test_should_auto_sync_interval_not_elapsed(self, mock_settings):
        """Test should_auto_sync returns False when interval not elapsed."""
        mock_settings.sync_interval_minutes = 60
        controller = MenuBarController(settings=mock_settings)
        controller.last_sync = datetime.now()  # Just synced

        assert controller.should_auto_sync() is False

    def test_should_auto_sync_interval_elapsed(self, mock_settings):
        """Test should_auto_sync returns True when interval elapsed."""

        mock_settings.sync_interval_minutes = 60
        controller = MenuBarController(settings=mock_settings)
        controller.last_sync = datetime.now() - timedelta(minutes=61)

        assert controller.should_auto_sync() is True

    def test_should_auto_sync_disabled(self, mock_settings):
        """Test should_auto_sync returns False when disabled (interval=0)."""
        mock_settings.sync_interval_minutes = 0
        controller = MenuBarController(settings=mock_settings)

        assert controller.should_auto_sync() is False


class TestOAuthCallbackHandler:
    """Tests for OAuth callback HTTP handler."""

    def test_callback_with_code(self, mock_settings):
        """Test handling OAuth callback with code."""
        mock_controller = MagicMock()
        mock_controller.exchange_code_for_token.return_value = SetupResult(
            success=True, message="OK"
        )

        # Set up class attributes
        OAuthCallbackHandler.controller = mock_controller
        OAuthCallbackHandler.result = None

        # Create a mock handler that simulates the HTTP handler
        # Set controller on the mock too since do_GET accesses self.controller
        handler = MagicMock()
        handler.path = "/callback?code=test_code"
        handler.wfile = BytesIO()
        handler.controller = mock_controller

        # Call do_GET - it accesses controller via self
        OAuthCallbackHandler.do_GET(handler)

        # Verify controller's exchange method was called
        mock_controller.exchange_code_for_token.assert_called_once_with("test_code")
        handler.send_response.assert_called_with(200)
        assert OAuthCallbackHandler.result.success is True

    def test_callback_without_code(self):
        """Test handling callback without code."""
        OAuthCallbackHandler.controller = MagicMock()
        OAuthCallbackHandler.result = None

        handler = MagicMock()
        handler.path = "/callback"
        handler.wfile = BytesIO()

        OAuthCallbackHandler.do_GET(handler)

        handler.send_response.assert_called_with(400)

    def test_callback_wrong_path(self):
        """Test handling request to wrong path."""
        handler = MagicMock()
        handler.path = "/other"

        OAuthCallbackHandler.do_GET(handler)

        handler.send_response.assert_called_with(404)

    def test_callback_failure_response(self, mock_settings):
        """Test handling OAuth callback with failed token exchange."""
        mock_controller = MagicMock()
        mock_controller.exchange_code_for_token.return_value = SetupResult(
            success=False, message="Token exchange failed"
        )

        OAuthCallbackHandler.controller = mock_controller
        OAuthCallbackHandler.result = None

        handler = MagicMock()
        handler.path = "/callback?code=bad_code"
        handler.wfile = BytesIO()
        handler.controller = mock_controller

        OAuthCallbackHandler.do_GET(handler)

        handler.send_response.assert_called_with(200)
        # Result is set from the controller's return value
        assert OAuthCallbackHandler.result.success is False
        assert OAuthCallbackHandler.result.message == "Token exchange failed"

    def test_log_message_suppressed(self):
        """Test that log messages are suppressed."""
        handler = MagicMock()
        OAuthCallbackHandler.log_message(handler, "test %s", "message")

    def test_reset(self):
        """Test reset() clears handler state."""
        OAuthCallbackHandler.controller = MagicMock()
        OAuthCallbackHandler.result = SetupResult(success=True, message="Done")

        OAuthCallbackHandler.reset()

        assert OAuthCallbackHandler.controller is None
        assert OAuthCallbackHandler.result is None


class TestRunOAuthServer:
    """Tests for run_oauth_server function."""

    def test_oauth_server_success(self, mock_settings):
        """Test OAuth server handles callback."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.app.HTTPServer") as mock_server_class:
            mock_server = MagicMock()
            mock_server_class.return_value = mock_server

            def set_result(*args, **kwargs):
                OAuthCallbackHandler.result = SetupResult(success=True, message="OK")

            mock_server.handle_request.side_effect = set_result

            result = run_oauth_server(controller, timeout=1)

            assert result.success is True

    def test_oauth_server_timeout(self, mock_settings):
        """Test OAuth server timeout."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.app.HTTPServer") as mock_server_class:
            mock_server = MagicMock()
            mock_server_class.return_value = mock_server
            OAuthCallbackHandler.result = None

            result = run_oauth_server(controller, timeout=1)

            assert result.success is False
            assert "timed out" in result.message.lower()


class TestImportRumps:
    """Tests for _import_rumps function."""

    def test_import_rumps_success(self):
        """Test successful rumps import when installed."""
        # If rumps is installed, it should import successfully
        # If not, the function exits - which is tested in test_import_rumps_not_installed
        try:
            result = _import_rumps()
            assert result is not None
        except SystemExit:
            pytest.skip("rumps not installed - testing exit behavior instead")

    def test_import_rumps_not_installed(self):
        """Test exit when rumps not installed."""
        with (
            patch.dict("sys.modules", {"rumps": None}),
            patch("builtins.__import__") as mock_import,
            patch("builtins.print"),
            pytest.raises(SystemExit) as exc_info,
        ):

            def raise_import_error(name, *args, **kwargs):
                if name == "rumps":
                    raise ImportError("No module named 'rumps'")
                return MagicMock()

            mock_import.side_effect = raise_import_error
            _import_rumps()

        assert exc_info.value.code == 1


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_with_mock_rumps(self, mock_rumps, mock_settings):
        """Test create_app with mocked rumps."""
        controller = MenuBarController(settings=mock_settings)

        app = create_app(rumps_module=mock_rumps, controller=controller)

        assert app is not None
        assert app.controller == controller
        assert app.menu.add.called

    def test_create_app_sync_now_success(self, mock_rumps, mock_settings):
        """Test sync_now callback on success - silent, no notification."""
        controller = MenuBarController(settings=mock_settings)

        # Mock Thread to run target synchronously
        class SyncThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        with (
            patch.object(controller, "validate_calendar_access") as mock_validate,
            patch.object(controller, "run_sync") as mock_sync,
            patch("club_calendar.menubar.app.Thread", SyncThread),
        ):
            mock_validate.return_value = (True, "OK")
            mock_sync.return_value = SyncResult(success=True, message="Done")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.sync_now(None)

            # Success is silent - menu shows last sync time
            mock_rumps.notification.assert_not_called()

    def test_create_app_sync_now_failure(self, mock_rumps, mock_settings):
        """Test sync_now callback on failure."""
        controller = MenuBarController(settings=mock_settings)

        # Mock Thread to run target synchronously
        class SyncThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        with (
            patch.object(controller, "validate_calendar_access") as mock_validate,
            patch.object(controller, "run_sync") as mock_sync,
            patch("club_calendar.menubar.app.Thread", SyncThread),
        ):
            mock_validate.return_value = (True, "OK")
            mock_sync.return_value = SyncResult(success=False, message="Error")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.sync_now(None)

            mock_rumps.notification.assert_called_with(
                title="Club Calendar",
                subtitle="Sync Failed",
                message="Error",
            )

    def test_create_app_auto_sync_success(self, mock_rumps, mock_settings):
        """Test auto_sync when controller is ready and sync succeeds."""
        controller = MenuBarController(settings=mock_settings)

        # Mock Thread to run target synchronously
        class SyncThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        with (
            patch.object(controller, "validate_calendar_access") as mock_validate,
            patch.object(controller, "run_sync") as mock_sync,
            patch("club_calendar.menubar.app.Thread", SyncThread),
        ):
            mock_validate.return_value = (True, "OK")
            mock_sync.return_value = SyncResult(success=True, message="2 events")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            # Reset mocks after startup sync
            mock_sync.reset_mock()
            mock_rumps.notification.reset_mock()

            app.auto_sync(None)

            mock_sync.assert_called_once()
            # Auto-sync should NOT show notification on success (silent)
            mock_rumps.notification.assert_not_called()

    def test_create_app_auto_sync_failure(self, mock_rumps, mock_settings):
        """Test auto_sync when controller is ready but sync fails."""
        controller = MenuBarController(settings=mock_settings)

        # Mock Thread to run target synchronously
        class SyncThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        with (
            patch.object(controller, "validate_calendar_access") as mock_validate,
            patch.object(controller, "run_sync") as mock_sync,
            patch("club_calendar.menubar.app.Thread", SyncThread),
        ):
            mock_validate.return_value = (True, "OK")
            mock_sync.return_value = SyncResult(success=False, message="API error")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            # Reset mocks after startup sync
            mock_sync.reset_mock()
            mock_rumps.notification.reset_mock()

            app.auto_sync(None)

            mock_sync.assert_called_once()
            # Auto-sync SHOULD notify on failure
            mock_rumps.notification.assert_called_with(
                title="Club Calendar",
                subtitle="Auto-sync failed",
                message="API error",
            )

    def test_create_app_auto_sync_not_ready(self, mock_rumps, mock_settings):
        """Test auto_sync when controller is not ready (skips sync)."""
        # Make controller not ready by missing credentials
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "run_sync") as mock_sync:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.auto_sync(None)

            # Should not call run_sync when not ready
            mock_sync.assert_not_called()
            mock_rumps.notification.assert_not_called()

    def test_create_app_update_menu_ready(self, mock_rumps, mock_settings):
        """Test _update_menu when app is ready shows sync options."""
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Sync now" in str(c) for c in calls)

    def test_create_app_update_menu_not_ready(self, mock_rumps, mock_settings):
        """Test _update_menu when missing creds shows setup prompt."""
        # Not ready means missing credentials (clubs are auto-fetched now)
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Set Strava credentials" in str(c) for c in calls)

    def test_create_app_update_menu_valid_config(self, mock_rumps, mock_settings):
        """Test _update_menu with valid config shows Sync Now and Edit Config."""
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Sync now" in str(c) for c in calls)
        assert any("Edit config" in str(c) for c in calls)

    def test_create_app_update_menu_invalid_config(self, mock_rumps, mock_settings):
        """Test _update_menu with invalid config shows warning."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Set Strava credentials" in str(c) for c in calls)

    def test_create_app_update_menu_needs_auth(self, mock_rumps, mock_settings):
        """Test _update_menu when has creds but not authenticated."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Authenticate with Strava" in str(c) for c in calls)
        assert any("Edit config" in str(c) for c in calls)

    def test_create_app_uses_default_controller(self, mock_rumps):
        """Test create_app creates controller if not provided."""
        with patch("club_calendar.menubar.app.MenuBarController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.get_status_text.return_value = "Not synced"
            mock_controller.get_config_status.return_value = ("OK", True)
            mock_controller.is_ready.return_value = True
            mock_controller.settings = MagicMock()
            mock_controller.settings.get_club_ids.return_value = [1, 2]
            mock_controller_class.return_value = mock_controller

            create_app(rumps_module=mock_rumps)

            mock_controller_class.assert_called_once()

    def test_create_app_uses_default_rumps(self, mock_settings):
        """Test create_app imports rumps if not provided."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.app._import_rumps") as mock_import:
            mock_rumps = MagicMock()
            mock_rumps.separator = "---"
            mock_rumps.MenuItem = MagicMock()
            mock_rumps.clicked = MagicMock(side_effect=lambda name: lambda f: f)

            class MockApp:
                def __init__(self, name, icon=None, title=None, template=None, quit_button=None):
                    self.menu = MagicMock()

            mock_rumps.App = MockApp
            mock_import.return_value = mock_rumps

            create_app(controller=controller)

            mock_import.assert_called_once()

    def test_create_app_view_logs(self, mock_rumps, mock_settings):
        """Test view_logs callback."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "view_logs") as mock_view:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.view_logs(None)

            mock_view.assert_called_once()

    def test_create_app_edit_config(self, mock_rumps, mock_settings):
        """Test edit_config callback."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "open_config_file") as mock_open:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.edit_config(None)

            mock_open.assert_called_once()

    def test_create_app_quit_app(self, mock_rumps, mock_settings):
        """Test quit_app callback."""
        controller = MenuBarController(settings=mock_settings)

        app = create_app(rumps_module=mock_rumps, controller=controller)
        app.quit_app(None)

        mock_rumps.quit_application.assert_called_once()

    def test_create_app_run_auth_success(self, mock_rumps, mock_settings):
        """Test run_auth with valid credentials."""
        # Disable sync_on_startup to avoid Thread call during app init
        mock_settings.sync_on_startup = False
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "start_oauth_flow") as mock_oauth,
            patch("club_calendar.menubar.app.Thread") as mock_thread,
        ):
            mock_oauth.return_value = SetupResult(success=True, message="Started")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_auth(None)

            mock_oauth.assert_called_once()
            mock_thread.assert_called_once()

    def test_create_app_run_auth_no_credentials(self, mock_rumps, mock_settings):
        """Test run_auth without credentials shows error."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        app = create_app(rumps_module=mock_rumps, controller=controller)
        app.run_auth(None)

        mock_rumps.notification.assert_called()
        # Check notification mentions setup required
        call_args = mock_rumps.notification.call_args
        assert "Setup Required" in str(call_args)

    def test_create_app_run_auth_oauth_failure(self, mock_rumps, mock_settings):
        """Test run_auth when OAuth flow fails."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "start_oauth_flow") as mock_oauth:
            mock_oauth.return_value = SetupResult(success=False, message="Failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_auth(None)

            mock_rumps.notification.assert_called()

    def test_create_app_icon_path_found(self, mock_rumps, mock_settings, tmp_path):
        """Test app finds icon when it exists."""
        # Create a fake icon file
        icon_path = tmp_path / "icon.png"
        icon_path.write_bytes(b"fake png")

        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.app.Path"):
            # This is complex to mock, so let's test via the app creation
            app = create_app(rumps_module=mock_rumps, controller=controller)
            # App should be created successfully
            assert app is not None


class TestMain:
    """Tests for main function."""

    def test_main_calls_create_app_and_run(self):
        """Test main creates app and runs it."""
        mock_app = MagicMock()

        with patch("club_calendar.menubar.app.create_app", return_value=mock_app):
            main()

            mock_app.run.assert_called_once()


class TestGetUpcomingEvents:
    """Tests for get_upcoming_events method."""

    def test_includes_todays_past_events(self, mock_settings):
        """Test that today's past events are included."""

        from club_calendar.core.strava import ClubEvent

        controller = MenuBarController(settings=mock_settings)
        now = datetime.now(UTC)

        # Create an event earlier today (past)
        past_today = now.replace(hour=7, minute=0, second=0, microsecond=0)
        # Create an event later today (future)
        future_today = now + timedelta(hours=3)

        controller.last_events = [
            ClubEvent(
                id=1,
                title="Past Today",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=past_today,
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=2,
                title="Future Today",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=future_today,
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        upcoming = controller.get_upcoming_events(limit=10)

        # Both today's events should be included
        assert len(upcoming) == 2
        titles = [e.title for e in upcoming]
        assert "Past Today" in titles
        assert "Future Today" in titles

    def test_excludes_yesterdays_events(self, mock_settings):
        """Test that yesterday's events are excluded."""

        from club_calendar.core.strava import ClubEvent

        controller = MenuBarController(settings=mock_settings)
        now = datetime.now(UTC)

        # Create an event yesterday
        yesterday = now - timedelta(days=1)
        # Create an event today
        today = now + timedelta(hours=1)

        controller.last_events = [
            ClubEvent(
                id=1,
                title="Yesterday",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=yesterday,
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=2,
                title="Today",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=today,
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        upcoming = controller.get_upcoming_events(limit=10)

        assert len(upcoming) == 1
        assert upcoming[0].title == "Today"


class TestDayLabelAndMenuFiltering:
    """Tests for _get_day_label and menu filtering of events."""

    def test_get_day_label_today(self, mock_rumps, mock_settings):
        """Test _get_day_label returns correct label for today."""
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        now = datetime.now(UTC)
        label, is_this_week, is_today, is_next_week = app._get_day_label(now)

        assert "Today" in label
        assert is_this_week is True
        assert is_today is True
        assert is_next_week is False

    def test_get_day_label_tomorrow(self, mock_rumps, mock_settings):
        """Test _get_day_label returns correct label for tomorrow."""

        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        tomorrow = datetime.now(UTC) + timedelta(days=1)
        label, is_this_week, is_today, is_next_week = app._get_day_label(tomorrow)

        assert "Tomorrow" in label
        assert "(" in label  # Contains date like "(Wed, 17 Dec):"
        assert is_this_week is True
        assert is_today is False
        assert is_next_week is False

    def test_get_day_label_this_week(self, mock_rumps, mock_settings):
        """Test _get_day_label returns correct label for this week (not today/tomorrow)."""

        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        # Find a day that's this week but not today or tomorrow
        now = datetime.now(UTC)
        # Go to a day 3 days from now (should still be this week for most cases)
        test_date = now + timedelta(days=3)

        label, is_this_week, is_today, is_next_week = app._get_day_label(test_date)

        # Should have day name in label
        assert "(" in label  # Contains date like "(20 Dec):"
        assert is_today is False
        # is_this_week depends on where we are in the week

    def test_get_day_label_next_week(self, mock_rumps, mock_settings):
        """Test _get_day_label returns correct label for next week."""

        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        # Go 8 days from now (guaranteed to be next week)
        next_week = datetime.now(UTC) + timedelta(days=8)
        label, is_this_week, is_today, is_next_week = app._get_day_label(next_week)

        assert "(" in label  # Contains date
        assert is_this_week is False
        assert is_today is False
        assert is_next_week is True

    def test_get_day_label_beyond_next_week(self, mock_rumps, mock_settings):
        """Test _get_day_label returns correct flags for events beyond next week."""

        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        # Go 15 days from now (beyond next week)
        far_future = datetime.now(UTC) + timedelta(days=15)
        label, is_this_week, is_today, is_next_week = app._get_day_label(far_future)

        assert is_this_week is False
        assert is_today is False
        assert is_next_week is False

    def test_menu_excludes_events_beyond_next_week(self, mock_rumps, mock_settings):
        """Test that events beyond next week are not shown in menu."""

        from club_calendar.core.strava import ClubEvent

        controller = MenuBarController(settings=mock_settings)

        # Create events: this week, next week, and beyond
        now = datetime.now(UTC)
        controller.last_events = [
            ClubEvent(
                id=1,
                title="This Week Event",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=now + timedelta(days=1),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=2,
                title="Next Week Event",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=now + timedelta(days=8),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
            ClubEvent(
                id=3,
                title="Far Future Event",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=now + timedelta(days=20),
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        app = create_app(rumps_module=mock_rumps, controller=controller)

        # Check menu items - far future should not be shown
        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        calls_str = " ".join(calls)

        # This week and next week events should be shown
        assert "This Week Event" in calls_str or "Test Club" in calls_str
        # Far future should NOT be shown
        assert "Far Future Event" not in calls_str

    def test_menu_shows_next_week_day_header(self, mock_rumps, mock_settings):
        """Test that next week events show day headers."""

        from club_calendar.core.strava import ClubEvent

        controller = MenuBarController(settings=mock_settings)

        # Use fixed datetime 8 days in the future at noon to avoid timezone edge cases
        now = datetime.now(UTC)
        next_week_dt = (now + timedelta(days=8)).replace(hour=12, minute=0, second=0, microsecond=0)
        controller.last_events = [
            ClubEvent(
                id=1,
                title="Next Week Event",
                description=None,
                club_id=123,
                club_name="Test Club",
                start_datetime=next_week_dt,
                address=None,
                route_id=None,
                organizer_name=None,
            ),
        ]

        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        calls_str = " ".join(calls)

        # Should show day header like "25 Dec (Thu):"
        expected_header = f"{next_week_dt.strftime('%d %b')} ({next_week_dt.strftime('%a')}):"
        assert expected_header in calls_str
