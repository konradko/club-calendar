"""Tests for calendar generation."""

from datetime import datetime

from club_calendar_core.calendar import (
    calendar_to_ics,
    create_calendar,
    generate_combined_calendar,
    generate_per_club_calendars,
    write_calendars,
)
from club_calendar_core.strava import ClubEvent
from icalendar import Calendar


def make_event(
    id: int = 1,
    title: str = "Test Event",
    club_id: int = 100,
    club_name: str = "Test Club",
    description: str | None = None,
    organizer_name: str | None = None,
    route_id: int | None = None,
    address: str | None = None,
) -> ClubEvent:
    """Create a test event with optional fields."""
    return ClubEvent(
        id=id,
        title=title,
        club_id=club_id,
        club_name=club_name,
        start_datetime=datetime(2024, 6, 15, 9, 0),
        description=description,
        organizer_name=organizer_name,
        route_id=route_id,
        address=address,
    )


def test_create_calendar_basic():
    """Test basic calendar creation."""
    events = [make_event()]
    cal = create_calendar("Test", events)

    assert cal["prodid"] == "-//Club Calendar//club-calendar//EN"
    assert cal["version"] == "2.0"
    assert cal["x-wr-calname"] == "Test"


def test_create_calendar_with_description():
    """Test event with description is included."""
    events = [make_event(description="Join us for a morning ride!")]
    cal = create_calendar("Test", events)

    event = list(cal.walk("VEVENT"))[0]
    assert "Join us for a morning ride!" in str(event["description"])


def test_create_calendar_with_organizer():
    """Test event with organizer name is included."""
    events = [make_event(organizer_name="John Doe")]
    cal = create_calendar("Test", events)

    event = list(cal.walk("VEVENT"))[0]
    assert "Organizer: John Doe" in str(event["description"])


def test_create_calendar_with_route():
    """Test event with route ID includes link."""
    events = [make_event(route_id=12345)]
    cal = create_calendar("Test", events)

    event = list(cal.walk("VEVENT"))[0]
    assert "https://www.strava.com/routes/12345" in str(event["description"])


def test_create_calendar_with_address():
    """Test event with address sets location."""
    events = [make_event(address="123 Main St, City")]
    cal = create_calendar("Test", events)

    event = list(cal.walk("VEVENT"))[0]
    assert event["location"] == "123 Main St, City"


def test_create_calendar_full_event():
    """Test event with all optional fields."""
    events = [
        make_event(
            description="Morning ride",
            organizer_name="Jane",
            route_id=999,
            address="Park Entrance",
        )
    ]
    cal = create_calendar("Test", events)

    event = list(cal.walk("VEVENT"))[0]
    desc = str(event["description"])
    assert "Morning ride" in desc
    assert "Organizer: Jane" in desc
    assert "Route: https://www.strava.com/routes/999" in desc
    assert event["location"] == "Park Entrance"


def test_generate_per_club_calendars_multiple_events_same_club():
    """Test multiple events from same club are grouped."""
    events = [
        make_event(id=1, club_id=100, club_name="Club A"),
        make_event(id=2, club_id=100, club_name="Club A"),
        make_event(id=3, club_id=200, club_name="Club B"),
    ]
    calendars = generate_per_club_calendars(events)

    assert len(calendars) == 2
    assert 100 in calendars
    assert 200 in calendars

    # Parse and check event count
    cal_a = Calendar.from_ical(calendars[100])
    events_a = list(cal_a.walk("VEVENT"))
    assert len(events_a) == 2

    cal_b = Calendar.from_ical(calendars[200])
    events_b = list(cal_b.walk("VEVENT"))
    assert len(events_b) == 1


def test_calendar_to_ics():
    """Test ICS byte conversion."""
    events = [make_event()]
    cal = create_calendar("Test", events)
    ics_bytes = calendar_to_ics(cal)

    assert isinstance(ics_bytes, bytes)
    assert b"BEGIN:VCALENDAR" in ics_bytes
    assert b"BEGIN:VEVENT" in ics_bytes


def test_generate_combined_calendar():
    """Test combined calendar generation."""
    events = [make_event(id=1), make_event(id=2)]
    ics_bytes = generate_combined_calendar(events, "All Events")

    cal = Calendar.from_ical(ics_bytes)
    assert cal["x-wr-calname"] == "All Events"
    assert len(list(cal.walk("VEVENT"))) == 2


def test_write_calendars(tmp_path):
    """Test write_calendars writes combined and per-club files."""
    events = [
        make_event(id=1, club_id=100, club_name="Club A"),
        make_event(id=2, club_id=100, club_name="Club A"),
        make_event(id=3, club_id=200, club_name="Club B"),
    ]

    written = write_calendars(events, tmp_path)

    # Should return 3 paths: combined + 2 per-club
    assert len(written) == 3
    assert "combined" in written
    assert "club-100" in written
    assert "club-200" in written

    # Verify combined file exists and has all events
    combined_path = written["combined"]
    assert combined_path.exists()
    combined_cal = Calendar.from_ical(combined_path.read_bytes())
    assert len(list(combined_cal.walk("VEVENT"))) == 3

    # Verify per-club files exist and have correct events
    club_a_path = written["club-100"]
    assert club_a_path.exists()
    club_a_cal = Calendar.from_ical(club_a_path.read_bytes())
    assert len(list(club_a_cal.walk("VEVENT"))) == 2

    club_b_path = written["club-200"]
    assert club_b_path.exists()
    club_b_cal = Calendar.from_ical(club_b_path.read_bytes())
    assert len(list(club_b_cal.walk("VEVENT"))) == 1


def test_write_calendars_creates_directory(tmp_path):
    """Test write_calendars creates output directory if needed."""
    events = [make_event()]
    nested_dir = tmp_path / "nested" / "output"

    written = write_calendars(events, nested_dir)

    assert nested_dir.exists()
    assert written["combined"].exists()
