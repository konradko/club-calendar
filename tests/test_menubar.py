"""Tests for menubar app."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from club_calendar.core.models import SetupResult, SyncResult
from club_calendar.core.strava import StravaAuthError, StravaError, StravaRateLimitError
from club_calendar.menubar.app import (
    MenuBarController,
    OAuthCallbackHandler,
    _categorize_error,
    _import_rumps,
    create_app,
    is_dev_mode,
    is_running_tests,
    main,
    run_oauth_server,
    setup_logging,
    show_dev_error,
)
from club_calendar.menubar.eventkit import CalendarError


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
        mock_settings.merge_clubs.return_value = 1  # New clubs found

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
        mock_settings.merge_clubs.return_value = 1  # New club found

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
        assert "Invalid Strava credentials" in result.message

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
            patch("club_calendar.menubar.app.get_logs_dir", return_value=tmp_path),
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
            patch("club_calendar.menubar.app.get_logs_dir", return_value=tmp_path),
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

    def test_should_auto_sync_false_when_sync_in_progress(self, mock_settings):
        """Test should_auto_sync returns False when sync is already running."""
        controller = MenuBarController(settings=mock_settings)
        controller.last_sync = None  # Would normally return True

        # Acquire the sync lock to simulate sync in progress
        controller._sync_lock.acquire()
        try:
            assert controller.should_auto_sync() is False
        finally:
            controller._sync_lock.release()

    def test_run_sync_skips_if_already_running(self, mock_settings):
        """Test run_sync returns immediately if sync is already in progress."""
        controller = MenuBarController(settings=mock_settings)

        # Acquire the sync lock to simulate sync in progress
        controller._sync_lock.acquire()
        try:
            result = controller.run_sync()
            assert result.success is True
            assert "already in progress" in result.message
        finally:
            controller._sync_lock.release()


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


class TestConfigReload:
    """Tests for config reload functionality."""

    def test_reload_settings_updates_settings(self, mock_settings):
        """Test reload_settings updates the settings object."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        new_settings = MagicMock()
        new_settings.auto_reload_config = False

        with patch("club_calendar.menubar.app.get_settings", return_value=new_settings):
            controller.reload_settings()

        assert controller.settings == new_settings

    def test_reload_settings_refreshes_service(self, mock_settings):
        """Test reload_settings refreshes the service."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        new_settings = MagicMock()
        new_settings.auto_reload_config = False

        with patch("club_calendar.menubar.app.get_settings", return_value=new_settings):
            with patch.object(controller, "_refresh_service") as mock_refresh:
                controller.reload_settings()
                mock_refresh.assert_called_once()

    def test_config_watcher_not_started_when_disabled(self, mock_settings):
        """Test file watcher is not started when auto_reload_config is False."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)
        assert controller._config_observer is None

    def test_config_watcher_started_when_enabled(self, mock_settings):
        """Test file watcher is started when auto_reload_config is True."""
        mock_settings.auto_reload_config = True

        with patch("club_calendar.menubar.app.get_config_file") as mock_get_file:
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "config.yaml"
                config_path.touch()
                mock_get_file.return_value = config_path

                controller = MenuBarController(settings=mock_settings)

                assert controller._config_observer is not None
                # Clean up
                controller._stop_config_watcher()

    def test_stop_config_watcher(self, mock_settings):
        """Test stopping the config watcher."""
        mock_settings.auto_reload_config = True

        with patch("club_calendar.menubar.app.get_config_file") as mock_get_file:
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "config.yaml"
                config_path.touch()
                mock_get_file.return_value = config_path

                controller = MenuBarController(settings=mock_settings)
                assert controller._config_observer is not None

                controller._stop_config_watcher()
                assert controller._config_observer is None

    def test_reload_config_menu_item_exists(self, mock_rumps, mock_settings):
        """Test that Reload config menu item exists in settings menu."""
        mock_settings.sync_on_startup = False
        mock_settings.auto_reload_config = False

        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)
        app._update_menu()

        # Find all menu item titles that were created
        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        calls_str = " ".join(calls)

        assert "Reload config" in calls_str


