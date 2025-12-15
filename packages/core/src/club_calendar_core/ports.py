"""Protocol definitions for dependency injection.

These protocols define the interfaces that different deployments
(CLI, macOS, Docker) can implement for configuration and token storage.
"""

from pathlib import Path
from typing import Protocol


class TokenStore(Protocol):
    """Storage for OAuth tokens.

    Implementations:
    - EnvTokenStore: Read from environment variables (CLI, Docker)
    - KeychainTokenStore: macOS Keychain (macOS package)
    """

    def get_refresh_token(self) -> str | None:
        """Get the stored refresh token."""
        ...

    def save_refresh_token(self, token: str) -> None:
        """Save the refresh token."""
        ...

    def get_access_token(self) -> tuple[str, int] | None:
        """Get stored access token and expiry timestamp.

        Returns:
            Tuple of (token, expires_at) or None if not stored
        """
        ...

    def save_access_token(self, token: str, expires_at: int) -> None:
        """Save access token with expiry timestamp."""
        ...


class ConfigProvider(Protocol):
    """Configuration source.

    Implementations:
    - EnvConfig: Environment variables + .env file (CLI, Docker)
    - SettingsConfig: Pydantic settings + Keychain (macOS package)
    """

    def get_client_id(self) -> str:
        """Get Strava API client ID."""
        ...

    def get_client_secret(self) -> str:
        """Get Strava API client secret."""
        ...

    def get_club_ids(self) -> list[int]:
        """Get list of club IDs to sync."""
        ...

    def get_output_path(self) -> Path | None:
        """Get output directory for calendar files.

        Returns:
            Path to output directory, or None for stdout
        """
        ...
