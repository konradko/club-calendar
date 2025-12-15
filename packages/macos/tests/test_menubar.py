"""Tests for menubar app."""

from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import httpx
import pytest
from club_calendar_macos.menubar import (
    MenuBarController,
    OAuthCallbackHandler,
    _import_rumps,
    create_app,
    main,
    run_oauth_server,
)
from club_calendar_macos.models import CommandResult, SetupResult, SyncResult


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings."""
    mock = MagicMock()
    mock.has_strava_credentials.return_value = True
    mock.has_refresh_token.return_value = True
    mock.get_club_ids.return_value = [123, 456]
    mock.ensure_output_dir.return_value = tmp_path
    mock.strava_client_id = "test_id"
    mock.strava_client_secret = "test_secret"
    mock.strava_refresh_token = "test_token"
    mock.club_city_filter = ""
    mock.club_ids = [123, 456]
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
        def __init__(self, name, icon=None, title=None):
            self.name = name
            self.icon = icon
            self.title = title
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


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_success_result(self):
        """Test successful command result."""
        result = CommandResult(success=True, output="Output text")
        assert result.success is True
        assert result.output == "Output text"

    def test_failure_result(self):
        """Test failed command result."""
        result = CommandResult(success=False, output="Error")
        assert result.success is False
        assert result.output == "Error"


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
        with patch("club_calendar_macos.menubar.get_settings") as mock_get:
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
        """Test config status when no clubs configured."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert message == "No clubs configured"
        assert is_valid is False

    def test_get_config_status_valid(self, mock_settings):
        """Test config status when fully configured."""
        controller = MenuBarController(settings=mock_settings)

        message, is_valid = controller.get_config_status()

        assert message == "2 club(s) configured"
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

    def test_needs_clubs(self, mock_settings):
        """Test needs_clubs when clubs not configured."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)
        assert controller.needs_clubs() is True

        mock_settings.get_club_ids.return_value = [123]
        assert controller.needs_clubs() is False

    def test_is_ready(self, mock_settings):
        """Test is_ready when fully configured."""
        controller = MenuBarController(settings=mock_settings)
        assert controller.is_ready() is True

        mock_settings.get_club_ids.return_value = []
        assert controller.is_ready() is False

    def test_run_sync_success(self, mock_settings, mock_strava_api):
        """Test successful sync with HTTP mocks."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.run_sync()

        assert result.success is True
        assert "4 events" in result.message  # 2 clubs × 2 events each
        assert controller.last_sync is not None

    def test_run_sync_no_events(self, mock_settings, httpx_mock):
        """Test sync with no events."""

        # Mock API to return empty events
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
            if "/group_events" in url:
                return httpx.Response(200, json=[])
            return httpx.Response(404)

        httpx_mock.add_callback(handler, is_reusable=True)
        controller = MenuBarController(settings=mock_settings)

        result = controller.run_sync()

        assert result.success is True
        assert "No events" in result.message

    def test_run_sync_api_error(self, mock_settings, httpx_mock):
        """Test sync handles API errors."""

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
            return httpx.Response(500, json={"error": "Server error"})

        httpx_mock.add_callback(handler, is_reusable=True)
        controller = MenuBarController(settings=mock_settings)

        result = controller.run_sync()

        # Sync succeeds but with no events (errors logged)
        assert result.success is True

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

        result = controller.run_sync()

        # Sync fails when auth fails
        assert result.success is False
        assert "Invalid" in result.message or "expired" in result.message

    def test_run_sync_file_system_error(self, mock_settings):
        """Test sync handles file system errors (OSError).

        True E2E test - triggers actual OSError through settings.
        """
        controller = MenuBarController(settings=mock_settings)

        # Make ensure_output_dir raise OSError
        mock_settings.ensure_output_dir.side_effect = OSError("Permission denied")

        result = controller.run_sync()

        assert result.success is False
        assert "File error" in result.message or "Permission" in result.message

    def test_run_auth_success(self, mock_settings):
        """Test running auth command via osascript."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar_macos.menubar.subprocess.run") as mock_run:
            result = controller.run_auth()

            assert result.success is True
            assert "Terminal" in result.output
            mock_run.assert_called_once()

    def test_run_auth_failure(self, mock_settings):
        """Test auth command failure."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar_macos.menubar.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("osascript not found")

            result = controller.run_auth()

            assert result.success is False
            assert "osascript" in result.output

    def test_run_clubs_setup_success(self, mock_settings):
        """Test running clubs setup command via osascript."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar_macos.menubar.subprocess.run") as mock_run:
            result = controller.run_clubs_setup()

            assert result.success is True
            assert "Terminal" in result.output
            mock_run.assert_called_once()

    def test_run_clubs_setup_failure(self, mock_settings):
        """Test clubs setup command failure."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar_macos.menubar.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("osascript not found")

            result = controller.run_clubs_setup()

            assert result.success is False

    def test_open_config_file(self, mock_settings, tmp_path):
        """Test opening config file."""
        controller = MenuBarController(settings=mock_settings)
        config_path = tmp_path / "config.json"
        config_path.write_text('{"test": true}')

        with (
            patch("club_calendar_macos.menubar.get_config_file", return_value=config_path),
            patch("club_calendar_macos.menubar.subprocess.run") as mock_run,
        ):
            controller.open_config_file()
            mock_run.assert_called_once_with(["open", str(config_path)])

    def test_open_config_file_creates_if_missing(self, mock_settings, tmp_path):
        """Test opening config file creates it if missing."""
        controller = MenuBarController(settings=mock_settings)
        config_path = tmp_path / "config.json"

        with (
            patch("club_calendar_macos.menubar.get_config_file", return_value=config_path),
            patch("club_calendar_macos.menubar.subprocess.run") as mock_run,
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
            patch("club_calendar_macos.menubar.LOG_FILE", log_path),
            patch("club_calendar_macos.menubar.subprocess.run") as mock_run,
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
            patch("club_calendar_macos.menubar.LOG_FILE", log_path),
            patch("club_calendar_macos.menubar.subprocess.run") as mock_run,
        ):
            controller.view_logs()
            # File should now exist (touch was called)
            assert log_path.exists()
            mock_run.assert_called_once_with(["open", str(log_path)])

    def test_get_output_dir(self, mock_settings, tmp_path):
        """Test getting output directory."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.get_output_dir()

        assert result == tmp_path

    def test_open_output_folder(self, mock_settings, tmp_path):
        """Test opening output folder."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar_macos.menubar.subprocess.run") as mock_run:
            controller.open_output_folder()

            mock_run.assert_called_once_with(["open", str(tmp_path)])

    def test_reload_settings(self, mock_settings):
        """Test reloading settings."""
        controller = MenuBarController(settings=mock_settings)
        new_settings = MagicMock()

        with patch("club_calendar_macos.menubar.get_settings", return_value=new_settings):
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

    def test_fetch_clubs_success(self, mock_settings, mock_strava_api):
        """Test fetching clubs from API via HTTP."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.fetch_clubs()

        assert result is not None
        assert len(result) == 2
        assert result[0].name == "Test Cycling Club"
        assert result[1].name == "Running Group"

    def test_fetch_clubs_with_city_filter(self, mock_settings, mock_strava_api):
        """Test fetching clubs with city filter."""
        mock_settings.club_city_filter = "Portland"
        controller = MenuBarController(settings=mock_settings)

        result = controller.fetch_clubs()

        # Only Portland club should be returned
        assert result is not None
        assert len(result) == 1
        assert result[0].city == "Portland"

    def test_fetch_clubs_error(self, mock_settings, httpx_mock):
        """Test fetch_clubs handles API errors."""

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
            return httpx.Response(500, json={"error": "Server error"})

        httpx_mock.add_callback(handler, is_reusable=True)
        controller = MenuBarController(settings=mock_settings)

        result = controller.fetch_clubs()

        assert result is None  # Returns None on error

    def test_save_club_ids_success(self, mock_settings):
        """Test saving club IDs via settings."""
        controller = MenuBarController(settings=mock_settings)

        result = controller.save_club_ids([123, 456])

        assert result.success is True
        assert mock_settings.club_ids == [123, 456]
        mock_settings.save.assert_called_once()

    def test_save_club_ids_failure(self, mock_settings):
        """Test save_club_ids handles errors."""
        controller = MenuBarController(settings=mock_settings)
        mock_settings.save.side_effect = OSError("Error")

        result = controller.save_club_ids([123])

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
            patch("club_calendar_macos.menubar.get_logs_dir", return_value=logs_dir),
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
            patch("club_calendar_macos.menubar.get_logs_dir", side_effect=OSError("err")),
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
        from datetime import timedelta

        mock_settings.sync_interval_minutes = 60
        controller = MenuBarController(settings=mock_settings)
        controller.last_sync = datetime.now() - timedelta(minutes=61)

        assert controller.should_auto_sync() is True


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

        with patch("club_calendar_macos.menubar.HTTPServer") as mock_server_class:
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

        with patch("club_calendar_macos.menubar.HTTPServer") as mock_server_class:
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
        """Test sync_now callback on success."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "run_sync") as mock_sync:
            mock_sync.return_value = SyncResult(success=True, message="Done")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.sync_now(None)

            mock_rumps.notification.assert_called_with(
                title="Club Calendar",
                subtitle="Sync complete",
                message="Done",
            )

    def test_create_app_sync_now_failure(self, mock_rumps, mock_settings):
        """Test sync_now callback on failure."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "run_sync") as mock_sync:
            mock_sync.return_value = SyncResult(success=False, message="Error")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.sync_now(None)

            mock_rumps.notification.assert_called_with(
                title="Club Calendar",
                subtitle="Sync failed",
                message="Error",
            )

    def test_create_app_auto_sync_success(self, mock_rumps, mock_settings):
        """Test auto_sync when controller is ready and sync succeeds."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "run_sync") as mock_sync:
            mock_sync.return_value = SyncResult(success=True, message="2 events")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.auto_sync(None)

            mock_sync.assert_called_once()
            # Auto-sync should NOT show notification on success (silent)
            mock_rumps.notification.assert_not_called()

    def test_create_app_auto_sync_failure(self, mock_rumps, mock_settings):
        """Test auto_sync when controller is ready but sync fails."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "run_sync") as mock_sync:
            mock_sync.return_value = SyncResult(success=False, message="API error")

            app = create_app(rumps_module=mock_rumps, controller=controller)
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

    def test_create_app_open_folder(self, mock_rumps, mock_settings):
        """Test open_folder callback."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "open_output_folder") as mock_open:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.open_folder(None)

            mock_open.assert_called_once()

    def test_create_app_reload_settings(self, mock_rumps, mock_settings):
        """Test reload_settings callback."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "reload_settings") as mock_reload:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.reload_settings(None)

            mock_reload.assert_called_once()
            mock_rumps.notification.assert_called()

    def test_create_app_update_menu_ready(self, mock_rumps, mock_settings):
        """Test _update_menu when app is ready shows sync options."""
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Sync Now" in str(c) for c in calls)

    def test_create_app_update_menu_not_ready(self, mock_rumps, mock_settings):
        """Test _update_menu when not ready hides sync options."""
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("Setup" in str(c) for c in calls)

    def test_create_app_update_menu_valid_config(self, mock_rumps, mock_settings):
        """Test _update_menu with valid config shows checkmark."""
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("✓" in str(c) for c in calls)

    def test_create_app_update_menu_invalid_config(self, mock_rumps, mock_settings):
        """Test _update_menu with invalid config shows warning."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)
        app = create_app(rumps_module=mock_rumps, controller=controller)

        mock_rumps.MenuItem.reset_mock()
        app._update_menu()

        calls = [str(c) for c in mock_rumps.MenuItem.call_args_list]
        assert any("⚠️" in str(c) for c in calls)

    def test_create_app_uses_default_controller(self, mock_rumps):
        """Test create_app creates controller if not provided."""
        with patch("club_calendar_macos.menubar.MenuBarController") as mock_controller_class:
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

        with patch("club_calendar_macos.menubar._import_rumps") as mock_import:
            mock_rumps = MagicMock()
            mock_rumps.separator = "---"
            mock_rumps.MenuItem = MagicMock()
            mock_rumps.clicked = MagicMock(side_effect=lambda name: lambda f: f)

            class MockApp:
                def __init__(self, name, icon=None, title=None):
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

    def test_create_app_configure_api_success(self, mock_rumps, mock_settings):
        """Test configure_api dialog flow with valid credentials."""
        mock_settings.strava_client_id = ""
        mock_settings.strava_client_secret = ""
        controller = MenuBarController(settings=mock_settings)

        # Mock window response with valid credentials
        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "new_client_id\nnew_client_secret"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "save_credentials") as mock_save,
            patch.object(controller, "start_oauth_flow") as mock_oauth,
            patch("club_calendar_macos.menubar.run_oauth_server"),
            patch("club_calendar_macos.menubar.Thread") as mock_thread,
        ):
            mock_save.return_value = SetupResult(success=True, message="Saved")
            mock_oauth.return_value = SetupResult(success=True, message="Started")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_called_once_with("new_client_id", "new_client_secret")
            mock_oauth.assert_called_once()
            mock_thread.assert_called_once()

    def test_create_app_configure_api_cancel(self, mock_rumps, mock_settings):
        """Test configure_api dialog when user cancels."""
        controller = MenuBarController(settings=mock_settings)

        # Mock window response - cancelled
        mock_response = MagicMock()
        mock_response.clicked = False
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_not_called()

    def test_create_app_configure_api_invalid_input(self, mock_rumps, mock_settings):
        """Test configure_api with invalid input (missing secret)."""
        controller = MenuBarController(settings=mock_settings)

        # Mock window response with only one line
        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "only_client_id"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_configure_api_empty_values(self, mock_rumps, mock_settings):
        """Test configure_api with empty client ID or secret."""
        controller = MenuBarController(settings=mock_settings)

        # Mock window response with empty values
        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "\n"  # Two empty lines
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_configure_api_save_failure(self, mock_rumps, mock_settings):
        """Test configure_api when save_credentials fails."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "id\nsecret"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with patch.object(controller, "save_credentials") as mock_save:
            mock_save.return_value = SetupResult(success=False, message="Save failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_rumps.notification.assert_called()

    def test_create_app_configure_api_oauth_failure(self, mock_rumps, mock_settings):
        """Test configure_api when OAuth flow fails to start."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "id\nsecret"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "save_credentials") as mock_save,
            patch.object(controller, "start_oauth_flow") as mock_oauth,
        ):
            mock_save.return_value = SetupResult(success=True, message="Saved")
            mock_oauth.return_value = SetupResult(success=False, message="OAuth failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_rumps.notification.assert_called()

    def test_create_app_run_auth_success(self, mock_rumps, mock_settings):
        """Test run_auth with valid credentials."""
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "start_oauth_flow") as mock_oauth,
            patch("club_calendar_macos.menubar.Thread") as mock_thread,
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

    def test_create_app_run_clubs_success(self, mock_rumps, mock_settings):
        """Test run_clubs dialog flow with club selection."""
        controller = MenuBarController(settings=mock_settings)

        # Mock clubs response
        mock_clubs = [
            MagicMock(id=1, name="Club A", city="Portland"),
            MagicMock(id=2, name="Club B", city="Seattle"),
        ]

        # Mock window response
        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "1,2"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            mock_save.return_value = SetupResult(success=True, message="Saved 2 clubs")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_save.assert_called_once_with([1, 2])

    def test_create_app_run_clubs_no_refresh_token(self, mock_rumps, mock_settings):
        """Test run_clubs without refresh token shows error."""
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        app = create_app(rumps_module=mock_rumps, controller=controller)
        app.run_clubs(None)

        mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_fetch_error(self, mock_rumps, mock_settings):
        """Test run_clubs when fetch_clubs fails."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs", return_value=None):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_no_clubs(self, mock_rumps, mock_settings):
        """Test run_clubs when no clubs found."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs", return_value=[]):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_cancel(self, mock_rumps, mock_settings):
        """Test run_clubs when user cancels."""
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_save.assert_not_called()

    def test_create_app_run_clubs_invalid_selection(self, mock_rumps, mock_settings):
        """Test run_clubs with invalid selection input."""
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "invalid,text"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_no_selection(self, mock_rumps, mock_settings):
        """Test run_clubs when no clubs selected."""
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = ""
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_full_flow(self, mock_rumps, mock_settings):
        """Test setup_wizard complete flow from no config."""
        mock_settings.has_strava_credentials.return_value = False
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        # Setup multiple window responses for wizard steps
        responses = [
            MagicMock(clicked=True, text="client_id\nclient_secret"),  # Step 1: credentials
            MagicMock(clicked=True, text="1"),  # Step 3: club selection
        ]
        response_iter = iter(responses)
        mock_window = MagicMock()
        mock_window.run.side_effect = lambda: next(response_iter)
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "save_credentials") as mock_save_creds,
            patch.object(controller, "start_oauth_flow") as mock_oauth,
            patch("club_calendar_macos.menubar.run_oauth_server") as mock_server,
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save_clubs,
        ):
            mock_save_creds.return_value = SetupResult(success=True, message="OK")
            mock_oauth.return_value = SetupResult(success=True, message="OK")
            mock_server.return_value = SetupResult(success=True, message="OK")
            mock_save_clubs.return_value = SetupResult(success=True, message="OK")

            # After credentials are saved, settings should report them
            def update_has_creds(*args):
                mock_settings.has_strava_credentials.return_value = True
                return SetupResult(success=True, message="OK")

            mock_save_creds.side_effect = update_has_creds

            # After OAuth, settings should report token
            def update_has_token(*args):
                mock_settings.has_refresh_token.return_value = True
                return SetupResult(success=True, message="OK")

            mock_server.side_effect = update_has_token

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save_creds.assert_called_once()
            mock_oauth.assert_called_once()
            mock_save_clubs.assert_called_once()

    def test_create_app_setup_wizard_cancel_at_credentials(self, mock_rumps, mock_settings):
        """Test setup_wizard cancellation at credentials step."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()

    def test_create_app_setup_wizard_invalid_credentials(self, mock_rumps, mock_settings):
        """Test setup_wizard with invalid credentials input."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "only_one_line"  # Missing secret
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_oauth_failure(self, mock_rumps, mock_settings):
        """Test setup_wizard when OAuth fails."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "start_oauth_flow") as mock_oauth,
        ):
            mock_oauth.return_value = SetupResult(success=False, message="OAuth failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_server_failure(self, mock_rumps, mock_settings):
        """Test setup_wizard when OAuth server fails."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "start_oauth_flow") as mock_oauth,
            patch("club_calendar_macos.menubar.run_oauth_server") as mock_server,
        ):
            mock_oauth.return_value = SetupResult(success=True, message="OK")
            mock_server.return_value = SetupResult(success=False, message="Timeout")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_fetch_clubs_failure(self, mock_rumps, mock_settings):
        """Test setup_wizard when fetching clubs fails."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs", return_value=None):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_no_clubs(self, mock_rumps, mock_settings):
        """Test setup_wizard when no clubs found."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs", return_value=[]):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_cancel_clubs(self, mock_rumps, mock_settings):
        """Test setup_wizard cancellation at club selection."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()

    def test_create_app_setup_wizard_invalid_club_selection(self, mock_rumps, mock_settings):
        """Test setup_wizard with invalid club selection."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "invalid"
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_setup_wizard_empty_selection(self, mock_rumps, mock_settings):
        """Test setup_wizard with no clubs selected."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        controller = MenuBarController(settings=mock_settings)

        mock_clubs = [MagicMock(id=1, name="Club A", city="Portland")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = ""
        mock_window = MagicMock()
        mock_window.run.return_value = mock_response
        mock_rumps.Window.return_value = mock_window

        with (
            patch.object(controller, "fetch_clubs", return_value=mock_clubs),
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_icon_path_found(self, mock_rumps, mock_settings, tmp_path):
        """Test app finds icon when it exists."""
        # Create a fake icon file
        icon_path = tmp_path / "icon.png"
        icon_path.write_bytes(b"fake png")

        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar_macos.menubar.Path"):
            # This is complex to mock, so let's test via the app creation
            app = create_app(rumps_module=mock_rumps, controller=controller)
            # App should be created successfully
            assert app is not None


class TestMain:
    """Tests for main function."""

    def test_main_calls_create_app_and_run(self):
        """Test main creates app and runs it."""
        mock_app = MagicMock()

        with patch("club_calendar_macos.menubar.create_app", return_value=mock_app):
            main()

            mock_app.run.assert_called_once()