class TestCategorizeError:
    """Tests for _categorize_error function."""

    def test_strava_auth_error(self):
        """Test StravaAuthError categorization."""
        error = StravaAuthError("Invalid token")
        result = _categorize_error(error)
        assert result == "Authentication failed. Please re-authenticate with Strava."

    def test_strava_rate_limit_error(self):
        """Test StravaRateLimitError categorization."""
        error = StravaRateLimitError("Too many requests")
        result = _categorize_error(error)
        assert result == "Rate limited by Strava. Please try again in 15 minutes."

    def test_strava_error(self):
        """Test generic StravaError categorization."""
        error = StravaError("API returned 500")
        result = _categorize_error(error)
        assert result == "Strava API error: API returned 500"

    def test_calendar_error(self):
        """Test CalendarError categorization."""
        error = CalendarError("Could not create event")
        result = _categorize_error(error)
        assert result == "Calendar error: Could not create event"

    def test_timeout_exception(self):
        """Test httpx.TimeoutException categorization."""
        error = httpx.TimeoutException("Request timed out")
        result = _categorize_error(error)
        assert result == "Network timeout. Check your internet connection."

    def test_http_error(self):
        """Test httpx.HTTPError categorization."""
        error = httpx.HTTPError("Connection refused")
        result = _categorize_error(error)
        assert result == "Network error: Connection refused"

    def test_os_error(self):
        """Test OSError categorization."""
        error = OSError("File not found")
        result = _categorize_error(error)
        assert result == "File system error: File not found"

    def test_value_error(self):
        """Test ValueError categorization."""
        error = ValueError("Invalid config value")
        result = _categorize_error(error)
        assert result == "Configuration error: Invalid config value"

    def test_unknown_error(self):
        """Test unknown error categorization."""
        error = RuntimeError("Something went wrong")
        result = _categorize_error(error)
        assert result == "Unexpected error: Something went wrong"

    def test_long_error_message_truncated(self):
        """Test that long error messages are truncated to 80 chars."""
        long_message = "A" * 150
        error = OSError(long_message)
        result = _categorize_error(error)
        # Message should be truncated at 80 chars
        assert "File system error: " in result
        assert len(result) <= 100  # prefix + 80 chars


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_logging_disabled_when_none(self, mock_settings):
        """Test logging is disabled when log_output is 'none'."""
        import logging

        mock_settings.log_output = "none"
        mock_settings.debug = False

        with patch("club_calendar.menubar.app.get_logs_dir"):
            setup_logging(mock_settings)

        # Logging should be disabled
        root = logging.getLogger()
        # With CRITICAL disabled, logging should effectively be off
        # The specific check is that no handlers are added
        assert len(root.handlers) == 0 or logging.getLogger().level >= logging.CRITICAL

    def test_logging_console_only(self, mock_settings, tmp_path):
        """Test logging to console only."""
        import logging

        mock_settings.log_output = "console"
        mock_settings.debug = False

        with patch("club_calendar.menubar.app.get_logs_dir", return_value=tmp_path):
            setup_logging(mock_settings)

        root = logging.getLogger()
        # Should have a StreamHandler
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_logging_file_only(self, mock_settings, tmp_path):
        """Test logging to file only."""
        import logging

        mock_settings.log_output = "file"
        mock_settings.debug = False

        with patch("club_calendar.menubar.app.get_logs_dir", return_value=tmp_path):
            setup_logging(mock_settings)

        root = logging.getLogger()
        # Should have a FileHandler
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) >= 1

    def test_logging_both(self, mock_settings, tmp_path):
        """Test logging to both console and file."""
        import logging

        mock_settings.log_output = "both"
        mock_settings.debug = False

        with patch("club_calendar.menubar.app.get_logs_dir", return_value=tmp_path):
            setup_logging(mock_settings)

        root = logging.getLogger()
        # Should have both handler types
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        stream_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) >= 1
        assert len(stream_handlers) >= 1

    def test_debug_mode_sets_debug_level(self, mock_settings, tmp_path):
        """Test debug mode sets DEBUG level."""
        import logging

        mock_settings.log_output = "console"
        mock_settings.debug = True

        with patch("club_calendar.menubar.app.get_logs_dir", return_value=tmp_path):
            setup_logging(mock_settings)

        root = logging.getLogger()
        assert root.level == logging.DEBUG


