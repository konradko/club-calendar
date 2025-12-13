"""macOS menu bar app for Club Calendar."""

import logging
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from club_calendar.config import Settings, get_config_file, get_logs_dir, get_settings
from club_calendar.core import ClubCalendarService, OAuthResult, create_service_from_settings
from club_calendar.core import SyncResult as CoreSyncResult
from club_calendar.strava import Club

# Set up logging to file (macOS standard: ~/Library/Logs/)
LOG_FILE = get_logs_dir() / "club-calendar.log"
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    message: str


@dataclass
class CommandResult:
    """Result of running a CLI command."""

    success: bool
    output: str


@dataclass
class SetupResult:
    """Result of a setup operation."""

    success: bool
    message: str


class MenuBarController:
    """Business logic for menu bar app (testable without rumps).

    Uses ClubCalendarService for core operations.
    """

    def __init__(
        self, settings: Settings | None = None, service: ClubCalendarService | None = None
    ):
        self.settings = settings or get_settings()
        self._service = service
        self.last_sync: datetime | None = None

    @property
    def service(self) -> ClubCalendarService:
        """Get or create the service instance."""
        if self._service is None:
            self._service = create_service_from_settings(self.settings)
        return self._service

    def _refresh_service(self) -> None:
        """Refresh service after settings change."""
        self._service = create_service_from_settings(self.settings)

    def get_status_text(self) -> str:
        """Get current status text."""
        if self.last_sync:
            return f"Last sync: {self.last_sync.strftime('%H:%M')}"
        return "Not synced yet"

    def get_config_status(self) -> tuple[str, bool]:
        """Get configuration status message and whether it's valid.

        Returns (message, is_valid) tuple.
        """
        if not self.settings.has_strava_credentials():
            return ("Missing Strava credentials", False)
        if not self.settings.has_refresh_token():
            return ("Not authenticated", False)
        if not self.settings.get_club_ids():
            return ("No clubs configured", False)
        club_count = len(self.settings.get_club_ids())
        return (f"{club_count} club(s) configured", True)

    def needs_setup(self) -> bool:
        """Check if initial setup is needed."""
        return not self.settings.has_strava_credentials()

    def needs_auth(self) -> bool:
        """Check if authentication is needed."""
        return self.settings.has_strava_credentials() and not self.settings.has_refresh_token()

    def needs_clubs(self) -> bool:
        """Check if club selection is needed."""
        return (
            self.settings.has_strava_credentials()
            and self.settings.has_refresh_token()
            and not self.settings.get_club_ids()
        )

    def is_ready(self) -> bool:
        """Check if app is fully configured and ready to sync."""
        return (
            self.settings.has_strava_credentials()
            and self.settings.has_refresh_token()
            and bool(self.settings.get_club_ids())
        )

    def run_sync(self) -> SyncResult:
        """Run the sync operation using the service."""
        logger.info("Starting sync...")
        try:
            club_ids = self.settings.get_club_ids()
            output_dir = self.settings.ensure_output_dir()
            result: CoreSyncResult = self.service.sync_to_files(club_ids, output_dir)

            if result.success:
                self.last_sync = datetime.now()
                logger.info(f"Sync completed: {result.event_count} events")
                return SyncResult(success=True, message=result.message)
            else:
                logger.error(f"Sync failed: {result.message}")
                return SyncResult(success=False, message=result.message)
        except OSError as e:
            # File system errors (config read, output dir creation)
            logger.error(f"File error during sync: {e}")
            return SyncResult(success=False, message=f"File error: {e}")

    def run_auth(self) -> CommandResult:
        """Run the auth command in Terminal."""
        script = 'tell app "Terminal" to do script "club-calendar auth"'
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            return CommandResult(success=True, output="Opening Terminal for authentication...")
        except Exception as e:
            return CommandResult(success=False, output=str(e))

    def run_clubs_setup(self) -> CommandResult:
        """Run the clubs --save command in Terminal."""
        script = 'tell app "Terminal" to do script "club-calendar clubs --save"'
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            return CommandResult(success=True, output="Opening Terminal for club selection...")
        except Exception as e:
            return CommandResult(success=False, output=str(e))

    def open_config_file(self) -> None:
        """Open config file in default editor."""
        config_path = get_config_file()
        if not config_path.exists():
            self.settings.save()  # Create it with current settings
        subprocess.run(["open", str(config_path)])

    def view_logs(self) -> None:
        """Open log file in default text editor."""
        if not LOG_FILE.exists():
            LOG_FILE.touch()
        subprocess.run(["open", str(LOG_FILE)])

    def get_output_dir(self) -> Path:
        """Get the output directory path."""
        return self.settings.ensure_output_dir()

    def open_output_folder(self) -> None:
        """Open the output folder in Finder."""
        subprocess.run(["open", str(self.get_output_dir())])

    def reload_settings(self) -> None:
        """Reload settings from config file."""
        self.settings = get_settings()
        self._refresh_service()

    def save_credentials(self, client_id: str, client_secret: str) -> SetupResult:
        """Save Strava API credentials."""
        try:
            self.settings.strava_client_id = client_id.strip()
            self.settings.strava_client_secret = client_secret.strip()
            self.settings.save()
            self._refresh_service()
            return SetupResult(success=True, message="Credentials saved")
        except Exception as e:
            return SetupResult(success=False, message=str(e)[:100])

    def start_oauth_flow(self) -> SetupResult:
        """Start OAuth flow by opening browser."""
        if not self.settings.has_strava_credentials():
            return SetupResult(success=False, message="Configure credentials first")

        auth_url = self.service.get_authorization_url("http://localhost:5678/callback")
        webbrowser.open(auth_url)
        return SetupResult(success=True, message="Opening browser for authentication...")

    def exchange_code_for_token(self, code: str) -> SetupResult:
        """Exchange OAuth code for refresh token using service."""
        result: OAuthResult = self.service.exchange_code(code)

        if not result.success:
            return SetupResult(success=False, message=result.message)

        # Save to settings
        return self.save_token(result.refresh_token)

    def save_token(self, refresh_token: str) -> SetupResult:
        """Save refresh token."""
        try:
            self.settings.strava_refresh_token = refresh_token
            self.settings.save()
            self._refresh_service()
            return SetupResult(success=True, message="Authentication complete")
        except Exception as e:
            return SetupResult(success=False, message=str(e)[:100])

    def fetch_clubs(self) -> list[Club] | None:
        """Fetch list of clubs from Strava API."""
        try:
            clubs = self.service.get_clubs()
            # Filter to local clubs if city filter is set
            if self.settings.club_city_filter:
                cities = [c.strip().lower() for c in self.settings.club_city_filter.split(",")]
                clubs = [c for c in clubs if (c.city or "").lower() in cities]
            return clubs
        except Exception:
            return None

    def save_club_ids(self, club_ids: list[int]) -> SetupResult:
        """Save selected club IDs."""
        try:
            self.settings.club_ids = club_ids
            self.settings.save()
            return SetupResult(success=True, message=f"Saved {len(club_ids)} club(s)")
        except Exception as e:
            return SetupResult(success=False, message=str(e)[:100])


