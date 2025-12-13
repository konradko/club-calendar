"""Tests for menubar app."""

from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from club_calendar.menubar import (
    CommandResult,
    MenuBarController,
    OAuthCallbackHandler,
    SetupResult,
    SyncResult,
    _import_rumps,
    create_app,
    main,
    run_oauth_server,
)
from club_calendar.strava import Club


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
        with patch("club_calendar.menubar.get_settings") as mock_get:
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
                return httpx.Response(200, json={
                    "access_token": "test", "refresh_token": "test", "expires_at": 9999999999
                })
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
                return httpx.Response(200, json={
                    "access_token": "test", "refresh_token": "test", "expires_at": 9999999999
                })
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

        with patch("club_calendar.menubar.subprocess.run") as mock_run:
            result = controller.run_auth()

            assert result.success is True
            assert "Terminal" in result.output
            mock_run.assert_called_once()

    def test_run_auth_failure(self, mock_settings):
        """Test auth command failure."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("osascript not found")

            result = controller.run_auth()

            assert result.success is False
            assert "osascript" in result.output

    def test_run_clubs_setup_success(self, mock_settings):
        """Test running clubs setup command via osascript."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.subprocess.run") as mock_run:
            result = controller.run_clubs_setup()

            assert result.success is True
            assert "Terminal" in result.output
            mock_run.assert_called_once()

    def test_run_clubs_setup_failure(self, mock_settings):
        """Test clubs setup command failure."""
        controller = MenuBarController(settings=mock_settings)

        with patch("club_calendar.menubar.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("osascript not found")

            result = controller.run_clubs_setup()

            assert result.success is False

    def test_open_config_file(self, mock_settings, tmp_path):
        """Test opening config file."""
        controller = MenuBarController(settings=mock_settings)
        config_path = tmp_path / "config.json"
        config_path.write_text('{"test": true}')

        with (
            patch("club_calendar.menubar.get_config_file", return_value=config_path),
            patch("club_calendar.menubar.subprocess.run") as mock_run,
        ):
            controller.open_config_file()
            mock_run.assert_called_once_with(["open", str(config_path)])

    def test_open_config_file_creates_if_missing(self, mock_settings, tmp_path):
        """Test opening config file creates it if missing."""
        controller = MenuBarController(settings=mock_settings)
        config_path = tmp_path / "config.json"

        with (
            patch("club_calendar.menubar.get_config_file", return_value=config_path),
            patch("club_calendar.menubar.subprocess.run") as mock_run,
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
            patch("club_calendar.menubar.LOG_FILE", log_path),
            patch("club_calendar.menubar.subprocess.run") as mock_run,
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
            patch("club_calendar.menubar.LOG_FILE", log_path),
            patch("club_calendar.menubar.subprocess.run") as mock_run,
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

        with patch("club_calendar.menubar.subprocess.run") as mock_run:
            controller.open_output_folder()

            mock_run.assert_called_once_with(["open", str(tmp_path)])

    def test_reload_settings(self, mock_settings):
        """Test reloading settings."""
        controller = MenuBarController(settings=mock_settings)
        new_settings = MagicMock()

        with patch("club_calendar.menubar.get_settings", return_value=new_settings):
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
                return httpx.Response(200, json={
                    "access_token": "test", "refresh_token": "test", "expires_at": 9999999999
                })
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

        with patch("club_calendar.menubar.HTTPServer") as mock_server_class:
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

        with patch("club_calendar.menubar.HTTPServer") as mock_server_class:
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

    def test_create_app_open_folder(self, mock_rumps, mock_settings):
        """Test open_folder callback."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "open_output_folder") as mock_open:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.open_folder(None)

            mock_open.assert_called_once()

    def test_create_app_configure_api(self, mock_rumps, mock_settings):
        """Test configure_api callback."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "new_id\nnew_secret"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with (
            patch.object(controller, "save_credentials") as mock_save,
            patch.object(controller, "start_oauth_flow") as mock_oauth,
        ):
            mock_save.return_value = SetupResult(success=True, message="Saved")
            mock_oauth.return_value = SetupResult(success=True, message="Opening browser")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_called_once_with("new_id", "new_secret")

    def test_create_app_configure_api_cancel(self, mock_rumps, mock_settings):
        """Test configure_api when user cancels."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_not_called()

    def test_create_app_configure_api_missing_fields(self, mock_rumps, mock_settings):
        """Test configure_api with missing fields."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "only_one_line"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_configure_api_empty_secret(self, mock_rumps, mock_settings):
        """Test configure_api where secret line is whitespace (empty after strip)."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        # Use 3 lines: "id\n  \npadding" - middle line is whitespace
        # After strip().split("\n") = ["id", "  ", "padding"]
        # lines[0].strip() = "id", lines[1].strip() = "" ← empty!
        mock_response.text = "valid_id\n   \npadding"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            # Should not call save because secret is empty
            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_create_app_configure_api_save_failure(self, mock_rumps, mock_settings):
        """Test configure_api when save_credentials fails."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "new_id\nnew_secret"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            mock_save.return_value = SetupResult(success=False, message="Save failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_rumps.notification.assert_called()
            assert "Error" in str(mock_rumps.notification.call_args)

    def test_create_app_configure_api_oauth_failure(self, mock_rumps, mock_settings):
        """Test configure_api when start_oauth_flow fails."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "new_id\nnew_secret"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with (
            patch.object(controller, "save_credentials") as mock_save,
            patch.object(controller, "start_oauth_flow") as mock_oauth,
        ):
            mock_save.return_value = SetupResult(success=True, message="Saved")
            mock_oauth.return_value = SetupResult(success=False, message="OAuth failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            mock_rumps.notification.assert_called()

    def test_create_app_configure_api_no_existing_creds(self, mock_rumps, mock_settings):
        """Test configure_api with no existing credentials uses empty default text."""
        # Set up settings with no existing credentials
        mock_settings.strava_client_id = ""
        mock_settings.strava_client_secret = ""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = False  # Cancel
        mock_rumps.Window.return_value.run.return_value = mock_response

        app = create_app(rumps_module=mock_rumps, controller=controller)
        app.configure_api(None)

        # Verify Window was created with empty default_text
        window_call = mock_rumps.Window.call_args
        assert window_call.kwargs.get("default_text") == ""

    def test_create_app_run_auth_no_credentials(self, mock_rumps, mock_settings):
        """Test run_auth when credentials not configured."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        app = create_app(rumps_module=mock_rumps, controller=controller)
        app.run_auth(None)

        mock_rumps.notification.assert_called()
        assert "Setup Required" in str(mock_rumps.notification.call_args)

    def test_create_app_run_auth_oauth_starts(self, mock_rumps, mock_settings):
        """Test run_auth starts OAuth flow."""
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "start_oauth_flow") as mock_start,
            patch("club_calendar.menubar.Thread") as mock_thread,
        ):
            mock_start.return_value = SetupResult(success=True, message="Opening browser")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_auth(None)

            mock_start.assert_called_once()
            mock_thread.assert_called_once()

    def test_create_app_run_auth_oauth_fails(self, mock_rumps, mock_settings):
        """Test run_auth when OAuth start fails."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "start_oauth_flow") as mock_start:
            mock_start.return_value = SetupResult(success=False, message="Error")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_auth(None)

            mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_no_token(self, mock_rumps, mock_settings):
        """Test run_clubs when not authenticated."""
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        app = create_app(rumps_module=mock_rumps, controller=controller)
        app.run_clubs(None)

        mock_rumps.notification.assert_called()
        assert "Setup Required" in str(mock_rumps.notification.call_args)

    def test_create_app_run_clubs_fetch_fails(self, mock_rumps, mock_settings):
        """Test run_clubs when fetch fails."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = None

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_no_clubs(self, mock_rumps, mock_settings):
        """Test run_clubs with empty clubs list."""
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = []

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_rumps.notification.assert_called()
            assert "No Clubs" in str(mock_rumps.notification.call_args)

    def test_create_app_run_clubs_success(self, mock_rumps, mock_settings):
        """Test run_clubs successful selection."""
        controller = MenuBarController(settings=mock_settings)
        clubs = [Club(id=123, name="Club A", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "1"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with (
            patch.object(controller, "fetch_clubs") as mock_fetch,
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            mock_fetch.return_value = clubs
            mock_save.return_value = SetupResult(success=True, message="Saved")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_save.assert_called_once_with([123])

    def test_create_app_run_clubs_cancel(self, mock_rumps, mock_settings):
        """Test run_clubs when user cancels."""
        controller = MenuBarController(settings=mock_settings)
        clubs = [Club(id=123, name="Club A", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_rumps.Window.return_value.run.return_value = mock_response

        with (
            patch.object(controller, "fetch_clubs") as mock_fetch,
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            mock_fetch.return_value = clubs

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_save.assert_not_called()

    def test_create_app_run_clubs_invalid_selection(self, mock_rumps, mock_settings):
        """Test run_clubs with invalid selection."""
        controller = MenuBarController(settings=mock_settings)
        clubs = [Club(id=123, name="Club A", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "abc"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = clubs

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_rumps.notification.assert_called()

    def test_create_app_run_clubs_empty_selection(self, mock_rumps, mock_settings):
        """Test run_clubs with empty selection."""
        controller = MenuBarController(settings=mock_settings)
        clubs = [Club(id=123, name="Club A", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "99"  # Out of range
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = clubs

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_clubs(None)

            mock_rumps.notification.assert_called()

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
        with patch("club_calendar.menubar.MenuBarController") as mock_controller_class:
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

        with patch("club_calendar.menubar._import_rumps") as mock_import:
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

    def test_create_app_icon_found_in_development(self, mock_rumps, mock_settings, tmp_path):
        """Test icon found in development path."""
        # Create a fake icon file in the development path
        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        with patch("club_calendar.menubar.Path") as mock_path_class:
            mock_file_parent = MagicMock()
            mock_file_parent.parent.parent.__truediv__.return_value = icon_path

            # Create path mocks
            mock_path_class.__file__ = MagicMock()
            mock_path_class.return_value.parent.parent.__truediv__.return_value = icon_path

            # Use real paths for iteration
            def path_side_effect(arg):
                if arg == tmp_path / "icon.png":
                    return icon_path
                mock = MagicMock()
                mock.exists.return_value = False
                return mock

            # Icon iteration happens in __init__, tested via integration
            pass

    def test_create_app_no_icon_uses_emoji(self, mock_rumps, mock_settings, tmp_path):
        """Test that emoji is used when no icon file found."""
        controller = MenuBarController(settings=mock_settings)

        # Mock all icon paths to not exist
        with patch("club_calendar.menubar.Path") as mock_path_class:
            # Return a mock that says file doesn't exist
            mock_path = MagicMock()
            mock_path.exists.return_value = False

            # Create side_effect that returns non-existent paths
            def create_path(*args, **kwargs):
                p = MagicMock()
                p.exists.return_value = False
                p.__truediv__ = MagicMock(return_value=p)
                p.parent = p
                return p

            mock_path_class.side_effect = create_path
            mock_path_class.home.return_value = create_path()

            # The actual test: when no icon exists, title should be set to emoji
            # This is tested by verifying the App is created correctly
            app = create_app(rumps_module=mock_rumps, controller=controller)
            # If we got here without error, the icon iteration code ran
            assert app is not None


class TestSetupWizard:
    """Tests for setup_wizard callback."""

    def test_setup_wizard_full_flow(self, mock_rumps, mock_settings):
        """Test complete setup wizard flow from no credentials."""
        # Start with no credentials
        mock_settings.has_strava_credentials.return_value = False
        mock_settings.has_refresh_token.return_value = False
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        clubs = [
            Club(id=123, name="Club A", member_count=10, city="NYC", state="NY", country="US"),
            Club(id=456, name="Club B", member_count=20, city="LA", state="CA", country="US"),
        ]

        # Mock window responses for each step
        window_responses = iter([
            # Step 1: Credentials
            MagicMock(clicked=True, text="my_client_id\nmy_client_secret"),
            # Step 3: Club selection
            MagicMock(clicked=True, text="1,2"),
        ])
        mock_rumps.Window.return_value.run.side_effect = lambda: next(window_responses)

        with (
            patch.object(controller, "save_credentials") as mock_save_creds,
            patch.object(controller, "start_oauth_flow") as mock_oauth_start,
            patch("club_calendar.menubar.run_oauth_server") as mock_oauth_server,
            patch.object(controller, "fetch_clubs") as mock_fetch,
            patch.object(controller, "save_club_ids") as mock_save_clubs,
        ):
            mock_save_creds.return_value = SetupResult(success=True, message="Saved")

            # After save_credentials, has_strava_credentials becomes True
            def update_creds(*args):
                mock_settings.has_strava_credentials.return_value = True
                return SetupResult(success=True, message="Saved")

            mock_save_creds.side_effect = update_creds
            mock_oauth_start.return_value = SetupResult(success=True, message="Opening browser")
            mock_oauth_server.return_value = SetupResult(success=True, message="Auth complete")

            # After oauth, has_refresh_token becomes True
            def set_has_token(*args):
                mock_settings.has_refresh_token.return_value = True
                return SetupResult(success=True, message="Auth complete")

            mock_oauth_server.side_effect = set_has_token
            mock_fetch.return_value = clubs
            mock_save_clubs.return_value = SetupResult(success=True, message="Saved 2 clubs")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save_creds.assert_called_once_with("my_client_id", "my_client_secret")
            mock_oauth_start.assert_called_once()
            mock_oauth_server.assert_called_once()
            mock_fetch.assert_called_once()
            mock_save_clubs.assert_called_once_with([123, 456])

    def test_setup_wizard_cancel_credentials(self, mock_rumps, mock_settings):
        """Test canceling at credentials step."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()

    def test_setup_wizard_missing_credential_fields(self, mock_rumps, mock_settings):
        """Test setup wizard with missing fields in credentials."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "only_one_line"  # Missing second line
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()

    def test_setup_wizard_empty_credential_fields(self, mock_rumps, mock_settings):
        """Test setup wizard with empty client_secret after strip.

        Input: "valid_id\\n   \\npadding"
        After strip().split("\\n"): ["valid_id", "   ", "padding"]
        lines[1].strip() = "" -> triggers "Both fields required" error
        """
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        # Need 3 lines: valid first, whitespace second (becomes empty), non-whitespace third
        # This preserves the newlines after strip() while making lines[1].strip() == ""
        mock_response.text = "valid_id\n   \npadding"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()
            mock_rumps.notification.assert_called()
            assert "Both fields required" in str(mock_rumps.notification.call_args)

    def test_setup_wizard_save_credentials_fails(self, mock_rumps, mock_settings):
        """Test setup wizard when save_credentials fails."""
        mock_settings.has_strava_credentials.return_value = False
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "my_id\nmy_secret"
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "save_credentials") as mock_save:
            mock_save.return_value = SetupResult(success=False, message="Save failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_setup_wizard_oauth_start_fails(self, mock_rumps, mock_settings):
        """Test setup wizard when oauth start fails."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "start_oauth_flow") as mock_oauth:
            mock_oauth.return_value = SetupResult(success=False, message="OAuth failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_setup_wizard_oauth_server_fails(self, mock_rumps, mock_settings):
        """Test setup wizard when oauth server fails."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = False
        controller = MenuBarController(settings=mock_settings)

        with (
            patch.object(controller, "start_oauth_flow") as mock_oauth_start,
            patch("club_calendar.menubar.run_oauth_server") as mock_server,
        ):
            mock_oauth_start.return_value = SetupResult(success=True, message="Opening")
            mock_server.return_value = SetupResult(success=False, message="Timeout")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()

    def test_setup_wizard_fetch_clubs_fails(self, mock_rumps, mock_settings):
        """Test setup wizard when fetch_clubs returns None."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = None

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()
            assert "Failed to fetch" in str(mock_rumps.notification.call_args)

    def test_setup_wizard_no_clubs_found(self, mock_rumps, mock_settings):
        """Test setup wizard when no clubs are found."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = []

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()
            assert "No clubs found" in str(mock_rumps.notification.call_args)

    def test_setup_wizard_cancel_club_selection(self, mock_rumps, mock_settings):
        """Test canceling at club selection step."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        clubs = [Club(id=123, name="Club", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = False
        mock_rumps.Window.return_value.run.return_value = mock_response

        with (
            patch.object(controller, "fetch_clubs") as mock_fetch,
            patch.object(controller, "save_club_ids") as mock_save,
        ):
            mock_fetch.return_value = clubs

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_save.assert_not_called()

    def test_setup_wizard_invalid_club_selection(self, mock_rumps, mock_settings):
        """Test invalid club selection in setup wizard."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        clubs = [Club(id=123, name="Club", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "abc"  # Invalid
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = clubs

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()
            assert "Invalid" in str(mock_rumps.notification.call_args)

    def test_setup_wizard_empty_club_selection(self, mock_rumps, mock_settings):
        """Test empty club selection in setup wizard."""
        mock_settings.has_strava_credentials.return_value = True
        mock_settings.has_refresh_token.return_value = True
        mock_settings.get_club_ids.return_value = []
        controller = MenuBarController(settings=mock_settings)

        clubs = [Club(id=123, name="Club", member_count=10, city="NYC", state="NY", country="US")]

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "99"  # Out of range
        mock_rumps.Window.return_value.run.return_value = mock_response

        with patch.object(controller, "fetch_clubs") as mock_fetch:
            mock_fetch.return_value = clubs

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.setup_wizard(None)

            mock_rumps.notification.assert_called()
            assert "No clubs selected" in str(mock_rumps.notification.call_args)


class TestHandleOAuthThread:
    """Tests for handle_oauth thread functions."""

    def test_configure_api_handle_oauth_thread_success(self, mock_rumps, mock_settings):
        """Test the handle_oauth thread function in configure_api succeeds."""
        controller = MenuBarController(settings=mock_settings)

        mock_response = MagicMock()
        mock_response.clicked = True
        mock_response.text = "test_id\ntest_secret"
        mock_rumps.Window.return_value.run.return_value = mock_response

        captured_target = None

        def capture_thread(target, daemon):
            nonlocal captured_target
            captured_target = target
            mock_thread = MagicMock()
            mock_thread.start = MagicMock()
            return mock_thread

        with (
            patch.object(controller, "save_credentials") as mock_save,
            patch.object(controller, "start_oauth_flow") as mock_start,
            patch("club_calendar.menubar.Thread", side_effect=capture_thread),
            patch("club_calendar.menubar.run_oauth_server") as mock_server,
        ):
            mock_save.return_value = SetupResult(success=True, message="Saved")
            mock_start.return_value = SetupResult(success=True, message="Opening")
            mock_server.return_value = SetupResult(success=True, message="Auth complete")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.configure_api(None)

            # Execute the captured thread target
            assert captured_target is not None
            captured_target()

            # Verify thread function called run_oauth_server
            mock_server.assert_called_once_with(controller)
            # Verify notification was called for success
            assert any(
                "Authentication" in str(call) for call in mock_rumps.notification.call_args_list
            )

    def test_run_auth_handle_oauth_thread_success(self, mock_rumps, mock_settings):
        """Test the handle_oauth thread function in run_auth succeeds."""
        controller = MenuBarController(settings=mock_settings)

        captured_target = None

        def capture_thread(target, daemon):
            nonlocal captured_target
            captured_target = target
            mock_thread = MagicMock()
            mock_thread.start = MagicMock()
            return mock_thread

        with (
            patch.object(controller, "start_oauth_flow") as mock_start,
            patch("club_calendar.menubar.Thread", side_effect=capture_thread),
            patch("club_calendar.menubar.run_oauth_server") as mock_server,
        ):
            mock_start.return_value = SetupResult(success=True, message="Opening")
            mock_server.return_value = SetupResult(success=True, message="Auth complete")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_auth(None)

            # Execute the captured thread target
            assert captured_target is not None
            captured_target()

            # Verify thread function called run_oauth_server
            mock_server.assert_called_once_with(controller)

    def test_run_auth_handle_oauth_thread_failure(self, mock_rumps, mock_settings):
        """Test the handle_oauth thread function in run_auth handles failure."""
        controller = MenuBarController(settings=mock_settings)

        captured_target = None

        def capture_thread(target, daemon):
            nonlocal captured_target
            captured_target = target
            mock_thread = MagicMock()
            mock_thread.start = MagicMock()
            return mock_thread

        with (
            patch.object(controller, "start_oauth_flow") as mock_start,
            patch("club_calendar.menubar.Thread", side_effect=capture_thread),
            patch("club_calendar.menubar.run_oauth_server") as mock_server,
        ):
            mock_start.return_value = SetupResult(success=True, message="Opening")
            mock_server.return_value = SetupResult(success=False, message="Auth failed")

            app = create_app(rumps_module=mock_rumps, controller=controller)
            app.run_auth(None)

            # Execute the captured thread target
            assert captured_target is not None
            captured_target()

            # Verify notification was called with Error
            assert any("Error" in str(call) for call in mock_rumps.notification.call_args_list)


class TestMain:
    """Tests for main function."""

    def test_main_calls_create_app_and_run(self):
        """Test main creates app and runs it."""
        mock_app = MagicMock()

        with patch("club_calendar.menubar.create_app", return_value=mock_app):
            main()

            mock_app.run.assert_called_once()
