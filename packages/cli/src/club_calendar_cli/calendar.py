"""ICS calendar generation from club events."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from club_calendar_core.strava import ClubEvent
from icalendar import Calendar, Event


def create_calendar(name: str, events: list[ClubEvent]) -> Calendar:
    """Create an iCalendar from a list of club events."""
    cal = Calendar()
    cal.add("prodid", "-//Club Calendar//club-calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", name)

    for club_event in events:
        event = Event()
        event.add("uid", f"club-event-{club_event.id}@club-calendar")
        event.add("summary", club_event.title)
        event.add("dtstart", club_event.start_datetime)
        # Default duration of 2 hours if not specified
        event.add("dtend", club_event.start_datetime + timedelta(hours=2))
        event.add("dtstamp", datetime.now(UTC))

        # Description with details
        description_parts = []
        if club_event.description:
            description_parts.append(club_event.description)
        description_parts.append(f"Club: {club_event.club_name}")
        if club_event.organizer_name:
            description_parts.append(f"Organizer: {club_event.organizer_name}")
        if club_event.route_id:
            description_parts.append(f"Route: https://www.strava.com/routes/{club_event.route_id}")
        event.add("description", "\n\n".join(description_parts))

        # Location
        if club_event.address:
            event.add("location", club_event.address)

        # URL to event on Strava (if available)
        event.add(
            "url", f"https://www.strava.com/clubs/{club_event.club_id}/group_events/{club_event.id}"
        )

        cal.add_component(event)

    return cal


def calendar_to_ics(cal: Calendar) -> bytes:
    """Convert calendar to ICS bytes."""
    return cal.to_ical()


def generate_combined_calendar(events: list[ClubEvent], name: str = "Club Events") -> bytes:
    """Generate a combined calendar with all events."""
    cal = create_calendar(name, events)
    return calendar_to_ics(cal)


def generate_per_club_calendars(events: list[ClubEvent]) -> dict[int, bytes]:
    """Generate separate calendars for each club."""
    # Group events by club
    by_club: dict[int, list[ClubEvent]] = {}
    club_names: dict[int, str] = {}
    for event in events:
        if event.club_id not in by_club:
            by_club[event.club_id] = []
            club_names[event.club_id] = event.club_name
        by_club[event.club_id].append(event)

    # Generate calendar for each club
    calendars = {}
    for club_id, club_events in by_club.items():
        name = club_names[club_id]
        cal = create_calendar(f"{name} Events", club_events)
        calendars[club_id] = calendar_to_ics(cal)

    return calendars


def write_calendars(
    events: list[ClubEvent],
    output_dir: Path,
    combined_name: str = "club-calendar",
) -> dict[str, Path]:
    """Write all calendars to output directory.

    Returns dict mapping calendar name to file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written = {}

    # Combined calendar
    combined_path = output_dir / f"{combined_name}.ics"
    combined_ics = generate_combined_calendar(events)
    combined_path.write_bytes(combined_ics)
    written["combined"] = combined_path

    # Per-club calendars
    per_club = generate_per_club_calendars(events)
    for club_id, ics_data in per_club.items():
        club_path = output_dir / f"club-calendar-{club_id}.ics"
        club_path.write_bytes(ics_data)
        written[f"club-{club_id}"] = club_path

    return written