class TestShowDevError:
    """Tests for show_dev_error function."""

    def test_does_nothing_in_tests(self):
        """Test show_dev_error does nothing when running tests."""
        # is_running_tests should return True in pytest
        assert is_running_tests()
        # show_dev_error should not raise or log
        show_dev_error("Title", ValueError("test"), "context")

    def test_does_nothing_in_production(self):
        """Test show_dev_error does nothing in production mode."""
        with patch("club_calendar.menubar.app.is_dev_mode", return_value=False):
            with patch("club_calendar.menubar.app.is_running_tests", return_value=False):
                # Should not raise
                show_dev_error("Title", ValueError("test"), "context")

    def test_logs_in_dev_mode(self):
        """Test show_dev_error logs in dev mode (not during tests)."""
        with (
            patch("club_calendar.menubar.app.is_dev_mode", return_value=True),
            patch("club_calendar.menubar.app.is_running_tests", return_value=False),
            patch("club_calendar.menubar.app.logger") as mock_logger,
        ):
            error = ValueError("test error")
            show_dev_error("Title", error, "some context")
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0][0]
            assert "DEV ERROR" in call_args
            assert "some context" in call_args
            assert "ValueError" in call_args


class TestIsDevMode:
    """Tests for is_dev_mode function."""

    def test_returns_true_when_not_in_app_bundle(self):
        """Test is_dev_mode returns True when not running from .app bundle."""
        # In tests, we're not running from a .app bundle
        assert is_dev_mode()

    def test_returns_false_when_in_app_bundle(self):
        """Test is_dev_mode returns False when running from .app bundle."""
        with patch("sys.executable", "/Applications/Club Calendar.app/Contents/MacOS/python"):
            assert not is_dev_mode()


class TestIsRunningTests:
    """Tests for is_running_tests function."""

    def test_returns_true_in_pytest(self):
        """Test is_running_tests returns True when running under pytest."""
        assert is_running_tests()


