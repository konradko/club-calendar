"""macOS menu bar app for Club Calendar."""

import logging
import plistlib
import subprocess
import sys
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from club_calendar_core.service import ClubCalendarService, OAuthResult

from club_calendar_macos.config import (
    Settings,
    get_config_file,
    get_logs_dir,
    get_settings,
    get_token_store,
)
from club_calendar_macos.eventkit import sync_events_to_calendar
from club_calendar_macos.models import CommandResult, SetupResult, SyncResult

# Set up logging
LOG_FILE = get_logs_dir() / "club-calendar.log"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

# File handler (always)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATEFMT,
)
logger = logging.getLogger(__name__)

# Console handler for dev mode (not running from .app bundle)
if ".app/Contents/MacOS" not in sys.executable:
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
    logging.getLogger().addHandler(console)


def _create_service(settings: Settings) -> ClubCalendarService:
    """Create service from settings."""
    return ClubCalendarService(
        client_id=settings.strava_client_id,
        client_secret=settings.strava_client_secret,
        token_store=get_token_store(),
        refresh_token=settings.strava_refresh_token,
    )


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
            self._service = _create_service(self.settings)
        return self._service

    def _refresh_service(self) -> None:
        """Refresh service after settings change."""
        self._service = _create_service(self.settings)

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

        # Show cities and enabled clubs
        cities = self.settings.cities
        enabled_count = len(self.settings.get_club_ids())
        total_count = len(self.settings.clubs)

        if total_count == 0:
            msg = "Ready to sync (will fetch clubs)"
        elif enabled_count == 0:
            msg = f"{total_count} clubs (none enabled)"
        else:
            city_info = f"Cities: {', '.join(cities)}" if cities else "All cities"
            msg = f"{enabled_count}/{total_count} clubs enabled • {city_info}"

        return (msg, True)

    def needs_setup(self) -> bool:
        """Check if initial setup is needed."""
        return not self.settings.has_strava_credentials()

    def needs_auth(self) -> bool:
        """Check if authentication is needed."""
        return self.settings.has_strava_credentials() and not self.settings.has_refresh_token()

    def needs_clubs(self) -> bool:
        """Check if club configuration is needed.

        With auto-fetch, this is no longer a setup step - clubs are fetched on first sync.
        Returns False since clubs are managed via config file.
        """
        return False

    def is_ready(self) -> bool:
        """Check if app is fully configured and ready to sync.

        Only requires credentials and auth - clubs are auto-fetched on sync.
        """
        return self.settings.has_strava_credentials() and self.settings.has_refresh_token()

    def validate_strava_access(self) -> tuple[bool, str]:
        """Validate Strava API access by making a test request.

        Returns:
            Tuple of (success, message)
        """
        if not self.settings.has_strava_credentials():
            return False, "Missing Strava credentials"
        if not self.settings.has_refresh_token():
            return False, "Not authenticated with Strava"

        try:
            # Try to fetch clubs as a test - this validates token and API access
            clubs = self.service.get_clubs()
            return True, f"Connected ({len(clubs)} clubs)"
        except Exception as e:
            error_msg = str(e)[:100]
            logger.error(f"Strava validation failed: {error_msg}")
            return False, f"Strava error: {error_msg}"

    def validate_calendar_access(self) -> tuple[bool, str]:
        """Validate Apple Calendar access.

        Returns:
            Tuple of (success, message)
        """
        from club_calendar_macos.eventkit import request_calendar_access

        try:
            granted, error = request_calendar_access()
            if granted:
                return True, "Calendar access granted"
            else:
                return False, error or "Calendar access denied"
        except Exception as e:
            error_msg = str(e)[:100]
            logger.error(f"Calendar validation failed: {error_msg}")
            return False, f"Calendar error: {error_msg}"

    def validate_all(self) -> list[tuple[str, bool, str]]:
        """Validate all connections before sync.

        Returns:
            List of (check_name, success, message) tuples
        """
        results = []

        # Check Strava
        strava_ok, strava_msg = self.validate_strava_access()
        results.append(("Strava", strava_ok, strava_msg))

        # Check Calendar
        calendar_ok, calendar_msg = self.validate_calendar_access()
        results.append(("Calendar", calendar_ok, calendar_msg))

        return results

    def run_sync(self) -> SyncResult:
        """Run the sync operation - fetches clubs, events, and syncs to Apple Calendar.

        Flow:
        1. Fetch all user's clubs from Strava
        2. Merge with existing config (preserving enabled state)
        3. Save updated config
        4. Fetch events for enabled clubs only
        5. Apply flooding prevention filters
        6. Sync to Apple Calendar
        """
        logger.info("Starting sync...")
        try:
            # Step 1: Fetch all user's clubs
            clubs = self.service.get_clubs()
            logger.info(f"Fetched {len(clubs)} clubs from Strava")

            # Step 2: Merge with config
            new_clubs = self.settings.merge_clubs(
                [{"id": c.id, "name": c.name, "city": c.city} for c in clubs]
            )
            if new_clubs > 0:
                logger.info(f"Added {new_clubs} new clubs to config")

            # Step 3: Save config
            self.settings.save()

            # Step 4: Get enabled club IDs
            club_ids = self.settings.get_club_ids()
            if not club_ids:
                return SyncResult(
                    success=True,
                    message="No clubs enabled. Edit config to enable clubs.",
                )

            # Step 5: Fetch events from enabled clubs
            events = self.service.get_club_events(club_ids)
            logger.info(f"Fetched {len(events)} events from {len(club_ids)} enabled clubs")

            # Step 6: Apply flooding prevention filters
            events = self._filter_events(events)

            # Step 7: Sync to Apple Calendar
            result = sync_events_to_calendar(events)

            if result.success:
                self.last_sync = datetime.now()
                logger.info(f"Sync completed: {result.events_added} events")

                # Build notification message with event details
                message = self._build_sync_message(events, result.events_added)
                return SyncResult(success=True, message=message)
            else:
                logger.error(f"Sync failed: {result.message}")
                return SyncResult(success=False, message=result.message)
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return SyncResult(success=False, message=str(e)[:100])

    def _filter_events(self, events: list) -> list:
        """Apply flooding prevention filters.

        Filters by:
        - sync_weeks: Only include events within N weeks
        - max_events_per_club_per_week: Limit events per club per week (0 = unlimited)
        """
        from datetime import timedelta

        weeks = self.settings.sync_weeks
        max_per_week = self.settings.max_events_per_club_per_week

        # Filter by sync_weeks
        if weeks > 0:
            cutoff = datetime.now(UTC) + timedelta(weeks=weeks)
            original_count = len(events)
            events = [e for e in events if e.start_datetime <= cutoff]
            if len(events) < original_count:
                logger.info(f"Filtered to {len(events)} events within {weeks} weeks")

        # Sort by date
        events = sorted(events, key=lambda e: e.start_datetime)

        # Limit per club per week
        if max_per_week > 0:
            # Key: (club_id, year, week_number)
            week_counts: dict[tuple[int, int, int], int] = {}
            filtered = []
            for event in events:
                year, week_num, _ = event.start_datetime.isocalendar()
                key = (event.club_id, year, week_num)
                count = week_counts.get(key, 0)
                if count < max_per_week:
                    filtered.append(event)
                    week_counts[key] = count + 1
            if len(filtered) < len(events):
                logger.info(f"Limited to {len(filtered)} events ({max_per_week}/club/week)")
            events = filtered

        return events

    def _build_sync_message(self, events: list, added_count: int) -> str:
        """Build notification message with event details.

        - 0 events: "No upcoming events"
        - 1-2 events: Show event titles
        - 3+ events: Show club names with counts
        """
        if added_count == 0:
            return "No upcoming events found"

        if len(events) <= 2:
            # Show event titles
            titles = [e.title for e in events]
            return " | ".join(titles)
        else:
            # Group by club and show counts
            club_counts: dict[str, int] = {}
            for event in events:
                club_name = event.club_name or "Unknown"
                club_counts[club_name] = club_counts.get(club_name, 0) + 1

            parts = [f"{name}: {count}" for name, count in sorted(club_counts.items())]
            return f"{added_count} events • " + ", ".join(parts)

    def run_auth(self) -> CommandResult:
        """Run the auth command in Terminal."""
        script = 'tell app "Terminal" to do script "club-calendar auth"'
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            return CommandResult(success=True, output="Opening Terminal for authentication...")
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

    # Login item management

    @staticmethod
    def _get_launch_agent_path() -> Path:
        """Get path to the launch agent plist."""
        return Path.home() / "Library" / "LaunchAgents" / "com.club-calendar.menubar.plist"

    @staticmethod
    def _get_app_executable() -> str:
        """Get the path to the app executable.

        Returns the appropriate path whether running from:
        - .app bundle (DMG install): /Applications/Club Calendar.app/Contents/MacOS/Club Calendar
        - Source install: the current Python with -m entry point
        """
        executable = Path(sys.executable)

        # Check if running from a .app bundle
        if ".app/Contents/MacOS" in str(executable):
            return str(executable)

        # Running from source - use the entry point script
        # The entry point is installed as 'club-calendar-menubar' in the venv bin
        venv_bin = executable.parent
        entry_point = venv_bin / "club-calendar-menubar"
        if entry_point.exists():
            return str(entry_point)

        # Fallback: use python -m
        return f"{executable} -m club_calendar_macos.menubar"

    def is_login_enabled(self) -> bool:
        """Check if app is configured to start at login."""
        return self._get_launch_agent_path().exists()

    def enable_login(self) -> SetupResult:
        """Enable starting app at login via launchd."""
        try:
            plist_path = self._get_launch_agent_path()
            plist_path.parent.mkdir(parents=True, exist_ok=True)

            executable = self._get_app_executable()
            logs_dir = get_logs_dir()
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Build program arguments
            if " -m " in executable:
                # Python module invocation
                parts = executable.split()
                program_args = parts
            else:
                program_args = [executable]

            plist_data = {
                "Label": "com.club-calendar.menubar",
                "ProgramArguments": program_args,
                "RunAtLoad": True,
                "KeepAlive": False,  # Don't restart if quit manually
                "StandardOutPath": str(logs_dir / "menubar.log"),
                "StandardErrorPath": str(logs_dir / "menubar.error.log"),
            }

            with open(plist_path, "wb") as f:
                plistlib.dump(plist_data, f)

            # Load the agent
            subprocess.run(
                ["launchctl", "unload", str(plist_path)],
                capture_output=True,
            )
            subprocess.run(
                ["launchctl", "load", str(plist_path)],
                capture_output=True,
                check=True,
            )
            return SetupResult(success=True, message="Will start at login")
        except Exception as e:
            return SetupResult(success=False, message=str(e)[:100])

    def disable_login(self) -> SetupResult:
        """Disable starting app at login."""
        plist_path = self._get_launch_agent_path()

        try:
            if plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True,
                )
                plist_path.unlink()
            return SetupResult(success=True, message="Removed from login items")
        except Exception as e:
            return SetupResult(success=False, message=str(e)[:100])

    def set_sync_interval(self, minutes: int) -> SetupResult:
        """Set the auto-sync interval."""
        try:
            self.settings.sync_interval_minutes = minutes
            self.settings.save()
            return SetupResult(success=True, message=f"Sync interval: {minutes} min")
        except Exception as e:
            return SetupResult(success=False, message=str(e)[:100])

    def get_sync_interval(self) -> int:
        """Get the current sync interval in minutes."""
        return self.settings.sync_interval_minutes

    def should_auto_sync(self) -> bool:
        """Check if enough time has passed for auto-sync."""
        if not self.is_ready():
            return False
        if self.settings.sync_interval_minutes == 0:
            return False  # Auto-sync disabled
        if self.last_sync is None:
            return True
        elapsed = (datetime.now() - self.last_sync).total_seconds() / 60
        return elapsed >= self.settings.sync_interval_minutes


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
                        b"<html><body>"
                        b"<h1>Club Calendar</h1>"
                        b"<p><strong>Authentication successful!</strong></p>"
                        b"<p>You can close this window.</p>"
                        b"</body></html>"
                    )
                else:
                    msg = OAuthCallbackHandler.result.message
                    self.wfile.write(
                        f"<html><body>"
                        f"<h1>Club Calendar</h1>"
                        f"<p><strong>Authentication failed</strong></p>"
                        f"<p>{msg}</p>"
                        f"</body></html>".encode()
                    )
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body>"
                    b"<h1>Club Calendar</h1>"
                    b"<p><strong>Authentication failed</strong></p>"
                    b"<p>Missing authorization code</p>"
                    b"</body></html>"
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

    def notify(title, subtitle="", message=""):
        """Send notification, ignoring errors in dev mode (no Info.plist)."""
        try:
            rumps.notification(title=title, subtitle=subtitle, message=message)
        except RuntimeError:
            # No bundle identifier - running in dev mode
            logger.info(f"Notification (dev): {subtitle} - {message}")

    class ClubCalendarApp(rumps.App):
        """Menu bar app for syncing Strava club events."""

        def __init__(self):
            # Look for menu bar icon in common locations
            # Template images (ending in "Template") auto-tint for light/dark mode
            icon_path = None
            for path in [
                Path(__file__).parents[4]
                / "deploy"
                / "macos-menubar"
                / "icon_menubarTemplate.png",  # Dev
                Path(sys.executable).parent / "icon_menubarTemplate.png",  # PyInstaller bundle
            ]:
                if path.exists():
                    icon_path = str(path)
                    break

            super().__init__(
                "Club Calendar",
                icon=icon_path,
                template=True,
                title="📅" if not icon_path else None,
            )
            self.controller = controller
            self._update_menu()

        def _update_menu(self) -> None:
            """Update menu items based on current state."""
            self.menu.clear()

            if self.controller.is_ready():
                # Main actions
                self.menu.add(rumps.MenuItem("Sync Now", callback=self.sync_now))
                self.menu.add(rumps.MenuItem("Open Calendar", callback=self.open_calendar))
                self.menu.add(rumps.separator)

                # Status
                self.menu.add(rumps.MenuItem(self.controller.get_status_text(), callback=None))
                club_count = len(self.controller.settings.get_club_ids())
                if club_count > 0:
                    self.menu.add(rumps.MenuItem(f"{club_count} club(s) enabled", callback=None))
                else:
                    self.menu.add(rumps.MenuItem("Sync to fetch clubs", callback=None))
                self.menu.add(rumps.MenuItem("✓ Authenticated", callback=self.run_auth))
                self.menu.add(rumps.separator)

                # Sync interval
                interval_menu = rumps.MenuItem("Sync Interval")
                current_interval = self.controller.get_sync_interval()
                for minutes, label in [
                    (0, "Disabled"),
                    (15, "15 min"),
                    (30, "30 min"),
                    (60, "1 hour"),
                    (120, "2 hours"),
                ]:
                    item = rumps.MenuItem(
                        label, callback=lambda _, m=minutes: self.set_sync_interval(m)
                    )
                    item.state = current_interval == minutes
                    interval_menu.add(item)
                self.menu.add(interval_menu)

                self.menu.add(rumps.MenuItem("Edit Config...", callback=self.edit_config))
                self.menu.add(rumps.MenuItem("Validate Setup...", callback=self.validate_setup))
            elif not self.controller.settings.has_strava_credentials():
                # Step 1: Need credentials - click opens config
                self.menu.add(
                    rumps.MenuItem("⚙️ Set Strava Credentials...", callback=self.edit_config)
                )
                self.menu.add(rumps.MenuItem("Reload Settings", callback=self.reload_settings))
            else:
                # Step 2: Have credentials, need auth - click starts OAuth
                self.menu.add(
                    rumps.MenuItem("🔗 Authenticate with Strava...", callback=self.run_auth)
                )
                self.menu.add(rumps.separator)
                self.menu.add(rumps.MenuItem("Edit Config...", callback=self.edit_config))
                self.menu.add(rumps.MenuItem("Reload Settings", callback=self.reload_settings))

            self.menu.add(rumps.separator)
            self.menu.add(rumps.MenuItem("View Logs...", callback=self.view_logs))
            login_item = rumps.MenuItem("Start at Login", callback=self.toggle_login)
            login_item.state = self.controller.is_login_enabled()
            self.menu.add(login_item)

        def sync_now(self, _) -> None:
            """Run sync command."""
            result = self.controller.run_sync()
            if result.success:
                self._update_menu()
                notify(
                    title="Club Calendar",
                    subtitle="Calendar Updated",
                    message=result.message,
                )
            else:
                notify(
                    title="Club Calendar",
                    subtitle="Sync Failed",
                    message=result.message,
                )

        @rumps.timer(60)  # Check every minute
        def auto_sync(self, _) -> None:
            """Automatically sync in the background based on configured interval."""
            if self.controller.should_auto_sync():
                logger.info("Running auto-sync...")
                result = self.controller.run_sync()
                if result.success:
                    self._update_menu()
                    # Silent success - no notification for auto-sync
                    logger.info(f"Auto-sync complete: {result.message}")
                else:
                    # Only notify on failure
                    logger.warning(f"Auto-sync failed: {result.message}")
                    notify(
                        title="Club Calendar",
                        subtitle="Auto-sync failed",
                        message=result.message,
                    )

        def open_calendar(self, _) -> None:
            """Open the Apple Calendar app."""
            import subprocess

            subprocess.run(["open", "-a", "Calendar"])

        def run_auth(self, _) -> None:
            """Run OAuth authentication flow."""
            if not self.controller.settings.has_strava_credentials():
                notify(
                    "Club Calendar",
                    "Setup Required",
                    "Add strava_client_id and strava_client_secret to config file first",
                )
                return

            # Start OAuth flow
            result = self.controller.start_oauth_flow()
            if not result.success:
                notify("Club Calendar", "Error", result.message)
                return

            notify(
                "Club Calendar",
                "Authentication",
                "Complete authentication in your browser...",
            )

            # Run OAuth server in background thread
            def handle_oauth():
                oauth_result = run_oauth_server(self.controller)
                self._update_menu()
                notify(
                    "Club Calendar",
                    "Authentication" if oauth_result.success else "Error",
                    oauth_result.message,
                )

            Thread(target=handle_oauth, daemon=True).start()

        def reload_settings(self, _) -> None:
            """Reload settings and update menu."""
            self.controller.reload_settings()
            self._update_menu()
            notify(
                title="Club Calendar",
                subtitle="Settings Reloaded",
                message="Configuration updated",
            )

        def edit_config(self, _) -> None:
            """Open config file in default editor."""
            self.controller.open_config_file()

        def toggle_login(self, sender) -> None:
            """Toggle start at login setting."""
            if self.controller.is_login_enabled():
                result = self.controller.disable_login()
            else:
                result = self.controller.enable_login()

            self._update_menu()
            notify(
                title="Club Calendar",
                subtitle="Start at Login",
                message=result.message,
            )

        def set_sync_interval(self, minutes: int) -> None:
            """Set the sync interval."""
            result = self.controller.set_sync_interval(minutes)
            self._update_menu()
            notify(
                title="Club Calendar",
                subtitle="Sync Interval",
                message=result.message,
            )

        def view_logs(self, _) -> None:
            """Open log file."""
            self.controller.view_logs()

        def validate_setup(self, _) -> None:
            """Validate Strava and Calendar connections."""
            notify(
                "Club Calendar",
                "Validating...",
                "Checking Strava and Calendar access",
            )

            results = self.controller.validate_all()
            all_ok = all(ok for _, ok, _ in results)

            if all_ok:
                messages = [f"✓ {name}: {msg}" for name, ok, msg in results]
                notify(
                    "Club Calendar",
                    "Setup Valid",
                    " | ".join(messages),
                )
            else:
                # Show first failure
                for name, ok, msg in results:
                    if not ok:
                        notify(
                            "Club Calendar",
                            f"{name} Error",
                            msg,
                        )
                        break

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
