"""Configuration management using JSON config + macOS Keychain for secrets."""

import json
import logging
import os
import secrets as secrets_module
from dataclasses import dataclass, field
from pathlib import Path

import keyring
from club_calendar_core.ports import TokenStore

logger = logging.getLogger(__name__)

# Keychain service name
KEYCHAIN_SERVICE = "club-calendar"


def get_config_dir() -> Path:
    """Get the config directory (macOS standard: ~/Library/Application Support/)."""
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
    return get_config_dir() / "config.json"


def _get_secret(key: str) -> str:
    """Get a secret from keychain."""
    try:
        value = keyring.get_password(KEYCHAIN_SERVICE, key)
        return value or ""
    except Exception as e:
        logger.warning(f"Failed to read from keychain ({key}): {e}")
        return ""


def _set_secret(key: str, value: str) -> None:
    """Store a secret in keychain."""
    try:
        if value:
            keyring.set_password(KEYCHAIN_SERVICE, key, value)
        else:
            # Delete if empty
            try:
                keyring.delete_password(KEYCHAIN_SERVICE, key)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        logger.warning(f"Failed to write to keychain ({key}): {e}")


class KeychainTokenStore(TokenStore):
    """Token storage using macOS Keychain."""

    def get_refresh_token(self) -> str | None:
        token = _get_secret("refresh_token")
        return token if token else None

    def save_refresh_token(self, token: str) -> None:
        _set_secret("refresh_token", token)

    def get_access_token(self) -> tuple[str, int] | None:
        """Access tokens are short-lived and not persisted."""
        return None

    def save_access_token(self, token: str, expires_at: int) -> None:
        """Access tokens are short-lived and not persisted."""
        pass


@dataclass
class Settings:
    """Application settings."""

    # Strava API credentials
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""

    # Club configuration
    club_ids: list[int] = field(default_factory=list)
    club_city_filter: str = ""

    # Output configuration
    output_dir: Path = field(default_factory=lambda: get_config_dir() / "calendars")
    calendar_secret: str = ""

    def __post_init__(self):
        """Generate calendar secret if not set."""
        if not self.calendar_secret:
            self.calendar_secret = secrets_module.token_urlsafe(24)

    def get_club_ids(self) -> list[int]:
        """Return club IDs."""
        return self.club_ids

    def has_strava_credentials(self) -> bool:
        """Check if Strava API credentials are configured."""
        return bool(self.strava_client_id and self.strava_client_secret)

    def has_refresh_token(self) -> bool:
        """Check if refresh token is available."""
        return bool(self.strava_refresh_token)

    def ensure_output_dir(self) -> Path:
        """Create output directory with secret subdirectory."""
        secret_dir = self.output_dir / self.calendar_secret
        secret_dir.mkdir(parents=True, exist_ok=True)
        return secret_dir

    def save(self) -> None:
        """Save settings - secrets to keychain, rest to JSON."""
        # Secrets go to keychain
        _set_secret("client_secret", self.strava_client_secret)
        _set_secret("refresh_token", self.strava_refresh_token)

        # Non-secrets go to JSON
        config = {
            "strava_client_id": self.strava_client_id,
            "club_ids": self.club_ids,
            "club_city_filter": self.club_city_filter,
            "output_dir": str(self.output_dir),
            "calendar_secret": self.calendar_secret,
        }
        get_config_file().write_text(json.dumps(config, indent=2))

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from keychain + config file, with env var fallback."""
        # Load JSON config
        config_file = get_config_file()
        config: dict = {}
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text())
            except json.JSONDecodeError:
                config = {}

        # Get values: env vars > keychain/config
        strava_client_id = os.environ.get("STRAVA_CLIENT_ID") or config.get("strava_client_id", "")

        # Secrets: env > keychain
        strava_client_secret = os.environ.get("STRAVA_CLIENT_SECRET") or _get_secret(
            "client_secret"
        )
        strava_refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN") or _get_secret(
            "refresh_token"
        )

        # Club IDs: env var is comma-separated string, config is list
        club_ids_env = os.environ.get("CLUB_IDS", "")
        if club_ids_env:
            club_ids = [int(x.strip()) for x in club_ids_env.split(",") if x.strip()]
        else:
            club_ids = config.get("club_ids", [])

        club_city_filter = os.environ.get("CLUB_CITY_FILTER") or config.get("club_city_filter", "")

        # Output dir
        output_dir_str = os.environ.get("OUTPUT_DIR") or config.get(
            "output_dir", str(get_config_dir() / "calendars")
        )

        calendar_secret = os.environ.get("CALENDAR_SECRET") or config.get("calendar_secret", "")

        return cls(
            strava_client_id=strava_client_id,
            strava_client_secret=strava_client_secret,
            strava_refresh_token=strava_refresh_token,
            club_ids=club_ids,
            club_city_filter=club_city_filter,
            output_dir=Path(output_dir_str),
            calendar_secret=calendar_secret,
        )


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings.load()


def get_token_store() -> KeychainTokenStore:
    """Get token store instance."""
    return KeychainTokenStore()