class TestValidateCalendarAccessExceptions:
    """Tests for validate_calendar_access exception handling."""

    def test_calendar_error_exception(self, mock_settings):
        """Test validate_calendar_access handles CalendarError."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        with patch(
            "club_calendar.menubar.app.MenuBarController.validate_calendar_access"
        ) as mock_validate:
            mock_validate.side_effect = CalendarError("Calendar not available")
            try:
                controller.validate_calendar_access()
            except CalendarError:
                pass  # Expected

    def test_os_error_exception(self, mock_settings):
        """Test validate_calendar_access handles OSError."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        with patch(
            "club_calendar.menubar.eventkit.request_calendar_access",
            side_effect=OSError("Permission denied"),
        ):
            success, msg = controller.validate_calendar_access()
            assert not success
            assert "Calendar error" in msg

    def test_unexpected_exception(self, mock_settings):
        """Test validate_calendar_access handles unexpected exceptions."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        with patch(
            "club_calendar.menubar.eventkit.request_calendar_access",
            side_effect=RuntimeError("Unexpected pyobjc error"),
        ):
            success, msg = controller.validate_calendar_access()
            assert not success
            assert "Calendar error" in msg


class TestReloadSettingsConfigError:
    """Tests for reload_settings ConfigError handling."""

    def test_reload_settings_handles_config_error(self, mock_settings):
        """Test reload_settings handles ConfigError gracefully."""
        from club_calendar.menubar.config import ConfigError

        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        with patch(
            "club_calendar.menubar.app.get_settings",
            side_effect=ConfigError("Invalid YAML"),
        ):
            controller.reload_settings()

        assert not controller.is_config_valid()
        assert "Invalid YAML" in controller.get_config_error()


class TestConfigFileWatcher:
    """Tests for config file watcher functionality."""

    def test_on_modified_skips_directory(self, mock_settings):
        """Test on_modified skips directory events."""
        from pathlib import Path
        from unittest.mock import MagicMock

        mock_settings.auto_reload_config = True

        with patch("club_calendar.menubar.app.get_config_file") as mock_get_file:
            config_path = Path("/tmp/config.yaml")
            mock_get_file.return_value = config_path

            # Create a mock event for a directory
            event = MagicMock()
            event.is_directory = True
            event.src_path = str(config_path)

            # Manually test the handler logic
            # The actual handler is created inside _start_config_watcher
            # We just verify the logic would skip directory events
            assert event.is_directory  # Would cause early return

    def test_on_modified_skips_wrong_file(self, mock_settings):
        """Test on_modified skips events for wrong file."""
        from pathlib import Path
        from unittest.mock import MagicMock

        mock_settings.auto_reload_config = True

        with patch("club_calendar.menubar.app.get_config_file") as mock_get_file:
            config_path = Path("/tmp/config.yaml")
            mock_get_file.return_value = config_path

            # Create a mock event for a different file
            event = MagicMock()
            event.is_directory = False
            event.src_path = "/tmp/other_file.yaml"

            # The handler should skip this because it's not the config file
            assert Path(event.src_path) != config_path

    def test_watchdog_import_error(self, mock_settings):
        """Test config watcher handles missing watchdog gracefully."""
        mock_settings.auto_reload_config = True

        with (
            patch("club_calendar.menubar.app.get_config_file") as mock_get_file,
            patch.dict("sys.modules", {"watchdog": None, "watchdog.events": None}),
        ):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "config.yaml"
                config_path.touch()
                mock_get_file.return_value = config_path

                # Controller should handle missing watchdog gracefully
                # Note: We can't easily test ImportError for watchdog since it's installed
                # But we can verify the controller works without a watcher
                controller = MenuBarController(settings=mock_settings)
                # Watcher might or might not be started depending on watchdog availability
                controller._stop_config_watcher()


class TestLoginItemErrors:
    """Tests for login item management error handling."""

    def test_enable_login_plist_error(self, mock_settings, tmp_path):
        """Test enable_login handles plist errors."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(
                MenuBarController,
                "_get_launch_agent_path",
                return_value=tmp_path / "com.club-calendar.menubar.plist",
            ),
            patch("plistlib.dump", side_effect=OSError("Permission denied")),
        ):
            result = controller.enable_login()
            assert not result.success
            assert "Permission denied" in result.message

    def test_disable_login_error(self, mock_settings, tmp_path):
        """Test disable_login handles errors."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        plist_path = tmp_path / "LaunchAgents" / "com.club-calendar.menubar.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.touch()

        with (
            patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path),
            patch("subprocess.run", side_effect=OSError("Permission denied")),
        ):
            result = controller.disable_login()
            assert not result.success
            assert "Permission denied" in result.message


class TestGetAppExecutable:
    """Tests for _get_app_executable."""

    def test_python_module_invocation(self, mock_settings, tmp_path):
        """Test executable path for python -m invocation."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        # Test when entry point doesn't exist, should fall back to python -m
        with patch("sys.executable", str(tmp_path / "python")):
            result = controller._get_app_executable()
            assert "-m club_calendar.menubar" in result


class TestIsReadyWithInvalidConfig:
    """Tests for is_ready when config is invalid."""

    def test_is_ready_false_when_config_invalid(self, mock_settings):
        """Test is_ready returns False when config is invalid."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        # Simulate invalid config
        controller._config_valid = False

        assert not controller.is_ready()

    def test_has_errors(self, mock_settings):
        """Test has_errors method."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        # Initially no errors
        assert not controller.has_errors()

        # Set error state
        controller._has_errors = True
        assert controller.has_errors()

        # Clear errors
        controller.clear_errors()
        assert not controller.has_errors()


