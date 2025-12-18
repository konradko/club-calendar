"""Configuration management using YAML config file."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

import yaml

logger = logging.getLogger(__name__)

# Config schema version - bump when adding new fields or changing structure
# Comment/example changes don't require version bump (will update on next save)
CURRENT_SCHEMA_VERSION = 4


def get_config_dir() -> Path:
    """Get the config directory (macOS standard: ~/Library/Application Support/).

    Can be overridden via CLUB_CALENDAR_CONFIG_DIR environment variable.
    """
    env_dir = os.environ.get("CLUB_CALENDAR_CONFIG_DIR")
    if env_dir:
        config_dir = Path(env_dir)
    else:
        config_dir = Path.home() / "Library" / "Application Support" / "Club Calendar"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_logs_dir() -> Path:
    """Get the logs directory (macOS standard: ~/Library/Logs/)."""
    logs_dir = Path.home() / "Library" / "Logs" / "Club Calendar"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_config_file() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / "config.yaml"


class ClubInfo(TypedDict):
    """Club information stored in config."""

    name: str
    city: str | None
    enabled: bool


@dataclass
class Settings:
    """Application settings.

    Config is city-based: clubs in configured cities are auto-enabled.
    Users can manually enable/disable individual clubs via JSON config.

    Schema versions:
      v0: Unversioned (implicit for old configs without schema_version field)
      v1: Initial versioned schema with examples/comments
    """

    # Schema version for migrations
    schema_version: int = CURRENT_SCHEMA_VERSION

    # Strava API credentials
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""

    # City filter - new clubs in these cities are auto-enabled
    cities: list[str] = field(default_factory=list)

    # Clubs dict: club_id -> {name, city, enabled}
    # Persists enabled state between syncs
    clubs: dict[str, ClubInfo] = field(default_factory=dict)

    # Sync configuration
    sync_interval_minutes: int = 60  # Default: 1 hour
    sync_on_startup: bool = True  # Sync when app starts

    # Strava API URLs (override for mock server testing)
    strava_api_url: str = ""
    strava_token_url: str = ""
    strava_auth_url: str = ""

    # Calendar settings
    calendar_name: str = "Club Calendar"  # Name of calendar in Apple Calendar

    # OAuth callback port for Strava authentication (49152-65535 range avoids conflicts)
    oauth_callback_port: int = 51678

    # Logging
    debug: bool = False  # Enable verbose logging (INFO level)
    log_output: str = "none"  # "console", "file", or "none"

    # Auto-reload config on file change
    auto_reload_config: bool = False

    # Flooding prevention
    max_events_per_club_per_week: int = 10  # Max events per club per week (0 = unlimited)
    sync_weeks: int = 8  # How many weeks ahead to sync events

    # Menu display (total limit, prioritizes this week over next week)
    max_menu_events: int = 15  # Max events shown in menu (0 = unlimited)

    def get_club_ids(self) -> list[int]:
        """Return IDs of enabled clubs only."""
        return [int(club_id) for club_id, info in self.clubs.items() if info.get("enabled", False)]

    def get_enabled_clubs(self) -> dict[int, ClubInfo]:
        """Return enabled clubs with their info."""
        return {
            int(club_id): info for club_id, info in self.clubs.items() if info.get("enabled", False)
        }

    def has_strava_credentials(self) -> bool:
        """Check if Strava API credentials are configured."""
        return bool(self.strava_client_id and self.strava_client_secret)

    def has_refresh_token(self) -> bool:
        """Check if refresh token is available."""
        return bool(self.strava_refresh_token)

    def has_clubs(self) -> bool:
        """Check if any clubs are enabled."""
        return len(self.get_club_ids()) > 0

    def merge_clubs(self, fetched_clubs: list[dict]) -> int:
        """Merge fetched clubs with existing config.

        - Existing clubs: preserve enabled state
        - New clubs: auto-enable if city in cities list (or all if no cities)

        Args:
            fetched_clubs: List of club dicts from Strava API with id, name, city

        Returns:
            Number of new clubs added
        """
        new_count = 0
        cities_lower = [c.lower() for c in self.cities]

        for club in fetched_clubs:
            club_id = str(club["id"])
            club_city = club.get("city") or ""

            if club_id in self.clubs:
                # Existing club - update name/city but preserve enabled
                self.clubs[club_id]["name"] = club["name"]
                self.clubs[club_id]["city"] = club_city
            else:
                # New club - auto-enable based on city filter
                auto_enable = (
                    not cities_lower  # No cities = enable all
                    or club_city.lower() in cities_lower
                )
                self.clubs[club_id] = ClubInfo(
                    name=club["name"],
                    city=club_city,
                    enabled=auto_enable,
                )
                new_count += 1
                status = "enabled" if auto_enable else "disabled"
                logger.info(f"New club: {club['name']} ({club_city}) - {status}")

        return new_count

    def save(self) -> None:
        """Save all settings to YAML config file."""
        # Format cities as YAML with example
        if self.cities:
            cities_yaml = "\n".join(f"  - {city}" for city in self.cities)
            cities_block = f"cities:\n{cities_yaml}"
        else:
            cities_block = """# City filter - auto-enable new clubs in these cities (empty = all)
