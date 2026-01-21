"""macOS menu bar app for Club Calendar."""

import logging
import plistlib
import subprocess
import sys
import time
import traceback
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Lock, Thread, current_thread
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from watchdog.observers import Observer

import httpx
import yaml

try:
    from AppKit import (
        NSColor,
        NSFont,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSImage,
    )
    from Foundation import NSAttributedString, NSMutableAttributedString

    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False

from club_calendar.core.models import SetupResult, SyncResult
from club_calendar.core.service import ClubCalendarService, OAuthResult
from club_calendar.core.strava import (
    ClubEvent,
    StravaAuthError,
    StravaError,
    StravaRateLimitError,
)
from club_calendar.menubar.config import (
    ConfigError,
    Settings,
    get_config_file,
    get_logs_dir,
    get_settings,
)
from club_calendar.menubar.eventkit import CalendarError, sync_events_to_calendar
from club_calendar.menubar.utils import (
    DayLabel,
    get_activity_emoji,
    oauth_error_html,
    oauth_success_html,
)

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger(__name__)


def setup_logging(settings: Settings) -> None:
    """Configure logging based on settings.

    Can be called multiple times safely (e.g., on config reload).
    Cleans up existing handlers before adding new ones.
    """
    root = logging.getLogger()

    # Remove existing handlers to prevent duplicates on reconfiguration
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)

    # Re-enable logging (in case it was disabled previously)
    logging.disable(logging.NOTSET)

    if settings.log_output == "none":
        logging.disable(logging.CRITICAL)
        return

    level = logging.DEBUG if settings.debug else logging.INFO
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATEFMT)
    root.setLevel(level)

    handlers: list[logging.Handler] = []
    if settings.log_output in ("file", "both"):
        handlers.append(logging.FileHandler(get_logs_dir() / "club-calendar.log"))
    if settings.log_output in ("console", "both"):
        handlers.append(logging.StreamHandler())

    if not handlers:
        logging.disable(logging.CRITICAL)
        return

    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        root.addHandler(handler)


def is_dev_mode() -> bool:
    """Check if running in development mode (not from .app bundle)."""
    return ".app/Contents/MacOS" not in sys.executable


def is_running_tests() -> bool:
    """Check if running under pytest."""
    return "pytest" in sys.modules


def show_dev_error(title: str, error: Exception, context: str = "") -> None:
    """Log detailed error in dev mode with stack trace.

    In dev mode, logs full error details to console.
    In production or during tests, does nothing (errors go through normal flow).

    Args:
        title: Error title for log message
        error: The exception that occurred
        context: Additional context about what was being attempted
    """
    if not is_dev_mode() or is_running_tests():
        return

    error_type = type(error).__name__
    error_msg = str(error)
    stack = traceback.format_exc()

    logger.error(f"DEV ERROR [{context}]: {error_type}: {error_msg}\n{stack}")


def _categorize_error(error: Exception) -> str:
    """Categorize an error into a user-friendly message.

    Args:
        error: The exception to categorize

    Returns:
        User-friendly error message
    """
    if isinstance(error, StravaAuthError):
        return "Authentication failed. Please re-authenticate with Strava."
    if isinstance(error, StravaRateLimitError):
        return "Rate limited by Strava. Please try again in 15 minutes."
    if isinstance(error, StravaError):
        return f"Strava API error: {str(error)[:80]}"
    if isinstance(error, CalendarError):
        return f"Calendar error: {str(error)[:80]}"
    if isinstance(error, httpx.TimeoutException):
        return "Network timeout. Check your internet connection."
    if isinstance(error, httpx.HTTPError):
        return f"Network error: {str(error)[:80]}"
    if isinstance(error, OSError):
        return f"File system error: {str(error)[:80]}"
    if isinstance(error, ValueError):
        return f"Configuration error: {str(error)[:80]}"
    # Fallback for unknown errors
    return f"Unexpected error: {str(error)[:80]}"


def _create_service(settings: Settings) -> ClubCalendarService:
    """Create service from settings."""
    return ClubCalendarService(
        client_id=settings.strava_client_id,
        client_secret=settings.strava_client_secret,
        refresh_token=settings.strava_refresh_token,
        api_url=settings.strava_api_url or None,
        token_url=settings.strava_token_url or None,
        auth_url=settings.strava_auth_url or None,
    )