class OAuthCallbackHandler:
    """HTTP handler for OAuth callback.

    This is a class that holds state and is configured before use.
    Call create_handler() to get a BaseHTTPRequestHandler subclass.
    """

    controller: MenuBarController | None = None
    result: SetupResult | None = None

    @classmethod
    def reset(cls) -> None:
        """Reset handler state."""
        cls.controller = None
        cls.result = None

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    def do_GET(self):  # noqa: N802 - HTTP method name
        """Handle GET request for OAuth callback."""
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]

            if code and OAuthCallbackHandler.controller:
                ctrl = OAuthCallbackHandler.controller
                OAuthCallbackHandler.result = ctrl.exchange_code_for_token(code)
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                if OAuthCallbackHandler.result.success:
                    self.wfile.write(
                        b"<html><body><h1>Success!</h1>"
                        b"<p>You can close this window.</p></body></html>"
                    )
                else:
                    msg = OAuthCallbackHandler.result.message
                    self.wfile.write(
                        f"<html><body><h1>Error</h1><p>{msg}</p></body></html>".encode()
                    )
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Error</h1><p>Missing authorization code</p></body></html>"
                )
        else:
            self.send_response(404)
            self.end_headers()


def _create_oauth_handler_class():
    """Create an HTTP request handler class that uses OAuthCallbackHandler."""

    class Handler(BaseHTTPRequestHandler, OAuthCallbackHandler):
        pass

    return Handler