# Example:
#   cities:
#     - London
#     - Manchester
cities: []"""

        # Format clubs as YAML with example
        if self.clubs:
            clubs_lines = ["clubs:"]
            for club_id, info in self.clubs.items():
                city_str = info.get("city") or ""
                enabled = "true" if info.get("enabled", False) else "false"
                # Quote strings to handle special YAML chars like [ ] : etc
                name_quoted = f'"{info["name"]}"'
                city_quoted = f'"{city_str}"' if city_str else '""'
                clubs_lines.append(f"  {club_id}:")
                clubs_lines.append(f"    name: {name_quoted}")
                clubs_lines.append(f"    city: {city_quoted}")
                clubs_lines.append(f"    enabled: {enabled}")
            clubs_block = "\n".join(clubs_lines)
        else:
            clubs_block = """# Clubs - populated after first sync
# You can manually enable/disable clubs here
# Example:
#   clubs:
#     123456:
#       name: Morning Runners
#       city: London
#       enabled: true
clubs: {}"""

        content = f"""# Club Calendar Configuration
#
# schema_version: do not edit manually
#
# Setup:
#   1. Go to https://www.strava.com/settings/api
#   2. Create an app (any name, localhost callback URL)
#   3. Copy Client ID and Client Secret below
#   4. Save this file and click "Authenticate..." in the menu
#
# After authentication, click "Sync Now" to fetch your clubs.
# New clubs matching your cities filter are auto-enabled.

schema_version: {CURRENT_SCHEMA_VERSION}

strava_client_id: {self.strava_client_id or '""'}
strava_client_secret: {self.strava_client_secret or '""'}
strava_refresh_token: {self.strava_refresh_token or '""'}  # auto-set after auth

# Sync settings
sync_interval_minutes: {self.sync_interval_minutes}
sync_on_startup: {str(self.sync_on_startup).lower()}
sync_weeks: {self.sync_weeks}
max_events_per_club_per_week: {self.max_events_per_club_per_week}  # 0 = unlimited
max_menu_events: {self.max_menu_events}  # menu display limit (0 = unlimited)

# Calendar settings
calendar_name: "{self.calendar_name}"

# OAuth callback port (49152-65535 range recommended)
oauth_callback_port: {self.oauth_callback_port}

# Logging
debug: {str(self.debug).lower()}  # Enable verbose logging
log_output: "{self.log_output}"  # "console", "file", or "none"
auto_reload_config: {str(self.auto_reload_config).lower()}  # Watch config file for changes

{cities_block}