class MenuBarController:
    """Business logic for menu bar app (testable without rumps).

    Uses ClubCalendarService for core operations. Thread-safe access to
    shared state (last_sync, last_events) is protected by a lock.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        service: ClubCalendarService | None = None,
        menu_update_callback: "callable | None" = None,
    ):
        self.settings = settings or get_settings()
        self._service = service
        self._lock = Lock()
        self._sync_lock = Lock()  # Prevent concurrent syncs
        self._last_sync: datetime | None = None
        self._last_events: list[ClubEvent] = []
        self._config_observer: Observer | None = None
        self._menu_update_callback = menu_update_callback
        self._config_valid: bool = True
        self._config_error: str = ""
        self._strava_auth_error: bool = False
        self._has_errors: bool = False
        self._start_config_watcher()

    @property
    def last_sync(self) -> datetime | None:
        """Get last sync time (thread-safe)."""
        with self._lock:
            return self._last_sync

    @last_sync.setter
    def last_sync(self, value: datetime | None) -> None:
        """Set last sync time (thread-safe)."""
        with self._lock:
            self._last_sync = value

    @property
    def last_events(self) -> list[ClubEvent]:
        """Get last synced events (thread-safe)."""
        with self._lock:
            return self._last_events.copy()  # Return copy to prevent mutation

    @last_events.setter
    def last_events(self, value: list[ClubEvent]) -> None:
        """Set last synced events (thread-safe)."""
        with self._lock:
            self._last_events = value

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

    def is_ready(self) -> bool:
        """Check if app is fully configured and ready to sync.

        Only requires credentials and auth - clubs are auto-fetched on sync.
        Also requires valid config file.
        """
        if not self._config_valid:
            return False
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
        except (StravaError, httpx.HTTPError, httpx.TimeoutException) as e:
            error_msg = str(e)[:100]
            logger.error(f"Strava validation failed: {error_msg}")
            show_dev_error("Strava Validation", e, "Validating API access")
            return False, f"Strava error: {error_msg}"

    def validate_calendar_access(self) -> tuple[bool, str]:
        """Validate Apple Calendar access.

        Returns:
            Tuple of (success, message)
        """
        from club_calendar.menubar.eventkit import request_calendar_access

        try:
            granted, error = request_calendar_access()
            if granted:
                return True, "Calendar access granted"
            else:
                return False, error or "Calendar access denied"
        except (CalendarError, OSError) as e:
            error_msg = str(e)[:100]
            logger.error(f"Calendar validation failed: {error_msg}")
            show_dev_error("Calendar Access", e, "Requesting calendar access")
            return False, f"Calendar error: {error_msg}"
        except Exception as e:
            # Catch any unexpected errors (e.g., pyobjc errors)
            error_msg = str(e)[:100]
            logger.error(f"Calendar validation failed (unexpected): {error_msg}")
            show_dev_error("Calendar Access", e, "Requesting calendar access")
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

    def _sync_clubs(self) -> None:
        """Fetch clubs from Strava and merge with config.

        Raises:
            StravaError: On API errors
        """
        clubs = self.service.get_clubs()
        logger.info(f"Fetched {len(clubs)} clubs from Strava")

        new_clubs = self.settings.merge_clubs(
            [{"id": c.id, "name": c.name, "city": c.city} for c in clubs]
        )
        if new_clubs > 0:
            logger.info(f"Added {new_clubs} new clubs to config")

        self.settings.save()

    def _sync_events(
        self, club_ids: list[int]
    ) -> tuple[list[ClubEvent], list[tuple[int, Exception]]]:
        """Fetch and filter events from enabled clubs.

        Args:
            club_ids: List of club IDs to fetch events from

        Returns:
            Tuple of (filtered_events, fetch_errors)

        Raises:
            StravaAuthError: On authentication errors
        """
        events, fetch_errors = self.service.get_club_events(club_ids)
        if fetch_errors:
            failed_clubs = len(fetch_errors)
            logger.warning(
                f"Failed to fetch events from {failed_clubs} club(s): "
                f"{[(cid, str(e)[:50]) for cid, e in fetch_errors]}"
            )
        logger.info(f"Fetched {len(events)} events from {len(club_ids)} enabled clubs")

        # Apply flooding prevention filters and sort
        events = self._filter_events(events)
        return events, fetch_errors

    def _sync_to_calendar(
        self, events: list[ClubEvent], fetch_errors: list[tuple[int, Exception]]
    ) -> SyncResult:
        """Sync events to Apple Calendar and build result message.

        Args:
            events: Events to sync
            fetch_errors: Any errors from fetching clubs

        Returns:
            SyncResult with success status and message
        """
        result = sync_events_to_calendar(events, self.settings.calendar_name)

        if result.success:
            self.last_sync = datetime.now()
            logger.info(f"Sync completed: {result.events_added} events")

            message = self._build_sync_message(events, result.events_added)
            if fetch_errors:
                message = f"{message} ({len(fetch_errors)} club(s) failed)"
            return SyncResult(success=True, message=message)
        else:
            logger.error(f"Sync failed: {result.message}")
            return SyncResult(success=False, message=result.message)

    def run_sync(self) -> SyncResult:
        """Run the sync operation - fetches clubs, events, and syncs to Apple Calendar.

        Flow:
        1. Clear log file (prod mode only)
        2. Reload settings from disk (pick up external edits)
        3. Fetch and merge clubs from Strava
        4. Fetch events from enabled clubs
        5. Sync to Apple Calendar

        Returns:
            SyncResult with success status and message
        """
        # Prevent concurrent syncs
        if not self._sync_lock.acquire(blocking=False):
            logger.info("Sync already in progress, skipping")
            return SyncResult(success=True, message="Sync already in progress")

        try:
            return self._do_sync()
        finally:
            self._sync_lock.release()

    def _do_sync(self) -> SyncResult:
        """Internal sync implementation (must hold _sync_lock)."""
        # Reset error states at start of sync
        self._strava_auth_error = False
        self._has_errors = False

        # Clear log file at start of sync (logs show last sync only)
        log_file = get_logs_dir() / "club-calendar.log"
        if log_file.exists():
            log_file.write_text("")

        logger.info("Starting sync...")
        try:
            # Reload settings to pick up external edits
            self.reload_settings()

            # Sync clubs from Strava
            self._sync_clubs()

            # Get enabled club IDs
            club_ids = self.settings.get_club_ids()
            if not club_ids:
                return SyncResult(
                    success=True,
                    message="No clubs enabled. Edit config to enable clubs.",
                )

            # Fetch and filter events
            events, fetch_errors = self._sync_events(club_ids)

            # Store for menu display
            self.last_events = sorted(events, key=lambda e: e.start_datetime)

            # Sync to calendar
            return self._sync_to_calendar(events, fetch_errors)

        except StravaAuthError as e:
            logger.error(f"Strava auth error: {e}")
            self._strava_auth_error = True
            show_dev_error("Sync Failed", e, "Running calendar sync")
            return SyncResult(success=False, message="Invalid Strava credentials")
        except (StravaError, httpx.HTTPError, CalendarError, OSError, ValueError) as e:
            logger.error(f"Sync error: {e}")
            self._has_errors = True
            show_dev_error("Sync Failed", e, "Running calendar sync")
            return SyncResult(success=False, message=_categorize_error(e))

    def _filter_events(self, events: list[ClubEvent]) -> list[ClubEvent]:
        """Apply flooding prevention filters.

        Filters by:
        - sync_weeks: Only include events within N weeks
        - max_events_per_club_per_week: Limit events per club per week (0 = unlimited)
        """
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

    def _build_sync_message(self, events: list[ClubEvent], added_count: int) -> str:
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

    def get_upcoming_events(self, limit: int = 7) -> list[ClubEvent]:
        """Get upcoming events for menu display.

        Includes today's events (even if past start time) and future events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of events sorted by date, limited to `limit` items
        """
        now = datetime.now(UTC)
        today = now.date()
        # Include today's events (even past) and future events
        upcoming = [e for e in self.last_events if e.start_datetime.date() >= today]
        return upcoming[:limit]

    def open_event_in_calendar(self, event) -> None:
        """Open an event in Apple Calendar.

        Uses the Strava event URL which Calendar stores in the event URL field.
        Falls back to just opening Calendar app.
        """
        # Open Calendar app - it will show today's view
        # Unfortunately there's no direct way to open a specific event by URL
        subprocess.run(["open", "-a", "Calendar"])

    def open_config_file(self) -> None:
        """Open config file in default editor."""
        config_path = get_config_file()
        if not config_path.exists():
            self.settings.save()  # Create it with current settings
        subprocess.run(["open", str(config_path)])

    def view_logs(self) -> None:
        """Open log file in default text editor."""
        log_file = get_logs_dir() / "club-calendar.log"
        if not log_file.exists():
            log_file.touch()
        subprocess.run(["open", str(log_file)])

    def reload_settings(self) -> None:
        """Reload settings from config file."""
        old_auto_reload = self.settings.auto_reload_config
        try:
            self.settings = get_settings()
            self._config_valid = True
            self._config_error = ""
            self._refresh_service()
            # Reconfigure logging in case log_output or debug changed
            setup_logging(self.settings)
        except ConfigError as e:
            self._config_valid = False
            self._config_error = str(e)
            logger.error(f"Config reload failed: {e}")
            return  # Don't restart watcher or refresh service

        # Restart watcher if setting changed
        if self.settings.auto_reload_config != old_auto_reload:
            self._stop_config_watcher()
            self._start_config_watcher()

    def is_config_valid(self) -> bool:
        """Check if config file is valid."""
        return self._config_valid

    def get_config_error(self) -> str:
        """Get config error message if invalid."""
        return self._config_error

    def has_strava_auth_error(self) -> bool:
        """Check if there's a Strava authentication error."""
        return self._strava_auth_error

    def clear_strava_auth_error(self) -> None:
        """Clear Strava auth error state (called after config edit)."""
        self._strava_auth_error = False

    def has_errors(self) -> bool:
        """Check if there are unhandled errors logged."""
        return self._has_errors

    def clear_errors(self) -> None:
        """Clear error state (called after viewing logs)."""
        self._has_errors = False

    def _start_config_watcher(self) -> None:
        """Start file watcher if auto_reload_config is enabled."""
        if not self.settings.auto_reload_config:
            return
        if self._config_observer is not None:
            return  # Already running

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.warning("watchdog not available, config auto-reload disabled")
            return

        config_path = get_config_file()
        config_dir = config_path.parent
        debounce_seconds = 0.5
        last_reload: list[float] = [0.0]  # Mutable container for closure

        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(handler_self, callback: "callable", target_path: Path):  # noqa: N805
                handler_self._callback = callback
                handler_self._target_path = target_path

            def on_modified(handler_self, event) -> None:  # noqa: N805
                if event.is_directory:
                    return
                if Path(event.src_path) != handler_self._target_path:
                    return
                now = time.time()
                if now - last_reload[0] < debounce_seconds:
                    return
                last_reload[0] = now
                logger.info("Config file changed, reloading...")
                handler_self._callback()

        def on_config_changed() -> None:
            self.reload_settings()
            if self._menu_update_callback:
                self._menu_update_callback()

        handler = ConfigFileHandler(on_config_changed, config_path)
        self._config_observer = Observer()
        self._config_observer.schedule(handler, str(config_dir), recursive=False)
        self._config_observer.daemon = True
        self._config_observer.start()
        logger.info(f"Started config file watcher for {config_path}")

    def _stop_config_watcher(self) -> None:
        """Stop file watcher if running."""
        if self._config_observer is not None:
            self._config_observer.stop()
            # Don't join if called from within the watcher thread itself
            # (e.g., during reload_settings triggered by file change)
            if current_thread() is not self._config_observer:
                self._config_observer.join(timeout=1.0)
            self._config_observer = None
            logger.info("Stopped config file watcher")

    def save_credentials(self, client_id: str, client_secret: str) -> SetupResult:
        """Save Strava API credentials."""
        try:
            self.settings.strava_client_id = client_id.strip()
            self.settings.strava_client_secret = client_secret.strip()
            self.settings.save()
            self._refresh_service()
            return SetupResult(success=True, message="Credentials saved")
        except (OSError, yaml.YAMLError, PermissionError) as e:
            show_dev_error("Save Credentials", e, "Saving Strava credentials")
            return SetupResult(success=False, message=str(e)[:100])

    def start_oauth_flow(self) -> SetupResult:
        """Start OAuth flow by opening browser."""
        if not self.settings.has_strava_credentials():
            return SetupResult(success=False, message="Configure credentials first")

        port = self.settings.oauth_callback_port
        auth_url = self.service.get_authorization_url(f"http://localhost:{port}/callback")
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
        except (OSError, yaml.YAMLError, PermissionError) as e:
            show_dev_error("Save Token", e, "Saving refresh token")
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
        return f"{executable} -m club_calendar.menubar"

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
        except (OSError, plistlib.InvalidFileException, subprocess.SubprocessError) as e:
            show_dev_error("Enable Login", e, "Setting up launch agent")
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
        except (OSError, subprocess.SubprocessError) as e:
            show_dev_error("Disable Login", e, "Removing launch agent")
            return SetupResult(success=False, message=str(e)[:100])

    def set_sync_interval(self, minutes: int) -> SetupResult:
        """Set the auto-sync interval."""
        try:
            self.settings.sync_interval_minutes = minutes
            self.settings.save()
            return SetupResult(success=True, message=f"Sync interval: {minutes} min")
        except (OSError, yaml.YAMLError, PermissionError) as e:
            show_dev_error("Set Interval", e, "Saving sync interval")
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
        if self._sync_lock.locked():
            return False  # Sync already in progress
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
                    self.wfile.write(oauth_success_html())
                else:
                    self.wfile.write(oauth_error_html(OAuthCallbackHandler.result.message))
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(oauth_error_html("Missing authorization code"))
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

    port = controller.settings.oauth_callback_port
    handler_class = _create_oauth_handler_class()
    server = HTTPServer(("localhost", port), handler_class)
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

    # Configure logging based on settings
    setup_logging(controller.settings)

    def notify(title, subtitle="", message=""):
        """Send notification, ignoring errors in dev mode (no Info.plist)."""
        try:
            rumps.notification(title=title, subtitle=subtitle, message=message)
        except RuntimeError:
            # No bundle identifier - running in dev mode
            logger.info(f"Notification (dev): {subtitle} - {message}")

    class ClubCalendarApp(rumps.App):
        """Menu bar app for syncing Strava club events.

        This class is defined inside create_app() because:
        1. rumps is an optional dependency (macOS only)
        2. The class must inherit from rumps.App
        3. @rumps.clicked decorators need rumps at class definition time

        Thread safety: Background operations (sync, OAuth) run in daemon threads.
        Menu updates from background threads use NSOperationQueue.mainQueue() for
        thread-safe AppKit access.
        """

        def __init__(self):
            # Look for menu bar icon in common locations
            # Template images (ending in "Template") auto-tint for light/dark mode
            icon_path = None
            icon_path_2x = None
            search_bases = [
                Path(__file__).parents[3] / "deploy",  # Dev
            ]
            # PyInstaller bundle: check _MEIPASS (frozen app resources)
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                search_bases.insert(0, Path(sys._MEIPASS))
            for base in search_bases:
                path_1x = base / "icon_menubarTemplate.png"
                path_2x = base / "icon_menubarTemplate@2x.png"
                if path_1x.exists():
                    icon_path = str(path_1x)
                    if path_2x.exists():
                        icon_path_2x = str(path_2x)
                    break

            super().__init__(
                "Club Calendar",
                icon=None,  # We'll set it manually for proper Retina support
                template=True,
                title="📅" if not icon_path else None,
                quit_button=None,  # We add our own Quit button
            )

            # Create multi-resolution NSImage for crisp Retina display
            if icon_path and HAS_APPKIT:
                self._set_retina_icon(icon_path, icon_path_2x)

            self.controller = controller
            # Set menu update callback for config file watcher
            self.controller._menu_update_callback = self._update_menu_on_main_thread
            self._update_menu()

            # Auto-sync on startup if ready and enabled
            if self.controller.is_ready() and self.controller.settings.sync_on_startup:
                self._sync_on_startup()

        def _set_retina_icon(self, path_1x: str, path_2x: str | None) -> None:
            """Set menu bar icon with proper Retina support.

            Creates an NSImage with both 1x and 2x representations so macOS
            can display the correct resolution for the screen.
            """
            # Create NSImage at the correct point size (22x22 points)
            image = NSImage.alloc().initWithSize_((22, 22))

            # Load 1x representation
            rep_1x = NSImage.alloc().initByReferencingFile_(path_1x)
            if rep_1x:
                for rep in rep_1x.representations():
                    image.addRepresentation_(rep)

            # Load 2x representation if available
            if path_2x:
                rep_2x = NSImage.alloc().initByReferencingFile_(path_2x)
                if rep_2x:
                    for rep in rep_2x.representations():
                        image.addRepresentation_(rep)

            # Enable template mode for automatic light/dark theme adaptation
            image.setTemplate_(True)

            # Set directly on the status item (bypass rumps' 20x20 scaling)
            self._icon_nsimage = image
            self._icon = path_1x

        def _sync_on_startup(self) -> None:
            """Run initial sync in background thread."""

            def do_sync():
                result = self.controller.run_sync()
                if result.success:
                    self._update_menu_on_main_thread()

            Thread(target=do_sync, daemon=True).start()

        def _get_day_label(self, event_dt: datetime) -> DayLabel:
            """Categorize event date for menu grouping.

            Returns DayLabel with formatted string and flags for:
            - Today: "Today (Mon, 16 Dec):"
            - Tomorrow: "Tomorrow (Tue, 17 Dec):"
            - This week: "Wednesday (18 Dec):"
            - Next week: "22 Dec (Mon):"
            - Beyond: "25 Dec (Thu):"

            Args:
                event_dt: Event datetime (expected to be localized)

            Returns:
                DayLabel with label string and week categorization flags
            """
            now = datetime.now(event_dt.tzinfo or UTC)
            event_date = event_dt.date()
            today = now.date()

            event_year, event_week, _ = event_dt.isocalendar()
            now_year, current_week, _ = now.isocalendar()
            is_this_week = event_year == now_year and event_week == current_week
            is_next_week = (event_year == now_year and event_week == current_week + 1) or (
                event_year == now_year + 1 and current_week >= 52 and event_week == 1
            )

            if event_date == today:
                label = f"Today ({event_dt.strftime('%a, %d %b')}):"
                return DayLabel(label, is_this_week=True, is_today=True, is_next_week=False)
            elif event_date == today + timedelta(days=1):
                label = f"Tomorrow ({event_dt.strftime('%a, %d %b')}):"
                return DayLabel(label, is_this_week=True, is_today=False, is_next_week=False)
            elif is_this_week:
                label = f"{event_dt.strftime('%A')} ({event_dt.strftime('%d %b')}):"
                return DayLabel(label, is_this_week=True, is_today=False, is_next_week=False)
            elif is_next_week:
                label = f"{event_dt.strftime('%d %b')} ({event_dt.strftime('%a')}):"
                return DayLabel(label, is_this_week=False, is_today=False, is_next_week=True)
            else:
                label = f"{event_dt.strftime('%d %b')} ({event_dt.strftime('%a')}):"
                return DayLabel(label, is_this_week=False, is_today=False, is_next_week=False)

        def _create_muted_menu_item(self, label: str, callback) -> "rumps.MenuItem":
            """Create a menu item with muted (gray) text for event details.

            Args:
                label: The menu item text
                callback: Callback function when clicked

            Returns:
                A rumps.MenuItem with muted text styling
            """
            item = rumps.MenuItem(label, callback=callback)

            # Apply muted color if AppKit is available
            if HAS_APPKIT:
                try:
                    # Create attributed string with secondary label color (gray)
                    attrs = {
                        NSForegroundColorAttributeName: NSColor.secondaryLabelColor(),
                    }
                    attributed_title = NSAttributedString.alloc().initWithString_attributes_(
                        label, attrs
                    )
                    # Access underlying NSMenuItem and set attributed title
                    item._menuitem.setAttributedTitle_(attributed_title)
                except Exception:
                    pass  # Fall back to plain text if styling fails

            return item

        def _create_bold_prefix_menu_item(
            self, bold_part: str, regular_part: str
        ) -> "rumps.MenuItem":
            """Create a menu item with bold prefix and regular suffix.

            Args:
                bold_part: Text to display in bold (e.g., "Today")
                regular_part: Text to display in regular weight (e.g., " (Tue, 16 Dec):")

            Returns:
                A rumps.MenuItem with mixed text styling
            """
            full_label = bold_part + regular_part
            item = rumps.MenuItem(full_label, callback=None)

            # Apply mixed formatting if AppKit is available
            if HAS_APPKIT:
                try:
                    # Create mutable attributed string
                    attr_string = NSMutableAttributedString.alloc().initWithString_(full_label)

                    # Apply bold to the prefix
                    bold_font = NSFont.boldSystemFontOfSize_(0)
                    bold_range = (0, len(bold_part))
                    attr_string.addAttribute_value_range_(
                        NSFontAttributeName, bold_font, bold_range
                    )

                    item._menuitem.setAttributedTitle_(attr_string)
                except Exception:
                    pass  # Fall back to plain text if styling fails

            return item

        def _add_event_menu_item(
            self, event, dt: datetime, is_today: bool, is_this_week: bool
        ) -> None:
            """Add a single event to the menu.

            Args:
                event: ClubEvent to display
                dt: Localized datetime
                is_today: Whether event is today
                is_this_week: Whether event is this week (affects format)
            """
            emoji = get_activity_emoji(event.activity_type)
            club = event.club_name
            title = event.title[:25] + "…" if len(event.title) > 25 else event.title

            # Simple format: emoji  time  club: title
            # Day info comes from section headers
            time_str = dt.strftime("%H:%M")
            label = f"{emoji}  {time_str}  {club}: {title}"

            # Future today events are normal, past and future days are muted
            now = datetime.now(dt.tzinfo)
            is_future_today = is_today and dt > now
            if is_future_today:
                item = rumps.MenuItem(label, callback=lambda _, e=event: self.open_event(e))
            else:
                item = self._create_muted_menu_item(
                    label,
                    callback=lambda _, e=event: self.open_event(e),
                )
            self.menu.add(item)

        def _build_events_section(self, max_events: int) -> None:
            """Build the upcoming events section of the menu."""
            upcoming = self.controller.get_upcoming_events(limit=50)
            if not upcoming:
                return

            # Separate this week and next week events
            this_week_events = []
            next_week_events = []

            for event in upcoming:
                dt = event.start_datetime.astimezone()
                day_label, is_this_week, is_today, is_next_week = self._get_day_label(dt)
                if is_this_week:
                    this_week_events.append((event, dt, day_label, is_today))
                elif is_next_week:
                    next_week_events.append((event, dt, day_label))

            # Apply total limit: this week first, then next week
            total_shown = 0
            current_label = None

            # This week events
            for event, dt, day_label, is_today in this_week_events:
                if max_events > 0 and total_shown >= max_events:
                    break

                # Day header
                if day_label != current_label:
                    if day_label.startswith("Today"):
                        self.menu.add(self._create_bold_prefix_menu_item("Today", day_label[5:]))
                    elif day_label.startswith("Tomorrow"):
                        self.menu.add(self._create_bold_prefix_menu_item("Tomorrow", day_label[8:]))
                    else:
                        self.menu.add(rumps.MenuItem(day_label, callback=None))
                    current_label = day_label

                total_shown += 1
                self._add_event_menu_item(event, dt, is_today, is_this_week=True)

            # Next week events (fill remaining slots)
            if next_week_events and (max_events == 0 or total_shown < max_events):
                self.menu.add(rumps.separator)
                next_week_label = None

                for event, dt, day_label in next_week_events:
                    if max_events > 0 and total_shown >= max_events:
                        break

                    # Day header within next week
                    if day_label != next_week_label:
                        self.menu.add(rumps.MenuItem(day_label, callback=None))
                        next_week_label = day_label

                    total_shown += 1
                    self._add_event_menu_item(event, dt, is_today=False, is_this_week=False)

            self.menu.add(rumps.separator)

        def _build_settings_menu(self) -> "rumps.MenuItem":
            """Build the settings submenu."""
            settings_menu = rumps.MenuItem("Settings")

            # Sync interval
            interval_menu = rumps.MenuItem("Sync interval")
            current_interval = self.controller.get_sync_interval()
            for minutes, label in [
                (0, "Disabled"),
                (30, "30 min"),
                (60, "1 hour"),
                (120, "2 hours"),
                (240, "4 hours"),
            ]:
                item = rumps.MenuItem(
                    label, callback=lambda _, m=minutes: self.set_sync_interval(m)
                )
                item.state = current_interval == minutes
                interval_menu.add(item)
            settings_menu.add(interval_menu)

            login_item = rumps.MenuItem("Start at login", callback=self.toggle_login)
            login_item.state = self.controller.is_login_enabled()
            settings_menu.add(login_item)

            settings_menu.add(rumps.separator)
            settings_menu.add(rumps.MenuItem("Edit config...", callback=self.edit_config))
            settings_menu.add(rumps.MenuItem("Reload config", callback=self.reload_config))
            settings_menu.add(rumps.MenuItem("View logs...", callback=self.view_logs))

            return settings_menu

        def _update_menu(self) -> None:
            """Update menu items based on current state."""
            self.menu.clear()

            # Show warning states at top of menu
            if not self.controller.is_config_valid():
                self.menu.add(rumps.MenuItem("⚠️ Invalid config", callback=self.edit_config))
                self.menu.add(rumps.separator)
                self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))
                return

            if self.controller.has_strava_auth_error():
                self.menu.add(
                    rumps.MenuItem("⚠️ Invalid Strava credentials", callback=self.edit_config)
                )
                self.menu.add(rumps.separator)

            if self.controller.has_errors():
                self.menu.add(rumps.MenuItem("⚠️ Errors", callback=self.view_logs))
                self.menu.add(rumps.separator)

            if self.controller.is_ready():
                # Upcoming events grouped by day
                max_events = self.controller.settings.max_menu_events
                self._build_events_section(max_events)

                # Main actions
                self.menu.add(rumps.MenuItem("Sync now", callback=self.sync_now))
                self.menu.add(rumps.separator)

                # Settings submenu
                self.menu.add(self._build_settings_menu())
            elif not self.controller.settings.has_strava_credentials():
                # Step 1: Need credentials - click opens config
                self.menu.add(
                    rumps.MenuItem("Set Strava credentials...", callback=self.edit_config)
                )
                self.menu.add(rumps.separator)
                self.menu.add(self._build_settings_menu())
            else:
                # Step 2: Have credentials, need auth - click starts OAuth
                self.menu.add(rumps.MenuItem("Authenticate with Strava...", callback=self.run_auth))
                self.menu.add(rumps.separator)
                self.menu.add(self._build_settings_menu())

            self.menu.add(rumps.separator)
            self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

        def _update_menu_on_main_thread(self) -> None:
            """Schedule menu update on main thread (required by AppKit).

            Uses NSOperationQueue for thread-safe menu updates. In test environments
            without PyObjC, logs a warning - callers should mock this method.
            """
            try:
                from Foundation import NSOperationQueue

                NSOperationQueue.mainQueue().addOperationWithBlock_(self._update_menu)
            except ImportError:
                # In tests, this should be mocked. Direct call from background thread
                # would cause race conditions with AppKit, so we log and skip.
                logger.warning(
                    "Foundation not available - skipping menu update from background thread"
                )
                # Only safe to call directly if we're on the main thread (e.g., in tests)
                import threading

                if threading.current_thread() is threading.main_thread():
                    self._update_menu()

        def sync_now(self, _) -> None:
            """Run sync command in background thread."""

            def do_sync():
                # Validate calendar access first
                cal_ok, cal_msg = self.controller.validate_calendar_access()
                if not cal_ok:
                    notify(
                        title="Club Calendar",
                        subtitle="Calendar Error",
                        message=cal_msg,
                    )
                    return

                result = self.controller.run_sync()
                if result.success:
                    self._update_menu_on_main_thread()
                    # Silent success - menu shows last sync time
                else:
                    notify(
                        title="Club Calendar",
                        subtitle="Sync Failed",
                        message=result.message,
                    )

            Thread(target=do_sync, daemon=True).start()

        @rumps.timer(60)  # Check every minute
        def auto_sync(self, _) -> None:
            """Automatically sync in the background based on configured interval."""
            if not self.controller.should_auto_sync():
                return

            logger.info("Running auto-sync...")

            def do_auto_sync():
                # Validate calendar access first
                cal_ok, cal_msg = self.controller.validate_calendar_access()
                if not cal_ok:
                    logger.warning(f"Auto-sync skipped: {cal_msg}")
                    notify(
                        title="Club Calendar",
                        subtitle="Calendar Error",
                        message=cal_msg,
                    )
                    return

                result = self.controller.run_sync()
                if result.success:
                    self._update_menu_on_main_thread()
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

            Thread(target=do_auto_sync, daemon=True).start()

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

            # Run OAuth server in background thread
            def handle_oauth():
                oauth_result = run_oauth_server(self.controller)
                self._update_menu()
                # Only notify on error - success is visible in menu
                if not oauth_result.success:
                    notify("Club Calendar", "Authentication Failed", oauth_result.message)

            Thread(target=handle_oauth, daemon=True).start()

        def open_event(self, event) -> None:
            """Open event in Apple Calendar."""
            self.controller.open_event_in_calendar(event)

        def edit_config(self, _) -> None:
            """Open config file in default editor."""
            self.controller.clear_strava_auth_error()
            self.controller.open_config_file()

        def toggle_login(self, sender) -> None:
            """Toggle start at login setting."""
            if self.controller.is_login_enabled():
                self.controller.disable_login()
            else:
                self.controller.enable_login()
            self._update_menu()
            # Silent - menu checkmark shows state

        def set_sync_interval(self, minutes: int) -> None:
            """Set the sync interval."""
            self.controller.set_sync_interval(minutes)
            self._update_menu()
            # Silent - menu checkmark shows selected interval

        def reload_config(self, _) -> None:
            """Reload config from file."""
            self.controller.reload_settings()
            self._update_menu()
            notify(title="Club Calendar", subtitle="Config reloaded", message="")

        def view_logs(self, _) -> None:
            """Open log file and clear error state."""
            self.controller.clear_errors()
            self.controller.view_logs()
            self._update_menu()

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
