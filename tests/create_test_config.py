#!/usr/bin/env python3
"""Generate test config for mock Strava server testing."""

import os

from club_calendar.menubar.config import Settings

# Set config dir from env or use default
config_dir = os.environ.get("CLUB_CALENDAR_CONFIG_DIR")
if not config_dir:
    config_dir = os.path.join(os.path.dirname(__file__), "test-config")
    os.environ["CLUB_CALENDAR_CONFIG_DIR"] = config_dir

os.makedirs(config_dir, exist_ok=True)

# Get mock server port from env or use default
mock_port = os.environ.get("MOCK_PORT", "51679")

settings = Settings(
    strava_client_id="mock_client_id",
    strava_client_secret="mock_client_secret",
    strava_refresh_token="mock_refresh_token",
    calendar_name="Test Club Calendar",
    sync_interval_minutes=0,
    debug=True,
    log_output="console",
    strava_api_url=f"http://localhost:{mock_port}/api/v3",
    strava_token_url=f"http://localhost:{mock_port}/oauth/token",
    strava_auth_url=f"http://localhost:{mock_port}/oauth/authorize",
)
settings.save()

print(f"Test config created at {config_dir}/config.yaml")
