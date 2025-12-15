"""Tests for CLI config module."""

import os


class TestEnvTokenStore:
    """Tests for EnvTokenStore class."""

    def test_get_access_token_returns_none(self, tmp_path, monkeypatch):
        """Test get_access_token always returns None (not persisted)."""
        from club_calendar_cli.config import EnvTokenStore

        monkeypatch.chdir(tmp_path)
        store = EnvTokenStore()

        result = store.get_access_token()

        assert result is None

    def test_save_access_token_is_noop(self, tmp_path, monkeypatch):
        """Test save_access_token does nothing (not persisted)."""
        from club_calendar_cli.config import EnvTokenStore

        monkeypatch.chdir(tmp_path)
        store = EnvTokenStore()

        # Should not raise and do nothing
        store.save_access_token("token", 9999999999)

        # Should still return None
        assert store.get_access_token() is None

    def test_update_env_file_creates_new_file(self, tmp_path, monkeypatch):
        """Test _update_env_file creates .env if it doesn't exist."""
        from club_calendar_cli.config import EnvTokenStore

        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        store = EnvTokenStore(env_file=env_file)

        store._update_env_file("TEST_KEY", "test_value")

        assert env_file.exists()
        assert env_file.read_text() == "TEST_KEY=test_value\n"

    def test_update_env_file_updates_existing_key(self, tmp_path, monkeypatch):
        """Test _update_env_file updates existing key in .env file."""
        from club_calendar_cli.config import EnvTokenStore

        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=old_value\nOTHER_KEY=other\n")
        store = EnvTokenStore(env_file=env_file)

        store._update_env_file("EXISTING_KEY", "new_value")

        content = env_file.read_text()
        assert "EXISTING_KEY=new_value" in content
        assert "OTHER_KEY=other" in content
        assert "old_value" not in content

    def test_update_env_file_adds_new_key(self, tmp_path, monkeypatch):
        """Test _update_env_file adds new key to existing .env file."""
        from club_calendar_cli.config import EnvTokenStore

        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=value\n")
        store = EnvTokenStore(env_file=env_file)

        store._update_env_file("NEW_KEY", "new_value")

        content = env_file.read_text()
        assert "EXISTING_KEY=value" in content
        assert "NEW_KEY=new_value" in content


class TestEnvConfig:
    """Tests for EnvConfig class."""

    def test_refresh_token_setter_saves_to_store(self, tmp_path, monkeypatch):
        """Test refresh_token setter saves value to token store."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "")

        config = EnvConfig()
        config.refresh_token = "new_token"

        # Check it was saved to environment
        assert os.environ.get("STRAVA_REFRESH_TOKEN") == "new_token"
        # Check it's retrievable via property
        assert config.refresh_token == "new_token"

    def test_refresh_token_setter_with_none_does_not_save(self, tmp_path, monkeypatch):
        """Test refresh_token setter with None doesn't update store."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "existing")

        config = EnvConfig()
        config.refresh_token = None

        # Original value should remain (setter doesn't save None)
        assert os.environ.get("STRAVA_REFRESH_TOKEN") == "existing"

    def test_city_filter_empty(self, monkeypatch):
        """Test city_filter returns empty list when env var is empty."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.setenv("CLUB_CITY_FILTER", "")

        config = EnvConfig()

        assert config.city_filter == []

    def test_city_filter_single_city(self, monkeypatch):
        """Test city_filter parses single city."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.setenv("CLUB_CITY_FILTER", "Portland")

        config = EnvConfig()

        assert config.city_filter == ["Portland"]

    def test_city_filter_multiple_cities(self, monkeypatch):
        """Test city_filter parses comma-separated cities."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.setenv("CLUB_CITY_FILTER", "Portland, Seattle, San Francisco")

        config = EnvConfig()

        assert config.city_filter == ["Portland", "Seattle", "San Francisco"]

    def test_city_filter_strips_whitespace(self, monkeypatch):
        """Test city_filter strips whitespace from city names."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.setenv("CLUB_CITY_FILTER", "  Portland  ,  Seattle  ")

        config = EnvConfig()

        assert config.city_filter == ["Portland", "Seattle"]

    def test_city_filter_ignores_empty_entries(self, monkeypatch):
        """Test city_filter ignores empty entries from extra commas."""
        from club_calendar_cli.config import EnvConfig

        monkeypatch.setenv("CLUB_CITY_FILTER", "Portland,,Seattle,")

        config = EnvConfig()

        assert config.city_filter == ["Portland", "Seattle"]
