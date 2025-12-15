"""Tests for macOS config module."""

import json
from pathlib import Path
from unittest.mock import patch

from club_calendar_macos.config import (
    KeychainTokenStore,
    Settings,
    _get_secret,
    _set_secret,
    get_config_dir,
    get_config_file,
    get_logs_dir,
    get_settings,
)


class TestConfigFunctions:
    """Tests for config path functions."""

    def test_get_config_dir_creates_directory(self, tmp_path):
        """Test get_config_dir creates the directory."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch("club_calendar_macos.config.Path.home", return_value=fake_home):
            result = get_config_dir()

        expected = fake_home / "Library" / "Application Support" / "Club Calendar"
        assert result == expected
        assert result.exists()

    def test_get_logs_dir_creates_directory(self, tmp_path):
        """Test get_logs_dir creates the directory."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch("club_calendar_macos.config.Path.home", return_value=fake_home):
            result = get_logs_dir()

        expected = fake_home / "Library" / "Logs" / "Club Calendar"
        assert result == expected
        assert result.exists()

    def test_get_config_file_returns_json_path(self, mock_config_file):
        """Test get_config_file returns a path ending with config.json."""
        # The conftest mock returns a temp path, verify the interface
        result = get_config_file()
        assert result.name == "config.json"
        assert isinstance(result, Path)


class TestSecretFunctions:
    """Tests for keychain secret functions."""

    def test_get_secret_returns_value(self, mock_keychain):
        """Test _get_secret returns value from keychain."""
        mock_keychain["club-calendar:test_key"] = "test_value"
        result = _get_secret("test_key")
        assert result == "test_value"

    def test_get_secret_returns_empty_for_missing(self, mock_keychain):
        """Test _get_secret returns empty string for missing key."""
        result = _get_secret("nonexistent")
        assert result == ""

    def test_get_secret_handles_exception(self):
        """Test _get_secret handles keychain exceptions."""
        with patch("keyring.get_password", side_effect=Exception("Keychain error")):
            result = _get_secret("key")
            assert result == ""

    def test_set_secret_stores_value(self, mock_keychain):
        """Test _set_secret stores value in keychain."""
        _set_secret("my_key", "my_value")
        assert mock_keychain["club-calendar:my_key"] == "my_value"

    def test_set_secret_deletes_empty_value(self, mock_keychain):
        """Test _set_secret deletes key when value is empty."""
        mock_keychain["club-calendar:my_key"] = "existing"
        _set_secret("my_key", "")
        assert "club-calendar:my_key" not in mock_keychain

    def test_set_secret_handles_exception(self):
        """Test _set_secret handles keychain exceptions."""
        with patch("keyring.set_password", side_effect=Exception("Keychain error")):
            # Should not raise
            _set_secret("key", "value")

    def test_set_secret_delete_handles_password_not_found(self):
        """Test _set_secret handles PasswordDeleteError when key doesn't exist."""
        import keyring.errors

        with patch(
            "keyring.delete_password",
            side_effect=keyring.errors.PasswordDeleteError("No password found"),
        ):
            # Should not raise when trying to delete non-existent key
            _set_secret("nonexistent_key", "")


class TestSettingsClass:
    """Tests for Settings class."""

    def test_settings_load_from_existing_config(self, mock_config_file):
        """Test loading settings when config file exists with data."""
        mock_config_file.write_text(
            json.dumps(
                {
                    "strava_client_id": "from_config",
                    "club_ids": [111, 222],
                    "club_city_filter": "Portland",
                    "calendar_secret": "test_secret",
                }
            )
        )

        settings = Settings.load()

        assert settings.strava_client_id == "from_config"
        assert settings.club_ids == [111, 222]
        assert settings.club_city_filter == "Portland"
        assert settings.calendar_secret == "test_secret"

    def test_settings_load_env_overrides_config(self, mock_config_file, monkeypatch):
        """Test that environment variables override config file values."""
        mock_config_file.write_text(
            json.dumps({"strava_client_id": "from_config", "club_ids": [111]})
        )

        monkeypatch.setenv("STRAVA_CLIENT_ID", "from_env")
        monkeypatch.setenv("CLUB_IDS", "999,888")

        settings = Settings.load()

        assert settings.strava_client_id == "from_env"
        assert settings.club_ids == [999, 888]

    def test_settings_save_and_load(self, mock_config_file, mock_keychain):
        """Test saving and loading settings preserves values."""
        settings = Settings(
            strava_client_id="test_id",
            strava_client_secret="test_secret",
            strava_refresh_token="test_token",
            club_ids=[123, 456],
        )
        settings.save()

        loaded = Settings.load()

        assert loaded.strava_client_id == "test_id"
        assert loaded.strava_client_secret == "test_secret"
        assert loaded.strava_refresh_token == "test_token"
        assert loaded.club_ids == [123, 456]

    def test_settings_corrupt_config_file(self, mock_config_file):
        """Test loading handles corrupt config file gracefully."""
        mock_config_file.write_text("not valid json {{{")

        settings = Settings.load()
        assert settings.strava_client_id == ""
        assert settings.club_ids == []

    def test_get_settings_function(self):
        """Test get_settings convenience function."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_settings_generates_calendar_secret(self):
        """Test that calendar_secret is generated if not provided."""
        settings = Settings()
        assert settings.calendar_secret
        assert len(settings.calendar_secret) > 10

    def test_settings_methods(self, mock_keychain):
        """Test helper methods on Settings."""
        settings = Settings()

        assert not settings.has_strava_credentials()
        assert not settings.has_refresh_token()
        assert settings.get_club_ids() == []

        settings.strava_client_id = "id"
        settings.strava_client_secret = "secret"
        assert settings.has_strava_credentials()

        settings.strava_refresh_token = "token"
        assert settings.has_refresh_token()

        settings.club_ids = [1, 2]
        assert settings.get_club_ids() == [1, 2]

    def test_settings_ensure_output_dir(self, tmp_path):
        """Test ensure_output_dir creates directory with secret subdirectory."""
        settings = Settings(
            output_dir=tmp_path,
            calendar_secret="test_secret_123",
        )

        result = settings.ensure_output_dir()

        expected = tmp_path / "test_secret_123"
        assert result == expected
        assert result.exists()
        assert result.is_dir()


class TestKeychainTokenStore:
    """Tests for KeychainTokenStore class."""

    def test_get_access_token_returns_none(self, mock_keychain):
        """Test get_access_token always returns None (not persisted)."""
        store = KeychainTokenStore()

        result = store.get_access_token()

        assert result is None

    def test_save_access_token_is_noop(self, mock_keychain):
        """Test save_access_token does nothing (not persisted)."""
        store = KeychainTokenStore()

        # Should not raise and do nothing
        store.save_access_token("token", 9999999999)

        # Should still return None
        assert store.get_access_token() is None