def run_oauth_server(controller: MenuBarController, timeout: float = 120) -> SetupResult:
    """Run OAuth callback server and wait for callback.

    This is a standalone function for running the OAuth server in a thread.
    """
    OAuthCallbackHandler.controller = controller
    OAuthCallbackHandler.result = None

    handler_class = _create_oauth_handler_class()
    server = HTTPServer(("localhost", 5678), handler_class)
    server.timeout = timeout

    server.handle_request()
    server.server_close()

    if OAuthCallbackHandler.result:
        return OAuthCallbackHandler.result
    return SetupResult(success=False, message="OAuth callback timed out")


def _import_rumps():
    """Import rumps, exiting if not available."""
    try:
        import rumps

        return rumps
    except ImportError:
        print("rumps not installed. Install with: uv sync --extra menubar")
        sys.exit(1)


def create_app(rumps_module=None, controller=None):
    """Create and return the rumps app.

    The ClubCalendarApp class is defined inside this function because:
    1. rumps is an optional dependency (macOS only)
    2. The class must inherit from rumps.App
    3. @rumps.clicked decorators need rumps at class definition time

    This is a standard Python pattern for optional dependency injection.

    Args:
        rumps_module: Optional rumps module (for testing with mock)
        controller: Optional MenuBarController (for testing)

    Returns:
        Configured ClubCalendarApp instance
    """
    rumps = rumps_module or _import_rumps()
    controller = controller or MenuBarController()

    class ClubCalendarApp(rumps.App):
        """Menu bar app for syncing Strava club events."""

        def __init__(self):
            # Look for icon in common locations
            icon_path = None
            for path in [
                Path(__file__).parent.parent.parent / "icon.png",  # Development
                Path(sys.executable).parent.parent / "Resources" / "icon.png",  # PyInstaller bundle
                Path.home() / ".club-calendar" / "icon.png",  # User config
            ]:
                if path.exists():
                    icon_path = str(path)
                    break

            super().__init__("Club Calendar", icon=icon_path, title="📅" if not icon_path else None)
            self.controller = controller
            self._update_menu()

        def _update_menu(self) -> None:
            """Update menu items based on current state."""
            self.menu.clear()

            if self.controller.is_ready():
                # === Configured state ===
                # Status line
                self.menu.add(rumps.MenuItem(self.controller.get_status_text(), callback=None))
                club_count = len(self.controller.settings.get_club_ids())
                self.menu.add(rumps.MenuItem(f"✓ {club_count} club(s)", callback=None))
                self.menu.add(rumps.separator)

                # Main actions
                self.menu.add(rumps.MenuItem("Sync Now", callback=self.sync_now))
                self.menu.add(rumps.MenuItem("Open Calendars", callback=self.open_folder))
                self.menu.add(rumps.separator)

                # Settings submenu
                settings_menu = rumps.MenuItem("Settings")
                settings_menu.add(rumps.MenuItem("Change Clubs...", callback=self.run_clubs))
                settings_menu.add(rumps.MenuItem("Re-authenticate...", callback=self.run_auth))
                settings_menu.add(rumps.separator)
                settings_menu.add(rumps.MenuItem("Edit Config File...", callback=self.edit_config))
                self.menu.add(settings_menu)
            else:
                # === Not configured state ===
                message, _ = self.controller.get_config_status()
                self.menu.add(rumps.MenuItem(f"⚠️ {message}", callback=None))
                self.menu.add(rumps.separator)
                self.menu.add(rumps.MenuItem("Run Setup Wizard...", callback=self.setup_wizard))

            self.menu.add(rumps.separator)
            self.menu.add(rumps.MenuItem("View Logs...", callback=self.view_logs))
            self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

        @rumps.clicked("Sync Now")
        def sync_now(self, _) -> None:
            """Run sync command."""
            result = self.controller.run_sync()
            if result.success:
                self._update_menu()
                rumps.notification(
                    title="Club Calendar",
                    subtitle="Sync complete",
                    message=result.message,
                )
            else:
                rumps.notification(
                    title="Club Calendar",
                    subtitle="Sync failed",
                    message=result.message,
                )

        @rumps.clicked("Open Calendar Folder")
        def open_folder(self, _) -> None:
            """Open the output folder in Finder."""
            self.controller.open_output_folder()

        @rumps.clicked("Configure Strava API...")
        def configure_api(self, _) -> None:
            """Show dialog to configure Strava API credentials and authenticate."""
            existing_id = self.controller.settings.strava_client_id or ""
            existing_secret = self.controller.settings.strava_client_secret or ""

            # Build default text with both fields
            if existing_id or existing_secret:
                default_text = f"{existing_id}\n{existing_secret}"
            else:
                default_text = ""

            window = rumps.Window(
                message=(
                    "Enter your Strava API credentials\n"
                    "(from strava.com/settings/api)\n\n"
                    "Line 1: Client ID\n"
                    "Line 2: Client Secret"
                ),
                title="Strava API Setup",
                default_text=default_text,
                ok="Authenticate",
                cancel="Cancel",
                dimensions=(320, 60),
            )
            response = window.run()
            if not response.clicked:
                return

            # Parse two lines
            lines = response.text.strip().split("\n")
            if len(lines) < 2:
                rumps.notification(
                    "Club Calendar", "Error", "Enter Client ID on line 1, Secret on line 2"
                )
                return

            client_id = lines[0].strip()
            client_secret = lines[1].strip()

            if not client_id or not client_secret:
                rumps.notification("Club Calendar", "Error", "Both ID and secret required")
                return

            # Save credentials
            save_result = self.controller.save_credentials(client_id, client_secret)
            if not save_result.success:
                rumps.notification("Club Calendar", "Error", save_result.message)
                return

            self._update_menu()

            # Auto-trigger OAuth
            oauth_result = self.controller.start_oauth_flow()
            if not oauth_result.success:
                rumps.notification("Club Calendar", "Error", oauth_result.message)
                return

            rumps.notification(
                "Club Calendar",
                "Authentication",
                "Complete authentication in your browser...",
            )

            # Run OAuth server in background thread
            def handle_oauth():
                server_result = run_oauth_server(self.controller)
                self._update_menu()
                rumps.notification(
                    "Club Calendar",
                    "Authentication" if server_result.success else "Error",
                    server_result.message,
                )

            Thread(target=handle_oauth, daemon=True).start()

        @rumps.clicked("Authenticate with Strava...")
        def run_auth(self, _) -> None:
            """Run OAuth authentication flow (re-auth only)."""
            if not self.controller.settings.has_strava_credentials():
                rumps.notification(
                    "Club Calendar",
                    "Setup Required",
                    "Use 'Configure Strava API...' first",
                )
                return

            # Start OAuth flow
            result = self.controller.start_oauth_flow()
            if not result.success:
                rumps.notification("Club Calendar", "Error", result.message)
                return

            rumps.notification(
                "Club Calendar",
                "Authentication",
                "Complete authentication in your browser...",
            )

            # Run OAuth server in background thread
            def handle_oauth():
                oauth_result = run_oauth_server(self.controller)
                self._update_menu()
                rumps.notification(
                    "Club Calendar",
                    "Authentication" if oauth_result.success else "Error",
                    oauth_result.message,
                )

            Thread(target=handle_oauth, daemon=True).start()

        @rumps.clicked("Select Clubs...")
        def run_clubs(self, _) -> None:
            """Show dialog to select clubs."""
            if not self.controller.settings.has_refresh_token():
                rumps.notification(
                    "Club Calendar",
                    "Setup Required",
                    "Authenticate with Strava first",
                )
                return

            clubs = self.controller.fetch_clubs()
            if clubs is None:
                rumps.notification("Club Calendar", "Error", "Failed to fetch clubs")
                return

            if not clubs:
                rumps.notification("Club Calendar", "No Clubs", "No clubs found")
                return

            # Show clubs list with checkboxes via alert
            club_names = [f"{c.name} ({c.city or 'Unknown'})" for c in clubs]
            club_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(club_names))

            window = rumps.Window(
                message=f"Enter club numbers to sync (comma-separated):\n\n{club_list}",
                title="Select Clubs",
                default_text=",".join(str(i + 1) for i in range(len(clubs))),
                ok="Save",
                cancel="Cancel",
            )
            response = window.run()
            if not response.clicked:
                return

            # Parse selection
            try:
                selections = [int(x.strip()) for x in response.text.split(",") if x.strip()]
                selected_ids = [clubs[i - 1].id for i in selections if 1 <= i <= len(clubs)]
            except (ValueError, IndexError):
                rumps.notification("Club Calendar", "Error", "Invalid selection")
                return

            if not selected_ids:
                rumps.notification("Club Calendar", "Error", "No clubs selected")
                return

            result = self.controller.save_club_ids(selected_ids)
            self._update_menu()
            rumps.notification(
                title="Club Calendar",
                subtitle="Club Selection",
                message=result.message,
            )

        @rumps.clicked("Reload Settings")
        def reload_settings(self, _) -> None:
            """Reload settings and update menu."""
            self.controller.reload_settings()
            self._update_menu()
            rumps.notification(
                title="Club Calendar",
                subtitle="Settings Reloaded",
                message="Configuration updated",
            )

        @rumps.clicked("Edit Config File...")
        def edit_config(self, _) -> None:
            """Open config file in default editor."""
            self.controller.open_config_file()

        @rumps.clicked("Run Setup Wizard...")
        def setup_wizard(self, _) -> None:
            """Run the setup wizard - guides through all setup steps."""
            logger.info("Starting setup wizard")

            # Step 1: Credentials
            if not self.controller.settings.has_strava_credentials():
                window = rumps.Window(
                    message=(
                        "Welcome to Club Calendar!\n\n"
                        "Step 1: Enter your Strava API credentials\n"
                        "(Get them from strava.com/settings/api)\n\n"
                        "Line 1: Client ID\n"
                        "Line 2: Client Secret"
                    ),
                    title="Setup Wizard - Step 1/3",
                    default_text="",
                    ok="Next",
                    cancel="Cancel",
                    dimensions=(320, 60),
                )
                response = window.run()
                if not response.clicked:
                    return

                lines = response.text.strip().split("\n")
                if len(lines) < 2:
                    rumps.notification("Club Calendar", "Error", "Enter both ID and Secret")
                    return

                client_id = lines[0].strip()
                client_secret = lines[1].strip()

                if not client_id or not client_secret:
                    rumps.notification("Club Calendar", "Error", "Both fields required")
                    return

                result = self.controller.save_credentials(client_id, client_secret)
                if not result.success:
                    rumps.notification("Club Calendar", "Error", result.message)
                    return
                logger.info("Credentials saved")

            # Step 2: OAuth
            if not self.controller.settings.has_refresh_token():
                rumps.notification(
                    "Club Calendar",
                    "Step 2/3: Authentication",
                    "Opening browser to authorize with Strava...",
                )

                oauth_result = self.controller.start_oauth_flow()
                if not oauth_result.success:
                    rumps.notification("Club Calendar", "Error", oauth_result.message)
                    return

                # Wait for OAuth callback
                server_result = run_oauth_server(self.controller)
                if not server_result.success:
                    rumps.notification("Club Calendar", "Error", server_result.message)
                    return
                logger.info("OAuth completed")

            # Step 3: Select clubs
            rumps.notification(
                "Club Calendar",
                "Step 3/3: Select Clubs",
                "Fetching your clubs...",
            )

            clubs = self.controller.fetch_clubs()
            if clubs is None:
                rumps.notification("Club Calendar", "Error", "Failed to fetch clubs")
                return

            if not clubs:
                rumps.notification("Club Calendar", "Error", "No clubs found")
                return

            club_names = [f"{c.name} ({c.city or 'Unknown'})" for c in clubs]
            club_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(club_names))

            window = rumps.Window(
                message=f"Select clubs to sync (comma-separated numbers):\n\n{club_list}",
                title="Setup Wizard - Step 3/3",
                default_text=",".join(str(i + 1) for i in range(len(clubs))),
                ok="Finish",
                cancel="Cancel",
            )
            response = window.run()
            if not response.clicked:
                return

            try:
                selections = [int(x.strip()) for x in response.text.split(",") if x.strip()]
                selected_ids = [clubs[i - 1].id for i in selections if 1 <= i <= len(clubs)]
            except (ValueError, IndexError):
                rumps.notification("Club Calendar", "Error", "Invalid selection")
                return

            if not selected_ids:
                rumps.notification("Club Calendar", "Error", "No clubs selected")
                return

            result = self.controller.save_club_ids(selected_ids)
            self._update_menu()
            logger.info(f"Setup complete - {len(selected_ids)} clubs configured")
            rumps.notification(
                "Club Calendar",
                "Setup Complete!",
                f"{len(selected_ids)} club(s) configured. Click 'Sync Now' to fetch events.",
            )

        @rumps.clicked("View Logs...")
        def view_logs(self, _) -> None:
            """Open log file."""
            self.controller.view_logs()

        @rumps.clicked("Quit")
        def quit_app(self, _) -> None:
            """Quit the application."""
            rumps.quit_application()

    return ClubCalendarApp()


def main() -> None:
    """Run the menu bar app."""
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
