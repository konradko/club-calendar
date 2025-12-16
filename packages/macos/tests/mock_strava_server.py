#!/usr/bin/env python3
"""Mock Strava API server for e2e testing.

Generates realistic club events dynamically for any requested club ID.
Events are generated for this week, next week, and week after.

Usage:
    python mock_strava_server.py
    python mock_strava_server.py --data scenarios/custom.json
"""

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Default athlete (returned for /athlete and /oauth/token)
DEFAULT_ATHLETE = {
    "id": 12345,
    "firstname": "Test",
    "lastname": "User",
}

# Default clubs (returned for /athlete/clubs)
# IDs are chosen so club_id % 4 matches activity type index in EVENT_TEMPLATES:
#   0 = Ride, 1 = Run, 2 = Swim, 3 = Hike
DEFAULT_CLUBS = [
    {"id": 1000, "name": "Cyclists", "city": "London", "member_count": 30},
    {"id": 1001, "name": "Runners", "city": "London", "member_count": 50},
    {"id": 1002, "name": "Swimmers", "city": "London", "member_count": 20},
    {"id": 1003, "name": "Hikers", "city": "London", "member_count": 25},
]

# Event title templates by activity type
EVENT_TEMPLATES = {
    "Ride": ["Group Ride", "Easy Spin", "Hill Climb", "Recovery Ride", "Coffee Ride"],
    "Run": ["Group Run", "Easy Jog", "Park Run", "Trail Run", "Interval Session"],
    "Swim": ["Open Water Swim", "Lake Swim", "Morning Swim", "Endurance Swim"],
    "Hike": ["Group Hike", "Nature Walk", "Hill Walk", "Countryside Walk"],
}


def _generate_events_for_club(club_id: int, clubs: list[dict] | None = None) -> list[dict]:
    """Generate dynamic events for a club.

    Uses club_id as seed for reproducible randomness.
    Generates: 1-2 events this week, 1 next week, 1 week after.

    Args:
        club_id: The club ID to generate events for
        clubs: Optional list of club dicts to look up name from
    """
    # Seed random with club_id for reproducibility
    rng = random.Random(club_id)

    # Determine activity type based on club_id
    activity_types = list(EVENT_TEMPLATES.keys())
    activity_type = activity_types[club_id % len(activity_types)]
    titles = EVENT_TEMPLATES[activity_type]

    # Get club name from provided clubs or defaults
    club_name = f"Club {club_id}"
    all_clubs = (clubs or []) + DEFAULT_CLUBS
    for club in all_clubs:
        if club["id"] == club_id:
            club_name = club["name"]
            break

    events = []
    event_id_base = club_id * 100
    now = datetime.now(UTC)

    # Generate specific events based on activity type for a cleaner test dataset:
    # - Today: 1 swim (7am), 1 ride (+3h) = 2 total
    # - Tomorrow: 1 run (7am), 1 hike (10am) = 2 total
    # - Next week: 1 of each type

    if activity_type == "Ride":
        # Ride: later today + next week
        event_dt = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )
        event_dt = (now + timedelta(days=8)).replace(hour=18, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base + 1,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )

    elif activity_type == "Run":
        # Run: tomorrow + next week
        event_dt = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )
        event_dt = (now + timedelta(days=9)).replace(hour=9, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base + 1,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )

    elif activity_type == "Swim":
        # Swim: earlier today + next week
        event_dt = now.replace(hour=7, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )
        event_dt = (now + timedelta(days=10)).replace(hour=19, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base + 1,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )

    elif activity_type == "Hike":
        # Hike: tomorrow + later this week + next week
        event_dt = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )
        # Later this week (3 days from now)
        event_dt = (now + timedelta(days=3)).replace(hour=14, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base + 1,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )
        event_dt = (now + timedelta(days=11)).replace(hour=9, minute=0, second=0, microsecond=0)
        events.append(
            _create_event(
                event_id=event_id_base + 2,
                title=rng.choice(titles),
                club_id=club_id,
                club_name=club_name,
                activity_type=activity_type,
                event_dt=event_dt,
            )
        )

    return events


def _create_event(
    event_id: int,
    title: str,
    club_id: int,
    club_name: str,
    activity_type: str,
    event_dt: datetime,
) -> dict:
    """Create a Strava-like event dict."""
    return {
        "id": event_id,
        "title": title,
        "description": f"Join us for {title.lower()}!",
        "activity_type": activity_type,
        "club_id": club_id,
        "club": {"id": club_id, "name": club_name},
        "organizing_athlete": {"firstname": "Organizer"},
        "upcoming_occurrences": [event_dt.strftime("%Y-%m-%dT%H:%M:%SZ")],
        "zone": "Europe/London",
        "address": "Meeting Point",
        "route_id": None,
        "women_only": False,
        "private": False,
    }