{clubs_block}
"""
        get_config_file().write_text(content)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from config file, with env var fallback."""
        # Load YAML config
        config_file = get_config_file()
        config: dict = {}
        if config_file.exists():
            content = config_file.read_text()
            if not content.strip():
                # Empty file - create fresh config
                logger.info("Config file empty, creating fresh config")
                cls().save()
                config = {}
            else:
                try:
                    config = yaml.safe_load(content) or {}
                except yaml.YAMLError:
                    # Corrupted config - comment it out and create fresh
                    logger.warning("Config file corrupted, creating fresh config")
                    commented = "\n".join(f"# {line}" for line in content.splitlines())
                    header = "# === CORRUPTED CONFIG (commented out) ===\n"
                    footer = "\n# === END CORRUPTED CONFIG ===\n\n"
                    # Create fresh settings, save with corrupted content preserved
                    fresh = cls()
                    fresh.save()
                    # Prepend corrupted content to saved file
                    new_content = header + commented + footer + config_file.read_text()
                    config_file.write_text(new_content)
                    config = {}

        # Get values from config file
        strava_client_id = config.get("strava_client_id", "")
        strava_client_secret = config.get("strava_client_secret", "")
        strava_refresh_token = config.get("strava_refresh_token", "")

        # Cities filter (list)
        cities = config.get("cities", [])

        # Clubs dict - convert integer keys to strings (YAML parses unquoted numbers as int)
        raw_clubs = config.get("clubs", {})
        clubs = {str(k): v for k, v in raw_clubs.items()} if raw_clubs else {}

        # Migration: convert old club_ids to clubs dict if present
        if "club_ids" in config and not clubs:
            old_ids = config.get("club_ids", [])
            for club_id in old_ids:
                clubs[str(club_id)] = ClubInfo(name=f"Club {club_id}", city=None, enabled=True)

        # Sync interval
        sync_interval_minutes = config.get("sync_interval_minutes", 60)

        # Sync on startup
        sync_on_startup = config.get("sync_on_startup", True)

        # Flooding prevention
        max_events_per_club_per_week = config.get("max_events_per_club_per_week", 10)
        sync_weeks = config.get("sync_weeks", 8)

        # Menu display
        max_menu_events = config.get("max_menu_events", 15)

        # Calendar settings
        calendar_name = config.get("calendar_name", "Club Calendar")
        oauth_callback_port = config.get("oauth_callback_port", 51678)

        # Logging
        debug = config.get("debug", False)
        log_output = config.get("log_output", "none")
        auto_reload_config = config.get("auto_reload_config", False)

        # Strava API URLs (for mock server testing)
        strava_api_url = config.get("strava_api_url", "")
        strava_token_url = config.get("strava_token_url", "")
        strava_auth_url = config.get("strava_auth_url", "")

        # Schema version (default to 0 for old unversioned configs)
        schema_version = config.get("schema_version", 0)

        settings = cls(
            schema_version=schema_version,
            strava_client_id=strava_client_id,
            strava_client_secret=strava_client_secret,
            strava_refresh_token=strava_refresh_token,
            cities=cities,
            clubs=clubs,
            sync_interval_minutes=sync_interval_minutes,
            sync_on_startup=sync_on_startup,
            max_events_per_club_per_week=max_events_per_club_per_week,
            sync_weeks=sync_weeks,
            max_menu_events=max_menu_events,
            calendar_name=calendar_name,
            oauth_callback_port=oauth_callback_port,
            debug=debug,
            log_output=log_output,
            auto_reload_config=auto_reload_config,
            strava_api_url=strava_api_url,
            strava_token_url=strava_token_url,
            strava_auth_url=strava_auth_url,
        )

        # Auto-upgrade config if schema version is older
        if schema_version < CURRENT_SCHEMA_VERSION:
            logger.info(
                f"Upgrading config from schema v{schema_version} to v{CURRENT_SCHEMA_VERSION}"
            )
            settings.schema_version = CURRENT_SCHEMA_VERSION
            settings.save()

        return settings


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings.load()
