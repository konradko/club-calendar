"""Tests for macOS config module."""

from pathlib import Path
from unittest.mock import patch

import yaml
from club_calendar_macos.config import (
    ConfigTokenStore,
    Settings,
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

    def test_get_config_dir_uses_env_var(self, tmp_path, monkeypatch):
        """Test get_config_dir uses CLUB_CALENDAR_CONFIG_DIR env var."""
        custom_dir = tmp_path / "custom_config"
        monkeypatch.setenv("CLUB_CALENDAR_CONFIG_DIR", str(custom_dir))

        result = get_config_dir()

        assert result == custom_dir
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

    def test_get_config_file_returns_yaml_path(self, mock_config_file):
        """Test get_config_file returns a path ending with config.yaml."""
        result = get_config_file()
        assert result.name == "config.yaml"
        assert isinstance(result, Path)


class TestSettingsClass:
    """Tests for Settings class."""

    def test_settings_load_from_existing_config(self, mock_config_file):
        """Test loading settings when config file exists with data."""
        mock_config_file.write_text(
            yaml.dump(
                {
                    "strava_client_id": "from_config",
                    "strava_client_secret": "secret_from_config",
                    "cities": ["Portland", "Seattle"],
                    "clubs": {"123": {"name": "Test Club", "city": "Portland", "enabled": True}},
                    "sync_weeks": 4,
                    "max_events_per_club_per_week": 3,
                }
            )
        )

        settings = Settings.load()

        assert settings.strava_client_id == "from_config"
        assert settings.strava_client_secret == "secret_from_config"
        assert settings.cities == ["Portland", "Seattle"]
        assert "123" in settings.clubs
        assert settings.clubs["123"]["name"] == "Test Club"
        assert settings.sync_weeks == 4
        assert settings.max_events_per_club_per_week == 3

    def test_settings_load_env_overrides_config(self, mock_config_file, monkeypatch):
        """Test that environment variables override config file values."""
        mock_config_file.write_text(
            yaml.dump({"strava_client_id": "from_config", "cities": ["Portland"]})
        )

        monkeypatch.setenv("STRAVA_CLIENT_ID", "from_env")
        monkeypatch.setenv("CLUB_CITIES", "Seattle, Denver")

        settings = Settings.load()

        assert settings.strava_client_id == "from_env"
        assert settings.cities == ["Seattle", "Denver"]

    def test_settings_save_and_load(self, mock_config_file):
        """Test saving and loading settings preserves values."""
        settings = Settings(
            strava_client_id="test_id",
            strava_client_secret="test_secret",
            strava_refresh_token="test_token",
            cities=["Portland"],
            clubs={"123": {"name": "Test Club", "city": "Portland", "enabled": True}},
        )
        settings.save()

        loaded = Settings.load()

        assert loaded.strava_client_id == "test_id"
        assert loaded.strava_client_secret == "test_secret"
        assert loaded.strava_refresh_token == "test_token"
        assert loaded.cities == ["Portland"]
        assert loaded.get_club_ids() == [123]

    def test_settings_corrupt_config_file(self, mock_config_file):
        """Test loading handles corrupt config file gracefully."""
        mock_config_file.write_text("not valid yaml: {{{\n  - invalid")

        settings = Settings.load()
        assert settings.strava_client_id == ""
        assert settings.clubs == {}

    def test_settings_empty_config_file(self, mock_config_file):
        """Test loading handles empty config file gracefully."""
        mock_config_file.write_text("")

        settings = Settings.load()

        # Should create fresh defaults
        assert settings.strava_client_id == ""
        assert settings.clubs == {}
        assert settings.sync_interval_minutes == 60

    def test_settings_sync_interval_env_var(self, mock_config_file, monkeypatch):
        """Test SYNC_INTERVAL_MINUTES env var overrides config."""
        mock_config_file.write_text("sync_interval_minutes: 30")
        monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "120")

        settings = Settings.load()

        assert settings.sync_interval_minutes == 120

    def test_get_settings_function(self):
        """Test get_settings convenience function."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_settings_methods(self):
        """Test helper methods on Settings."""
        settings = Settings()

        assert not settings.has_strava_credentials()
        assert not settings.has_refresh_token()
        assert not settings.has_clubs()
        assert settings.get_club_ids() == []

        settings.strava_client_id = "id"
        settings.strava_client_secret = "secret"
        assert settings.has_strava_credentials()

        settings.strava_refresh_token = "token"
        assert settings.has_refresh_token()

        settings.clubs = {
            "1": {"name": "Club 1", "city": "Portland", "enabled": True},
            "2": {"name": "Club 2", "city": "Seattle", "enabled": True},
        }
        assert settings.get_club_ids() == [1, 2]
        assert settings.has_clubs()

    def test_settings_merge_clubs_new_clubs(self):
        """Test merge_clubs adds new clubs with auto-enable based on cities."""
        settings = Settings(cities=["Portland"])

        fetched = [
            {"id": 1, "name": "Portland Club", "city": "Portland"},
            {"id": 2, "name": "Seattle Club", "city": "Seattle"},
        ]

        new_count = settings.merge_clubs(fetched)

        assert new_count == 2
        assert settings.clubs["1"]["enabled"] is True  # Portland matches
        assert settings.clubs["2"]["enabled"] is False  # Seattle doesn't match

    def test_settings_merge_clubs_preserves_enabled(self):
        """Test merge_clubs preserves existing enabled state."""
        settings = Settings(
            cities=["Portland"],
            clubs={"1": {"name": "Old Name", "city": "Portland", "enabled": False}},
        )

        fetched = [{"id": 1, "name": "New Name", "city": "Portland"}]

        new_count = settings.merge_clubs(fetched)

        assert new_count == 0  # No new clubs
        assert settings.clubs["1"]["name"] == "New Name"  # Updated
        assert settings.clubs["1"]["enabled"] is False  # Preserved

    def test_settings_merge_clubs_no_cities_enables_all(self):
        """Test merge_clubs enables all clubs when no cities filter."""
        settings = Settings(cities=[])

        fetched = [
            {"id": 1, "name": "Club A", "city": "Portland"},
            {"id": 2, "name": "Club B", "city": "Seattle"},
        ]

        settings.merge_clubs(fetched)

        assert settings.clubs["1"]["enabled"] is True
        assert settings.clubs["2"]["enabled"] is True

    def test_settings_migrate_old_club_ids(self, mock_config_file):
        """Test migration from old club_ids format."""
        mock_config_file.write_text(yaml.dump({"strava_client_id": "id", "club_ids": [123, 456]}))

        settings = Settings.load()

        assert "123" in settings.clubs
        assert "456" in settings.clubs
        assert settings.clubs["123"]["enabled"] is True

    def test_settings_get_enabled_clubs(self):
        """Test get_enabled_clubs returns only enabled clubs."""
        settings = Settings(
            clubs={
                "1": {"name": "Enabled", "city": "Portland", "enabled": True},
                "2": {"name": "Disabled", "city": "Seattle", "enabled": False},
            }
        )

        enabled = settings.get_enabled_clubs()

        assert len(enabled) == 1
        assert 1 in enabled
        assert enabled[1]["name"] == "Enabled"

    def test_settings_save_format(self, mock_config_file):
        """Test save produces clean YAML format."""
        settings = Settings(
            strava_client_id="test",
            strava_client_secret="secret",
            clubs={
                "1": {"name": "Test Club", "city": "Portland", "enabled": True},
            },
        )
        settings.save()

        content = mock_config_file.read_text()
        assert "# Club Calendar" in content
        assert "strava_client_id: test" in content
        assert "strava_client_secret: secret" in content
        assert "clubs:" in content
        assert 'name: "Test Club"' in content
        assert "enabled: true" in content

    def test_settings_save_load_preserves_enabled_state(self, mock_config_file):
        """Test save/load roundtrip preserves club enabled state."""
        # Create settings with mix of enabled/disabled clubs
        settings = Settings(
            strava_client_id="test",
            clubs={
                "123": {"name": "Enabled Club", "city": "Portland", "enabled": True},
                "456": {"name": "Disabled Club", "city": "Seattle", "enabled": False},
            },
        )
        settings.save()

        # Load fresh and verify
        loaded = Settings.load()

        assert loaded.clubs["123"]["enabled"] is True
        assert loaded.clubs["456"]["enabled"] is False

    def test_settings_merge_then_save_preserves_user_choices(self, mock_config_file):
        """Test that merging new clubs then saving preserves existing enabled state."""
        # User has disabled club 123
        settings = Settings(
            strava_client_id="test",
            cities=["Portland"],
            clubs={"123": {"name": "My Club", "city": "Portland", "enabled": False}},
        )
        settings.save()

        # Simulate sync fetching clubs (including the one user disabled)
        fetched_clubs = [
            {"id": 123, "name": "My Club (Updated Name)", "city": "Portland"},
            {"id": 456, "name": "New Club", "city": "Portland"},
        ]
        settings.merge_clubs(fetched_clubs)
        settings.save()

        # Load fresh and verify user's choice was preserved
        loaded = Settings.load()

        # User's disabled choice should be preserved even after merge
        assert loaded.clubs["123"]["enabled"] is False
        assert loaded.clubs["123"]["name"] == "My Club (Updated Name)"  # Name updated
        # New club should be auto-enabled (matches city filter)
        assert loaded.clubs["456"]["enabled"] is True

    def test_settings_schema_version_upgrade(self, mock_config_file):
        """Test that old config without schema_version gets upgraded."""
        from club_calendar_macos.config import CURRENT_SCHEMA_VERSION

        # Write old-style config without schema_version
        old_config = {
            "strava_client_id": "my_id",
            "strava_client_secret": "my_secret",
            "cities": ["London"],
        }
        mock_config_file.write_text(yaml.dump(old_config))

        # Loading should trigger upgrade
        settings = Settings.load()

        # Values should be preserved
        assert settings.strava_client_id == "my_id"
        assert settings.strava_client_secret == "my_secret"
        assert settings.cities == ["London"]
        assert settings.schema_version == CURRENT_SCHEMA_VERSION

        # Config file should be updated with new format
        content = mock_config_file.read_text()
        assert f"schema_version: {CURRENT_SCHEMA_VERSION}" in content
        # Should have new comment format
        assert "# Club Calendar Configuration" in content

    def test_settings_schema_version_current_no_upgrade(self, mock_config_file):
        """Test that current schema version doesn't trigger upgrade."""
        from club_calendar_macos.config import CURRENT_SCHEMA_VERSION

        # Create settings with current version
        settings = Settings(
            strava_client_id="test_id",
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        settings.save()

        # Get file modification time
        import os

        mtime_before = os.path.getmtime(mock_config_file)

        # Load - should not trigger save
        import time

        time.sleep(0.01)  # Ensure different mtime if file is modified
        Settings.load()

        mtime_after = os.path.getmtime(mock_config_file)

        # File should not have been modified (no upgrade needed)
        assert mtime_before == mtime_after


class TestConfigTokenStore:
    """Tests for ConfigTokenStore class."""

    def test_get_refresh_token(self, mock_config_file):
        """Test get_refresh_token reads from config."""
        mock_config_file.write_text(yaml.dump({"strava_refresh_token": "my_token"}))

        store = ConfigTokenStore()
        result = store.get_refresh_token()

        assert result == "my_token"

    def test_get_refresh_token_returns_none_when_empty(self, mock_config_file):
        """Test get_refresh_token returns None when not set."""
        mock_config_file.write_text(yaml.dump({}))

        store = ConfigTokenStore()
        result = store.get_refresh_token()

        assert result is None

    def test_save_refresh_token(self, mock_config_file):
        """Test save_refresh_token writes to config."""
        mock_config_file.write_text(yaml.dump({"strava_client_id": "test"}))

        store = ConfigTokenStore()
        store.save_refresh_token("new_token")

        # Reload and verify
        settings = Settings.load()
        assert settings.strava_refresh_token == "new_token"

    def test_get_access_token_returns_none(self):
        """Test get_access_token always returns None (not persisted)."""
        store = ConfigTokenStore()
        result = store.get_access_token()
        assert result is None

    def test_save_access_token_is_noop(self):
        """Test save_access_token does nothing (not persisted)."""
        store = ConfigTokenStore()
        store.save_access_token("token", 9999999999)
        assert store.get_access_token() is None