class MockStravaServer(ThreadingHTTPServer):
    """Mock Strava server with address reuse enabled."""

    allow_reuse_address = True


class MockStravaHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock Strava API.

    Supports two modes:
    1. Dynamic mode (default): Generates events for any requested club ID
    2. Scenario mode: Uses static data from JSON file (for specific test scenarios)
    """

    # Use HTTP/1.1 to support keep-alive connections
    protocol_version = "HTTP/1.1"

    # Scenario data (None = dynamic mode)
    scenario_data: dict | None = None
    # Clubs list (used for dynamic event generation)
    clubs: list[dict] = DEFAULT_CLUBS

    def log_message(self, format, *args):
        print(f"[Mock Strava] {format % args}")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/api/v3/athlete":
            if self.scenario_data:
                self._send_json(self.scenario_data.get("athlete", DEFAULT_ATHLETE))
            else:
                self._send_json(DEFAULT_ATHLETE)

        elif self.path == "/api/v3/athlete/clubs":
            if self.scenario_data:
                self._send_json(self.scenario_data.get("clubs", []))
            else:
                self._send_json(self.clubs)

        elif self.path.startswith("/api/v3/clubs/") and "/group_events" in self.path:
            club_id_str = self.path.split("/clubs/")[1].split("/")[0]
            try:
                club_id = int(club_id_str)
            except ValueError:
                self._send_json({"error": "Invalid club ID"}, 400)
                return

            if self.scenario_data:
                # Scenario mode: use static events, "dynamic", or empty
                events_data = self.scenario_data.get("events", {}).get(club_id_str, [])
                if events_data == "dynamic":
                    # Generate dynamic events even in scenario mode
                    clubs = self.scenario_data.get("clubs", [])
                    events = _generate_events_for_club(club_id, clubs)
                else:
                    events = events_data
            else:
                # Dynamic mode: generate events for any club
                events = _generate_events_for_club(club_id, self.clubs)

            self._send_json(events)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):  # noqa: N802
        # Read and discard request body to prevent it bleeding into next request
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            self.rfile.read(content_length)

        if self.path == "/oauth/token":
            athlete = DEFAULT_ATHLETE
            if self.scenario_data:
                athlete = self.scenario_data.get("athlete", DEFAULT_ATHLETE)
            self._send_json(
                {
                    "access_token": "mock_access_token",
                    "refresh_token": "mock_refresh_token",
                    "expires_at": 9999999999,
                    "athlete": athlete,
                }
            )
        else:
            self._send_json({"error": "Not found"}, 404)


def _load_clubs_from_config() -> list[dict]:
    """Try to load clubs from app config file."""
    try:
        from pathlib import Path

        config_file = (
            Path.home() / "Library" / "Application Support" / "Club Calendar" / "config.yaml"
        )
        if config_file.exists():
            import yaml

            config = yaml.safe_load(config_file.read_text()) or {}
            clubs_dict = config.get("clubs", {})
            clubs = []
            for club_id, info in clubs_dict.items():
                name = info.get("name", f"Club {club_id}")
                clubs.append(
                    {
                        "id": int(club_id),
                        "name": name,
                        "city": info.get("city", ""),
                        "member_count": 10,
                    }
                )
            if clubs:
                return clubs
    except Exception as e:
        print(f"[Mock Strava] Could not load clubs from config: {e}")
    return DEFAULT_CLUBS


def main():
    parser = argparse.ArgumentParser(description="Mock Strava API server")
    parser.add_argument("--port", type=int, default=51679, help="Port to listen on")
    parser.add_argument("--data", type=str, help="JSON file with scenario data")
    args = parser.parse_args()

    # Load scenario data or use dynamic mode
    if args.data:
        with open(args.data) as f:
            MockStravaHandler.scenario_data = json.load(f)
        print(f"[Mock Strava] Loaded scenario from {args.data}")
    else:
        # Dynamic mode: try to load clubs from app config
        MockStravaHandler.clubs = _load_clubs_from_config()
        club_names = [c["name"] for c in MockStravaHandler.clubs]
        print(f"[Mock Strava] Dynamic mode with clubs: {', '.join(club_names)}")

    mode = "scenario" if args.data else "dynamic"
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                    Mock Strava API Server                      ║
╠═══════════════════════════════════════════════════════════════╣
║  Port: {args.port:<56}║
║  Mode: {mode:<56}║
╠═══════════════════════════════════════════════════════════════╣
║  Endpoints:                                                    ║
║    GET  /api/v3/athlete              - Get athlete             ║
║    GET  /api/v3/athlete/clubs        - Get clubs               ║
║    GET  /api/v3/clubs/ID/group_events - Get club events        ║
║    POST /oauth/token                 - Token exchange          ║
╚═══════════════════════════════════════════════════════════════╝
""")

    server = MockStravaServer(("localhost", args.port), MockStravaHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Mock Strava] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
