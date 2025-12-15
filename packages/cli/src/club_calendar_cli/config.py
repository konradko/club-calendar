"""Environment-based configuration for CLI.

This module provides a simple config implementation using environment
variables and .env files. It implements the TokenStore protocol from core.
"""

import os
from pathlib import Path

from club_calendar_core.ports import TokenStore
from dotenv import load_dotenv

# Load .env file from current directory
load_dotenv()


class EnvTokenStore(TokenStore):
    """Token storage using environment variables.

    For CLI usage, tokens are read from environment variables.
    Saving tokens updates the .env file.
    """

    def __init__(self, env_file: Path | None = None):
        self.env_file = env_file or Path(".env")

    def get_refresh_token(self) -> str | None:
        return os.environ.get("STRAVA_REFRESH_TOKEN")

    def save_refresh_token(self, token: str) -> None:
        """Save token by appending to .env file."""
        os.environ["STRAVA_REFRESH_TOKEN"] = token
        self._update_env_file("STRAVA_REFRESH_TOKEN", token)

    def get_access_token(self) -> tuple[str, int] | None:
        """Access tokens are not persisted in env-based config."""
        return None

    def save_access_token(self, token: str, expires_at: int) -> None:
        """Access tokens are not persisted in env-based config."""
        pass

    def _update_env_file(self, key: str, value: str) -> None:
        """Update or add a key in the .env file."""
        if not self.env_file.exists():
            self.env_file.write_text(f"{key}={value}\n")
            return

        lines = self.env_file.read_text().splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}")

        self.env_file.write_text("\n".join(new_lines) + "\n")


class EnvConfig:
    """Configuration from environment variables.

    Environment variables (can be set in .env file):
    - STRAVA_CLIENT_ID: Strava API client ID
    - STRAVA_CLIENT_SECRET: Strava API client secret
    - STRAVA_REFRESH_TOKEN: OAuth refresh token
    - STRAVA_CLUB_IDS: Comma-separated list of club IDs
    - CLUB_CITY_FILTER: Comma-separated list of cities for filtering
    - OUTPUT_DIR: Directory for calendar files (default: ./output)
    """

    def __init__(self):
        self._token_store = EnvTokenStore()

    @property
    def client_id(self) -> str:
        return os.environ.get("STRAVA_CLIENT_ID", "")

    @property
    def client_secret(self) -> str:
        return os.environ.get("STRAVA_CLIENT_SECRET", "")

    @property
    def refresh_token(self) -> str | None:
        return self._token_store.get_refresh_token()

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        if value:
            self._token_store.save_refresh_token(value)

    @property
    def club_ids(self) -> list[int]:
        ids_str = os.environ.get("STRAVA_CLUB_IDS", "")
        if not ids_str:
            return []
        return [int(x.strip()) for x in ids_str.split(",") if x.strip()]

    @club_ids.setter
    def club_ids(self, value: list[int]) -> None:
        ids_str = ",".join(str(x) for x in value)
        os.environ["STRAVA_CLUB_IDS"] = ids_str
        self._token_store._update_env_file("STRAVA_CLUB_IDS", ids_str)

    @property
    def city_filter(self) -> list[str]:
        cities_str = os.environ.get("CLUB_CITY_FILTER", "")
        if not cities_str:
            return []
        return [c.strip() for c in cities_str.split(",") if c.strip()]

    @property
    def output_dir(self) -> Path:
        return Path(os.environ.get("OUTPUT_DIR", "./output"))

    @property
    def token_store(self) -> EnvTokenStore:
        return self._token_store

    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def has_refresh_token(self) -> bool:
        return bool(self.refresh_token)


def get_config() -> EnvConfig:
    """Get the configuration instance."""
    return EnvConfig()