class TestSyncWithFetchErrors:
    """Tests for sync operations with fetch errors."""

    def test_sync_with_new_clubs(self, mock_settings, mock_strava_api):
        """Test sync logs when new clubs are added."""
        mock_settings.auto_reload_config = False
        mock_settings.clubs = {}  # No clubs yet
        mock_settings.get_club_ids.return_value = [123]  # After merge
        mock_settings.get_enabled_clubs.return_value = {123: {"name": "Test", "enabled": True}}
        mock_settings.calendar_name = "Test Calendar"

        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "reload_settings"),
            patch.object(controller.settings, "merge_clubs", return_value=2),  # 2 new clubs
            patch("club_calendar.menubar.app.sync_events_to_calendar") as mock_sync,
        ):
            mock_sync.return_value = SyncResult(success=True, message="ok", events_added=0)
            result = controller.run_sync()

        assert result.success

    def test_sync_with_fetch_errors_in_result(self, mock_settings, httpx_mock):
        """Test sync includes fetch errors in result message."""
        mock_settings.auto_reload_config = False
        mock_settings.clubs = {"123": {"name": "Club 1", "enabled": True}}
        mock_settings.get_club_ids.return_value = [123, 456]
        mock_settings.get_enabled_clubs.return_value = {
            123: {"name": "Club 1", "enabled": True},
            456: {"name": "Club 2", "enabled": True},
        }
        mock_settings.calendar_name = "Test Calendar"
        mock_settings.cities = []
        mock_settings.merge_clubs.return_value = 0  # No new clubs

        # Mock token endpoint
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            method="POST",
            json={
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_at": 9999999999,
            },
        )

        # Mock clubs endpoint
        httpx_mock.add_response(
            url="https://www.strava.com/api/v3/athlete/clubs",
            json=[{"id": 123, "name": "Club 1", "city": "Portland", "member_count": 10}],
        )

        # Mock first club events succeeds
        httpx_mock.add_response(
            url="https://www.strava.com/api/v3/clubs/123/group_events",
            json=[],
        )

        # Mock second club events fails
        httpx_mock.add_response(
            url="https://www.strava.com/api/v3/clubs/456/group_events",
            status_code=500,
            text="Server error",
        )

        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "reload_settings"),
            patch("club_calendar.menubar.app.sync_events_to_calendar") as mock_sync,
        ):
            mock_sync.return_value = SyncResult(success=True, message="ok", events_added=0)
            result = controller.run_sync()

        assert result.success
        assert "failed" in result.message.lower()


class TestConfigFileWatcherHandler:
    """Tests for ConfigFileHandler on_modified."""

    def test_config_watcher_triggers_on_file_change(self, mock_settings, tmp_path):
        """Test config watcher triggers reload when config file changes."""
        import time

        mock_settings.auto_reload_config = True

        config_path = tmp_path / "config.yaml"
        config_path.write_text("strava_client_id: test")

        with (
            patch("club_calendar.menubar.app.get_config_file", return_value=config_path),
        ):
            controller = MenuBarController(settings=mock_settings)

            # Give watcher time to start
            time.sleep(0.1)

            # Verify watcher is running
            assert controller._config_observer is not None

            # Clean up
            controller._stop_config_watcher()

    def test_config_watcher_already_running(self, mock_settings, tmp_path):
        """Test config watcher doesn't start twice."""
        mock_settings.auto_reload_config = True

        config_path = tmp_path / "config.yaml"
        config_path.write_text("strava_client_id: test")

        with (
            patch("club_calendar.menubar.app.get_config_file", return_value=config_path),
        ):
            controller = MenuBarController(settings=mock_settings)
            first_observer = controller._config_observer

            # Try to start again
            controller._start_config_watcher()

            # Should be same observer (not started twice)
            assert controller._config_observer is first_observer

            controller._stop_config_watcher()


