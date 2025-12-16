#!/usr/bin/env python3
"""Mock Strava API server for e2e testing.

A clean mock of Strava API endpoints. Scenario data is loaded from a JSON file.

Date placeholders in upcoming_occurrences:
  "+1d"  -> 1 day from now
  "+3d"  -> 3 days from now
  "+1w"  -> 1 week from now
  "+2w"  -> 2 weeks from now

Usage:
    python mock_strava_server.py --data scenarios/happy.json
"""

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Default mock data (used if no file provided)
DEFAULT_DATA = {
    "athlete": {"id": 12345, "firstname": "Test", "lastname": "User"},
    "clubs": [],
    "events": {},
}


def _expand_date_placeholder(placeholder: str) -> str:
    """Expand a date placeholder like '+3d' or '+1w' to ISO datetime."""
    match = re.match(r"\+(\d+)([dw])", placeholder)
    if not match:
        return placeholder  # Return as-is if not a placeholder

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        dt = datetime.now(UTC) + timedelta(days=amount)
    else:  # 'w'
        dt = datetime.now(UTC) + timedelta(weeks=amount)

    # Round to nearest hour for cleaner times
    dt = dt.replace(minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _process_events(data: dict) -> dict:
    """Process events to expand date placeholders."""
    if "events" not in data:
        return data

    for _club_id, events in data["events"].items():
        for event in events:
            if "upcoming_occurrences" in event:
                event["upcoming_occurrences"] = [
                    _expand_date_placeholder(d) for d in event["upcoming_occurrences"]
                ]
    return data


class MockStravaServer(ThreadingHTTPServer):
    """Mock Strava server with address reuse enabled."""

    allow_reuse_address = True


class MockStravaHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock Strava API."""

    data = DEFAULT_DATA

    def log_message(self, format, *args):
        print(f"[Mock Strava] {format % args}")

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Connection", "close")  # Prevent keep-alive issues
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):  # noqa: N802
        if self.path == "/api/v3/athlete":
            self._send_json(self.data.get("athlete", DEFAULT_DATA["athlete"]))

        elif self.path == "/api/v3/athlete/clubs":
            self._send_json(self.data.get("clubs", []))

        elif self.path.startswith("/api/v3/clubs/") and "/group_events" in self.path:
            club_id = self.path.split("/clubs/")[1].split("/")[0]
            events = self.data.get("events", {}).get(club_id, [])
            self._send_json(events)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):  # noqa: N802
        if self.path == "/oauth/token":
            self._send_json(
                {
                    "access_token": "mock_access_token",
                    "refresh_token": "mock_refresh_token",
                    "expires_at": 9999999999,
                    "athlete": self.data.get("athlete", DEFAULT_DATA["athlete"]),
                }
            )
        else:
            self._send_json({"error": "Not found"}, 404)


def main():
    parser = argparse.ArgumentParser(description="Mock Strava API server")
    parser.add_argument("--port", type=int, default=51679, help="Port to listen on")
    parser.add_argument("--data", type=str, help="JSON file with scenario data")
    args = parser.parse_args()

    # Load scenario data
    if args.data:
        with open(args.data) as f:
            data = json.load(f)
        MockStravaHandler.data = _process_events(data)
        print(f"[Mock Strava] Loaded data from {args.data}")
    else:
        print("[Mock Strava] Using default empty data")

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                    Mock Strava API Server                      ║
╠═══════════════════════════════════════════════════════════════╣
║  Port: {args.port:<56}║
║  Data: {(args.data or 'default'):<56}║
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