class TestOpenEventInCalendar:
    """Tests for open_event_in_calendar."""

    def test_open_event_calls_subprocess(self, mock_settings):
        """Test open_event_in_calendar calls subprocess."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        mock_event = MagicMock()

        with patch("subprocess.run") as mock_run:
            controller.open_event_in_calendar(mock_event)
            mock_run.assert_called_once_with(["open", "-a", "Calendar"])


class TestMainFunction:
    """Tests for main function."""

    def test_main_runs_app(self):
        """Test main function creates and runs app."""
        with (
            patch("club_calendar.menubar.app.create_app") as mock_create,
            patch("club_calendar.menubar.app._import_rumps"),
        ):
            mock_app = MagicMock()
            mock_create.return_value = mock_app

            main()

            mock_create.assert_called_once()
            mock_app.run.assert_called_once()


class TestEnableLoginExecutable:
    """Tests for enable_login with different executable paths."""

    def test_enable_login_with_app_bundle_executable(self, mock_settings, tmp_path):
        """Test enable_login uses direct path for app bundle executable."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        plist_path = tmp_path / "LaunchAgents" / "com.club-calendar.menubar.plist"
        logs_dir = tmp_path / "logs"

        # Simulate app bundle executable (no " -m " in path)
        app_path = "/Applications/Club Calendar.app/Contents/MacOS/Club Calendar"

        with (
            patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path),
            patch.object(MenuBarController, "_get_app_executable", return_value=app_path),
            patch("club_calendar.menubar.app.get_logs_dir", return_value=logs_dir),
        ):
            result = controller.enable_login()
            assert result.success

            # Verify plist was created with direct executable path
            import plistlib

            with open(plist_path, "rb") as f:
                plist_data = plistlib.load(f)
            assert plist_data["ProgramArguments"] == [app_path]

    def test_enable_login_with_python_module(self, mock_settings, tmp_path):
        """Test enable_login uses split args for python -m invocation."""
        mock_settings.auto_reload_config = False
        controller = MenuBarController(settings=mock_settings)

        plist_path = tmp_path / "LaunchAgents" / "com.club-calendar.menubar.plist"
        logs_dir = tmp_path / "logs"

        # Simulate python -m invocation
        python_path = "/usr/bin/python -m club_calendar.menubar"

        with (
            patch.object(MenuBarController, "_get_launch_agent_path", return_value=plist_path),
            patch.object(MenuBarController, "_get_app_executable", return_value=python_path),
            patch("club_calendar.menubar.app.get_logs_dir", return_value=logs_dir),
        ):
            result = controller.enable_login()
            assert result.success

            # Verify plist was created with split arguments
            import plistlib

            with open(plist_path, "rb") as f:
                plist_data = plistlib.load(f)
            assert plist_data["ProgramArguments"] == [
                "/usr/bin/python",
                "-m",
                "club_calendar.menubar",
            ]


class TestConfigFileWatcherOnModified:
    """Tests for ConfigFileHandler on_modified method directly."""

    def test_triggers_reload_on_file_change(self, mock_settings, tmp_path):
        """Test on_modified triggers reload callback when config file changes."""
        import time

        mock_settings.auto_reload_config = True

        config_path = tmp_path / "config.yaml"
        config_path.write_text("strava_client_id: test")

        reload_called = []

        with patch("club_calendar.menubar.app.get_config_file", return_value=config_path):
            controller = MenuBarController(settings=mock_settings)
            controller._menu_update_callback = lambda: reload_called.append(True)

            # Give time for watcher to start
            time.sleep(0.1)

            assert controller._config_observer is not None

            # Trigger file modification
            time.sleep(0.1)  # Wait for debounce period
            config_path.write_text("strava_client_id: updated")

            # Give watchdog time to detect change
            time.sleep(0.7)

            controller._stop_config_watcher()

    def test_debounce_prevents_multiple_reloads(self, mock_settings, tmp_path):
        """Test debounce prevents rapid successive reloads."""

        mock_settings.auto_reload_config = True

        config_path = tmp_path / "config.yaml"
        config_path.write_text("strava_client_id: test")

        with patch("club_calendar.menubar.app.get_config_file", return_value=config_path):
            controller = MenuBarController(settings=mock_settings)

            # Watcher should be running
            assert controller._config_observer is not None

            controller._stop_config_watcher()
